"""
SANGYAN — Entity & Claim Extractor (Step 3)
Extracts: SEBI reg numbers, UPI IDs, phone numbers, URLs,
Telegram handles, company names (spaCy NER), financial claims,
payment requests, urgency signals, remote access mentions.
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

SEBI_REG_PATTERN = re.compile(
    r'\b(INH\d{9}|INA\d{9}|INP\d{9}|INR\d{9}|IND\d{9}|INZ\d{9}|INB\d{9}|INF\d{9})\b',
    re.IGNORECASE,
)

UPI_PATTERN = re.compile(r'[\w.\-]{3,}@[\w]{3,}', re.IGNORECASE)

PHONE_PATTERN = re.compile(r'\b[6-9]\d{9}\b')

URL_PATTERN = re.compile(
    r'https?://[^\s<>"]+|www\.[^\s<>"]+',
    re.IGNORECASE,
)

TGME_PATTERN = re.compile(
    r'(?:t\.me|telegram\.me)/[\w+]+|@[\w]{5,}',
    re.IGNORECASE,
)

WHATSAPP_PATTERN = re.compile(
    r'chat\.whatsapp\.com/[\w]+|wa\.me/[\w]+',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Keyword lists (loaded from taxonomy file)
# ---------------------------------------------------------------------------

def _load_taxonomy() -> dict:
    import os
    base = os.path.dirname(os.path.dirname(__file__))
    taxonomy_path = os.path.join(base, "data", "red_flag_taxonomy.json")
    try:
        with open(taxonomy_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"categories": []}


_TAXONOMY = _load_taxonomy()


def _keywords_for(category_id: str) -> List[str]:
    for cat in _TAXONOMY.get("categories", []):
        if cat["id"] == category_id:
            return cat.get("keywords", [])
    return []


GUARANTEE_KEYWORDS = _keywords_for("guaranteed_returns")
URGENCY_KEYWORDS = _keywords_for("urgency_pressure")
PAYMENT_KEYWORDS = _keywords_for("payment_pressure")
IMPERSONATION_KEYWORDS = _keywords_for("impersonation_signals")
REMOTE_ACCESS_KEYWORDS = _keywords_for("remote_access")
CHANNEL_ISOLATION_KEYWORDS = _keywords_for("channel_isolation")


# ---------------------------------------------------------------------------
# NLP (spaCy) — lazy load
# ---------------------------------------------------------------------------

_NLP = None


def _get_nlp():
    global _NLP
    if _NLP is None:
        try:
            import spacy
            _NLP = spacy.load("en_core_web_sm")
        except Exception as exc:
            logger.warning(f"spaCy model not available: {exc}. ORG extraction disabled.")
            _NLP = False
    return _NLP


# ---------------------------------------------------------------------------
# Data class for extracted entities
# ---------------------------------------------------------------------------

@dataclass
class ExtractedEntities:
    sebi_registrations: List[str] = field(default_factory=list)
    upi_ids: List[str] = field(default_factory=list)
    phone_numbers: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    telegram_handles: List[str] = field(default_factory=list)
    whatsapp_links: List[str] = field(default_factory=list)
    org_names: List[str] = field(default_factory=list)

    # Claim flags
    guaranteed_returns_phrases: List[str] = field(default_factory=list)
    payment_request_phrases: List[str] = field(default_factory=list)
    urgency_phrases: List[str] = field(default_factory=list)
    impersonation_phrases: List[str] = field(default_factory=list)
    remote_access_phrases: List[str] = field(default_factory=list)
    channel_isolation_phrases: List[str] = field(default_factory=list)

    # Derived booleans
    has_payment_request: bool = False
    has_guaranteed_returns: bool = False
    has_urgency: bool = False
    has_remote_access: bool = False
    has_impersonation: bool = False
    has_channel_isolation: bool = False


def _match_keywords(text_lower: str, keywords: List[str]) -> List[str]:
    """Return all keyword phrases found (case-insensitive) in text."""
    found = []
    for kw in keywords:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


def extract_entities(text: str) -> ExtractedEntities:
    """
    Full entity extraction from raw text.
    Returns an ExtractedEntities dataclass.
    """
    ent = ExtractedEntities()
    text_lower = text.lower()

    # --- Structural extractions ---
    ent.sebi_registrations = list({m.upper() for m in SEBI_REG_PATTERN.findall(text)})
    ent.upi_ids = list({m for m in UPI_PATTERN.findall(text) if "@" in m})
    ent.phone_numbers = list({m for m in PHONE_PATTERN.findall(text)})
    ent.urls = list({m for m in URL_PATTERN.findall(text)})
    ent.telegram_handles = list({m for m in TGME_PATTERN.findall(text)})
    ent.whatsapp_links = list({m for m in WHATSAPP_PATTERN.findall(text)})

    # --- spaCy NER for ORG names ---
    nlp = _get_nlp()
    if nlp and isinstance(nlp, object) and nlp is not False:
        try:
            doc = nlp(text[:5000])  # limit to 5 000 chars for speed
            ent.org_names = list({ent_span.text for ent_span in doc.ents if ent_span.label_ == "ORG"})
        except Exception as exc:
            logger.warning(f"spaCy NER failed: {exc}")

    # --- Keyword-based claim flags ---
    ent.guaranteed_returns_phrases = _match_keywords(text_lower, GUARANTEE_KEYWORDS)
    ent.payment_request_phrases = _match_keywords(text_lower, PAYMENT_KEYWORDS)
    ent.urgency_phrases = _match_keywords(text_lower, URGENCY_KEYWORDS)
    ent.impersonation_phrases = _match_keywords(text_lower, IMPERSONATION_KEYWORDS)
    ent.remote_access_phrases = _match_keywords(text_lower, REMOTE_ACCESS_KEYWORDS)
    ent.channel_isolation_phrases = _match_keywords(text_lower, CHANNEL_ISOLATION_KEYWORDS)

    # Derived booleans
    ent.has_guaranteed_returns = bool(ent.guaranteed_returns_phrases)
    ent.has_payment_request = bool(ent.payment_request_phrases)
    ent.has_urgency = bool(ent.urgency_phrases)
    ent.has_remote_access = bool(ent.remote_access_phrases)
    ent.has_impersonation = bool(ent.impersonation_phrases)
    ent.has_channel_isolation = bool(ent.channel_isolation_phrases)

    return ent
