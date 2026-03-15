from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure application logging once for the FastAPI backend."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
