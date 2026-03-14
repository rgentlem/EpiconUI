from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from project_store import epimind_home

DEFAULT_OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")).strip()
DEFAULT_OPENAI_MODEL = os.environ.get("OPENAI_MODEL", os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")).strip()


def config_root(base_dir: str | Path | None = None) -> Path:
    root = epimind_home(base_dir) / "config"
    root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except PermissionError:
        pass
    return root


def llm_config_path(base_dir: str | Path | None = None) -> Path:
    return config_root(base_dir) / "llm.json"


def mask_api_key(api_key: str | None) -> str:
    if not api_key:
        return ""
    stripped = api_key.strip()
    if len(stripped) <= 6:
        return "*" * len(stripped)
    return f"{stripped[:3]}{'*' * (len(stripped) - 6)}{stripped[-3:]}"


def load_llm_config(base_dir: str | Path | None = None) -> dict[str, Any]:
    path = llm_config_path(base_dir)
    env_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not path.exists():
        return {
            "configured": bool(DEFAULT_OPENAI_BASE_URL and DEFAULT_OPENAI_MODEL and env_api_key),
            "base_url": DEFAULT_OPENAI_BASE_URL,
            "model": DEFAULT_OPENAI_MODEL,
            "api_key": env_api_key,
            "api_key_masked": mask_api_key(env_api_key),
            "has_api_key": bool(env_api_key),
            "api_key_source": "environment" if env_api_key else "",
            "system_prompt": "",
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    api_key = str(payload.get("api_key", "")).strip() or env_api_key
    api_key_source = "stored" if str(payload.get("api_key", "")).strip() else "environment" if env_api_key else ""
    base_url = str(payload.get("base_url", "")).strip() or DEFAULT_OPENAI_BASE_URL
    model = str(payload.get("model", "")).strip() or DEFAULT_OPENAI_MODEL
    return {
        "configured": bool(base_url and model and api_key),
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "api_key_masked": mask_api_key(api_key),
        "has_api_key": bool(api_key),
        "api_key_source": api_key_source,
        "system_prompt": str(payload.get("system_prompt", "")),
    }


def llm_config_summary(base_dir: str | Path | None = None) -> dict[str, Any]:
    payload = load_llm_config(base_dir)
    return {
        "configured": payload["configured"],
        "base_url": payload["base_url"],
        "model": payload["model"],
        "has_api_key": payload["has_api_key"],
        "api_key_masked": payload["api_key_masked"],
        "api_key_source": payload["api_key_source"],
        "system_prompt": payload["system_prompt"],
    }


def save_llm_config(
    *,
    base_url: str,
    model: str,
    api_key: str,
    system_prompt: str = "",
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    existing = load_llm_config(base_dir)
    normalized_base_url = base_url.strip().rstrip("/") or existing.get("base_url", "")
    normalized_model = model.strip() or existing.get("model", "")
    normalized_key = api_key.strip() or existing.get("api_key", "")
    payload = {
        "base_url": normalized_base_url,
        "model": normalized_model,
        "api_key": normalized_key,
        "system_prompt": system_prompt.strip(),
    }

    missing: list[str] = []
    if not payload["base_url"]:
        missing.append("base_url")
    if not payload["model"]:
        missing.append("model")
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    path = llm_config_path(base_dir)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except PermissionError:
        pass
    return llm_config_summary(base_dir)


def clear_llm_config(base_dir: str | Path | None = None) -> None:
    path = llm_config_path(base_dir)
    if path.exists():
        path.unlink()
