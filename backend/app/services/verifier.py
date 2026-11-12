"""Deterministic, evidence-backed equality checks for structured attributes.

This service does not interpret prose, establish evidence authenticity, enforce
financial policy, or authorize payment. Supply canonical backend offer data.
"""

import hashlib
import json
import math

from pydantic import JsonValue

from app.schemas import (
    CheckKind,
    CheckResult,
    Offer,
    PurchaseIntent,
    VerificationResult,
    VerificationStatus,
)

VERIFIER_VERSION = "deterministic-attributes-v1"
PERCENT_SCALE = 100.0


def _is_supported(value: JsonValue) -> bool:
    if type(value) in (bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is str:
        return bool(value.strip())
    return False


def _check_attribute(requirement: str, expected: JsonValue, offer: Offer) -> CheckResult:
    evidence = list(offer.evidence.get(requirement, []))
    actual = offer.attributes.get(requirement)
    if not _is_supported(expected):
        status = VerificationStatus.UNKNOWN
        explanation = "The requested value needs an unsupported or ambiguous interpretation."
    elif not _is_supported(actual) or type(actual) is not type(expected):
        status = VerificationStatus.UNKNOWN
        explanation = "The structured value is absent, ambiguous, or has an incompatible type."
    elif actual != expected:
        # A known structured failure cannot become eligible merely by removing evidence.
        status = VerificationStatus.FAIL
        explanation = "The structured offer value does not equal the requested value."
    elif not evidence:
        status = VerificationStatus.UNKNOWN
        explanation = "The structured value matches, but supporting evidence is absent."
    else:
        status = VerificationStatus.PASS
        explanation = "The structured value exactly matches and supporting evidence is recorded."
    return CheckResult(
        requirement=requirement,
        status=status,
        kind=CheckKind.DETERMINISTIC,
        evidence=evidence,
        explanation=explanation,
    )


def _snapshot_id(intent: PurchaseIntent, offer: Offer) -> str:
    payload = {
        "verifier_version": VERIFIER_VERSION,
        "intent": intent.model_dump(mode="python"),
        "offer": offer.model_dump(mode="python"),
    }
    # Reject non-JSON/non-finite input rather than canonicalizing it into a different value.
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return f"verification-v1-{hashlib.sha256(encoded).hexdigest()}"


def verify_offer(intent: PurchaseIntent, offer: Offer) -> VerificationResult:
    """Return required/preferred checks and a reproducible in-memory snapshot.

    Only explicit attribute maps are evaluated. No implicit currency, budget,
    quantity, category, merchant, or payment decision is made. Known mandatory
    failure wins over UNKNOWN; no mandatory checks yields UNKNOWN, not vacuous PASS.
    """
    # Existing instances may have been mutated or built without validation.
    intent = PurchaseIntent.model_validate(intent.model_dump(warnings=False))
    offer = Offer.model_validate(offer.model_dump(warnings=False))
    snapshot_id = _snapshot_id(intent, offer)
    required = [
        _check_attribute(key, value, offer)
        for key, value in sorted(intent.required_attributes.items())
    ]
    preferred = [
        _check_attribute(key, value, offer)
        for key, value in sorted(intent.preferred_attributes.items())
    ]
    missing_evidence = [check.requirement for check in required if not check.evidence]
    if any(check.status == VerificationStatus.FAIL for check in required):
        status = VerificationStatus.FAIL
        explanation = "At least one mandatory structured requirement failed."
    elif not required or any(check.status == VerificationStatus.UNKNOWN for check in required):
        status = VerificationStatus.UNKNOWN
        explanation = (
            "Mandatory verification is incomplete or no mandatory attributes were provided."
        )
    else:
        status = VerificationStatus.PASS
        explanation = "All mandatory structured attributes match with recorded evidence."
    score = (
        PERCENT_SCALE
        * sum(check.status == VerificationStatus.PASS for check in preferred)
        / len(preferred)
        if preferred
        else 0.0
    )
    return VerificationResult(
        verification_snapshot_id=snapshot_id,
        offer_id=offer.offer_id,
        status=status,
        required_checks=required,
        preferred_checks=preferred,
        preference_score=score,
        missing_evidence=missing_evidence,
        explanation=explanation,
    )
