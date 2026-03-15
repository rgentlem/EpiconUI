"""FastAPI NHANES agent package with compatibility exports."""

from legacy_nhanes_agent import run_nhanes_extraction_query


def create_app():
    """Lazily import and create the FastAPI app."""
    from nhanes_agent.app.main import create_app as _create_app

    return _create_app()


__all__ = ["create_app", "run_nhanes_extraction_query"]
