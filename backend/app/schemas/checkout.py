"""Backend checkout records. Browser actions carry identifiers, never payment terms."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from app.schemas.domain import DomainModel, PaymentIntent
from app.services.paypal import Identifier, PayPalOrderTerms


class OrderCreationState(StrEnum):
    CREATING = "CREATING"
    READY = "READY"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"


class CheckoutRecord(DomainModel):
    payment: PaymentIntent
    terms: PayPalOrderTerms
    order_creation: OrderCreationState = OrderCreationState.CREATING
    order_id: Identifier | None = None
    capture_id: Identifier | None = None
    capture_decline_code: Literal["INSTRUMENT_DECLINED"] | None = None
    decline_request_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_terms(self) -> Self:
        if (self.capture_decline_code is None) != (self.decline_request_id is None):
            raise ValueError("Decline evidence requires both code and dispatch reference")
        if (self.terms.reference_id, self.terms.amount_minor, self.terms.currency) != (
            self.payment.payment_intent_id,
            self.payment.amount_minor,
            self.payment.currency,
        ):
            raise ValueError("Provider terms must match the persisted payment binding")
        if self.order_creation == OrderCreationState.READY and self.order_id is None:
            raise ValueError("Ready checkout requires a provider order ID")
        if self.payment.state.value == "SUCCEEDED" and self.capture_id is None:
            raise ValueError("Successful checkout requires a verified capture ID")
        return self
