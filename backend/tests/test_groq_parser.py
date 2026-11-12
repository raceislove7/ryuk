"""Groq SDK transport, boundary validation and production dependency tests; no live calls."""

import asyncio
import json
from copy import deepcopy
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from test_intent_parser import CASES, GOLD, expected_with_sources

from app.api.checkout import get_checkout_actor
from app.main import app
from app.schemas.intent_parser import LLMIntentExtraction
from app.services.intent_parser import (
    GroqIntentParser,
    IntentClarificationRequired,
    IntentParserUnavailable,
    InvalidParserOutput,
    groq_extraction_schema,
)


@pytest.fixture(autouse=True)
def authenticate_mock_groq_tests():
    app.dependency_overrides[get_checkout_actor] = lambda: "groq-test"
    yield
    app.dependency_overrides.pop(get_checkout_actor, None)


def completion(payload: Any, *, finish: str = "stop", refusal: str | None = None) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(payload),
                    "refusal": refusal,
                },
            }
        ],
    }


async def parse_mock(query: str, response: dict) -> Any:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"] == {
            "name": "purchase_intent_extraction",
            "strict": True,
            "schema": groq_extraction_schema(query),
        }
        assert "tools" not in body
        assert body["messages"][1] == {"role": "user", "content": query}
        return httpx2.Response(200, json=response)

    async with AsyncOpenAI(
        api_key="test-only",
        base_url="https://api.groq.com/openai/v1",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    ) as client:
        return await GroqIntentParser(client, "test-model").parse(query)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_gold_cases(case: dict) -> None:
    if case["expected"] is not None:
        assert asyncio.run(
            parse_mock(case["query"], completion(case["extraction"]))
        ).model_dump() == expected_with_sources(case["query"], case["extraction"], case["expected"])
    else:
        with pytest.raises(IntentClarificationRequired):
            asyncio.run(parse_mock(case["query"], completion(case["extraction"])))


@pytest.mark.parametrize(
    "kind",
    ["extra", "source", "roles", "truncated", "refused", "json", "empty", "choices", "tools"],
)
def test_invalid_output_fails_closed(kind: str) -> None:
    payload = deepcopy(GOLD["extraction"])
    if kind == "extra":
        payload["capture"] = True
    if kind == "source":
        payload["budget"]["quote"] = "invented budget USD 1"
    if kind == "roles":
        payload["budget"], payload["approval_threshold"] = (
            payload["approval_threshold"],
            payload["budget"],
        )
    response = completion(payload)
    choice = response["choices"][0]
    if kind == "truncated":
        choice["finish_reason"] = "length"
    if kind == "refused":
        choice["message"]["refusal"] = "private refusal"
    if kind in {"json", "empty"}:
        choice["message"]["content"] = "{broken" if kind == "json" else None
    if kind == "choices":
        response["choices"] = []
    if kind == "tools":
        choice["message"]["tool_calls"] = [
            {"id": "x", "type": "function", "function": {"name": "pay", "arguments": "{}"}}
        ]
    with pytest.raises(InvalidParserOutput):
        asyncio.run(parse_mock(GOLD["query"], response))


