"""Closed provider schema for strict structured output, distinct from the domain DTO."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr

from .domain import DomainModel, NonEmptyString, PositiveInteger

MAX_QUERY_LENGTH = 4_000
SUPPORTED_CURRENCY_EXPONENTS = {"USD": 2, "EUR": 2, "CHF": 2, "GBP": 2, "JPY": 0}
SupportedCurrency = Literal["USD", "EUR", "CHF", "GBP", "JPY"]


class ParseIntentRequest(DomainModel):
    query: Annotated[NonEmptyString, Field(max_length=MAX_QUERY_LENGTH)]


class MoneyMention(DomainModel):
    """Raw written amount plus an exact source quote; the server converts minor units."""

    amount_text: NonEmptyString
    quote: NonEmptyString


class ExtractedAttribute(DomainModel):
    name: Annotated[NonEmptyString, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    value: StrictBool | StrictInt | StrictFloat | StrictStr
    quote: NonEmptyString


class LLMIntentExtraction(DomainModel):
    """Every field is required; nullable fields represent ambiguity, never infinity.

    Lists replace open dictionaries so provider strict JSON schema can close every
    object. The backend builds required/preferred maps only after validation.
    """

    status: Literal["READY", "NEEDS_CLARIFICATION"]
    clarification: str | None
    category: NonEmptyString | None
    currency: SupportedCurrency | None
    budget: MoneyMention | None
    approval_threshold: MoneyMention | None
    required_attributes: list[ExtractedAttribute]
    preferred_attributes: list[ExtractedAttribute]
    quantity: PositiveInteger | None
    notes: str | None
