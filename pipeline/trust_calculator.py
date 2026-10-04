"""
SANGYAN — Trust Calculator (Step 8)
Aggregates all evidence into a single trust score and verdict.

Score 70-100: TRUST ESTABLISHED  🟢
Score 40-69:  PAUSE              🟡
Score 0-39:   STOP               🔴
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ScoreDeduction:
    reason: str
    points: int


@dataclass
class TrustResult:
    score: int
    verdict: str            # STOP | PAUSE | TRUST
    verdict_label: str
    color: str
    emoji: str
    deductions: List[ScoreDeduction] = field(default_factory=list)
    caveat: str = (
        "This analysis is based on available evidence. "
        "Always verify independently before transferring money."
    )


VERDICT_STOP = "STOP"
VERDICT_PAUSE = "PAUSE"
VERDICT_TRUST = "TRUST"


def calculate_trust(
    sebi_result=None,
    payment_results=None,
    phishtank_results=None,
    i4c_results=None,
    red_flag_report=None,
    ml_result=None,
    social_results=None,
    extracted_entities=None,
) -> TrustResult:
    """
    Compute trust score from all evidence signals.
    Returns TrustResult with score, verdict, and deduction breakdown.
    """
    score = 100
    deductions: List[ScoreDeduction] = []

    def deduct(reason: str, points: int):
        nonlocal score
        score = max(0, score - points)
        deductions.append(ScoreDeduction(reason=reason, points=points))

    # --- SEBI registration signals ---
    if sebi_result:
        if sebi_result.status == "NOT_FOUND":
            deduct("SEBI registration NOT FOUND in registry", 50)
        elif sebi_result.status == "EXPIRED":
            deduct("SEBI registration is EXPIRED", 40)
        elif sebi_result.status == "MISMATCH":
            deduct("Name MISMATCH in SEBI registry", 35)
        elif sebi_result.status == "UNAVAILABLE":
            deduct("SEBI registry unavailable — could not verify", 15)
        # VERIFIED = no deduction

    elif extracted_entities and extracted_entities.sebi_registrations:
        # Reg number present but not checked (shouldn't happen, but be safe)
        deduct("SEBI registration present but not verifiable", 20)

    # --- Payment signals ---
    if payment_results:
        personal_or_unverifiable = [
            r for r in payment_results
            if r.status in ("PERSONAL_UPI", "NOT_VERIFIABLE")
        ]
        if personal_or_unverifiable:
            deduct("Payment destination not linked to any registered entity", 30)

    # --- Guaranteed returns ---
    if extracted_entities and extracted_entities.has_guaranteed_returns:
        deduct("Guaranteed returns claimed (regulatory violation)", 25)

    # --- PhishTank ---
    if phishtank_results:
        phishing = [r for r in phishtank_results if r.status == "KNOWN_PHISHING"]
        if phishing:
            deduct(f"Known phishing URL found (PhishTank verified)", 45)

    # --- I4C suspect repository ---
    if i4c_results:
        in_repo = [r for r in i4c_results if r.status == "IN_REPOSITORY"]
        if in_repo:
            deduct("Identifier appears in I4C suspect complaints repository", 30)

    # --- Remote access ---
    if extracted_entities and extracted_entities.has_remote_access:
        deduct("Remote access tool requested (CRITICAL red flag)", 50)

    # --- Urgency signals ---
    if extracted_entities and extracted_entities.urgency_phrases:
        count = min(len(extracted_entities.urgency_phrases), 3)
        for i in range(count):
            deduct(f"Urgency/pressure tactic detected ({extracted_entities.urgency_phrases[i]})", 15)

    # --- ML score ---
    if ml_result and ml_result.combined_score > 0.8:
        deduct(f"AI models flag as high-probability scam (score: {ml_result.combined_score:.0%})", 20)

    # --- Unverified social handle ---
    if social_results:
        bad_social = [
            r for r in social_results
            if r.status in ("DOES_NOT_MATCH", "UNKNOWN_ENTITY", "FAKE_PATTERN")
        ]
        if bad_social:
            deduct("Social handle does not match any official verified account", 20)

    # --- Suspicious URL patterns ---
    if red_flag_report and red_flag_report.url_anomalies:
        deduct(f"Suspicious URL patterns detected ({len(red_flag_report.url_anomalies)} anomalies)", 20)

    # --- Impersonation signals ---
    if extracted_entities and extracted_entities.has_impersonation:
        deduct("Impersonation of regulator/government body detected", 20)

    # --- Determine verdict ---
    score = max(0, score)
    if score >= 70:
        verdict = VERDICT_TRUST
        verdict_label = "TRUST ESTABLISHED"
        color = "#16A34A"
        emoji = "🟢"
    elif score >= 40:
        verdict = VERDICT_PAUSE
        verdict_label = "PAUSE — MORE VERIFICATION REQUIRED"
        color = "#D97706"
        emoji = "🟡"
    else:
        verdict = VERDICT_STOP
        verdict_label = "STOP — CRITICAL CONTRADICTION FOUND"
        color = "#DC2626"
        emoji = "🔴"

    return TrustResult(
        score=score,
        verdict=verdict,
        verdict_label=verdict_label,
        color=color,
        emoji=emoji,
        deductions=deductions,
    )