@pytest.mark.parametrize("failure", [400, 401, 429, 500, "timeout"])
def test_errors_safe_without_retry(failure: int | str) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        if failure == "timeout":
            raise httpx2.ReadTimeout("private-detail", request=request)
        return httpx2.Response(failure, json={"error": {"message": "private-detail"}})

    async def run() -> None:
        async with AsyncOpenAI(
            api_key="test-only",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        ) as client:
            with pytest.raises(IntentParserUnavailable) as caught:
                await GroqIntentParser(client, "test-model").parse(GOLD["query"])
            assert "private-detail" not in str(caught.value)

    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize(
    "provider,missing",
    [("groq", "GROQ_API_KEY"), ("groq", "GROQ_MODEL"), ("unsupported-secret", None), ("", None)],
)
def test_unavailable_configuration(
    monkeypatch: pytest.MonkeyPatch, provider: str, missing: str | None
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    if missing:
        monkeypatch.setenv(missing, "   ")
    with TestClient(app) as client:
        response = client.post("/v1/agent/parse", json={"query": GOLD["query"]})
        assert response.status_code == 503
        assert "test-only" not in response.text and "unsupported-secret" not in response.text
        assert client.get("/health").status_code == 200


def test_groq_production_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        assert request.url.host == "api.groq.com"
        assert request.headers["authorization"] == "Bearer test-only"
        assert "test-only" not in request.content.decode()
        return httpx2.Response(200, json=completion(GOLD["extraction"]))

    def factory(**kwargs: Any) -> AsyncOpenAI:
        assert kwargs["max_retries"] == 0 and kwargs["timeout"] == 20.0
        return AsyncOpenAI(
            **kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        )

    monkeypatch.setattr("app.api.agent.AsyncOpenAI", factory)
    with TestClient(app) as client:
        response = client.post("/v1/agent/parse", json={"query": GOLD["query"]})
        assert response.status_code == 200
        assert response.json() == expected_with_sources(
            GOLD["query"], GOLD["extraction"], GOLD["expected"]
        )
        assert "test-only" not in response.text
    assert len(calls) == 1


@pytest.mark.parametrize("query", ["", "   ", "x" * 4001])
def test_invalid_query_rejected_before_http(query: str) -> None:
    with pytest.raises(IntentClarificationRequired):
        asyncio.run(parse_mock(query, completion(GOLD["extraction"])))


def test_groq_union_is_equivalent_and_does_not_mutate_shared_schema():
    original = LLMIntentExtraction.model_json_schema()

    def types(schema):
        return {
            branch["type"]
            for branch in schema["$defs"]["ExtractedAttribute"]["properties"]["value"]["anyOf"]
        }

    assert types(original) == {"boolean", "integer", "number", "string"}
    assert types(groq_extraction_schema()) == {"boolean", "number", "string"}
    assert types(LLMIntentExtraction.model_json_schema()) == types(original)


@pytest.mark.parametrize(
    "status,category",
    [
        (400, "REQUEST"),
        (401, "AUTH"),
        (403, "ACCESS"),
        (404, "MODEL"),
        (429, "LIMIT"),
        (500, "UNAVAILABLE"),
    ],
)
def test_provider_failure_categories_are_safe_and_actionable(monkeypatch, status, category):
    from app.api.agent import get_intent_parser
    from app.services.intent_parser import IntentProviderRejected

    class Parser:
        async def parse(self, query):
            raise IntentProviderRejected(status)

    app.dependency_overrides[get_intent_parser] = lambda: Parser()
    try:
        with TestClient(app) as client:
            response = client.post("/v1/agent/parse", json={"query": GOLD["query"]})
        assert response.status_code == 503
        assert response.json()["detail"]["message"] == IntentProviderRejected.MESSAGES[category]
        assert "private-provider-detail" not in response.text
    finally:
        app.dependency_overrides.pop(get_intent_parser, None)


def test_groq_amount_grammar_excludes_currency_and_preserves_numeric_token():
    import re

    pattern = groq_extraction_schema()["$defs"]["MoneyMention"]["properties"]["amount_text"][
        "pattern"
    ]
    assert re.fullmatch(pattern, "1,500")
    assert re.fullmatch(pattern, "1300.50")
    for invalid in ["USD 1,500", "$1500", "1,500 dollars", "1 500", "1,50"]:
        assert not re.fullmatch(pattern, invalid)
    assert (
        LLMIntentExtraction.model_json_schema()["$defs"]["MoneyMention"]["properties"][
            "amount_text"
        ]["pattern"]
        == r"\S"
    )


def test_exact_ui_example_keeps_budget_and_mandatory_roles():
    query = (
        "Find a hotel in Switzerland for 5 nights under USD 1,500.\n"
        "Gym, mountain view and free cancellation are required.\n"
        "Private pool preferred. Ask me above USD 1,300."
    )
    extraction = deepcopy(GOLD["extraction"])
    extraction["budget"] = {"amount_text": "1,500", "quote": "under USD 1,500"}
    extraction["approval_threshold"] = {"amount_text": "1,300", "quote": "Ask me above USD 1,300"}
    for attribute in extraction["required_attributes"]:
        attribute["quote"] = {
            "country": "Switzerland",
            "nights": "5 nights",
            "gym": "Gym, mountain view and free cancellation are required.",
            "mountain_view": "Gym, mountain view and free cancellation are required.",
            "free_cancellation": "Gym, mountain view and free cancellation are required.",
        }[attribute["name"]]
    extraction["preferred_attributes"][0]["quote"] = "Private pool preferred."
    result = asyncio.run(parse_mock(query, completion(extraction)))
    assert result.budget_max_minor == 150000 and result.approval_threshold_minor == 130000
    assert all(
        result.required_attributes[k] is True for k in ["gym", "mountain_view", "free_cancellation"]
    )


def test_ui_money_evidence_is_bound_to_role_bearing_source_spans():
    query = "5 nights under USD 1,500. Ask me above USD 1,300."
    schema = groq_extraction_schema(query)
    for field, quote, amount in [
        ("budget", "under USD 1,500", "1,500"),
        ("approval_threshold", "Ask me above USD 1,300", "1,300"),
    ]:
        money = schema["properties"][field]["anyOf"][0]["properties"]
        assert money["quote"]["enum"] == [quote]
        assert money["amount_text"]["enum"] == [amount]
