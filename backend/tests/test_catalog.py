"""Fixture validation, isolated reads, explicit search semantics, and HTTP contracts."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas import Offer
from app.schemas.catalog import SYNTHETIC_NOTICE, SYNTHETIC_SOURCE, CatalogSearchRequest
from app.services.catalog import DEFAULT_FIXTURE_PATH, CatalogLoadError, CatalogService


@pytest.fixture
def catalog() -> CatalogService:
    return CatalogService()


@pytest.fixture
def fixture_data() -> dict[str, Any]:
    return json.loads(DEFAULT_FIXTURE_PATH.read_text())


def write_fixture(tmp_path: Path, data: Any) -> Path:
    """Write only temporary test data, never modify the committed fixture."""
    path = tmp_path / "hotels.json"
    path.write_text(json.dumps(data))
    return path


def ids(result: Any) -> list[str]:
    return [offer.offer_id for offer in result.offers]


def test_committed_fixture_has_labeled_valid_distinct_offers(fixture_data: dict) -> None:
    assert fixture_data["synthetic"] is True
    assert fixture_data["notice"] == SYNTHETIC_NOTICE
    offers = [Offer.model_validate(row) for row in fixture_data["offers"]]
    assert len(offers) >= 6
    assert len({offer.offer_id for offer in offers}) == len(offers)
    for offer in offers:
        assert offer.title.startswith("[Synthetic] ")
        assert offer.source == SYNTHETIC_SOURCE
        assert offer.merchant_id.startswith("synthetic-hotel-merchant-")
        assert offer.evidence
        assert type(offer.amount_minor) is int
        for excerpts in offer.evidence.values():
            assert excerpts and all("Synthetic" in excerpt for excerpt in excerpts)


def test_demo_prices_and_missing_evidence_are_preserved(catalog: CatalogService) -> None:
    offers = [catalog.get_offer(f"synthetic-hotel-{i:03d}") for i in range(1, 6)]
    assert [offer.amount_minor for offer in offers[:3]] == [118_000, 139_000, 162_000]
    assert offers[3].attributes["gym"] is False
    assert "free_cancellation" not in offers[4].attributes
    assert "free_cancellation" not in offers[4].evidence


def test_no_filters_keeps_overbudget_and_unknown_candidates(catalog: CatalogService) -> None:
    result = catalog.search(CatalogSearchRequest())
    assert result.total == 8
    assert result.synthetic is True and result.notice == SYNTHETIC_NOTICE
    assert {"synthetic-hotel-003", "synthetic-hotel-005"} <= set(ids(result))
    assert not {"status", "policy", "verified"} & result.model_dump().keys()


@pytest.mark.parametrize(
    "filters,expected",
    [
        ({"query": "sWiTzErLaNd zErMaTt"}, ["002"]),
        ({"query": "  Alpine    Switzerland "}, ["001", "008"]),
        ({"country": "frANCE"}, ["007"]),
        ({"currency": "EUR"}, ["006", "007"]),
        ({"nights": 2}, ["008"]),
        ({"max_amount_minor": 51_000, "currency": "USD"}, ["008"]),
        ({"max_amount_minor": 0, "currency": "USD"}, []),
        ({"attributes": {"private_pool": True}}, ["002", "003"]),
        ({"attributes": {"gym": False}}, ["004"]),
        ({"attributes": {"free_cancellation": False}}, ["006"]),
        ({"attributes": {"free_cancellation": True}}, ["001", "002", "003", "004", "007", "008"]),
        ({"attributes": {"gym": True, "private_pool": True}}, ["002", "003"]),
        ({"attributes": {"does_not_exist": True}}, []),
        ({"attributes": {"rooms": True}}, []),  # Integer 1 is not boolean True.
        (
            {
                "country": "Switzerland",
                "currency": "USD",
                "nights": 5,
                "max_amount_minor": 130_000,
                "attributes": {"gym": True},
            },
            ["001", "005"],
        ),
        ({"query": "a hotel that does not exist"}, []),
    ],
)
def test_explicit_filters_use_and(
    catalog: CatalogService, filters: dict, expected: list[str]
) -> None:
    result = catalog.search(CatalogSearchRequest(**filters))
    assert ids(result) == [f"synthetic-hotel-{number}" for number in expected]
    assert result.total == len(expected)


def test_pagination_has_stable_order_and_total_after_filtering(catalog: CatalogService) -> None:
    first = catalog.search(CatalogSearchRequest(currency="USD", limit=2))
    second = catalog.search(CatalogSearchRequest(currency="USD", offset=2, limit=2))
    assert ids(first) == ["synthetic-hotel-001", "synthetic-hotel-002"]
    assert ids(second) == ["synthetic-hotel-003", "synthetic-hotel-004"]
    assert first.total == second.total == 6
    assert (second.offset, second.limit) == (2, 2)
    beyond = catalog.search(CatalogSearchRequest(offset=100))
    assert beyond.offers == [] and beyond.total == 8


def test_order_is_by_offer_id_not_file_order(tmp_path: Path, fixture_data: dict) -> None:
    fixture_data["offers"].reverse()
    service = CatalogService(write_fixture(tmp_path, fixture_data))
    assert ids(service.search(CatalogSearchRequest())) == [
        f"synthetic-hotel-{number:03d}" for number in range(1, 9)
    ]


def test_reads_cannot_mutate_canonical_offers(catalog: CatalogService) -> None:
    offer = catalog.get_offer("synthetic-hotel-001")
    original = offer.model_dump()
    offer.amount_minor = 1
    offer.merchant_id = "attacker-merchant"
    offer.attributes["gym"] = False
    offer.evidence["gym"].clear()
    assert catalog.get_offer("synthetic-hotel-001").model_dump() == original
    result = catalog.search(CatalogSearchRequest())
    result.offers[0].attributes["gym"] = False
    result.offers[0].evidence.clear()
    assert catalog.get_offer("synthetic-hotel-001").model_dump() == original
    assert catalog.get_offer("unknown-offer") is None


def test_default_path_ignores_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    assert CatalogService().search(CatalogSearchRequest()).total == 8


@pytest.mark.parametrize(
    "changes",
    [
        {"synthetic": False},
        {"synthetic": 1},
        {"notice": "real inventory"},
        {"catalog_id": "untrusted"},
        {"offers": []},
        {"unexpected": "field"},
    ],
)
def test_invalid_metadata_fails_closed(tmp_path: Path, fixture_data: dict, changes: dict) -> None:
    fixture_data.update(changes)
    with pytest.raises(CatalogLoadError, match="unavailable or invalid"):
        CatalogService(write_fixture(tmp_path, fixture_data))


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_minor": 1180.0},
        {"amount_minor": "118000"},
        {"amount_minor": True},
        {"amount_minor": -1},
        {"source": "live merchant"},
        {"title": "Real hotel"},
        {"merchant_id": "   "},
        {"evidence": {}},
        {"capture_now": True},
    ],
)
def test_one_invalid_offer_rejects_all(tmp_path: Path, fixture_data: dict, changes: dict) -> None:
    fixture_data["offers"][-1].update(changes)
    with pytest.raises(CatalogLoadError):
        CatalogService(write_fixture(tmp_path, fixture_data))


def test_duplicate_ids_cannot_overwrite_canonical_offer(tmp_path: Path, fixture_data: dict) -> None:
    duplicate = deepcopy(fixture_data["offers"][0])
    duplicate["merchant_id"] = "substituted-merchant"
    fixture_data["offers"].append(duplicate)
    with pytest.raises(CatalogLoadError):
        CatalogService(write_fixture(tmp_path, fixture_data))


@pytest.mark.parametrize("contents", ["not JSON", "null", "[]", "{}", '{"offers":'])
def test_malformed_catalog_is_not_silently_empty(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "hotels.json"
    path.write_text(contents)
    with pytest.raises(CatalogLoadError):
        CatalogService(path)


def test_missing_file_and_invalid_encoding_fail_without_raw_data(tmp_path: Path) -> None:
    with pytest.raises(CatalogLoadError):
        CatalogService(tmp_path / "missing.json")
    path = tmp_path / "invalid.json"
    path.write_bytes(b"\xffprivate-input\xfe")
    with pytest.raises(CatalogLoadError) as caught:
        CatalogService(path)
    assert "private-input" not in str(caught.value)


@pytest.mark.parametrize(
    "filters",
    [
        {"max_amount_minor": True},
        {"max_amount_minor": "130000"},
        {"max_amount_minor": 1.5},
        {"max_amount_minor": -1},
        {"max_amount_minor": 130_000},
        {"limit": 0},
        {"limit": 101},
        {"limit": True},
        {"limit": "2"},
        {"offset": -1},
        {"offset": True},
        {"nights": 0},
        {"nights": True},
        {"nights": "5"},
        {"currency": "usd"},
        {"query": "   "},
        {"query": "x" * 201},
        {"country": ""},
        {"attributes": {"gym": 1}},
        {"attributes": {"gym": "true"}},
        {"attributes": {"gym": None}},
        {"attributes": {" ": True}},
        {"fixture_path": "/etc/passwd"},
        {"bypass_policy": True},
    ],
)
def test_untrusted_filters_are_rejected(filters: dict) -> None:
    with pytest.raises(ValidationError):
        CatalogSearchRequest(**filters)


def test_search_api_returns_synthetic_offers_with_filters() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/offers/search",
            json={
                "country": "Switzerland",
                "nights": 5,
                "currency": "USD",
                "max_amount_minor": 130_000,
                "attributes": {"gym": True},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["synthetic"] is True and body["notice"] == SYNTHETIC_NOTICE
        assert body["catalog_id"] == "agentpay-synthetic-hotels-v1"
        assert body["total"] == 2
        assert [offer["offer_id"] for offer in body["offers"]] == [
            "synthetic-hotel-001",
            "synthetic-hotel-005",
        ]
        assert all(
            Offer.model_validate(offer).source == SYNTHETIC_SOURCE for offer in body["offers"]
        )
        assert client.get("/health").json() == {"status": "ok"}
        assert "/v1/offers/search" in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize(
    "body",
    [
        {"max_amount_minor": "130000"},
        {"limit": 0},
        {"fixture_path": "../../etc/passwd"},
        [],
    ],
)
def test_api_rejects_invalid_json_shape_and_coercion(body: Any) -> None:
    with TestClient(app) as client:
        assert client.post("/v1/offers/search", json=body).status_code == 422


def test_empty_api_results_still_identify_synthetic_data() -> None:
    with TestClient(app) as client:
        body = client.post("/v1/offers/search", json={"country": "Atlantis"}).json()
    assert body["total"] == 0 and body["offers"] == []
    assert body["synthetic"] is True and "Synthetic" in body["notice"]


def test_app_refuses_startup_when_catalog_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_catalog() -> None:
        raise CatalogLoadError("Synthetic hotel catalog is unavailable or invalid")

    monkeypatch.setattr("app.main.CatalogService", broken_catalog)
    with pytest.raises(CatalogLoadError), TestClient(app):
        pass
