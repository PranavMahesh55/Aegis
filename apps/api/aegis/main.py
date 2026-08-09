from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from aegis.adapters.datahub.client import DataHubAdapter
from aegis.api.routes import router
from aegis.config import get_settings
from aegis.context_store import BusinessContextStore
from aegis.domain.transitions import InvalidTransition
from aegis.persistence.store import AegisStore
from aegis.services.agent_runtime import AgentRunService, RunAdmissionError
from aegis.services.workflow import VersionConflict, WorkflowService


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    settings = get_settings()
    store = AegisStore(
        settings.database_path,
        prime_blocked=settings.prime_blocked and settings.data_mode.lower() != "live",
    )
    datahub = DataHubAdapter(settings)
    context_store = BusinessContextStore(settings.context_database_path)
    app.state.store = store
    app.state.datahub = datahub
    app.state.context_store = context_store
    app.state.workflow = WorkflowService(store, datahub, context_store)
    app.state.agent_runs = AgentRunService(settings, store, datahub)
    yield


app = FastAPI(
    title="Aegis API",
    version="0.1.0",
    description="Context-safety control plane for production AI agents",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)
app.include_router(router)


class SPAStaticFiles(StaticFiles):
    """Serve index.html for extensionless client routes, while preserving asset 404s."""

    async def get_response(self, path: str, scope: dict[str, Any]) -> Any:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code != 404 or Path(path).suffix:
                raise
            response = await super().get_response("index.html", scope)
        # The shell points to content-hashed assets and must not outlive a rollout.
        # Without this, a long-lived browser tab can keep an old index.html and never
        # discover the new bundle even though the container is already up to date.
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


def problem(status: int, code: str, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"https://aegis.local/problems/{code.lower().replace('_', '-')}",
            "title": title,
            "status": status,
            "detail": detail,
            "code": code,
            "traceId": f"req-{uuid4().hex[:12]}",
            "errors": [],
        },
    )


@app.exception_handler(InvalidTransition)
async def invalid_transition_handler(_: Request, error: InvalidTransition) -> JSONResponse:
    return problem(409, "INVALID_INCIDENT_TRANSITION", "Invalid incident transition", str(error))


@app.exception_handler(VersionConflict)
async def version_conflict_handler(_: Request, error: VersionConflict) -> JSONResponse:
    return problem(409, "INCIDENT_VERSION_CONFLICT", "Incident changed", str(error))


@app.exception_handler(RunAdmissionError)
async def run_admission_handler(_: Request, error: RunAdmissionError) -> JSONResponse:
    return problem(error.status_code, error.code, "Agent run rejected", error.detail)


web_dist = Path(__file__).parents[2] / "web" / "dist"
if web_dist.exists():
    app.mount("/", SPAStaticFiles(directory=web_dist, html=True), name="web")
