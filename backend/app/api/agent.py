"""Intent extraction endpoint; no policy, approval, or payment side effects."""

import os
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from openai import AsyncOpenAI

from app.api.checkout import Actor
from app.schemas import PurchaseIntent
from app.schemas.intent_parser import ParseIntentRequest
from app.services.intent_parser import (
    GroqIntentParser,
    IntentClarificationRequired,
    IntentParser,
    IntentParserUnavailable,
    IntentProviderRejected,
    InvalidParserOutput,
    OpenAIIntentParser,
)
from app.services.session import DemoSessions

PROVIDER_TIMEOUT_SECONDS = 20.0
router = APIRouter(prefix="/v1/agent", tags=["intent"])


async def get_intent_parser() -> AsyncIterator[IntentParser]:
    """Create the real parser lazily so health/catalog startup needs no LLM credentials."""
    provider = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
    if provider not in {"openai", "groq"}:
        raise HTTPException(
            status_code=503,
            detail={"code": "PARSER_UNAVAILABLE", "message": "Unsupported LLM provider."},
        )
    prefix = "GROQ" if provider == "groq" else "OPENAI"
    api_key = os.environ.get(f"{prefix}_API_KEY", "").strip()
    model = os.environ.get(f"{prefix}_MODEL", "").strip()
    if not api_key or not model:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PARSER_UNAVAILABLE",
                "message": (
                    f"Configure backend {prefix}_API_KEY and {prefix}_MODEL to enable parsing."
                ),
            },
        )
    # Fixed destinations prevent configuration from redirecting provider credentials.
    base_url = (
        "https://api.groq.com/openai/v1" if provider == "groq" else "https://api.openai.com/v1"
    )
    async with AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=PROVIDER_TIMEOUT_SECONDS,
        max_retries=0,
    ) as client:
        parser_type = GroqIntentParser if provider == "groq" else OpenAIIntentParser
        yield parser_type(client, model)


def require_model_actor(request: Request, actor: Actor) -> str:
    auth = getattr(request.app.state, "demo_sessions", None)
    if isinstance(auth, DemoSessions) and not auth.allow_model_request():
        raise HTTPException(429, detail="Model request limit reached; try again later")
    return actor


@router.post("/parse", response_model=PurchaseIntent, dependencies=[Depends(require_model_actor)])
async def authenticated_parse_intent(
    body: ParseIntentRequest,
    actor: Actor,
    parser: Annotated[IntentParser, Depends(get_intent_parser)],
) -> PurchaseIntent:
    """Authenticate before initializing a billable provider, including direct API calls."""
    return await parse_intent(body, parser)


async def parse_intent(
    body: ParseIntentRequest,
    parser: Annotated[IntentParser, Depends(get_intent_parser)],
) -> PurchaseIntent:
    """Return a typed proposal; parsed values never change active financial policy."""
    try:
        return await parser.parse(body.query)
    except IntentClarificationRequired:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INTENT_CLARIFICATION_REQUIRED",
                "message": "Clarify the finite total budget, explicit currency and requirements.",
            },
        ) from None
    except InvalidParserOutput:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "INVALID_PARSER_OUTPUT",
                "message": "The model returned an invalid extraction.",
            },
        ) from None
    except IntentParserUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PARSER_UNAVAILABLE",
                "message": (
                    IntentProviderRejected.MESSAGES[error.category]
                    if isinstance(error, IntentProviderRejected)
                    else "The intent model is unavailable. Try again later."
                ),
            },
        ) from None
