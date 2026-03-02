"""
FastAPI application — single process, no worker proxy.

Serves scenarios, HTML-rendered documents, interactive intake forms,
and server-side grading.  All training state lives in a local SQLite
database (``data/scenarios.sqlite``).

Run with:
    uvicorn api.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from training.document_renderer import DocumentRenderer
from training.exercise_engine import ExerciseEngine
from training.grader import Grader
from training.scenario_store import ScenarioStore

from api.routes.scenarios import router as scenarios_router
from api.routes.config import router as config_router
from api.routes.progress import router as progress_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources at startup, clean up on shutdown."""
    logger.info("Starting VITATrainer API")

    app.state.engine = ExerciseEngine()
    app.state.store = ScenarioStore()
    app.state.renderer = DocumentRenderer()
    app.state.grader = Grader()

    yield

    app.state.store.close()
    logger.info("Shut down VITATrainer API")


app = FastAPI(
    title="VITATrainer",
    description="VITA tax preparation training — practice exercises with server-side grading",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files (CSS for document templates)
app.mount(
    "/static",
    StaticFiles(directory="training/templates"),
    name="static",
)

# API + HTML routes
app.include_router(scenarios_router)
app.include_router(config_router, prefix="/api/v1")
app.include_router(progress_router, prefix="/api/v1")
