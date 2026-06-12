#!/usr/bin/env python3
"""Minimal Candy AI API - personas + avatars only."""

import json
import mimetypes
import sys
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

try:
    from src.studio_fusion import (
        create_studio_job,
        get_studio_job,
        studio_capabilities,
        studio_health,
    )
except Exception as exc:
    print(f"Studio fusion unavailable: {exc}")
    create_studio_job = None
    get_studio_job = None
    studio_capabilities = None
    studio_health = None

app = FastAPI(title="Candy AI Clone - Minimal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load personas
AVATAR_DIR = Path("/app/avatar_engine/identities")
PERSONAS_FILE = Path("/app/avatar_engine/nova_roleplay_brain.py")
ACTIVE_PERSONA = {"key": "nova"}
CHAT_HISTORY: dict[str, list[dict[str, str]]] = {}
USER_PREFS: dict[str, dict] = {}
SESSION_PERSONAS: dict[str, str] = {}

def load_personas():
    """Extract personas from the brain file."""
    try:
        sys.path.insert(0, "/app")
        sys.path.insert(0, "/app/avatar_engine")
        from nova_roleplay_brain import PERSONAS
        return PERSONAS
    except Exception as e:
        print(f"Error loading personas: {e}")
        return {}

def active_persona():
    personas = load_personas()
    key = ACTIVE_PERSONA.get("key") or "nova"
    if key not in personas:
        key = next(iter(personas), "nova")
        ACTIVE_PERSONA["key"] = key
    return key, personas.get(key, {"name": "Nova", "type": "companion"})

@app.get("/api/personas")
def api_personas():
    personas = load_personas()
    active_key, _ = active_persona()
    return {
        "personas": {
            k: {"name": v["name"], "type": v["type"], "avatar": f"/avatar/{v.get('avatar', '')}"}
            for k, v in personas.items()
        },
        "active": active_key
    }

@app.post("/api/switch")
async def api_switch(request: Request):
    data = await request.json()
    persona_key = data.get("persona", "nova")
    personas = load_personas()
    if persona_key not in personas:
        return JSONResponse({"error": "unknown persona"}, status_code=404)
    ACTIVE_PERSONA["key"] = persona_key
    return {"status": "ok", "active": persona_key, "persona": personas[persona_key]}

@app.get("/api/history/{session_id}")
def api_history(session_id: str):
    return {"history": CHAT_HISTORY.get(session_id, [])}

@app.post("/api/clear/{session_id}")
def api_clear(session_id: str):
    CHAT_HISTORY.pop(session_id, None)
    SESSION_PERSONAS.pop(session_id, None)
    return {"status": "cleared"}

@app.post("/api/chat/nsfw")
async def api_chat(request: Request):
    data = await request.json()
    message = str(data.get("message", "")).strip()
    session_id = data.get("session_id", "nsfw")
    if not message:
        return JSONResponse({"error": "empty message"}, status_code=400)

    personas = load_personas()
    persona_key = data.get("persona_key") or SESSION_PERSONAS.get(session_id) or ACTIVE_PERSONA.get("key") or "nova"
    if persona_key not in personas:
        persona_key = next(iter(personas), "nova")
    SESSION_PERSONAS[session_id] = persona_key
    key, persona = persona_key, personas.get(persona_key, {"name": "Nova", "type": "companion"})
    persona_name = persona.get("name", key.title())
    history = CHAT_HISTORY.setdefault(session_id, [])
    history.append({"role": "user", "text": message, "created_at": str(time.time())})

    response = (
        f"Hey, ik ben {persona_name}. Ik ben online in deze clone. "
        "Chat werkt nu lokaal; de volgende stap is dit koppelen aan je echte Hermes/model route."
    )
    history.append({"role": "ai", "text": response, "created_at": str(time.time())})
    return {
        "response": response,
        "persona": persona_name,
        "session_id": session_id,
        "status": "ok",
    }

@app.get("/api/user/preferences/{user_id}")
def api_get_user_preferences(user_id: str):
    return USER_PREFS.get(user_id, {
        "preferences": {},
        "boundaries": {},
    })

@app.post("/api/user/preferences")
async def api_set_user_preferences(request: Request):
    data = await request.json()
    user_id = data.get("user_id", "anonymous")
    boundaries = {
        key: value
        for key, value in data.items()
        if key.startswith("boundary.")
    }
    USER_PREFS[user_id] = {
        "preferences": data,
        "boundaries": boundaries,
    }
    return {"status": "success", "message": "Preferences updated"}

@app.get("/api/user/learning/{user_id}")
def api_user_learning(user_id: str):
    interaction_count = sum(len(history) for history in CHAT_HISTORY.values())
    return {
        "interaction_count": interaction_count,
        "media_request_count": 0,
        "media_request_rate": 0,
        "learning_confidence": 0.5,
    }

@app.get("/api/user/ready_content/{user_id}")
def api_ready_content(user_id: str):
    return {"user_id": user_id, "ready_content": []}

@app.get("/api/user/accuracy/{user_id}")
def api_user_accuracy(user_id: str):
    return {
        "user_id": user_id,
        "accuracy": {
            "accuracy": 0,
            "total_predictions": 0,
            "accepted_predictions": 0,
            "accuracy_rate": 0,
        },
    }

@app.post("/api/content/deliver")
async def api_content_deliver(request: Request):
    data = await request.json()
    return {"status": "success", "content_id": data.get("content_id")}

@app.get("/api/avatar/lemonslice/health")
def api_avatar_health(persona_key: str | None = None):
    return {
        "status": "unavailable",
        "configured": False,
        "persona_key": persona_key,
        "missing": ["LEMONSLICE_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"],
    }

@app.post("/api/avatar/lemonslice/session")
async def api_avatar_session(request: Request):
    return JSONResponse({
        "error": "lemonslice_not_configured",
        "missing": ["LEMONSLICE_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"],
    }, status_code=400)

@app.post("/api/avatar/lemonslice/session/{session_id}/control")
async def api_avatar_control(session_id: str, request: Request):
    return {"status": "ignored", "session_id": session_id}

@app.get("/avatar/{filename}")
def get_avatar(filename: str):
    path = AVATAR_DIR / filename
    if path.exists() and path.is_file():
        media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return FileResponse(
            path,
            media_type=media_type,
            filename=filename,
            headers={"Cache-Control": "public, max-age=3600"}
        )
    return JSONResponse({"error": "not found"}, status_code=404)

@app.get("/health")
def health():
    studio = studio_health() if studio_health else {"status": "unavailable"}
    return {"status": "ok", "personas": len(load_personas()), "studio": studio}

@app.get("/api/studio/capabilities")
def api_studio_capabilities():
    if not studio_capabilities:
        return JSONResponse({"error": "studio unavailable"}, status_code=503)
    return studio_capabilities()

@app.post("/api/studio/jobs")
async def api_create_studio_job(request: Request):
    if not create_studio_job:
        return JSONResponse({"error": "studio unavailable"}, status_code=503)
    try:
        payload = await request.json()
        return create_studio_job(payload)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

@app.get("/api/studio/jobs/{job_id}")
def api_get_studio_job(job_id: str):
    if not get_studio_job:
        return JSONResponse({"error": "studio unavailable"}, status_code=503)
    job = get_studio_job(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    return job

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8069, log_level="info")
