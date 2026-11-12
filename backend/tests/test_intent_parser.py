"""Same 15 gold cases through fake and real-SDK mocked provider paths; no paid calls."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from app.api.agent import get_intent_parser
from app.api.checkout import get_checkout_actor
from app.main import app
from app.schemas import PurchaseIntent
from app.services.intent_parser import (
    FakeIntentParser,
    IntentClarificationRequired,
    IntentParserUnavailable,
    InvalidParserOutput,
    OpenAIIntentParser,
)


@pytest.fixture(autouse=True)
def authenticated_parser_tests(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    app.dependency_overrides[get_checkout_actor] = lambda: "parser-test"
    yield
    app.dependency_overrides.pop(get_checkout_actor, None)


CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures" / "intent_prompts.json").read_text()
)["cases"]
GOLD = CASES[0]


def expected_with_sources(query: str, extraction: dict, expected: dict) -> dict:
    sources = [
        {
            "role": role,
            "name": a["name"],
            "quote": a["quote"],
            "start": query.index(a["quote"]),
            "end": query.index(a["quote"]) + len(a["quote"]),
        }
        for role in ("required", "preferred")
        for a in extraction[f"{role}_attributes"]
    ]
    return expected | ({"requirement_sources": sources} if sources else {})


@pytest.fixture
def parser_api():
    """Explicit trusted actor only in API contract tests, not production authentication."""
    app.dependency_overrides[get_checkout_actor] = lambda: "synthetic-parser-user"
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_checkout_actor, None)


def provider_response(payload: Any, *, status: str = "completed", refusal: bool = False) -> dict:
    """Build a Responses API message; the actual SDK performs structured parsing."""
    content = (
        [{"type": "refusal", "refusal": "A provider refusal"}]
        if refusal
        else [{"type": "output_text", "text": json.dumps(payload), "annotations": []}]
    )
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "status": status,
        "model": "test-structured-model",
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": content,
            }
        ],
    }


async def sdk_parse(
    query: str,
    payload: Any,
    *,
    status: str = "completed",
    refusal: bool = False,
    captured: list | None = None,
) -> PurchaseIntent:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/responses"
        if captured is not None:
            captured.append(json.loads(request.content))
        return httpx2.Response(200, json=provider_response(payload, status=status, refusal=refusal))

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as http_client:
        async with AsyncOpenAI(
            api_key="test-only-placeholder", http_client=http_client, max_retries=0
        ) as client:
            return await OpenAIIntentParser(client, "test-structured-model").parse(query)


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
@pytest.mark.parametrize("implementation", ["fake", "sdk"])
def test_fifteen_gold_prompts_match_expected_contract(case: dict, implementation: str) -> None:
    parser = FakeIntentParser({case["query"]: case["extraction"]})
    operation = (
        parser.parse(case["query"])
        if implementation == "fake"
        else sdk_parse(case["query"], case["extraction"])
    )
    if case["expected_error"]:
        with pytest.raises(IntentClarificationRequired):
            asyncio.run(operation)
    else:
        intent = asyncio.run(operation)
        expected = PurchaseIntent.model_validate(case["expected"]).model_dump()
        actual = intent.model_dump()
        sources = actual.pop("requirement_sources", [])
        assert actual == expected
        assert len(sources) == len(intent.required_attributes) + len(intent.preferred_attributes)
        assert all(intent.query[s["start"] : s["end"]] == s["quote"] for s in sources)
        assert type(intent.budget_max_minor) is int
        assert intent.query == case["query"]


def test_provider_request_uses_strict_closed_schema_and_no_tools() -> None:
    captured = []
    asyncio.run(sdk_parse(GOLD["query"], GOLD["extraction"], captured=captured))
    body = captured[0]
    assert body["store"] is False and body["tools"] == []
    assert body["input"][1] == {"role": "user", "content": GOLD["query"]}
    assert body["input"][0]["role"] == "system"
    format = body["text"]["format"]
    assert format["type"] == "json_schema" and format["strict"] is True

    def check_closed(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                check_closed(value)
        elif isinstance(node, list):
            for value in node:
                check_closed(value)

    check_closed(format["schema"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("budget", None),
        ("currency", None),
    ],
)
def test_missing_values_never_become_unlimited_or_default_currency(field: str, value: Any) -> None:
    payload = deepcopy(GOLD["extraction"])
    payload[field] = value
    with pytest.raises(IntentClarificationRequired):
        asyncio.run(FakeIntentParser({GOLD["query"]: payload}).parse(GOLD["query"]))


@pytest.mark.parametrize(
    "field,value",
    [
        ("capture_now", True),
        ("intent_review_required", False),
        ("query", "rewritten by provider"),
        ("quantity", True),
        ("quantity", 0),
        ("quantity", "2"),
        ("quantity", 1.5),
        ("currency", "CAD"),
        ("category", "   "),
        ("status", "APPROVED"),
    ],
)
def test_invalid_or_authority_bearing_fields_are_rejected(field: str, value: Any) -> None:
    payload = deepcopy(GOLD["extraction"])
    payload[field] = value
    with pytest.raises(InvalidParserOutput):
        asyncio.run(sdk_parse(GOLD["query"], payload))


@pytest.mark.parametrize("amount", [1500, 1500.0, True, "1e9", "Infinity", "NaN", "-10", "1,50"])
def test_invalid_money_formats_are_not_coerced(amount: Any) -> None:
    payload = deepcopy(GOLD["extraction"])
    payload["budget"]["amount_text"] = amount
    with pytest.raises((InvalidParserOutput, IntentClarificationRequired)):
        asyncio.run(sdk_parse(GOLD["query"], payload))


def test_hallucinated_amount_with_real_quote_is_rejected() -> None:
    payload = deepcopy(GOLD["extraction"])
    payload["budget"]["amount_text"] = "999999999"
    with pytest.raises(InvalidParserOutput):
        asyncio.run(sdk_parse(GOLD["query"], payload))


def test_hallucinated_quote_is_rejected() -> None:
    payload = deepcopy(GOLD["extraction"])
    payload["budget"] = {"amount_text": "999999999", "quote": "Budget USD 999999999"}
    with pytest.raises(InvalidParserOutput):
        asyncio.run(sdk_parse(GOLD["query"], payload))


def test_unlimited_request_cannot_receive_a_fabricated_finite_budget() -> None:
    query = "Find a hotel with unlimited budget in USD."
    with pytest.raises(InvalidParserOutput):
        asyncio.run(sdk_parse(query, GOLD["extraction"]))


@pytest.mark.parametrize("preferred", [True, False])
def test_explicit_mandatory_preferred_roles_cannot_be_swapped(preferred: bool) -> None:
    payload = deepcopy(GOLD["extraction"])
    if preferred:
        payload["preferred_attributes"].append(payload["required_attributes"].pop(2))
    else:
        payload["required_attributes"].append(payload["preferred_attributes"].pop())
    with pytest.raises(InvalidParserOutput, match="wording"):
        asyncio.run(sdk_parse(GOLD["query"], payload))


@pytest.mark.parametrize("duplicate_across_roles", [True, False])
def test_duplicate_attributes_cannot_overwrite_a_requirement(duplicate_across_roles: bool) -> None:
    payload = deepcopy(GOLD["extraction"])
    item = deepcopy(payload["required_attributes"][0])  # Country quote has no role cue.
    payload["preferred_attributes" if duplicate_across_roles else "required_attributes"].append(
        item
    )
    with pytest.raises(InvalidParserOutput):
        asyncio.run(sdk_parse(GOLD["query"], payload))


def test_no_threshold_is_conservative_not_unlimited_authorization() -> None:
    case = next(case for case in CASES if case["id"] == "no-threshold-defaults-to-review")
    intent = asyncio.run(sdk_parse(case["query"], case["extraction"]))
    assert intent.approval_threshold_minor == 0
    assert intent.budget_max_minor == 50_000


def test_threshold_above_budget_requires_clarification() -> None:
    query = GOLD["query"].replace("1,300", "1,600")
    payload = deepcopy(GOLD["extraction"])
    payload["approval_threshold"] = {"amount_text": "1,600", "quote": "Ask me above USD 1,600"}
    with pytest.raises(IntentClarificationRequired, match="cannot exceed"):
        asyncio.run(sdk_parse(query, payload))


@pytest.mark.parametrize(
    "query,quote,amount",
    [
        ("A hotel. Budget USD -100.", "Budget USD -100", "100"),
        ("A hotel. Budget USD 100 per night.", "Budget USD 100 per night", "100"),
        ("A hotel. Budget unlimited USD 100.", "Budget unlimited USD 100", "100"),
    ],
)
def test_unsafe_budget_interpretations_need_clarification(
    query: str, quote: str, amount: str
) -> None:
    payload = deepcopy(GOLD["extraction"])
    payload.update(
        budget={"amount_text": amount, "quote": quote},
        approval_threshold=None,
        required_attributes=[],
        preferred_attributes=[],
    )
    with pytest.raises(IntentClarificationRequired):
        asyncio.run(sdk_parse(query, payload))


@pytest.mark.parametrize(
    "query,currency",
    [
        ("A hotel. Budget $1500.", "USD"),
        ("A hotel. Budget USD 1500 or EUR 1400.", "USD"),
    ],
)
def test_ambiguous_currency_cannot_be_guessed(query: str, currency: str) -> None:
    payload = deepcopy(GOLD["extraction"])
    payload["currency"] = currency
    with pytest.raises(IntentClarificationRequired):
        asyncio.run(sdk_parse(query, payload))


@pytest.mark.parametrize("status,refusal", [("incomplete", False), ("completed", True)])
def test_partial_or_refused_provider_output_is_never_returned(status: str, refusal: bool) -> None:
    with pytest.raises(InvalidParserOutput):
        asyncio.run(sdk_parse(GOLD["query"], GOLD["extraction"], status=status, refusal=refusal))


def test_provider_errors_are_safe_and_not_retried() -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        return httpx2.Response(429, json={"error": {"message": "private-provider-detail"}})

    async def scenario() -> None:
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as http_client:
            async with AsyncOpenAI(
                api_key="test-only-placeholder", http_client=http_client, max_retries=0
            ) as client:
                with pytest.raises(IntentParserUnavailable) as caught:
                    await OpenAIIntentParser(client, "test-model").parse(GOLD["query"])
                assert "private-provider-detail" not in str(caught.value)

    asyncio.run(scenario())
    assert len(calls) == 1


def test_transport_timeout_is_safe() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("private-network-detail", request=request)

    async def scenario() -> None:
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as http_client:
            async with AsyncOpenAI(
                api_key="test-only-placeholder", http_client=http_client, max_retries=0
            ) as client:
                with pytest.raises(IntentParserUnavailable) as caught:
                    await OpenAIIntentParser(client, "test-model").parse(GOLD["query"])
                assert "private-network-detail" not in str(caught.value)

    asyncio.run(scenario())


def test_fake_is_deterministic_isolated_and_has_no_unknown_prompt_fallback() -> None:
    mapping = {GOLD["query"]: deepcopy(GOLD["extraction"])}
    fake = FakeIntentParser(mapping)
    mapping[GOLD["query"]]["budget"] = None
    first, second = asyncio.run(fake.parse(GOLD["query"])), asyncio.run(fake.parse(GOLD["query"]))
    assert first == second
    first.required_attributes.clear()
    assert asyncio.run(fake.parse(GOLD["query"])) == second
    with pytest.raises(IntentClarificationRequired):
        asyncio.run(fake.parse("not a registered prompt"))


@pytest.mark.parametrize("query", ["", "   ", "x" * 4001, 123])
def test_bad_requests_fail_before_provider_call(query: Any) -> None:
    captured = []
    with pytest.raises(IntentClarificationRequired):
        asyncio.run(sdk_parse(query, GOLD["extraction"], captured=captured))
    assert captured == []


def test_parse_api_with_injected_fake_preserves_roles(parser_api) -> None:
    fake = FakeIntentParser({case["query"]: case["extraction"] for case in CASES})
    app.dependency_overrides[get_intent_parser] = lambda: fake
    try:
        with TestClient(app) as client:
            response = client.post("/v1/agent/parse", json={"query": GOLD["query"]})
            assert response.status_code == 200
            assert response.json() == expected_with_sources(
                GOLD["query"], GOLD["extraction"], GOLD["expected"]
            )
            case = next(case for case in CASES if case["id"] == "missing-budget")
            response = client.post("/v1/agent/parse", json={"query": case["query"]})
            assert response.status_code == 422
            assert response.json()["detail"]["code"] == "INTENT_CLARIFICATION_REQUIRED"
            assert (
                client.post("/v1/agent/parse", json={"query": " ", "pay": True}).status_code == 422
            )
    finally:
        app.dependency_overrides.pop(get_intent_parser, None)


def test_unconfigured_parser_is_unavailable_but_other_routes_work(
    monkeypatch: pytest.MonkeyPatch,
    parser_api,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with TestClient(app) as client:
        response = client.post("/v1/agent/parse", json={"query": GOLD["query"]})
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "PARSER_UNAVAILABLE"
        assert client.get("/health").status_code == 200
        assert client.post("/v1/offers/search", json={}).status_code == 200


@pytest.mark.parametrize(
    "error,expected_code",
    [
        (InvalidParserOutput("private-model-output"), 502),
        (IntentParserUnavailable("private-provider-detail"), 503),
    ],
)
def test_api_sanitizes_model_and_provider_errors(
    error: Exception,
    expected_code: int,
    parser_api,
) -> None:
    class BrokenParser:
        async def parse(self, query: str) -> PurchaseIntent:
            raise error

    app.dependency_overrides[get_intent_parser] = lambda: BrokenParser()
    try:
        with TestClient(app) as client:
            response = client.post("/v1/agent/parse", json={"query": GOLD["query"]})
            assert response.status_code == expected_code
            assert "private-" not in response.text
    finally:
        app.dependency_overrides.pop(get_intent_parser, None)


def test_money_roles_cannot_be_swapped() -> None:
    payload = deepcopy(GOLD["extraction"])
    payload["budget"], payload["approval_threshold"] = (
        payload["approval_threshold"],
        payload["budget"],
    )
    with pytest.raises(InvalidParserOutput, match="role"):
        asyncio.run(sdk_parse(GOLD["query"], payload))


def test_money_quote_can_include_sentence_punctuation() -> None:
    payload = deepcopy(GOLD["extraction"])
    payload["budget"]["quote"] += "."
    assert asyncio.run(sdk_parse(GOLD["query"], payload)).budget_max_minor == 150_000


@pytest.mark.parametrize("implementation", ["fake", "sdk"])
def test_attribute_quote_punctuation_does_not_include_the_next_role_clause(implementation):
    case = next(case for case in CASES if case["id"] == "separate-preferences")
    payload = deepcopy(case["extraction"])
    gym = next(a for a in payload["required_attributes"] if a["name"] == "gym")
    gym["quote"] += "."
    operation = (
        FakeIntentParser({case["query"]: payload}).parse(case["query"])
        if implementation == "fake"
        else sdk_parse(case["query"], payload)
    )
    assert asyncio.run(operation).model_dump() == expected_with_sources(
        case["query"], payload, case["expected"]
    )


def test_hotel_quantity_cannot_be_confused_with_nights() -> None:
    payload = deepcopy(GOLD["extraction"])
    payload["quantity"] = 5
    with pytest.raises(InvalidParserOutput, match="rooms requirement"):
        asyncio.run(sdk_parse(GOLD["query"], payload))


def test_hotel_room_count_and_quantity_must_agree() -> None:
    case = next(case for case in CASES if case["id"] == "room-quantity")
    payload = deepcopy(case["extraction"])
    payload["quantity"] = 2
    with pytest.raises(InvalidParserOutput, match="contradicts"):
        asyncio.run(sdk_parse(case["query"], payload))
    payload["quantity"] = None
    assert asyncio.run(sdk_parse(case["query"], payload)).quantity == 3


def test_production_dependency_calls_sdk_with_backend_only_configuration(
    monkeypatch: pytest.MonkeyPatch,
    parser_api,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("OPENAI_MODEL", "test-structured-model")
    captured = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        captured.append(body)
        assert "test-only-placeholder" not in request.content.decode()
        return httpx2.Response(200, json=provider_response(GOLD["extraction"]))

    def client_factory(**kwargs: Any) -> AsyncOpenAI:
        assert kwargs["max_retries"] == 0 and kwargs["timeout"] == 20.0
        return AsyncOpenAI(
            **kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        )

    monkeypatch.setattr("app.api.agent.AsyncOpenAI", client_factory)
    with TestClient(app) as client:
        response = client.post("/v1/agent/parse", json={"query": GOLD["query"]})
        assert response.status_code == 200
        assert response.json() == expected_with_sources(
            GOLD["query"], GOLD["extraction"], GOLD["expected"]
        )
        assert "test-only-placeholder" not in response.text
    assert len(captured) == 1 and captured[0]["model"] == "test-structured-model"


def test_category_normalization_cannot_bypass_hotel_quantity_checks() -> None:
    payload = deepcopy(GOLD["extraction"])
    payload["category"] = " Hotel "
    assert asyncio.run(sdk_parse(GOLD["query"], payload)).category == "hotel"
    payload["quantity"] = 5
    with pytest.raises(InvalidParserOutput, match="rooms requirement"):
        asyncio.run(sdk_parse(GOLD["query"], payload))
