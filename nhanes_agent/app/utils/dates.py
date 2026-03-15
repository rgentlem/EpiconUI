from __future__ import annotations

from datetime import UTC, datetime


def now_iso() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()
