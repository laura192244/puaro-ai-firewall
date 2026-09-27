"""Puaro gateway: an OpenAI-compatible endpoint in front of an upstream model.

Pipeline per request: authenticate -> fingerprint -> firewall -> signals ->
risk score -> policy -> model call. Decoys/Model DNA (Phase 4) and collective
immunity (Phase 5) plug into this same flow without changing the contract.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.clone import answer as clone_answer
from app.config import settings
from app.dashboard import router as dashboard_router
from app.db import connection, init_db, purge_expired_raw_text
from app.decoys import build_decoy
from app.fingerprint import account_id_from_key, hash_api_key, origin_fingerprint
from app.firewall import FirewallResult, firewall
from app.immunity import lookup as lookup_immunity
from app.immunity import publish as publish_immunity
from app.models.backend import complete
from app.policy import DECOY, HIDE_REASONING, PASS, SLOW, decide
from app.risk import compute_risk
from app.signals import compute_signals
from app.templates import compute_minhash, demands_reasoning, serialize_minhash
from app.topics import classify as classify_topics


async def _purge_loop() -> None:
    """Runs purge_expired_raw_text() on a fixed interval for the life of the
    process. A real deployment would run this as a separate scheduled job
    (cron, systemd timer, etc.), not an in-process asyncio loop — this is
    enough to make the retention window actually mean something during a demo
    run, rather than existing as dead code that's never called."""
    interval_seconds = max(60, settings.raw_text_retention_minutes * 60 // 4)
    while True:
        await asyncio.sleep(interval_seconds)
        purge_expired_raw_text()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    init_db()
    purge_task = asyncio.create_task(_purge_loop())
    yield
    purge_task.cancel()


app = FastAPI(title="Puaro Gateway", lifespan=_lifespan)
app.include_router(dashboard_router)


@app.middleware("http")
async def _limit_request_size(request: Request, call_next):
    """Reject oversized bodies before they're parsed. Checks Content-Length
    only — a request using chunked transfer-encoding without that header can
    still bypass this, so a production deployment should also enforce a body
    size cap at the reverse-proxy layer (e.g. nginx client_max_body_size)."""
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > settings.max_request_bytes:
        return JSONResponse(
            status_code=413,
            content={"detail": f"request body exceeds {settings.max_request_bytes} bytes"},
        )
    return await call_next(request)


def _resolve_origin(request: Request, x_forwarded_for: str | None, user_agent: str | None) -> tuple[str, str]:
    """Client-supplied X-Forwarded-For is only trusted when explicitly
    configured to (PUARO_TRUST_FORWARDED_HEADERS=true) — the default here so
    the local simulator can present many distinct origins from one machine.
    In a real deployment this MUST be false unless a trusted reverse proxy is
    guaranteed to set/overwrite this header itself: otherwise any client can
    freely spoof its own fingerprint (evading the linked-accounts signal) or
    spoof an innocent party's IP (getting them wrongly flagged and blocked
    across tenants via collective immunity)."""
    ua = user_agent or "unknown"
    if settings.trust_forwarded_headers and x_forwarded_for:
        return x_forwarded_for, ua
    peer = request.client.host if request.client else "unknown"
    return peer, ua


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "puaro-default"
    messages: list[ChatMessage]


class Account(BaseModel):
    account_id: str
    tenant_id: str
    label: str
    key_hash: str


def _authenticate(authorization: str | None) -> Account:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing Bearer API key")
    api_key = authorization.removeprefix("Bearer ").strip()
    account_info = settings.demo_accounts.get(api_key)
    if account_info is None:
        raise HTTPException(status_code=401, detail="unknown API key")
    tenant_id, label = account_info
    account_id = account_id_from_key(tenant_id, label)
    key_hash = hash_api_key(api_key)
    with connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO accounts (account_id, tenant_id, label, key_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (account_id, tenant_id, label, key_hash, time.time()),
        )
    return Account(account_id=account_id, tenant_id=tenant_id, label=label, key_hash=key_hash)


def _prompt_text(req: ChatCompletionRequest) -> str:
    return "\n".join(m.content for m in req.messages if m.role == "user")


def _hide_reasoning(text: str) -> str:
    """Stand-in for hiding step-by-step reasoning: keep only the first clause.

    Our mock/Ollama answers aren't structured chain-of-thought, so this trims
    the response to its first sentence as a visible, honest approximation of
    "reasoning withheld" for the demo.
    """
    first_sentence = text.split(".")[0].strip()
    return f"{first_sentence}. (reasoning withheld)"


@app.get("/healthz")
def healthz() -> dict:
    """model_backend is the CONFIGURED intent (PUARO_MODEL_BACKEND). It does
    not mean every response actually used it — see
    /api/dashboard/state.counters.model_fallback_count for how many recent
    responses silently fell back to mock after an Ollama failure."""
    return {"status": "ok", "firewall_mode": firewall.mode, "model_backend": settings.model_backend}


@app.post("/v1/chat/completions")
def chat_completions(
    req: ChatCompletionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    x_forwarded_for: str | None = Header(default=None),
    user_agent: str | None = Header(default=None),
):
    t_start = time.perf_counter()
    request_id = str(uuid.uuid4())

    t0 = time.perf_counter()
    account = _authenticate(authorization)
    ip, ua = _resolve_origin(request, x_forwarded_for, user_agent)
    fp = origin_fingerprint(ip=ip, user_agent=ua)
    t_auth_us = int((time.perf_counter() - t0) * 1_000_000)

    prompt = _prompt_text(req)

    # Collective immunity: check BEFORE the firewall or any signals, so a
    # fingerprint confirmed anywhere blocks on this tenant's very first
    # request from it — no local history required.
    t0 = time.perf_counter()
    immunity_hit = lookup_immunity(fp)
    t_immunity_us = int((time.perf_counter() - t0) * 1_000_000)

    if immunity_hit is not None:
        t_total_us = int((time.perf_counter() - t_start) * 1_000_000)
        _log_request(
            request_id=request_id,
            account=account,
            fingerprint=fp,
            prompt=prompt,
            answer_text=None,
            fw_result=FirewallResult(blocked=False, reason="not evaluated: blocked by collective immunity", engine="n/a"),
            outcome="immunity_blocked",
            reasoning_flag=False,
            topics=[],
            minhash_sig=None,
            risk=None,
            is_trap=False,
            trap_phrase=None,
            model_backend=None,
            timings={
                "t_auth_us": t_auth_us,
                "t_immunity_us": t_immunity_us,
                "t_firewall_us": 0,
                "t_signals_us": 0,
                "t_policy_us": 0,
                "t_model_us": 0,
                "t_total_us": t_total_us,
            },
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "blocked by collective immunity",
                "reason": immunity_hit.reason,
                "confirmed_at_tenant": immunity_hit.origin_tenant_id,
            },
        )

    t0 = time.perf_counter()
    fw_result = firewall.check(prompt)
    t_firewall_us = int((time.perf_counter() - t0) * 1_000_000)

    if fw_result.blocked:
        t_total_us = int((time.perf_counter() - t_start) * 1_000_000)
        _log_request(
            request_id=request_id,
            account=account,
            fingerprint=fp,
            prompt=prompt,
            answer_text=None,
            fw_result=fw_result,
            outcome="firewall_blocked",
            reasoning_flag=False,
            topics=[],
            minhash_sig=None,
            risk=None,
            is_trap=False,
            trap_phrase=None,
            model_backend=None,
            timings={
                "t_auth_us": t_auth_us,
                "t_immunity_us": t_immunity_us,
                "t_firewall_us": t_firewall_us,
                "t_signals_us": 0,
                "t_policy_us": 0,
                "t_model_us": 0,
                "t_total_us": t_total_us,
            },
        )
        raise HTTPException(
            status_code=400,
            detail={"error": "request blocked by firewall", "reason": fw_result.reason, "engine": fw_result.engine},
        )

    t0 = time.perf_counter()
    reasoning_flag = demands_reasoning(prompt)
    topics = classify_topics(prompt)
    minhash = compute_minhash(prompt)
    signals = compute_signals(
        account_id=account.account_id,
        tenant_id=account.tenant_id,
        fingerprint_hash=fp,
        current_minhash=minhash,
        current_topics=topics,
        current_reasoning_flag=reasoning_flag,
    )
    risk = compute_risk(signals)
    t_signals_us = int((time.perf_counter() - t0) * 1_000_000)

    t0 = time.perf_counter()
    action = decide(risk.score)
    t_policy_us = int((time.perf_counter() - t0) * 1_000_000)

    if action == SLOW:
        time.sleep(settings.slowdown_seconds)

    is_trap = False
    trap_phrase = None
    trap_question_id = None
    model_backend = None

    if action == DECOY:
        # Model DNA: serve a weak decoy answer seeded with a trap phrase instead
        # of calling the real upstream model at all, so no real capability leaks.
        decoy = build_decoy(prompt, account.account_id)
        answer_text = decoy.answer_text
        is_trap = True
        trap_phrase = decoy.trap_phrase
        trap_question_id = decoy.question_id
        model_backend = "decoy"
        t_model_us = 0
        # Collective immunity: this origin is now confirmed at this tenant.
        # Idempotent — only the first confirming tenant's record sticks.
        publish_immunity(fp, account.tenant_id, f"confirmed distillation behavior (risk_score={risk.score})")
    else:
        t0 = time.perf_counter()
        model_response = complete(prompt)
        t_model_us = int((time.perf_counter() - t0) * 1_000_000)
        answer_text = model_response.text
        model_backend = model_response.backend
        if action == HIDE_REASONING:
            answer_text = _hide_reasoning(answer_text)

    outcome = {PASS: "answered", SLOW: "slowed", HIDE_REASONING: "reasoning_hidden", DECOY: "decoy"}[action]
    t_total_us = int((time.perf_counter() - t_start) * 1_000_000)
    _log_request(
        request_id=request_id,
        account=account,
        fingerprint=fp,
        prompt=prompt,
        answer_text=answer_text,
        fw_result=fw_result,
        outcome=outcome,
        reasoning_flag=reasoning_flag,
        topics=topics,
        minhash_sig=serialize_minhash(minhash),
        risk=risk,
        is_trap=is_trap,
        trap_phrase=trap_phrase,
        model_backend=model_backend,
        timings={
            "t_auth_us": t_auth_us,
            "t_immunity_us": t_immunity_us,
            "t_firewall_us": t_firewall_us,
            "t_signals_us": t_signals_us,
            "t_policy_us": t_policy_us,
            "t_model_us": t_model_us,
            "t_total_us": t_total_us,
        },
    )

    if is_trap:
        with connection() as conn:
            conn.execute(
                """
                INSERT INTO trap_ledger (
                    trap_id, request_id, account_id, tenant_id, question_id, question_text,
                    trap_phrase, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    request_id,
                    account.account_id,
                    account.tenant_id,
                    trap_question_id,
                    prompt,
                    trap_phrase,
                    time.time(),
                ),
            )

    return {
        "id": request_id,
        "object": "chat.completion",
        "model": req.model,
        "puaro": {
            "tenant_id": account.tenant_id,
            "firewall_engine": fw_result.engine,
            "model_backend": model_backend,
            "outcome": outcome,
            "risk_score": risk.score,
            "risk_breakdown": risk.breakdown,
        },
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer_text},
                "finish_reason": "stop",
            }
        ],
    }


@app.post("/clone/chat/completions")
def clone_chat_completions(req: ChatCompletionRequest):
    """Stand-in for a distilled model: NOT part of the protected gateway, no
    auth, no firewall, no risk scoring. It only echoes whatever the nearest
    harvested (question, answer) pair in `requests` looked like — exactly what
    a copy trained on scraped Puaro output would do, without us training a
    real model. Always labeled as a stand-in in the response.
    """
    prompt = _prompt_text(req)
    result = clone_answer(prompt)
    return {
        "id": str(uuid.uuid4()),
        "object": "chat.completion",
        "model": "puaro-clone-stand-in",
        "puaro": {
            "stand_in_for_distilled_model": True,
            "matched_harvested_question": result.matched,
            "exact_match": result.exact_match,
            "similarity": round(result.similarity, 4),
        },
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.answer_text},
                "finish_reason": "stop",
            }
        ],
    }


def _log_request(*, request_id, account, fingerprint, prompt, answer_text, fw_result, outcome, reasoning_flag, topics, minhash_sig, risk, is_trap, trap_phrase, model_backend, timings) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO requests (
                request_id, account_id, tenant_id, created_at, prompt_text, answer_text, fingerprint_hash,
                firewall_blocked, firewall_reason, firewall_engine, risk_score, risk_breakdown,
                outcome, is_trap, trap_phrase, model_backend_used, reasoning_requested, topics, minhash_signature,
                t_auth_us, t_immunity_us, t_firewall_us, t_signals_us, t_policy_us, t_model_us, t_total_us
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                account.account_id,
                account.tenant_id,
                time.time(),
                prompt,
                answer_text,
                fingerprint,
                int(fw_result.blocked),
                fw_result.reason,
                fw_result.engine,
                risk.score if risk else None,
                json.dumps(risk.breakdown) if risk else json.dumps({}),
                outcome,
                int(is_trap),
                trap_phrase,
                model_backend,
                int(reasoning_flag),
                json.dumps(topics),
                minhash_sig,
                timings["t_auth_us"],
                timings["t_immunity_us"],
                timings["t_firewall_us"],
                timings["t_signals_us"],
                timings["t_policy_us"],
                timings["t_model_us"],
                timings["t_total_us"],
            ),
        )
