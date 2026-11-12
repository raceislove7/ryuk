"""Internal backend policy inputs, never browser/model-authored authority records."""

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from .domain import Currency, DomainModel, MinorUnits, NonEmptyString


class FinancialPolicy(DomainModel):
    """Current policy loaded by trusted backend code, separately from parsed intent."""

    user_id: NonEmptyString
    version: NonEmptyString
    currency: Currency
    max_amount_minor: MinorUnits
    approval_threshold_minor: MinorUnits
    allowed_merchant_ids: frozenset[NonEmptyString]

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        """A review threshold cannot increase the active hard ceiling."""
        if self.approval_threshold_minor > self.max_amount_minor:
            raise ValueError("policy approval threshold must not exceed its hard ceiling")
        return self


class BudgetSnapshot(DomainModel):
    """Authoritative ledger/reservation values for one user and currency."""

    user_id: NonEmptyString
    currency: Currency
    limit_minor: MinorUnits
    settled_minor: MinorUnits
    reserved_minor: MinorUnits

    @property
    def remaining_minor(self) -> int:
        """Availability before this proposal, with overcommitment exposed as zero."""
        return max(0, self.limit_minor - self.settled_minor - self.reserved_minor)


class AttemptState(StrEnum):
    CLEAR = "CLEAR"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


class AttemptSnapshot(DomainModel):
    """Explicit trusted payment-history lookup; never default missing history to clear."""

    user_id: NonEmptyString
    proposal_id: NonEmptyString
    state: AttemptState
