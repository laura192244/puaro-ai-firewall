# Security

This is an ideathon prototype. It has not had an external security review.
Please don't point it at real production traffic.

## Reporting

This repo has no public users yet; if you find something concerning, open an
issue describing the problem generically (no exploit details) and we'll
follow up.

## Puaro's own threat model

**Secrets.** All secrets (the trap-phrase HMAC key, demo API keys) come from
environment variables only (`.env`, gitignored — never commit it). If
`PUARO_TRAP_HMAC_SECRET` leaks, an attacker who also controls a suspect model
could potentially precompute or recognize Model DNA trap phrases and avoid
reproducing them, defeating the "Prove" step for future confirmations. Treat
it like any other signing key: rotate it if it's ever exposed, and generate a
fresh one per deployment (`python -c "import secrets; print(secrets.token_hex(32))"`)
— never reuse the placeholder in `.env.example`.

**API keys and fingerprints.** API keys are never stored in cleartext —
`app/fingerprint.py` hashes them with SHA-256 before anything touches the
database. The collective-immunity table (`shared_fingerprints`) stores only a
hashed origin fingerprint (IP + User-Agent, deliberately excluding the
account's own key so that different accounts sharing infrastructure can be
linked), the confirming tenant's ID, and a short reason string — never
prompts, answers, or account identities.

**Tenant isolation.** Signal computation (`app/signals.py`) scopes the
linked-accounts query to the requesting account's own tenant. Collective
immunity is the one deliberate exception — it's designed to share confirmed
attacker fingerprints *across* tenants, by hash only, which is the entire
point of that feature.

**Raw conversation retention.** Prompt/answer text is stored only for a
short, configurable window (`PUARO_RAW_TEXT_RETENTION_MINUTES`, default 60
minutes) and purged by an in-process background loop (see `app/main.py`).
The trap ledger (`trap_ledger` table) is a deliberate exception: it holds the
account/question/trap-phrase mapping needed for the Model DNA verifier to
work, not raw customer conversation content, so it's exempt from that purge.
In a real deployment, the retention purge should run as a proper scheduled
job (cron/systemd timer), not an asyncio loop tied to the gateway process's
own lifetime — see the Limits/Roadmap sections in `README.md`.

**The Firewall step's own limits.** If the native `sentinel-core` engine
isn't installed for the current platform, Puaro automatically falls back to
a small regex rule set and labels this clearly everywhere (`/healthz`, the
dashboard banner, `make eval`) — it never silently claims stronger detection
than is actually running.

**No sandboxing of the native firewall dependency.** If `sentinel-core` is
installed, we call it as an ordinary trusted Python package; we do not
sandbox it. Only install it from the pinned commit referenced in
`THIRD_PARTY_NOTICES.md`.

**Origin fingerprint trust (`PUARO_TRUST_FORWARDED_HEADERS`).** By default
(and required for the local demo/simulator, which presents many fake origins
from one machine) Puaro trusts the client-supplied `X-Forwarded-For` header
as the origin IP for fingerprinting. Found and fixed during testing: with
that trusted unconditionally, any client could spoof its own fingerprint to
evade the linked-accounts signal, or spoof an *innocent* party's IP while
behaving like a bot — getting that innocent IP wrongly flagged and blocked
across every tenant via collective immunity. **In a real deployment, set
`PUARO_TRUST_FORWARDED_HEADERS=false`** unless a trusted reverse proxy is
guaranteed to overwrite that header itself; when false, Puaro uses the
actual TCP peer address instead. User-Agent is not covered by this setting
— it's inherently client-supplied in HTTP regardless of proxy configuration,
so it was never a fixable trust boundary the same way IP is.

**Request size limit (`PUARO_MAX_REQUEST_BYTES`, default 256 KiB).** Found
during testing: the gateway had no body size limit at all — a 2 MB payload
was accepted and processed with no rejection, an easy memory/CPU/storage
DoS vector (prompt text is also written to SQLite). A `Content-Length`
check now rejects oversized bodies with 413 before parsing. This only
checks `Content-Length`; a request using chunked transfer-encoding without
that header can still bypass it, so a production deployment should also
enforce a cap at the reverse-proxy layer (e.g. nginx `client_max_body_size`).

**Known gaps, said plainly:**
- No encryption at rest (SQLite, single local file).
- No TLS in local dev — add a reverse proxy in front for anything beyond a
  demo.
- No production-grade account provisioning (`PUARO_DEMO_ACCOUNTS` is an env
  var, meant for this demo only).
- Hard account bans are not implemented; the four automatic policy actions
  (pass/slow/hide-reasoning/decoy) never permanently ban an account, and no
  human-approval UI for a stronger action exists yet (see Roadmap).
