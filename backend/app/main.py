"""AgentPay API; checkout routes fail closed until trusted auth/services are provisioned."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.agent import router as agent_router
from app.api.checkout import router as checkout_router
from app.api.offers import router as offers_router
from app.api.workspace import router as workspace_router
from app.services.catalog import CatalogService
from app.services.provisioning import provision


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Load trusted fixtures once; invalid data prevents the API from starting."""
    application.state.catalog = CatalogService()
    async with AsyncExitStack() as stack:
        await provision(application, stack)
        yield
    for name in ("workspace", "demo_sessions", "checkout_service"):
        if hasattr(application.state, name):
            delattr(application.state, name)


app = FastAPI(title="Ryuk API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    """Never reflect raw input, field names, validator context, or submitted secrets."""
    return JSONResponse(status_code=422, content={"detail": "Please check the request fields."})


app.include_router(offers_router)
app.include_router(agent_router)
app.include_router(checkout_router)
app.include_router(workspace_router)


class HealthResponse(BaseModel):
    """Process liveness only; does not assert database or provider readiness."""

    status: Literal["ok"]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return API liveness without requiring credentials or external services."""
    return HealthResponse(status="ok")


@app.middleware("http")
async def private_api_responses(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    if request.url.path.startswith("/v1/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Cookie"
    return response
