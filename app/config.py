"""Environment-driven configuration. No secrets are hardcoded here."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_accounts(raw: str) -> dict[str, tuple[str, str]]:
    """Parse "tenant:label:key,tenant:label:key" into {key: (tenant, label)}."""
    accounts: dict[str, tuple[str, str]] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        tenant, label, key = entry.split(":", 2)
        accounts[key] = (tenant, label)
    return accounts


@dataclass(frozen=True)
class Settings:
    demo_accounts: dict[str, tuple[str, str]] = field(default_factory=dict)
    model_backend: str = "mock"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:0.5b"
    firewall_mode: str = "auto"
    trap_hmac_secret: str = ""
    db_path: str = "./data/puaro.db"
    raw_text_retention_minutes: int = 60
    weight_rate: float = 0.25
    weight_templates: float = 0.20
    weight_reasoning: float = 0.15
    weight_linked: float = 0.25
    weight_coverage: float = 0.15
    threshold_slow: int = 50
    threshold_hide_reasoning: int = 55
    threshold_decoy: int = 70
    signal_window_seconds: int = 300
    rate_cap_per_window: int = 20
    template_similarity_threshold: float = 0.5
    linked_account_cap: int = 3
    slowdown_seconds: float = 1.5
    trust_forwarded_headers: bool = True
    max_request_bytes: int = 262_144


def load_settings() -> Settings:
    return Settings(
        demo_accounts=_split_accounts(os.environ.get("PUARO_DEMO_ACCOUNTS", "")),
        model_backend=os.environ.get("PUARO_MODEL_BACKEND", "mock"),
        ollama_host=os.environ.get("PUARO_OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.environ.get("PUARO_OLLAMA_MODEL", "qwen2.5:0.5b"),
        firewall_mode=os.environ.get("PUARO_FIREWALL_MODE", "auto"),
        trap_hmac_secret=os.environ.get("PUARO_TRAP_HMAC_SECRET", ""),
        db_path=os.environ.get("PUARO_DB_PATH", "./data/puaro.db"),
        raw_text_retention_minutes=int(os.environ.get("PUARO_RAW_TEXT_RETENTION_MINUTES", "60")),
        weight_rate=float(os.environ.get("PUARO_WEIGHT_RATE", "0.25")),
        weight_templates=float(os.environ.get("PUARO_WEIGHT_TEMPLATES", "0.20")),
        weight_reasoning=float(os.environ.get("PUARO_WEIGHT_REASONING", "0.15")),
        weight_linked=float(os.environ.get("PUARO_WEIGHT_LINKED", "0.25")),
        weight_coverage=float(os.environ.get("PUARO_WEIGHT_COVERAGE", "0.15")),
        threshold_slow=int(os.environ.get("PUARO_THRESHOLD_SLOW", "50")),
        threshold_hide_reasoning=int(os.environ.get("PUARO_THRESHOLD_HIDE_REASONING", "55")),
        threshold_decoy=int(os.environ.get("PUARO_THRESHOLD_DECOY", "70")),
        signal_window_seconds=int(os.environ.get("PUARO_SIGNAL_WINDOW_SECONDS", "300")),
        rate_cap_per_window=int(os.environ.get("PUARO_RATE_CAP_PER_WINDOW", "20")),
        template_similarity_threshold=float(os.environ.get("PUARO_TEMPLATE_SIMILARITY_THRESHOLD", "0.5")),
        linked_account_cap=int(os.environ.get("PUARO_LINKED_ACCOUNT_CAP", "3")),
        slowdown_seconds=float(os.environ.get("PUARO_SLOWDOWN_SECONDS", "1.5")),
        trust_forwarded_headers=os.environ.get("PUARO_TRUST_FORWARDED_HEADERS", "true").lower() == "true",
        max_request_bytes=int(os.environ.get("PUARO_MAX_REQUEST_BYTES", "262144")),
    )


settings = load_settings()
