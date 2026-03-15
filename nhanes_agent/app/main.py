from __future__ import annotations

from fastapi import FastAPI

from nhanes_agent.app.api.routes_admin import router as admin_router
from nhanes_agent.app.api.routes_ingest import router as ingest_router
from nhanes_agent.app.api.routes_query import router as query_router
from nhanes_agent.app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Create the FastAPI application for the NHANES agent backend."""
    configure_logging()
    app = FastAPI(title="NHANES Agent", version="0.1.0")
    app.include_router(ingest_router)
    app.include_router(query_router)
    app.include_router(admin_router)
    return app


app = create_app()
