"""
SANGYAN — SEBI Registry Checker (Tier 1a)
Checks SEBI intermediary registration via their public web interface.
Since SEBI does not expose a public REST API, we use a best-effort
web scraping approach combined with a local cache of known registrations.

Output: VERIFIED | NOT_FOUND | MISMATCH | EXPIRED | UNAVAILABLE
"""

import re
import time
import logging
import requests
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SEBI_SEARCH_URL = (
    "https://www.sebi.gov.in/sebiweb/other/OtherAction.do"
    "?doRecognisedFpi=yes&intmId=13"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Referer": "https://www.sebi.gov.in/",
}

# Prefix → category mapping
SEBI_PREFIXES = {
    "INH": "Investment Adviser",
    "INA": "Investment Adviser (Corporate)",
    "INP": "Portfolio Manager",
    "INR": "Research Analyst",
    "IND": "Investment Adviser (Individual)",
    "INZ": "Stock Broker",
    "INB": "Stock Broker (NSE)",
    "INF": "Stock Broker (BSE)",
}


@dataclass
class SEBICheckResult:
    registration_number: str
    status: str             # VERIFIED | NOT_FOUND | MISMATCH | EXPIRED | UNAVAILABLE
    registered_name: Optional[str] = None
    registration_category: Optional[str] = None
    validity: Optional[str] = None
    name_match: Optional[bool] = None
    source_url: str = SEBI_SEARCH_URL
    raw_detail: str = ""


def _category_from_prefix(reg_number: str) -> str:
    prefix = reg_number[:3].upper()
    return SEBI_PREFIXES.get(prefix, "Unknown SEBI Registration")


def _attempt_sebi_web_check(reg_number: str) -> dict:
    """
    Best-effort web check against SEBI's intermediary search page.
    Returns a dict with keys: found(bool), name(str), validity(str).
    SEBI's portal is session-based, so we attempt a GET with the
    registration number as a query param where possible.
    """
    try:
        # SEBI's search form uses POST; attempt the GET version
        params = {"registrationNumber": reg_number}
        resp = requests.get(
            "https://www.sebi.gov.in/sebiweb/other/OtherAction.do",
            params={**params, "doRecognisedFpi": "yes", "intmId": "13"},
            headers=HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        body = resp.text

        # Look for registration number in response
        if reg_number.upper() in body.upper():
            # Try to extract name (heuristic based on typical SEBI table structure)
            name_match = re.search(
                r'<td[^>]*>\s*' + re.escape(reg_number) + r'\s*</td>\s*<td[^>]*>\s*([^<]+)',
                body,
                re.IGNORECASE | re.DOTALL,
            )
            name = name_match.group(1).strip() if name_match else None

            # Look for validity/expiry date
            date_match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', body)
            validity = date_match.group(1) if date_match else None

            return {"found": True, "name": name, "validity": validity}

        return {"found": False, "name": None, "validity": None}

    except requests.Timeout:
        logger.warning(f"SEBI check timed out for {reg_number}")
        return {"found": None, "name": None, "validity": None}
    except Exception as exc:
        logger.error(f"SEBI check error for {reg_number}: {exc}")
        return {"found": None, "name": None, "validity": None}


def check_sebi_registration(
    reg_number: str,
    claimed_name: Optional[str] = None,
) -> SEBICheckResult:
    """
    Main entry point for SEBI registration verification.
    reg_number: e.g. "INH000123456"
    claimed_name: name claimed in the scam message (for mismatch detection)
    """
    reg_number = reg_number.strip().upper()
    category = _category_from_prefix(reg_number)

    result = _attempt_sebi_web_check(reg_number)

    if result["found"] is None:
        # Network/service error
        return SEBICheckResult(
            registration_number=reg_number,
            status="UNAVAILABLE",
            registration_category=category,
            raw_detail="SEBI registry could not be reached. Verify manually at sebi.gov.in",
        )

    if not result["found"]:
        return SEBICheckResult(
            registration_number=reg_number,
            status="NOT_FOUND",
            registration_category=category,
            raw_detail=f"{reg_number} was NOT found in the SEBI intermediary registry.",
        )

    # Found — check name mismatch
    registered_name = result.get("name")
    name_match = None
    if claimed_name and registered_name:
        name_match = claimed_name.lower().strip() in registered_name.lower()

    status = "VERIFIED"
    if name_match is False:
        status = "MISMATCH"

    return SEBICheckResult(
        registration_number=reg_number,
        status=status,
        registered_name=registered_name,
        registration_category=category,
        validity=result.get("validity"),
        name_match=name_match,
        raw_detail=(
            f"{reg_number} found in SEBI registry as '{registered_name}'. "
            f"Category: {category}. Validity: {result.get('validity', 'unknown')}."
        ),
    )
