"""Volcengine Ark (豆包) — OpenAI-compatible Chat Completions."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from django.conf import settings


def chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    timeout: float = 120.0,
) -> str:
    key = (settings.ARK_API_KEY or "").strip()
    model = (settings.ARK_MODEL or "").strip()
    base = (settings.ARK_BASE_URL or "").rstrip("/")
    if not key or not model:
        raise RuntimeError("ARK_API_KEY or ARK_MODEL not configured")
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return (msg.get("content") or "").strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None
