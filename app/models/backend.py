"""Upstream model backends behind one interface: complete(prompt) -> (text, backend_name).

Default is the mock backend so the demo works with no GPU and no network.
Ollama is optional and only used if PUARO_MODEL_BACKEND=ollama and the server
responds; otherwise we fall back to mock and say so.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("puaro.model_backend")

MOCK = "mock"
OLLAMA = "ollama"

_CANNED_ANSWERS = [
    "That's a broad question. In short: identify the constraint, isolate the variable, "
    "and test the smallest change that could confirm or rule it out.",
    "Here is a concise way to think about it: define the goal, list the two or three "
    "options that actually matter, and pick the one with the lowest cost if you're wrong.",
    "A simple approach: break the task into steps, do the cheapest step first, and check "
    "the result before doing the expensive step.",
    "Consider the tradeoffs: speed versus correctness, simplicity versus flexibility. "
    "For a first pass, prefer the option you can verify quickly.",
    "The short version: gather the minimum information needed to decide, decide, and "
    "leave a note explaining why, so it's easy to revisit later.",
]


@dataclass(frozen=True)
class ModelResponse:
    text: str
    backend: str


def _mock_complete(prompt: str) -> ModelResponse:
    idx = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest(), 16) % len(_CANNED_ANSWERS)
    return ModelResponse(text=_CANNED_ANSWERS[idx], backend=MOCK)


def _ollama_complete(prompt: str) -> ModelResponse:
    import httpx

    resp = httpx.post(
        f"{settings.ollama_host}/api/generate",
        json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return ModelResponse(text=data.get("response", ""), backend=OLLAMA)


def complete(prompt: str) -> ModelResponse:
    if settings.model_backend == OLLAMA:
        try:
            return _ollama_complete(prompt)
        except Exception as exc:  # noqa: BLE001 - Ollama missing/unreachable -> mock fallback
            # Loud, not silent: PUARO_MODEL_BACKEND=ollama but this specific
            # call fell back to mock. Without this log line (and the
            # model_backend_used column it corresponds to in app/main.py),
            # an intermittently-timing-out Ollama would silently mix real and
            # canned answers with zero record of which was which anywhere.
            logger.warning("Ollama call failed, falling back to mock for this request: %s", exc)
            return _mock_complete(prompt)
    return _mock_complete(prompt)
