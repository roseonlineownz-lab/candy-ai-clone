from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import load_dotenv


ENV_PATHS = (
    Path(__file__).resolve().parent.parent / ".env",
    Path.home() / ".env",
    Path.home() / ".config/novamaster/livekit.env",
    Path.home() / ".hermes/livekit.env",
    Path.home() / ".hermes/.env",
)

LEMONSLICE_RPC_TOPIC = "lemonslice"
LEMONSLICE_READY_TYPE = "bot_ready"


class LemonSliceConfigError(RuntimeError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("Missing LemonSlice/LiveKit configuration: " + ", ".join(missing))


def load_runtime_env() -> None:
    for env_path in ENV_PATHS:
        if env_path.exists():
            load_dotenv(env_path, override=False)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _persona_env(name: str, persona_key: str | None) -> str:
    if persona_key:
        normalized = "".join(ch if ch.isalnum() else "_" for ch in persona_key.upper())
        value = _env(f"{name}_{normalized}")
        if value:
            return value
    return _env(name)


def _public_config(persona_key: str | None = None) -> dict[str, Any]:
    load_runtime_env()
    agent_id = _persona_env("LEMONSLICE_AGENT_ID", persona_key)
    agent_image_url = _persona_env("LEMONSLICE_AGENT_IMAGE_URL", persona_key)
    return {
        "api_key_present": bool(_env("LEMONSLICE_API_KEY")),
        "livekit_url_present": bool(_env("LIVEKIT_URL")),
        "livekit_api_key_present": bool(_env("LIVEKIT_API_KEY")),
        "livekit_api_secret_present": bool(_env("LIVEKIT_API_SECRET")),
        "agent_id_present": bool(agent_id),
        "agent_image_url_present": bool(agent_image_url),
        "agent_source": "agent_id" if agent_id else ("agent_image_url" if agent_image_url else None),
        "rpc_topic": LEMONSLICE_RPC_TOPIC,
        "ready_type": LEMONSLICE_READY_TYPE,
        "expected_warm_start_seconds": 5,
        "max_session_seconds": 3600,
    }


def get_lemonslice_health(persona_key: str | None = None) -> dict[str, Any]:
    config = _public_config(persona_key)
    missing = required_missing(persona_key)
    return {
        "configured": not missing,
        "missing": missing,
        **config,
    }


def required_missing(persona_key: str | None = None) -> list[str]:
    load_runtime_env()
    missing: list[str] = []
    for key in ("LEMONSLICE_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        if not _env(key):
            missing.append(key)
    if not (_persona_env("LEMONSLICE_AGENT_ID", persona_key) or _persona_env("LEMONSLICE_AGENT_IMAGE_URL", persona_key)):
        missing.append("LEMONSLICE_AGENT_ID or LEMONSLICE_AGENT_IMAGE_URL")
    return missing


def mint_livekit_token(room: str, identity: str, name: str, ttl_seconds: int = 3600) -> str:
    load_runtime_env()
    api_key = _env("LIVEKIT_API_KEY")
    api_secret = _env("LIVEKIT_API_SECRET")
    if not api_key or not api_secret:
        raise LemonSliceConfigError(["LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"])

    now = int(time.time())
    payload = {
        "iss": api_key,
        "sub": identity,
        "name": name,
        "nbf": now - 5,
        "exp": now + ttl_seconds,
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
    }
    return jwt.encode(payload, api_secret, algorithm="HS256")


def _avatar_prompt(persona: dict[str, Any] | None, override: str | None = None) -> str:
    if override:
        return override[:500]
    name = (persona or {}).get("name") or "Nova"
    return f"{name} is present, warm, expressive, and naturally conversational."


class LemonSliceLiveKitBridge:
    def __init__(self, api_base: str | None = None):
        self.api_base = (api_base or _env("LEMONSLICE_API_BASE", "https://lemonslice.com/api")).rstrip("/")

    async def create_session(
        self,
        *,
        persona_key: str | None,
        persona: dict[str, Any] | None,
        agent_prompt: str | None = None,
        agent_idle_prompt: str | None = None,
        idle_timeout: int | None = None,
        response_done_timeout: float | None = None,
        simulcast: bool = True,
    ) -> dict[str, Any]:
        missing = required_missing(persona_key)
        if missing:
            raise LemonSliceConfigError(missing)

        room = f"candy-avatar-{persona_key or 'persona'}-{uuid.uuid4().hex[:10]}"
        browser_identity = f"candy-ui-{uuid.uuid4().hex[:8]}"
        lemonslice_identity = f"lemonslice-avatar-{uuid.uuid4().hex[:8]}"
        browser_token = mint_livekit_token(room, browser_identity, "Candy UI")
        lemonslice_token = mint_livekit_token(room, lemonslice_identity, "LemonSlice Avatar")

        payload: dict[str, Any] = {
            "transport_type": "livekit",
            "agent_prompt": _avatar_prompt(persona, agent_prompt),
            "agent_idle_prompt": agent_idle_prompt or "calm, attentive, and ready to respond",
            "idle_timeout": idle_timeout if idle_timeout is not None else 60,
            "simulcast": simulcast,
            "properties": {
                "livekit_url": _env("LIVEKIT_URL"),
                "livekit_token": lemonslice_token,
            },
        }
        if response_done_timeout is not None:
            payload["response_done_timeout"] = response_done_timeout

        agent_id = _persona_env("LEMONSLICE_AGENT_ID", persona_key)
        agent_image_url = _persona_env("LEMONSLICE_AGENT_IMAGE_URL", persona_key)
        if agent_id:
            payload["agent_id"] = agent_id
        else:
            payload["agent_image_url"] = agent_image_url

        headers = {
            "X-API-Key": _env("LEMONSLICE_API_KEY"),
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.api_base}/liveai/sessions", headers=headers, json=payload)

        if response.status_code >= 400:
            detail: Any
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise RuntimeError(f"LemonSlice session create failed: HTTP {response.status_code}: {detail}")

        data = response.json()
        return {
            "session_id": data.get("session_id"),
            "room": room,
            "livekit_url": _env("LIVEKIT_URL"),
            "participant_token": browser_token,
            "participant_identity": browser_identity,
            "rpc_topic": LEMONSLICE_RPC_TOPIC,
            "ready_type": LEMONSLICE_READY_TYPE,
            "state": "ringing",
            "expected_warm_start_seconds": 5,
        }

    async def control_session(self, session_id: str, event: str = "terminate") -> dict[str, Any]:
        load_runtime_env()
        if not _env("LEMONSLICE_API_KEY"):
            raise LemonSliceConfigError(["LEMONSLICE_API_KEY"])
        headers = {
            "X-API-Key": _env("LEMONSLICE_API_KEY"),
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.api_base}/liveai/sessions/{session_id}/control",
                headers=headers,
                json={"event": event},
            )
        if response.status_code >= 400:
            raise RuntimeError(f"LemonSlice control failed: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError:
            return {"success": True}
