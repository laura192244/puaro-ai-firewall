"""Puaro's Firewall step.

Wraps the AISecurity `sentinel-core` public pattern engines (via
`EngineRegistry().analyze_patterns`) behind our own small interface:

    firewall.check(text) -> FirewallResult(blocked, reason, engine)

If the native `sentinel_core` package is not installed (e.g. it was not built
for this platform), we fall back to a small regex rule set behind the same
interface. The active mode is exposed via `firewall.mode` so the dashboard can
show "fallback firewall" and we never overclaim detection quality.

We do not quote sentinel-core's own accuracy numbers anywhere: its README says
those are historical and not revalidated, and its demo/test corpus is small
and synthetic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import settings

NATIVE = "native:sentinel-core"
FALLBACK = "fallback:regex"

_FALLBACK_PATTERNS = [
    (re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.I), "jailbreak"),
    (re.compile(r"you are now (DAN|in developer mode|unrestricted)", re.I), "jailbreak"),
    (re.compile(r"disregard your (system prompt|guidelines|rules)", re.I), "jailbreak"),
    (re.compile(r"reveal (your |the )?(system prompt|hidden instructions)", re.I), "prompt_leak"),
    (re.compile(r"\bunion\s+select\b", re.I), "injection"),
    (re.compile(r"\bor\s+1\s*=\s*1\b", re.I), "injection"),
    (re.compile(r"drop\s+table", re.I), "injection"),
    (re.compile(r"<script[^>]*>", re.I), "injection"),
    (re.compile(r"\$\{jndi:", re.I), "injection"),
    (re.compile(r"act as (an? )?(unfiltered|jailbroken|amoral) (ai|assistant)", re.I), "jailbreak"),
]


@dataclass(frozen=True)
class FirewallResult:
    blocked: bool
    reason: str
    engine: str  # NATIVE or FALLBACK
    categories: tuple[str, ...] = ()


class Firewall:
    def __init__(self, mode: str = "auto") -> None:
        self._registry = None
        self.mode = FALLBACK
        if mode not in ("auto", "regex", "native"):
            raise ValueError(f"invalid firewall mode: {mode}")
        if mode == "regex":
            return
        try:
            from sentinel_core import EngineRegistry  # type: ignore

            self._registry = EngineRegistry()
            self.mode = NATIVE
        except Exception as exc:  # noqa: BLE001 - any import/build failure -> fallback
            if mode == "native":
                raise RuntimeError(
                    "PUARO_FIREWALL_MODE=native but sentinel_core is not importable"
                ) from exc
            self._registry = None
            self.mode = FALLBACK

    def check(self, text: str) -> FirewallResult:
        if self._registry is not None:
            return self._check_native(text)
        return self._check_fallback(text)

    def _check_native(self, text: str) -> FirewallResult:
        result = self._registry.analyze_patterns(text)
        categories = tuple(result.categories)
        reason = f"sentinel-core: {', '.join(categories)}" if result.detected else "clean"
        return FirewallResult(blocked=bool(result.detected), reason=reason, engine=NATIVE, categories=categories)

    def _check_fallback(self, text: str) -> FirewallResult:
        hits = [name for pattern, name in _FALLBACK_PATTERNS if pattern.search(text)]
        if hits:
            categories = tuple(dict.fromkeys(hits))
            return FirewallResult(
                blocked=True,
                reason=f"fallback regex: {', '.join(categories)}",
                engine=FALLBACK,
                categories=categories,
            )
        return FirewallResult(blocked=False, reason="clean", engine=FALLBACK)


firewall = Firewall(settings.firewall_mode)
