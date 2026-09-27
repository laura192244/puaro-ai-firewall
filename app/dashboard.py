"""Dashboard API: live state + demo action buttons. The actual page is a
static HTML/JS file (app/static/dashboard.html) that polls these endpoints."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import demo_actions
from app.config import settings
from app.db import connection
from app.firewall import firewall

router = APIRouter()

STATIC_DIR = Path(__file__).parent / "static"

_last_scan: dict | None = None
_bot_counter = 0
_devci_counter = 0


@router.get("/dashboard")
def dashboard_page():
    return FileResponse(STATIC_DIR / "dashboard.html")


@router.get("/api/dashboard/state")
def dashboard_state():
    with connection() as conn:
        total_requests = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        real_clients_served = conn.execute("SELECT COUNT(*) FROM requests WHERE outcome = 'answered'").fetchone()[0]
        attackers_stopped = conn.execute(
            "SELECT COUNT(DISTINCT account_id) FROM requests "
            "WHERE outcome IN ('firewall_blocked', 'immunity_blocked', 'decoy')"
        ).fetchone()[0]
        # Configured intent (settings.model_backend) is not the same as what
        # actually served each answer. If PUARO_MODEL_BACKEND=ollama but some
        # responses' model_backend_used='mock', Ollama silently failed on
        # those specific calls — this counts exactly how often, instead of
        # letting the static /healthz value imply every answer was real.
        model_fallback_count = 0
        if settings.model_backend != "mock":
            model_fallback_count = conn.execute(
                "SELECT COUNT(*) FROM requests WHERE model_backend_used = 'mock'"
            ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT r.request_id, r.created_at, a.tenant_id, a.label, r.risk_score, r.risk_breakdown,
                   r.outcome, r.firewall_engine, r.is_trap
            FROM requests r
            LEFT JOIN accounts a ON r.account_id = a.account_id
            ORDER BY r.created_at DESC
            LIMIT 50
            """
        ).fetchall()

    recent = []
    for row in rows:
        d = dict(row)
        d["risk_breakdown"] = json.loads(d["risk_breakdown"]) if d["risk_breakdown"] else {}
        recent.append(d)

    return {
        "firewall_mode": firewall.mode,
        "model_backend": settings.model_backend,
        "counters": {
            "requests": total_requests,
            "real_clients_served": real_clients_served,
            "attackers_stopped": attackers_stopped,
            "trap_matches": _last_scan["clone"]["matches"] if _last_scan else None,
            "trap_total": _last_scan["clone"]["total"] if _last_scan else None,
            "model_fallback_count": model_fallback_count,
        },
        "last_scan": _last_scan,
        "recent_requests": recent,
    }


@router.post("/api/dashboard/action/send-client")
def action_send_client():
    return {"results": [r.__dict__ for r in demo_actions.send_client(1)]}


@router.post("/api/dashboard/action/send-bot")
def action_send_bot():
    global _bot_counter
    results = demo_actions.send_bot_burst(3, start_at=_bot_counter + 1)
    _bot_counter += 3
    return {"results": [r.__dict__ for r in results]}


@router.post("/api/dashboard/action/send-hacker")
def action_send_hacker():
    return {"results": [r.__dict__ for r in demo_actions.send_hacker(1)]}


@router.post("/api/dashboard/action/auto-play")
def action_auto_play():
    return demo_actions.run_full_demo()


@router.post("/api/dashboard/action/scan-suspect-model")
def action_scan_suspect_model():
    global _last_scan
    _last_scan = demo_actions.run_scan()
    return _last_scan


@router.post("/api/dashboard/action/attack-customer-b")
def action_attack_customer_b():
    result = demo_actions.attack_customer_b()
    if result.status_code == 0:
        raise HTTPException(status_code=502, detail=result.detail)
    return {"result": result.__dict__}


@router.post("/api/dashboard/action/reset")
def action_reset():
    global _last_scan, _bot_counter, _devci_counter
    demo_actions.reset_demo()
    _last_scan = None
    _bot_counter = 0
    _devci_counter = 0
    return {"status": "reset"}
