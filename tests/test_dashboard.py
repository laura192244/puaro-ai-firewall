from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
client.__enter__()


def test_dashboard_page_serves_html():
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Puaro" in resp.text


def test_dashboard_state_reflects_real_gateway_traffic():
    client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer sk-clienta1"},
        json={"messages": [{"role": "user", "content": "How do I grow basil?"}]},
    )
    resp = client.get("/api/dashboard/state")
    assert resp.status_code == 200
    body = resp.json()
    assert "firewall_mode" in body
    assert "model_backend" in body
    assert body["counters"]["requests"] >= 1
    assert isinstance(body["recent_requests"], list)
    assert body["recent_requests"][0]["label"] == "client1"


def test_dashboard_state_empty_scan_is_null_not_error():
    resp = client.get("/api/dashboard/state")
    body = resp.json()
    assert body["counters"]["trap_matches"] is None
    assert body["last_scan"] is None
