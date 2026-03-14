from __future__ import annotations

import json
from typing import Any
from urllib import error, request


def build_embeddings_endpoint(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/embeddings"):
        return trimmed
    return f"{trimmed}/embeddings"


def create_embeddings(
    *,
    base_url: str,
    api_key: str,
    model: str,
    texts: list[str],
    dimensions: int | None = None,
    batch_size: int = 32,
    timeout: int = 180,
) -> list[list[float]]:
    if not texts:
        return []

    endpoint = build_embeddings_endpoint(base_url)
    outputs: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        payload: dict[str, Any] = {
            "model": model,
            "input": batch,
        }
        if dimensions:
            payload["dimensions"] = dimensions

        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Embedding request failed with {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Unable to reach embedding endpoint: {exc.reason}") from exc

        items = data.get("data") or []
        if len(items) != len(batch):
            raise RuntimeError("Embedding response count did not match the input batch size.")

        outputs.extend([list(item.get("embedding") or []) for item in items])

    if len(outputs) != len(texts):
        raise RuntimeError("Embedding response count did not match the total input size.")

    return outputs
