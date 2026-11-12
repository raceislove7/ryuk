"""Search the trusted synthetic hotel catalog with explicit filters."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.schemas.catalog import CatalogSearchRequest, CatalogSearchResponse
from app.services.catalog import CatalogService

router = APIRouter(prefix="/v1/offers", tags=["offers"])


def get_catalog(request: Request) -> CatalogService:
    """Use the validated catalog loaded at application startup."""
    return request.app.state.catalog


@router.post("/search", response_model=CatalogSearchResponse)
def search_offers(
    filters: CatalogSearchRequest,
    catalog: Annotated[CatalogService, Depends(get_catalog)],
) -> CatalogSearchResponse:
    """Return labeled synthetic offers; results are not verified or payment-authorized."""
    return catalog.search(filters)
