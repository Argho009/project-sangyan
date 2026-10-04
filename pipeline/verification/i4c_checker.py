"""
SANGYAN — I4C Suspect Repository Checker (Tier 2b)
Checks mobile numbers, UPI IDs, and social handles against the
Indian Cyber Crime Coordination Centre (I4C) suspect repository
at cybercrime.gov.in.

MANDATORY CAVEAT always returned:
"This identifier appears in a complaints-based repository.
 This is a risk signal, not a legal determination."
"""

import logging
import os
import requests
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

I4C_API_BASE = os.getenv("I4C_API_BASE", "https://cybercrime.gov.in/Webform/")
MANDATORY_CAVEAT = (
    "This signal is based on complaints and may be incomplete. "
    "Presence indicates risk, not confirmed guilt. "
    "This is a risk signal, not a legal determination."
)

HEADERS = {
    "User-Agent": "SANGYAN-fraud-checker/1.0",
    "Accept": "application/json",
}


@dataclass
class I4CResult:
    identifier: str
    identifier_type: str   # phone | upi | handle
    status: str            # IN_REPOSITORY | NOT_FOUND | UNAVAILABLE
    complaint_count: Optional[int] = None
    detail: str = ""
    caveat: str = MANDATORY_CAVEAT


def _check_identifier(identifier: str, id_type: str) -> I4CResult:
    """
    Attempt to check identifier against I4C suspect repository.
    I4C does not expose a public documented API; this performs a
    best-effort check using their web form endpoint.
    Falls back to UNAVAILABLE gracefully.
    """
    try:
        # I4C suspect search endpoint (form-based)
        payload = {
            "mobileNo": identifier if id_type == "phone" else "",
            "vpaId": identifier if id_type == "upi" else "",
            "socialMediaHandle": identifier if id_type == "handle" else "",
        }
        resp = requests.post(
            I4C_API_BASE + "SearchSuspect.aspx",
            data=payload,
            headers=HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        body = resp.text.lower()

        # Heuristic: look for "found" / "no record" / complaint counts in response
        if "no record" in body or "not found" in body or "0 record" in body:
            return I4CResult(
                identifier=identifier,
                identifier_type=id_type,
                status="NOT_FOUND",
                detail=f"{identifier} was NOT found in the I4C suspect repository.",
                caveat=MANDATORY_CAVEAT,
            )
        elif "found" in body or "complaint" in body or "suspect" in body:
            return I4CResult(
                identifier=identifier,
                identifier_type=id_type,
                status="IN_REPOSITORY",
                detail=f"{identifier} APPEARS in the I4C suspect complaints repository.",
                caveat=MANDATORY_CAVEAT,
            )
        else:
            return I4CResult(
                identifier=identifier,
                identifier_type=id_type,
                status="UNAVAILABLE",
                detail="I4C check returned an ambiguous response. Verify manually at cybercrime.gov.in",
                caveat=MANDATORY_CAVEAT,
            )

    except requests.Timeout:
        logger.warning(f"I4C check timed out for {identifier}")
    except Exception as exc:
        logger.error(f"I4C check error for {identifier}: {exc}")

    return I4CResult(
        identifier=identifier,
        identifier_type=id_type,
        status="UNAVAILABLE",
        detail="I4C repository could not be reached. Check manually at cybercrime.gov.in/Webform/",
        caveat=MANDATORY_CAVEAT,
    )


def check_phone(phone: str) -> I4CResult:
    return _check_identifier(phone.strip(), "phone")


def check_upi(upi_id: str) -> I4CResult:
    return _check_identifier(upi_id.strip(), "upi")


def check_handle(handle: str) -> I4CResult:
    return _check_identifier(handle.lstrip("@"), "handle")
