from fastapi.testclient import TestClient

from src import nova_candy_app


def test_personalization_endpoints(monkeypatch):
    def fake_route_chat(*args, **kwargs):
        return "Hallo, ik ben online.", "test-model"

    monkeypatch.setattr(nova_candy_app, "route_chat", fake_route_chat)
    client = TestClient(nova_candy_app.app)
    user_id = "test_user_integration_999"

    payload = {
        "user_id": user_id,
        "intensity": 0.75,
        "visual_preference": 1.0,
        "boundary.pain": "hard",
        "boundary.bondage": "hard",
    }

    response = client.post("/api/user/preferences", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    response = client.get(f"/api/user/preferences/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["boundaries"].get("boundary.pain") == "hard"
    assert data["boundaries"].get("boundary.bondage") == "hard"

    chat_payload = {
        "message": "bondage",
        "session_id": "test_session_nsfw",
        "user_id": user_id,
    }
    response = client.post("/api/chat/nsfw", json=chat_payload)
    assert response.status_code == 200
    chat_data = response.json()
    assert chat_data.get("status") == "boundary_violation"
    assert "Ik voel me hier niet comfortabel bij" in chat_data.get("response")

    chat_payload = {
        "message": "Hallo, hoe gaat het?",
        "session_id": "test_session_nsfw",
        "user_id": user_id,
    }
    response = client.post("/api/chat/nsfw", json=chat_payload)
    assert response.status_code == 200
    chat_data = response.json()
    assert chat_data.get("status") != "boundary_violation"
    assert "response" in chat_data

    response = client.get(f"/api/user/learning/{user_id}")
    assert response.status_code == 200
    assert response.json()["interaction_count"] >= 1
