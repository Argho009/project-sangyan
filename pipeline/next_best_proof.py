"""
SANGYAN — Next Best Proof Engine (Step 9)
Given what is missing or contradictory, generates exactly 1-3
specific, actionable next steps for the user.
"""

from typing import List, Optional


OFFICIAL_LINKS = [
    {
        "label": "Verify SEBI registration yourself",
        "url": "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=13",
    },
    {
        "label": "Report cybercrime to I4C",
        "url": "https://cybercrime.gov.in",
    },
    {
        "label": "SEBI investor grievance (SCORES)",
        "url": "https://scores.sebi.gov.in",
    },
    {
        "label": "SEBI investor awareness",
        "url": "https://investor.sebi.gov.in",
    },
    {
        "label": "NSE official website",
        "url": "https://www.nseindia.com",
    },
    {
        "label": "Check PhishTank manually",
        "url": "https://www.phishtank.com",
    },
]


def generate_next_steps(
    verdict: str,
    sebi_result=None,
    payment_results=None,
    social_results=None,
    phishtank_results=None,
    extracted_entities=None,
    already_paid: bool = False,
) -> List[str]:
    """
    Generate 1-3 specific next steps based on what failed in the proof chain.
    verdict: STOP | PAUSE | TRUST
    """
    steps = []

    # Always top-priority if already paid
    if already_paid:
        steps.append(
            "You may have already sent money — report IMMEDIATELY at cybercrime.gov.in "
            "(helpline: 1930). Do not send any more money."
        )

    # STOP verdict — must-do steps
    if verdict == "STOP":
        steps.append("Do NOT transfer any money based on this message.")

    # SEBI failures
    if sebi_result:
        if sebi_result.status == "NOT_FOUND":
            steps.append(
                f"Search '{sebi_result.registration_number}' yourself at "
                f"sebi.gov.in/intermediary. If not found, this is a fraudulent claim."
            )
        elif sebi_result.status == "MISMATCH":
            steps.append(
                f"The registered name '{sebi_result.registered_name}' does NOT match the name in the message. "
                f"Call the registered entity's official number from sebi.gov.in to confirm their identity."
            )
        elif sebi_result.status in ("UNAVAILABLE", "EXPIRED"):
            steps.append(
                "Manually verify this registration at sebi.gov.in before proceeding. "
                "Do not pay until registration is confirmed active."
            )

    # Payment issues
    if payment_results:
        bad_payment = [r for r in payment_results if r.status in ("PERSONAL_UPI", "NOT_VERIFIABLE")]
        if bad_payment:
            steps.append(
                "Call the official number listed on sebi.gov.in for this entity and ask them "
                "to confirm the exact UPI ID they use. Do NOT use a number from the message itself."
            )

    # Suspicious URL
    if phishtank_results:
        phish = [r for r in phishtank_results if r.status == "KNOWN_PHISHING"]
        if phish:
            steps.append(
                "Do NOT click any link in this message. The URL has been identified as a known "
                "phishing page. Manually type the official broker website in your browser."
            )
    if extracted_entities and extracted_entities.urls:
        steps.append(
            "If you need to visit a website, manually type the official URL in your browser. "
            "Never click links in investment-related messages."
        )

    # Unverified social handles
    if social_results:
        bad = [r for r in social_results if r.status in ("DOES_NOT_MATCH", "UNKNOWN_ENTITY", "FAKE_PATTERN")]
        if bad:
            steps.append(
                "Check the official website of this broker for their verified social media handles. "
                "Any Telegram/WhatsApp group promising investment tips is NOT from a regulated entity."
            )

    # Remote access
    if extracted_entities and extracted_entities.has_remote_access:
        steps.append(
            "NEVER install any app or give remote access to your device based on a message. "
            "This is the #1 method used by fraudsters to empty bank accounts."
        )

    # Guaranteed returns
    if extracted_entities and extracted_entities.has_guaranteed_returns:
        steps.append(
            "SEBI prohibits guaranteeing returns. Any 'guaranteed profit' promise is illegal "
            "and is a hallmark of investment fraud."
        )

    # TRUST verdict caveat
    if verdict == "TRUST" and not steps:
        steps.append(
            "Verification checks passed. Always confirm directly with the entity on their "
            "official number from sebi.gov.in before transferring funds."
        )

    # Deduplicate and limit to 3
    seen = set()
    unique_steps = []
    for s in steps:
        if s not in seen:
            seen.add(s)
            unique_steps.append(s)

    return unique_steps[:3]


def get_official_links(
    sebi_result=None,
    verdict: str = "STOP",
) -> List[dict]:
    """Return relevant official links based on the situation."""
    links = list(OFFICIAL_LINKS[:3])   # always include top 3
    if verdict == "STOP":
        # Add cybercrime report link prominently
        report_link = {
            "label": "Report this scam now",
            "url": "https://cybercrime.gov.in",
        }
        if report_link not in links:
            links.insert(1, report_link)
    return links[:5]
