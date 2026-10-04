"""
SANGYAN — Main FastAPI Application
Pre-payment fraud interception system for Indian retail investors.

GUARDRAILS:
- Never stores user input after analysis
- Never gives stock tips or price predictions
- Never certifies anything 100% safe
- Never labels identifiers as "criminals" — only risk signals
- Never says PhishTank "not found" means safe
- Rate limited: 10 requests per IP per minute
"""

import logging
import os
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Pipeline imports
from pipeline.input_handler import SangyanInput, InputType, process_input
from pipeline.ocr_engine import extract_text_from_image
from pipeline.entity_extractor import extract_entities
from pipeline.red_flag_engine import run_red_flag_engine
from pipeline.ml_engine import run_ml_analysis
from pipeline.proof_chain import build_proof_chain
from pipeline.trust_calculator import calculate_trust
from pipeline.next_best_proof import generate_next_steps, get_official_links
from pipeline.verification.sebi_checker import check_sebi_registration
from pipeline.verification.phishtank_checker import check_urls
from pipeline.verification.i4c_checker import check_phone, check_upi, check_handle
from pipeline.verification.payment_checker import check_upi_id
from pipeline.verification.social_checker import check_social_handle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="SANGYAN",
    description="Pre-payment fraud interception system for Indian retail investors.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Guardrail patterns
# ---------------------------------------------------------------------------

STOCK_TIP_PATTERN = re.compile(
    r'\b(buy|sell|target price|stop loss|entry|exit|call|put|option tip|stock tip)\b',
    re.IGNORECASE,
)

STOCK_TIP_RESPONSE = {
    "message": (
        "SANGYAN only checks for fraud risk. "
        "For investment decisions, consult a SEBI-registered advisor at sebi.gov.in."
    )
}

