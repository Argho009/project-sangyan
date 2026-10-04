"""
SANGYAN — Claim Extractor (Step 4: What Must Be True)
For every entity and claim extracted, defines what independent evidence
would need to exist for that claim to be legitimate.
This generates the 'required proofs' list fed into the verification pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from pipeline.entity_extractor import ExtractedEntities


@dataclass
class RequiredProof:
    claim: str
    proof_needed: str
    verification_source: str
    is_critical: bool = False


@dataclass
class ClaimAnalysis:
    required_proofs: List[RequiredProof] = field(default_factory=list)
    sebi_numbers_to_check: List[str] = field(default_factory=list)
    upi_ids_to_check: List[str] = field(default_factory=list)
    urls_to_check: List[str] = field(default_factory=list)
    handles_to_check: List[str] = field(default_factory=list)
    phones_to_check: List[str] = field(default_factory=list)


def generate_required_proofs(entities: ExtractedEntities) -> ClaimAnalysis:
    """
    For every extracted entity, generate what independent proof would need
    to exist for the claim to be legitimate.
    """
    analysis = ClaimAnalysis()

    # SEBI registration claims
    for reg in entities.sebi_registrations:
        analysis.sebi_numbers_to_check.append(reg)
        entity_name = entities.org_names[0] if entities.org_names else "the claimed entity"
        analysis.required_proofs.append(RequiredProof(
            claim=f"SEBI registration {reg} belonging to {entity_name}",
            proof_needed=(
                f"{reg} must exist in the SEBI intermediary registry AND "
                f"the registered name must match '{entity_name}' AND "
                f"the registration must be currently active (not expired)."
            ),
            verification_source="sebi.gov.in/intermediary",
            is_critical=True,
        ))

    # UPI payment claims
    for upi in entities.upi_ids:
        analysis.upi_ids_to_check.append(upi)
        analysis.required_proofs.append(RequiredProof(
            claim=f"Payment to UPI ID: {upi}",
            proof_needed=(
                f"The UPI ID '{upi}' must be verifiably linked to the SEBI-registered "
                f"entity making the claim. Personal UPI handles (paytm, ybl, okaxis) "
                f"are not used by regulated entities to collect client funds."
            ),
            verification_source="Call registered entity via sebi.gov.in official number",
            is_critical=True,
        ))

    # URL claims
    for url in entities.urls:
        analysis.urls_to_check.append(url)
        analysis.required_proofs.append(RequiredProof(
            claim=f"Website/URL: {url}",
            proof_needed=(
                f"The domain in '{url}' must exactly match the official domain of the "
                f"claimed entity. It must use HTTPS. It must not be a URL shortener, "
                f"free hosting service, or domain registered less than 30 days ago."
            ),
            verification_source="PhishTank, WHOIS, official broker website",
            is_critical=False,
        ))

    # Social handle claims
    for handle in entities.telegram_handles:
        analysis.handles_to_check.append(handle)
        analysis.required_proofs.append(RequiredProof(
            claim=f"Telegram/social handle: {handle}",
            proof_needed=(
                f"The handle '{handle}' must exactly match the official verified social "
                f"handle listed on the entity's official website. "
                f"Note: SEBI, NSE, and BSE do NOT operate Telegram tip groups."
            ),
            verification_source="Official broker website, SANGYAN handle registry",
            is_critical=False,
        ))

    # Phone number claims
    for phone in entities.phone_numbers:
        analysis.phones_to_check.append(phone)
        analysis.required_proofs.append(RequiredProof(
            claim=f"Contact number: {phone}",
            proof_needed=(
                f"Phone number {phone} must match the official support number "
                f"listed on sebi.gov.in for the claimed entity."
            ),
            verification_source="SEBI intermediary registry, cybercrime.gov.in",
            is_critical=False,
        ))

    # Guaranteed returns — requires regulatory clearance
    if entities.has_guaranteed_returns:
        analysis.required_proofs.append(RequiredProof(
            claim="Guaranteed returns promised",
            proof_needed=(
                "For this claim to be legitimate, the entity would need regulatory "
                "permission to promise guaranteed returns — which NO SEBI-registered "
                "Investment Adviser, Research Analyst, or Portfolio Manager is permitted to do."
            ),
            verification_source="SEBI (Investment Advisers) Regulations, 2013",
            is_critical=True,
        ))

    return analysis
