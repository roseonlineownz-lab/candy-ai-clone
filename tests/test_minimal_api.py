from fastapi.testclient import TestClient

import minimal_api
from src import studio_fusion


def test_minimal_api_supports_card_to_chat_flow(monkeypatch):
    personas = {
        "nova": {"name": "Nova", "type": "girlfriend", "avatar": "nova.jpg"},
        "airi": {"name": "Airi", "type": "companion", "avatar": "airi.jpg"},
    }
    monkeypatch.setattr(minimal_api, "load_personas", lambda: personas)
    minimal_api.ACTIVE_PERSONA["key"] = "nova"
    minimal_api.CHAT_HISTORY.clear()

    client = TestClient(minimal_api.app)

    listing = client.get("/api/personas")
    assert listing.status_code == 200
    assert listing.json()["active"] == "nova"

    switched = client.post("/api/switch", json={"persona": "airi"})
    assert switched.status_code == 200
    assert switched.json()["active"] == "airi"

    reply = client.post("/api/chat/nsfw", json={
        "message": "hey",
        "session_id": "x_airi",
        "persona_key": "airi",
        "user_id": "test",
    })
    assert reply.status_code == 200
    assert reply.json()["status"] == "ok"
    assert "Airi" in reply.json()["response"]

    history = client.get("/api/history/x_airi")
    assert history.status_code == 200
    assert [item["role"] for item in history.json()["history"]] == ["user", "ai"]

    cleared = client.post("/api/clear/x_airi")
    assert cleared.status_code == 200
    assert client.get("/api/history/x_airi").json()["history"] == []

    prefs = client.get("/api/user/preferences/test")
    assert prefs.status_code == 200
    assert prefs.json()["preferences"] == {}

    accuracy = client.get("/api/user/accuracy/test")
    assert accuracy.status_code == 200
    assert accuracy.json()["accuracy"]["accuracy"] == 0
    assert accuracy.json()["accuracy"]["accuracy_rate"] == 0

    avatar = client.get("/api/avatar/lemonslice/health")
    assert avatar.status_code == 200
    assert avatar.json()["configured"] is False


def test_minimal_api_studio_job_retry_cancel_gallery(monkeypatch, tmp_path):
    monkeypatch.setattr(studio_fusion, "STATE_DIR", tmp_path)
    monkeypatch.setattr(studio_fusion, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(studio_fusion, "IDEMPOTENCY_FILE", tmp_path / "idempotency.json")
    monkeypatch.setattr(studio_fusion, "_http_ok", lambda url, timeout=0.5: False)
    monkeypatch.setattr(minimal_api, "create_studio_job", studio_fusion.create_studio_job)
    monkeypatch.setattr(minimal_api, "get_studio_job", studio_fusion.get_studio_job)
    monkeypatch.setattr(minimal_api, "cancel_studio_job", studio_fusion.cancel_studio_job)
    monkeypatch.setattr(minimal_api, "list_studio_jobs", studio_fusion.list_studio_jobs)
    monkeypatch.setattr(minimal_api, "get_studio_gallery", studio_fusion.get_studio_gallery)

    client = TestClient(minimal_api.app)

    payload = {
        "mode": "image",
        "prompt": "studio portrait",
        "idempotency_key": "fixed-retry-key",
    }
    first = client.post("/api/studio/jobs", json=payload)
    second = client.post("/api/studio/jobs", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["deduplicated"] is True

    job_id = first.json()["id"]
    cancelled = client.post(f"/api/studio/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    listing = client.get("/api/studio/jobs")
    assert listing.status_code == 200
    assert any(job["id"] == job_id for job in listing.json()["jobs"])

    gallery = client.get("/api/studio/gallery")
    assert gallery.status_code == 200
    assert any(item["id"] == job_id for item in gallery.json()["items"])