TRUST_CAVEAT = (
    "This analysis is based on available evidence. "
    "Always verify independently before transferring money."
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    input_type: InputType
    content: str


class AnalyzeResponse(BaseModel):
    verdict: str
    trust_score: int
    proof_chain: list
    evidence: list
    red_flags: list
    contradictions: list
    ml_signal: dict
    next_steps: list
    official_links: list
    caveat: str = TRUST_CAVEAT


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    from pipeline.ml_engine import _load_lr, _load_muril
    lr, vec = _load_lr()
    tok, muril = _load_muril()
    return {
        "status": "ok",
        "models_loaded": {
            "tfidf_lr": bool(lr and lr is not False),
            "muril": bool(tok and tok is not False),
        },
    }


# ---------------------------------------------------------------------------
# Main analysis endpoint
# ---------------------------------------------------------------------------

@app.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("10/minute")
async def analyze(request: Request, body: AnalyzeRequest):
    """
    Core analysis endpoint.
    Accepts screenshot/text/url/handle, runs full 10-step pipeline,
    returns structured proof chain and verdict.
    All user content is processed in memory and not persisted.
    """

    # --- GUARDRAIL: Stock tip detection ---
    if body.input_type == InputType.TEXT and STOCK_TIP_PATTERN.search(body.content):
        # Only block if it looks like a request FOR tips, not detection of scam tips
        # We detect scam "tip" promises — so we only block explicit user queries
        pass  # Allow — the user might be pasting a scam message that contains these words

    # ======================================================
    # STEP 1: Process input
    # ======================================================
    processed = process_input(SangyanInput(
        input_type=body.input_type,
        content=body.content,
    ))

    # ======================================================
    # STEP 2: OCR (if screenshot)
    # ======================================================
    ocr_detail = None
    raw_text = processed.raw_text

    if body.input_type == InputType.SCREENSHOT and processed.image_bytes:
        ocr_result = extract_text_from_image(processed.image_bytes)
        raw_text = ocr_result["text"]
        ocr_detail = {
            "engine": ocr_result["engine_used"],
            "confidence": ocr_result["confidence"],
        }
        if not raw_text:
            raise HTTPException(
                status_code=422,
                detail="OCR could not extract any text from the image. Please try a clearer screenshot.",
            )

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="No content to analyze.")

    # ======================================================
    # STEP 3: Entity extraction
    # ======================================================
    entities = extract_entities(raw_text)

    # ======================================================
    # STEP 4 + 5: Verification
    # ======================================================
    sebi_result = None
    if entities.sebi_registrations:
        claimed_name = entities.org_names[0] if entities.org_names else None
        sebi_result = check_sebi_registration(
            entities.sebi_registrations[0],
            claimed_name=claimed_name,
        )

    payment_results = [check_upi_id(uid) for uid in entities.upi_ids] if entities.upi_ids else []

    phishtank_results = check_urls(entities.urls) if entities.urls else []

    i4c_results = []
    for phone in entities.phone_numbers[:2]:   # limit to 2
        i4c_results.append(check_phone(phone))
    for upi in entities.upi_ids[:2]:
        i4c_results.append(check_upi(upi))

    social_results = []
    for handle in entities.telegram_handles[:3]:
        social_results.append(check_social_handle(handle))

    # ======================================================
    # STEP 3 (Tier 3): Red flag engine
    # ======================================================
    red_flag_report = run_red_flag_engine(raw_text, urls=entities.urls)

    # ======================================================
    # STEP 4 (Tier 4): ML analysis
    # ======================================================
    ml_result = run_ml_analysis(raw_text)

    # ======================================================
    # STEP 6: Build proof chain
    # ======================================================
    proof_chain = build_proof_chain(
        extracted_entities=entities,
        sebi_result=sebi_result,
        payment_results=payment_results,
        social_results=social_results,
        phishtank_results=phishtank_results,
        red_flag_report=red_flag_report,
    )

    # ======================================================
    # STEP 8: Trust calculation
    # ======================================================
    trust = calculate_trust(
        sebi_result=sebi_result,
        payment_results=payment_results,
        phishtank_results=phishtank_results,
        i4c_results=i4c_results,
        red_flag_report=red_flag_report,
        ml_result=ml_result,
        social_results=social_results,
        extracted_entities=entities,
    )

    # ======================================================
    # STEP 9: Next best proof
    # ======================================================
    next_steps = generate_next_steps(
        verdict=trust.verdict,
        sebi_result=sebi_result,
        payment_results=payment_results,
        social_results=social_results,
        phishtank_results=phishtank_results,
        extracted_entities=entities,
    )
    official_links = get_official_links(sebi_result=sebi_result, verdict=trust.verdict)

    # ======================================================
    # STEP 10: Build response
    # ======================================================

    # Evidence table
    evidence = []

    if sebi_result:
        evidence.append({
            "check": "SEBI Intermediary Registry",
            "result": sebi_result.status,
            "detail": sebi_result.raw_detail,
            "source": "sebi.gov.in",
            "confidence": "HIGH" if sebi_result.status != "UNAVAILABLE" else "LOW",
        })

    for pt in phishtank_results:
        evidence.append({
            "check": "PhishTank URL Check",
            "result": pt.status,
            "detail": pt.detail,
            "source": "phishtank.org",
            "confidence": "HIGH" if pt.status == "KNOWN_PHISHING" else "MEDIUM",
            "caveat": pt.caveat,
        })

    for i4c in i4c_results:
        evidence.append({
            "check": f"I4C Suspect Repository ({i4c.identifier_type})",
            "result": i4c.status,
            "detail": i4c.detail,
            "source": "cybercrime.gov.in",
            "confidence": "MEDIUM",
            "caveat": i4c.caveat,
        })

    for pay in payment_results:
        evidence.append({
            "check": f"Payment Verification ({pay.identifier})",
            "result": pay.status,
            "detail": pay.detail,
            "source": "SANGYAN broker registry",
            "confidence": "MEDIUM",
        })

    for soc in social_results:
        evidence.append({
            "check": f"Social Handle Verification ({soc.handle})",
            "result": soc.status,
            "detail": soc.detail,
            "source": "SANGYAN official handle registry",
            "confidence": "MEDIUM",
        })

    if ocr_detail:
        evidence.append({
            "check": "OCR Text Extraction",
            "result": "COMPLETED",
            "detail": f"Text extracted using {ocr_detail['engine']} (confidence: {ocr_detail['confidence']})",
            "source": "Tesseract / Google Vision",
            "confidence": ocr_detail["confidence"].upper(),
        })

    # Red flags serialised
    red_flags_out = [
        {
            "category": f.category,
            "category_label": f.category_label,
            "trigger": f.trigger,
            "points": f.points,
            "severity": f.severity,
            "regulatory_note": f.regulatory_note,
        }
        for f in red_flag_report.flags
    ]

    # ML signal
    ml_out = {
        "lr_score": ml_result.lr_score,
        "muril_score": ml_result.muril_score,
        "combined": ml_result.combined_score,
        "top_words": ml_result.top_words,
        "note": ml_result.note,
        "lr_available": ml_result.lr_available,
        "muril_available": ml_result.muril_available,
    }

    # Anonymised logging — no content stored
    logger.info(
        "Analysis complete | input_type=%s | verdict=%s | score=%d | flags=%d",
        body.input_type,
        trust.verdict,
        trust.score,
        len(red_flag_report.flags),
    )

    # GUARDRAIL: TRUST caveat always added
    caveat = TRUST_CAVEAT
    if trust.verdict == "TRUST":
        caveat += (
            " SANGYAN cannot guarantee legitimacy. "
            "Verify the entity's official contact on sebi.gov.in."
        )

    return AnalyzeResponse(
        verdict=trust.verdict,
        trust_score=trust.score,
        proof_chain=proof_chain.to_list(),
        evidence=evidence,
        red_flags=red_flags_out,
        contradictions=proof_chain.contradictions,
        ml_signal=ml_out,
        next_steps=next_steps,
        official_links=official_links,
        caveat=caveat,
    )


# ---------------------------------------------------------------------------
# 404 / generic error handlers
# ---------------------------------------------------------------------------

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse({"error": "Endpoint not found"}, status_code=404)


@app.exception_handler(500)
async def server_error(request: Request, exc):
    logger.exception("Internal server error")
    return JSONResponse(
        {"error": "Internal server error. Please try again."},
        status_code=500,
    )
