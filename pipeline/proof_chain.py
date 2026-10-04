"""
SANGYAN — Proof Chain Builder (Step 6 + 7)
Builds the 5-node proof chain and runs consistency checks.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any


# ---------------------------------------------------------------------------
# Node statuses
# ---------------------------------------------------------------------------

class NodeStatus:
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"
    NOT_APPLICABLE = "not_applicable"


# ---------------------------------------------------------------------------
# Proof nodes
# ---------------------------------------------------------------------------

@dataclass
class ClaimNode:
    type: str = "claim"
    content: str = ""
    registration: Optional[str] = None
    entity_name: Optional[str] = None
    upi_ids: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    handles: List[str] = field(default_factory=list)
    status: str = NodeStatus.UNVERIFIED
    detail: str = ""


@dataclass
class EntityNode:
    type: str = "entity"
    found: bool = False
    source: str = "SEBI intermediary list"
    registered_name: Optional[str] = None
    name_match: Optional[bool] = None
    sebi_status: str = "NOT_FOUND"   # VERIFIED | NOT_FOUND | MISMATCH | EXPIRED | UNAVAILABLE
    status: str = NodeStatus.UNVERIFIED
    detail: str = ""


@dataclass
class RegulatorNode:
    type: str = "regulator"
    verified: bool = False
    registration_valid: bool = False
    registration_category: Optional[str] = None
    expiry_date: Optional[str] = None
    contradictions: List[str] = field(default_factory=list)
    status: str = NodeStatus.UNVERIFIED
    detail: str = ""


@dataclass
class OfferNode:
    type: str = "offer"
    guaranteed_returns_claimed: bool = False
    regulatory_violation: bool = False
    violation_reason: str = ""
    impersonation_detected: bool = False
    status: str = NodeStatus.UNVERIFIED
    detail: str = ""


@dataclass
class PaymentNode:
    type: str = "payment"
    identifiers: List[str] = field(default_factory=list)
    linked_to_entity: bool = False
    verified_via: str = "not verifiable"
    risk_signals: List[str] = field(default_factory=list)
    status: str = NodeStatus.UNVERIFIED
    detail: str = ""


@dataclass
class ProofChain:
    claim: ClaimNode = field(default_factory=ClaimNode)
    entity: EntityNode = field(default_factory=EntityNode)
    regulator: RegulatorNode = field(default_factory=RegulatorNode)
    offer: OfferNode = field(default_factory=OfferNode)
    payment: PaymentNode = field(default_factory=PaymentNode)
    contradictions: List[str] = field(default_factory=list)

    def to_list(self) -> List[dict]:
        nodes = [self.claim, self.entity, self.regulator, self.offer, self.payment]
        return [
            {
                "node": n.type,
                "status": n.status,
                "detail": n.detail,
            }
            for n in nodes
        ]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_proof_chain(
    extracted_entities,          # ExtractedEntities from entity_extractor
    sebi_result=None,            # SEBICheckResult or None
    payment_results=None,        # list of PaymentCheckResult
    social_results=None,         # list of SocialCheckResult
    phishtank_results=None,      # list of PhishTankResult
    red_flag_report=None,        # RedFlagReport
) -> ProofChain:
    """
    Construct the 5-node proof chain from all verification results.
    """
    chain = ProofChain()

    # ----- NODE 1: CLAIM -----
    claim = ClaimNode()
    claim.registration = extracted_entities.sebi_registrations[0] if extracted_entities.sebi_registrations else None
    claim.entity_name = extracted_entities.org_names[0] if extracted_entities.org_names else None
    claim.upi_ids = extracted_entities.upi_ids
    claim.urls = extracted_entities.urls
    claim.handles = extracted_entities.telegram_handles

    content_parts = []
    if claim.registration:
        content_parts.append(f"SEBI registration: {claim.registration}")
    if claim.entity_name:
        content_parts.append(f"Entity: {claim.entity_name}")
    if claim.upi_ids:
        content_parts.append(f"Payment UPI: {', '.join(claim.upi_ids)}")
    if claim.handles:
        content_parts.append(f"Channel: {', '.join(claim.handles)}")
    claim.content = "; ".join(content_parts) if content_parts else "No structured claims found"
    claim.status = NodeStatus.VERIFIED if content_parts else NodeStatus.UNVERIFIED
    claim.detail = claim.content
    chain.claim = claim

    # ----- NODE 2: ENTITY -----
    entity = EntityNode()
    if sebi_result:
        entity.registered_name = sebi_result.registered_name
        entity.name_match = sebi_result.name_match
        entity.sebi_status = sebi_result.status
        entity.detail = sebi_result.raw_detail

        if sebi_result.status == "VERIFIED":
            entity.found = True
            entity.status = NodeStatus.VERIFIED
        elif sebi_result.status == "MISMATCH":
            entity.found = True
            entity.status = NodeStatus.CONTRADICTED
        elif sebi_result.status in ("NOT_FOUND", "EXPIRED"):
            entity.found = False
            entity.status = NodeStatus.CONTRADICTED
        else:
            entity.status = NodeStatus.UNVERIFIED
    else:
        entity.detail = "No SEBI registration number found in message to verify."
        entity.status = NodeStatus.UNVERIFIED
    chain.entity = entity

    # ----- NODE 3: REGULATOR -----
    regulator = RegulatorNode()
    if sebi_result:
        regulator.registration_category = sebi_result.registration_category
        regulator.expiry_date = sebi_result.validity
        regulator.registration_valid = sebi_result.status == "VERIFIED"
        regulator.verified = regulator.registration_valid

        if sebi_result.status == "VERIFIED":
            regulator.status = NodeStatus.VERIFIED
            regulator.detail = (
                f"Registration {sebi_result.registration_number} is active. "
                f"Category: {sebi_result.registration_category}."
            )
        elif sebi_result.status == "MISMATCH":
            regulator.status = NodeStatus.CONTRADICTED
            regulator.contradictions.append(
                f"Name in message does not match registered name '{sebi_result.registered_name}' in SEBI registry."
            )
            regulator.detail = f"Name mismatch detected for {sebi_result.registration_number}."
        elif sebi_result.status == "NOT_FOUND":
            regulator.status = NodeStatus.CONTRADICTED
            regulator.contradictions.append(
                f"Registration number {sebi_result.registration_number} does NOT exist in SEBI intermediary registry."
            )
            regulator.detail = f"{sebi_result.registration_number} not found in SEBI registry."
        else:
            regulator.status = NodeStatus.UNVERIFIED
            regulator.detail = "Registry could not be reached. Manual verification required."
    else:
        regulator.status = NodeStatus.UNVERIFIED
        regulator.detail = "No registration number to verify."
    chain.regulator = regulator

    # ----- NODE 4: OFFER -----
    offer = OfferNode()
    offer.guaranteed_returns_claimed = extracted_entities.has_guaranteed_returns
    offer.impersonation_detected = extracted_entities.has_impersonation

    violations = []
    if offer.guaranteed_returns_claimed:
        offer.regulatory_violation = True
        offer.violation_reason = (
            "SEBI (Investment Advisers) Regulations, 2013 prohibit registered entities "
            "from promising guaranteed returns. This message promises guaranteed returns — "
            "a clear regulatory violation."
        )
        violations.append(offer.violation_reason)

    if offer.impersonation_detected:
        offer.regulatory_violation = True
        viol = (
            "Message falsely claims government/regulatory endorsement. "
            "SEBI, NSE, BSE, and RBI do not endorse specific advisors or guarantee returns."
        )
        violations.append(viol)

    if violations:
        offer.status = NodeStatus.CONTRADICTED
        offer.detail = " | ".join(violations)
    elif sebi_result and sebi_result.status == "VERIFIED":
        offer.status = NodeStatus.VERIFIED
        offer.detail = "Offer type appears consistent with registered category."
    else:
        offer.status = NodeStatus.UNVERIFIED
        offer.detail = "Offer legitimacy could not be confirmed."
    chain.offer = offer

    # ----- NODE 5: PAYMENT -----
    payment = PaymentNode()
    payment.identifiers = extracted_entities.upi_ids + extracted_entities.phone_numbers

    if payment_results:
        linked = [r for r in payment_results if r.status == "LINKED_TO_REGISTERED_ENTITY"]
        if linked:
            payment.linked_to_entity = True
            payment.verified_via = linked[0].detail
            payment.status = NodeStatus.VERIFIED
            payment.detail = linked[0].detail
        else:
            personal = [r for r in payment_results if r.status == "PERSONAL_UPI"]
            if personal:
                payment.risk_signals.extend(personal[0].risk_signals)
                payment.status = NodeStatus.CONTRADICTED
                payment.detail = personal[0].detail
            else:
                # NOT_VERIFIABLE
                all_risks = []
                for r in payment_results:
                    all_risks.extend(r.risk_signals)
                payment.risk_signals = all_risks
                payment.status = NodeStatus.UNVERIFIED
                payment.detail = "Payment destination could not be verified as belonging to any registered entity."
    else:
        payment.status = NodeStatus.UNVERIFIED
        payment.detail = "No payment identifiers found to verify."
    chain.payment = payment

    # ----- CONSISTENCY CHECKS (Step 7) -----
    contradictions = list(regulator.contradictions)

    # CLAIM vs ENTITY
    if entity.name_match is False:
        contradictions.append(
            f"CLAIM vs ENTITY: The name in the message does not match the registered name "
            f"'{entity.registered_name}' for {sebi_result.registration_number if sebi_result else 'unknown'}."
        )

    # ENTITY vs REGULATOR
    if entity.found and not regulator.registration_valid:
        contradictions.append(
            "ENTITY vs REGULATOR: Entity was found but registration is expired or invalid."
        )

    # REGULATOR vs OFFER
    if regulator.verified and offer.guaranteed_returns_claimed:
        contradictions.append(
            f"REGULATOR vs OFFER: Entity '{sebi_result.registered_name if sebi_result else 'claimed'}' "
            f"is registered as '{sebi_result.registration_category if sebi_result else 'unknown'}'. "
            f"Registered advisors CANNOT legally promise guaranteed returns. "
            f"This message makes such a promise — a regulatory violation."
        )

    # OFFER vs PAYMENT
    if not payment.linked_to_entity and extracted_entities.has_payment_request:
        contradictions.append(
            "OFFER vs PAYMENT: Payment is requested but the payment destination (UPI/account) "
            "cannot be linked to any verified SEBI-registered entity. "
            "Legitimate entities use verified payment channels."
        )

    chain.contradictions = contradictions
    return chain
