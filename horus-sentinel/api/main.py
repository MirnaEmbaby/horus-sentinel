"""HORUS Sentinel — API entry point.

Exposes the Control Plane: a health probe plus job submission/retrieval. Submitting a
job runs it through the Authorization Engine first (a disallowed request is refused with
a 403), then persists it. Collection and reasoning are driven by the orchestrator.
"""

from __future__ import annotations

import utils.http_session
import utils.transport
import utils.session
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.chat import router as chat_router
from api.demo import router as demo_router
from api.routes import router as jobs_router
from api.setup import router as setup_router
from core.config import settings
from core.db import init_db

_UI_DIR = Path(__file__).resolve().parent.parent / "horus-ui"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create tables on startup; optionally run an in-process worker (WORKER_ENABLED)."""
    import asyncio

    init_db()
    worker_task: asyncio.Task[None] | None = None
    if settings.worker_enabled:
        from workflows.worker import Worker

        worker = Worker()
        worker_task = asyncio.create_task(worker.run_forever())
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()


app = FastAPI(
    title="HORUS Sentinel",
    description="Autonomous multi-agent OSINT & threat-intelligence platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(jobs_router)
app.include_router(demo_router)
app.include_router(setup_router)
app.include_router(chat_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, object]:
    """Liveness probe + brain backend snapshot."""
    return {
        "status": "ok",
        "service": "horus-sentinel",
        "env": settings.app_env,
        "brain_backend": settings.brain_backend,
        "brain_model": settings.horus_model_name,
        "hf_model_id": settings.hf_model_id,
        "report_language": settings.report_language,
    }


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Root — points to the Command Center UI and the interactive docs."""
    return {
        "message": "HORUS Sentinel API. Open /ui for the Command Center, /docs for the API.",
        "slogan": "The eye that never sleeps.",
        "tagline": "ARGUS's hundred eyes gather; the Eye of HORUS judges.",
    }


# Serve the self-contained Command Center (zero-build static UI) at /ui.
if _UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(_UI_DIR), html=True), name="ui")
