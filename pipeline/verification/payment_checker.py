"""
SANGYAN — Payment (UPI) Verifier (Tier 1b)
Checks if a UPI ID can be associated with a known SEBI-registered entity.
No API to truly link UPI to SEBI; uses pattern + registered broker data.

Output: LINKED_TO_REGISTERED_ENTITY | PERSONAL_UPI | NOT_VERIFIABLE
"""

import json
import os
import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Load authorised brokers
def _load_brokers() -> list:
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(base, "data", "authorised_brokers.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("authorised_brokers", [])
    except Exception:
        return []


BROKERS = _load_brokers()

# UPI handles that are almost always personal (not entity)
PERSONAL_UPI_SUFFIXES = {
    "ybl", "paytm", "okaxis", "okicici", "okhdfcbank",
    "oksbi", "apl", "upi", "ibl", "timecosmos",
}

# VPA suffixes registered to payment aggregators used by brokers
KNOWN_ENTITY_SUFFIXES = {
    "razorpay", "payu", "cashfree", "billdesk",
    "zerodha", "icicibank", "hdfcbank", "axisbank", "sbi",
}


@dataclass
class PaymentCheckResult:
    identifier: str
    status: str           # LINKED_TO_REGISTERED_ENTITY | PERSONAL_UPI | NOT_VERIFIABLE
    matched_broker: Optional[str] = None
    risk_signals: list = None
    detail: str = ""

    def __post_init__(self):
        if self.risk_signals is None:
            self.risk_signals = []


def check_upi_id(upi_id: str) -> PaymentCheckResult:
    """
    Heuristic UPI verification.
    1. Check if VPA handle/suffix matches a known broker domain.
    2. Check if it's a personal UPI suffix (high risk).
    3. Otherwise: NOT_VERIFIABLE.
    """
    upi_id = upi_id.strip().lower()
    risk_signals = []

    # Extract the suffix (everything after @)
    if "@" not in upi_id:
        return PaymentCheckResult(
            identifier=upi_id,
            status="NOT_VERIFIABLE",
            risk_signals=["malformed UPI ID — missing @ symbol"],
            detail="This does not appear to be a valid UPI ID.",
        )

    local_part, vpa_suffix = upi_id.split("@", 1)

    # Check if matches a known broker's official domain
    for broker in BROKERS:
        broker_name = broker["name"].lower()
        # Check VPA suffix contains broker name or known email domain
        email_domain = broker.get("official_email_domain", "").lower()
        if (email_domain and email_domain in vpa_suffix) or (
            broker_name.split()[0] in vpa_suffix
        ):
            return PaymentCheckResult(
                identifier=upi_id,
                status="LINKED_TO_REGISTERED_ENTITY",
                matched_broker=broker["name"],
                detail=(
                    f"UPI ID suffix '{vpa_suffix}' appears to be associated with "
                    f"{broker['name']} — a SEBI-registered broker. "
                    f"Confirm via official contact: {broker.get('official_support_number', 'N/A')}"
                ),
            )

    # Check if personal UPI suffix
    if vpa_suffix in PERSONAL_UPI_SUFFIXES:
        risk_signals.append(
            f"'{vpa_suffix}' is a personal UPI handle (e.g., PayTM, PhonePe) — "
            "not typically used by registered entities for collecting client funds"
        )
        return PaymentCheckResult(
            identifier=upi_id,
            status="PERSONAL_UPI",
            risk_signals=risk_signals,
            detail=(
                f"The UPI ID '{upi_id}' uses a personal payment handle. "
                "Regulated investment advisors and brokers do not collect "
                "client funds via personal UPI IDs."
            ),
        )

    # Neither matched
    risk_signals.append("UPI suffix not associated with any known registered entity")
    return PaymentCheckResult(
        identifier=upi_id,
        status="NOT_VERIFIABLE",
        risk_signals=risk_signals,
        detail=(
            f"Cannot independently verify that '{upi_id}' belongs to a "
            "SEBI-registered entity. Call the official number on sebi.gov.in "
            "to confirm this payment destination."
        ),
    )
