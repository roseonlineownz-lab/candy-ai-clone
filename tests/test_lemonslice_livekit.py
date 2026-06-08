import jwt

from src import lemonslice_livekit


def test_lemonslice_health_reports_missing_without_secret_values(monkeypatch):
    monkeypatch.setattr(lemonslice_livekit, "ENV_PATHS", ())
    for key in (
        "LEMONSLICE_API_KEY",
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "LEMONSLICE_AGENT_ID",
        "LEMONSLICE_AGENT_IMAGE_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    health = lemonslice_livekit.get_lemonslice_health("nova")

    assert health["configured"] is False
    assert "LEMONSLICE_API_KEY" in health["missing"]
    assert "LIVEKIT_API_SECRET" in health["missing"]
    assert health["api_key_present"] is False
    assert "api_key" not in health


def test_mint_livekit_token_grants_room_access(monkeypatch):
    monkeypatch.setattr(lemonslice_livekit, "ENV_PATHS", ())
    monkeypatch.setenv("LIVEKIT_API_KEY", "lk_test_key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "lk_test_secret")

    token = lemonslice_livekit.mint_livekit_token("room-a", "browser-a", "Candy UI", ttl_seconds=120)
    claims = jwt.decode(token, "lk_test_secret", algorithms=["HS256"], audience=None, options={"verify_aud": False})

    assert claims["iss"] == "lk_test_key"
    assert claims["sub"] == "browser-a"
    assert claims["name"] == "Candy UI"
    assert claims["video"]["room"] == "room-a"
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["canSubscribe"] is True
    assert claims["video"]["canPublishData"] is True
