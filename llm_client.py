from __future__ import annotations

import json
from typing import Any
from urllib import error, request


def build_chat_endpoint(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    return f"{trimmed}/chat/completions"


def extract_text_content(message: Any) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts: list[str] = []
        for item in message:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part.strip())
    return str(message or "")


def create_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1200,
    timeout: int = 180,
) -> dict[str, Any]:
    endpoint = build_chat_endpoint(base_url)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
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
        raise RuntimeError(f"LLM request failed with {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Unable to reach LLM endpoint: {exc.reason}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("LLM response did not include any choices.")

    content = extract_text_content((choices[0].get("message") or {}).get("content"))
    if not content.strip():
        raise RuntimeError("LLM response was empty.")

    return {
        "content": content,
        "raw": data,
    }
