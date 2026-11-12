"""Read-only synthetic catalog; no network search, verification, or policy."""

from pathlib import Path

from pydantic import ValidationError

from app.schemas import Offer
from app.schemas.catalog import CatalogSearchRequest, CatalogSearchResponse, HotelCatalogFixture

# Preserve the repository layout in the image: /app/backend and /app/fixtures.
DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "hotels.json"


class CatalogLoadError(RuntimeError):
    """Trusted catalog configuration is missing or invalid; do not return partial data."""


class CatalogService:
    """Load once, validate all records, and return isolated copies to callers."""

    def __init__(self, fixture_path: Path = DEFAULT_FIXTURE_PATH) -> None:
        try:
            fixture = HotelCatalogFixture.model_validate_json(fixture_path.read_text())
        except (OSError, UnicodeError, ValidationError):
            # Do not dump file contents or Pydantic input values into operational errors.
            raise CatalogLoadError("Synthetic hotel catalog is unavailable or invalid") from None
        self._offers = {
            offer.offer_id: offer.model_copy(deep=True)
            for offer in sorted(fixture.offers, key=lambda offer: offer.offer_id)
        }

    def get_offer(self, offer_id: str) -> Offer | None:
        """Look up canonical catalog data by ID without exposing internal mutable state."""
        offer = self._offers.get(offer_id)
        return offer.model_copy(deep=True) if offer is not None else None

    def search(self, filters: CatalogSearchRequest) -> CatalogSearchResponse:
        """Filter and paginate in stable offer-ID order; do not certify purchase safety."""
        matches = [offer for offer in self._offers.values() if self._matches(offer, filters)]
        page = matches[filters.offset : filters.offset + filters.limit]
        return CatalogSearchResponse(
            offers=[offer.model_copy(deep=True) for offer in page],
            total=len(matches),
            offset=filters.offset,
            limit=filters.limit,
        )

    @staticmethod
    def _matches(offer: Offer, filters: CatalogSearchRequest) -> bool:
        if filters.currency is not None and offer.currency != filters.currency:
            return False
        if filters.max_amount_minor is not None and offer.amount_minor > filters.max_amount_minor:
            return False
        if filters.country is not None:
            country = offer.attributes.get("country")
            if not isinstance(country, str) or country.casefold() != filters.country.casefold():
                return False
        if filters.nights is not None:
            nights = offer.attributes.get("nights")
            if type(nights) is not int or nights != filters.nights:
                return False
        if any(offer.attributes.get(key) is not value for key, value in filters.attributes.items()):
            return False
        if filters.query is not None:
            text = " ".join(
                str(part)
                for part in (
                    offer.title,
                    offer.attributes.get("city", ""),
                    offer.attributes.get("country", ""),
                )
            ).casefold()
            if not all(token in text for token in filters.query.casefold().split()):
                return False
        return True
