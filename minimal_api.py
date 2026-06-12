#!/usr/bin/env python3
"""Minimal Candy AI API - personas + avatars only."""

import json
import mimetypes
import sys
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

@app.get("/api/personas")
def api_personas():
    personas = load_personas()
    return {
        "personas": {
            k: {"name": v["name"], "type": v["type"], "avatar": f"/avatar/{v.get('avatar', '')}"}
            for k, v in personas.items()
        },
        "active": "nova"
    }

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
