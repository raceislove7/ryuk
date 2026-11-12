"""Explicit catalog filters and synthetic response metadata."""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, model_validator

from .domain import Currency, DomainModel, MinorUnits, NonEmptyString, Offer, PositiveInteger

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20
SYNTHETIC_SOURCE = "synthetic_fixture:hotels:v1"
SYNTHETIC_NOTICE = (
    "Synthetic demonstration data only. No real hotels, availability, bookings, "
    "or merchant payment relationships are represented."
)


class CatalogSearchRequest(DomainModel):
    """AND-combined retrieval filters, not purchase intent or financial policy."""

    query: Annotated[NonEmptyString, Field(max_length=200)] | None = None
    country: NonEmptyString | None = None
    nights: PositiveInteger | None = None
    currency: Currency | None = None
    max_amount_minor: MinorUnits | None = None
    attributes: dict[NonEmptyString, StrictBool] = Field(default_factory=dict)
    offset: MinorUnits = 0
    limit: Annotated[int, Field(strict=True, ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE

    @model_validator(mode="after")
    def validate_price_currency(self) -> Self:
        """Never compare price amounts from different currencies as equivalent."""
        if self.max_amount_minor is not None and self.currency is None:
            raise ValueError("currency is required with max_amount_minor")
        return self


class CatalogSearchResponse(DomainModel):
    catalog_id: Literal["agentpay-synthetic-hotels-v1"] = "agentpay-synthetic-hotels-v1"
    synthetic: Literal[True] = True
    notice: Literal[SYNTHETIC_NOTICE] = SYNTHETIC_NOTICE
    offers: list[Offer]
    total: MinorUnits
    offset: MinorUnits
    limit: Annotated[int, Field(strict=True, ge=1, le=MAX_PAGE_SIZE)]


class HotelCatalogFixture(DomainModel):
    """Fail closed when the trusted fixture file loses its labels or identity."""

    catalog_id: Literal["agentpay-synthetic-hotels-v1"]
    synthetic: StrictBool
    notice: Literal[SYNTHETIC_NOTICE]
    offers: Annotated[list[Offer], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_fixture(self) -> Self:
        """Require unique offers and synthetic labels without inventing evidence."""
        if not self.synthetic:
            raise ValueError("hotel fixtures must be labeled synthetic")
        offer_ids = [offer.offer_id for offer in self.offers]
        if len(offer_ids) != len(set(offer_ids)):
            raise ValueError("duplicate offer_id in hotel fixtures")
        for offer in self.offers:
            if offer.source != SYNTHETIC_SOURCE or not offer.title.startswith("[Synthetic] "):
                raise ValueError("each hotel offer must be labeled synthetic")
            if not offer.evidence:
                raise ValueError("each hotel fixture needs supporting evidence fields")
        return self
