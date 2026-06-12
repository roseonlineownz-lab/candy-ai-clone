from fastapi.testclient import TestClient

import minimal_api


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
