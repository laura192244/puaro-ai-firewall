"""Set test environment variables before any `app.*` module is imported anywhere,
since app.config.settings is a module-level singleton read once at import time."""
import os

os.environ.setdefault("PUARO_DB_PATH", "./data/test_puaro.db")
os.environ.setdefault("PUARO_FIREWALL_MODE", "regex")
os.environ.setdefault("PUARO_DEMO_ACCOUNTS", "custA:client1:sk-clienta1,custB:clientb1:sk-clientb1")
os.environ.setdefault("PUARO_TRAP_HMAC_SECRET", "test-secret-do-not-use-in-prod")
