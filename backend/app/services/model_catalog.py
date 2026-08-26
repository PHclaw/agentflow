from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).resolve().parents[4] / "config" / "models.json"


@lru_cache
def load_model_catalog() -> list[dict[str, Any]]:
    """从 config/models.json 读取可调用模型列表。"""
    if not CATALOG_PATH.exists():
        return [
            {
                "name": "qwen-plus",
                "display_name": "Qwen Plus",
                "provider": "dashscope",
                "description": "默认模型",
                "tags": ["默认"],
                "enabled": True,
            }
        ]
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    models = data.get("models") or []
    return [m for m in models if m.get("enabled", True)]


def list_model_names() -> list[str]:
    return [m["name"] for m in load_model_catalog()]


def get_model_entry(name: str) -> dict[str, Any] | None:
    for item in load_model_catalog():
        if item.get("name") == name:
            return item
    return None


def reload_catalog() -> list[dict[str, Any]]:
    load_model_catalog.cache_clear()
    return load_model_catalog()
