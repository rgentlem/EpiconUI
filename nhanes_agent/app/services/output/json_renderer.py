from __future__ import annotations

import json


def render_json_summary(payload: dict) -> str:
    """Render a deterministic JSON block for the machine-readable summary."""
    return json.dumps(payload, indent=2)
