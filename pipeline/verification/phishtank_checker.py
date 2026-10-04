"""
SANGYAN — PhishTank URL Checker (Tier 2a)
Queries PhishTank free API to check if a URL is a known phishing page.

IMPORTANT CAVEAT always returned:
"Not found in this database. Absence does not confirm safety."
"""

import hashlib
import logging
import os
import requests
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

PHISHTANK_API = "https://checkurl.phishtank.com/checkurl/"
PHISHTANK_API_KEY = os.getenv("PHISHTANK_API_KEY", "")   # set in .env

HEADERS = {
    "User-Agent": "phishtank/SANGYAN-fraud-checker",
    "Content-Type": "application/x-www-form-urlencoded",
}

ABSENCE_CAVEAT = (
    "Not found in PhishTank database. "
    "Absence does not confirm safety — the URL may still be malicious."
)


@dataclass
class PhishTankResult:
    url: str
    status: str          # KNOWN_PHISHING | NOT_IN_DATABASE | ERROR
    phishtank_id: Optional[str] = None
    verified: Optional[bool] = None
    detail: str = ""
    caveat: str = ""


def check_url(url: str) -> PhishTankResult:
    """
    Check a URL against the PhishTank database.
    Returns a PhishTankResult with status and mandatory caveat.
    """
    url = url.strip()
    payload = {
        "url": url,
        "format": "json",
    }
    if PHISHTANK_API_KEY:
        payload["app_key"] = PHISHTANK_API_KEY

    try:
        resp = requests.post(
            PHISHTANK_API,
            data=payload,
            headers=HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", {})
        in_database = results.get("in_database", False)

        if not in_database:
            return PhishTankResult(
                url=url,
                status="NOT_IN_DATABASE",
                detail="URL not found in PhishTank database.",
                caveat=ABSENCE_CAVEAT,
            )

        valid = results.get("valid", False)
        phish_id = results.get("phish_id", "")
        verified = results.get("verified", False)

        if valid:
            return PhishTankResult(
                url=url,
                status="KNOWN_PHISHING",
                phishtank_id=phish_id,
                verified=verified,
                detail=(
                    f"URL is a KNOWN PHISHING page. "
                    f"PhishTank ID: {phish_id}. Verified: {verified}."
                ),
                caveat="",
            )
        else:
            return PhishTankResult(
                url=url,
                status="NOT_IN_DATABASE",
                detail="URL found in database but marked invalid/removed.",
                caveat=ABSENCE_CAVEAT,
            )

    except requests.Timeout:
        logger.warning(f"PhishTank request timed out for {url}")
        return PhishTankResult(
            url=url,
            status="ERROR",
            detail="PhishTank service did not respond in time.",
            caveat=ABSENCE_CAVEAT,
        )
    except Exception as exc:
        logger.error(f"PhishTank check error: {exc}")
        return PhishTankResult(
            url=url,
            status="ERROR",
            detail=f"Could not complete PhishTank check: {str(exc)}",
            caveat=ABSENCE_CAVEAT,
        )


def check_urls(urls: list) -> list:
    """Check multiple URLs and return list of PhishTankResult."""
    return [check_url(u) for u in urls]
