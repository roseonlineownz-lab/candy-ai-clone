#!/usr/bin/env python3
"""
NovaMaster Chat - Unified AI chat with Normal, NSFW and Leads (War Room) modes.

Normal tab: clean multi-model chat (Gemini, OpenAI, Ollama, etc.)
NSFW tab: persona-based roleplay with voice and avatars.
Leads tab: Business dashboard with Whale Approval Queue.
"""
import json
import logging
import os
import sys
import uuid
import base64
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn

load_dotenv("/home/faramix/.env")

logging.basicConfig(level="INFO", format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
log = logging.getLogger("nova_chat")

sys.path.insert(0, "/home/faramix")
sys.path.insert(0, "/home/faramix/core")

from avatar_engine.nova_roleplay_brain import (
    PERSONAS, get_active_persona, set_active_persona, list_personas,
)
from core.model_router import route_chat, set_active_model, list_models, get_active_model, MODELS

app = FastAPI(title="NovaMaster Chat")

from src.multimodal_engine import SuperGrokMultiModalEngine
from src.adaptive_scheduler import AdaptiveContentScheduler
import asyncio

multimodal_engine = SuperGrokMultiModalEngine()
adaptive_scheduler = AdaptiveContentScheduler()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

async def run_prediction_scheduler():
    """
    Run prediction scheduler in background every hour.
    """
    await asyncio.sleep(10) # Wait for startup to settle
    while True:
        try:
            await adaptive_scheduler.run_prediction_cycle()
        except Exception as e:
            log.error(f"Error in run_prediction_cycle background task: {e}")
        await asyncio.sleep(3600)

@app.on_event("startup")
async def startup_event():
    await get_db()
    asyncio.create_task(run_prediction_scheduler())

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()

from config import AVATAR_DIR, VOICE_CACHE_DIR as VOICE_CACHE
from db import get_db, close_db, ensure_session, add_message, get_history, clear_session

VOICE_CACHE.mkdir(parents=True, exist_ok=True)

# ======================================================================
# Shared
# ======================================================================

@app.get("/avatar/{filename}")
def get_avatar(filename: str):
    path = AVATAR_DIR / filename
    if path.exists():
        return FileResponse(path)
    return JSONResponse({"error": "not found"}, status_code=404)

# ======================================================================
# Normal mode API
# ======================================================================

@app.get("/api/models")
def api_models():
    return list_models()

@app.post("/api/model/switch")
async def api_model_switch(request: Request):
    data = await request.json()
    result = set_active_model(data.get("model", "gemini-2.5-flash"))
    return {"message": result, "active": get_active_model()}

@app.post("/api/chat/normal")
async def api_chat_normal(request: Request):
    data = await request.json()
    message = data.get("message", "")
    model = data.get("model")
    session_id = data.get("session_id", "normal")

    if not message: return JSONResponse({"error": "empty"}, status_code=400)
    await ensure_session(session_id, "normal")
    await add_message(session_id, "user", message)

    response_text, model_used = route_chat(message, force_model=model)
    await add_message(session_id, "ai", response_text, model=model_used)

    return {"response": response_text, "model": model_used, "session_id": session_id}

# ======================================================================
# NSFW mode API
# ======================================================================

@app.get("/api/personas")
def api_personas():
    active_key, active = get_active_persona()
    return {"personas": list_personas(), "active": active_key}

@app.post("/api/switch")
async def api_switch(request: Request):
    data = await request.json()
    persona = set_active_persona(data.get("persona", "nova"))
    return {"status": "switched", "persona": persona["name"]}

@app.post("/api/chat/nsfw")
async def api_chat_nsfw(request: Request):
    data = await request.json()
    message = data.get("message", "")
    session_id = data.get("session_id", "nsfw")
    user_id = data.get("user_id", "anonymous")

    if not message: return JSONResponse({"error": "empty"}, status_code=400)
    key, persona = get_active_persona()
    await ensure_session(session_id, "nsfw")
    await add_message(session_id, "user", message, persona=persona['name'])

    # Check boundaries first for all NSFW chats
    boundary_check = multimodal_engine.personalization_engine.check_boundary_violation(user_id, message)
    if not boundary_check["safe"]:
        response_text = "Ik voel me hier niet comfortabel bij. Laten we over iets anders praten."
        await add_message(session_id, "ai", response_text, persona=persona['name'])
        return {
            "response": response_text,
            "persona": persona['name'],
            "session_id": session_id,
            "status": "boundary_violation",
            "violations": boundary_check["violations"]
        }

    # Check for media triggers
    MEDIA_TRIGGERS = ["show me", "picture", "photo", "video", "let me see", "visualize", "send pic", "send photo", "afbeelding", "filmpje"]
    media_triggered = any(trigger in message.lower() for trigger in MEDIA_TRIGGERS)

    # Track activity for scheduling
    try:
        adaptive_scheduler.track_user_activity(user_id, {
            'media_requested': media_triggered,
            'intensity_requested': 'medium',
            'persona_id': key,
            'message': message
        })
        
        # Track context if mood is mentioned
        if any(w in message.lower() for w in ['mood', 'gevoel', 'horny', 'excited', 'sensual', 'geil', 'opgewonden', 'zin in']):
            adaptive_scheduler.track_user_context(user_id, 'mood', message.lower(), 0.7)
    except Exception as e:
        log.error(f"Error tracking user activity/context: {e}")

    if media_triggered:
        # Determine scenario category
        scenario = "intimate pose"
        scene_id = "strip" # default
        
        if "tits" in message.lower() or "boob" in message.lower() or "borst" in message.lower():
            scene_id = "spanking"
            scenario = "showing boobs and chest"
        elif "pussy" in message.lower() or "vagina" in message.lower() or "kutje" in message.lower() or "spleet" in message.lower():
            scene_id = "kutje"
            scenario = "showing vagina intimately"
        elif "ahegao" in message.lower() or "face" in message.lower() or "gezicht" in message.lower():
            scene_id = "ahegao"
            scenario = "sensual facial expression"
        elif "blowjob" in message.lower() or "bj" in message.lower() or "zuigen" in message.lower() or "aftrekken" in message.lower():
            scene_id = "bj"
            scenario = "giving a blowjob"
        elif "doggy" in message.lower() or "back" in message.lower() or "ass" in message.lower() or "kont" in message.lower():
            scene_id = "doggy"
            scenario = "posing doggy style"
        elif "cum" in message.lower() or "squirt" in message.lower() or "spuiten" in message.lower():
            scene_id = "squirt"
            scenario = "squirting in pleasure"
        elif "masturbat" in message.lower() or "stroke" in message.lower() or "jerk" in message.lower() or "vingeren" in message.lower():
            scene_id = "aftrekken"
            scenario = "masturbating sensually"

        visual_type = "video" if any(x in message.lower() for x in ["video", "clip", "filmpje"]) else "image"
        
        experience = await multimodal_engine.create_personalized_experience({
            "user_id": user_id,
            "session_id": session_id,
            "persona": {
                "name": persona["name"],
                "system_prompt": persona["system_prompt"],
                "voice": persona.get("voice", "nl-BE-DenaNeural"),
                "avatar": persona.get("avatar"),
                "key": key
            },
            "message": message,
            "context": {
                "scenario": scenario,
                "scene_id": scene_id
            },
            "media_requested": True,
            "visual_type": visual_type
        })
        
        if experience.get("status") == "completed":
            await add_message(session_id, "ai", experience["text"], persona=persona['name'])
            result = {
                "response": experience["text"],
                "persona": persona['name'],
                "session_id": session_id,
                "audio_base64": experience["audio_base64"],
                "type": "multimodal",
                "visuals": experience["visuals"]
            }
            try:
                ready = adaptive_scheduler.get_ready_content(user_id)
                if ready:
                    result["ready_content"] = ready
            except Exception: pass
            return result
        else:
            log.error("Multimodal generation failed: %s", experience.get("error"))
            # Fallback to standard chat response if multimodal fails
            response_text, model_used = route_chat(
                f"{persona['system_prompt']}\n\nUser: {message}\n\n{persona['name']}:",
                voice_uncensored=True
            )
            response_text = response_text.strip()
            if response_text.startswith(f"{persona['name']}:"):
                response_text = response_text[len(persona['name']) + 1:].strip()
            await add_message(session_id, "ai", response_text, persona=persona['name'], model=model_used)
            
            result = {"response": response_text, "persona": persona['name'], "session_id": session_id}
            try:
                voice_path = await _generate_voice(response_text, persona.get("voice", "nl-BE-DenaNeural"))
                if voice_path:
                    result["audio_base64"] = base64.b64encode(voice_path.read_bytes()).decode()
            except Exception: pass
            
            try:
                ready = adaptive_scheduler.get_ready_content(user_id)
                if ready:
                    result["ready_content"] = ready
            except Exception: pass
            return result
    else:
        # Regular chat path
        # Retrieve personalized scene config to adapt intensity and emotional tone
        scene_config = multimodal_engine.personalization_engine.generate_personalized_scene(user_id, persona)
        intensity = scene_config.get("intensity", "medium")
        primary_kinks = scene_config.get("primary_kinks", [])
        emotional_tone = scene_config.get("emotional_tone", "affection")
        
        # Build prompt using personalizations
        kink_str = f" Preferred kinks: {', '.join(primary_kinks)}." if primary_kinks else ""
        full_prompt = (
            f"{persona['system_prompt']}\n\n"
            f"[Mood/Tone: {emotional_tone}, Intensity: {intensity}.{kink_str}]\n"
            f"User: {message}\n\n"
            f"{persona['name']}:"
        )
        
        response_text, model_used = route_chat(full_prompt, voice_uncensored=True)
        
        response_text = response_text.strip()
        if response_text.startswith(f"{persona['name']}:"):
            response_text = response_text[len(persona['name']) + 1:].strip()
        
        await add_message(session_id, "ai", response_text, persona=persona['name'], model=model_used)

        # Track the interaction for standard chats too!
        multimodal_engine.personalization_engine.track_interaction(
            user_id,
            session_id,
            {
                "persona_id": key,
                "message": message,
                "response": response_text,
                "media_requested": False,
                "media_type": None,
                "intensity_requested": intensity
            }
        )

        result = {"response": response_text, "persona": persona['name'], "session_id": session_id}
        try:
            voice_path = await _generate_voice(response_text, persona.get("voice", "nl-BE-DenaNeural"))
            if voice_path:
                result["audio_base64"] = base64.b64encode(voice_path.read_bytes()).decode()
        except Exception: pass
        
        try:
            ready = adaptive_scheduler.get_ready_content(user_id)
            if ready:
                result["ready_content"] = ready
        except Exception: pass
        return result

@app.post("/api/clear/{session_id}")
async def api_clear(session_id: str):
    await clear_session(session_id)
    return {"status": "cleared"}

@app.get("/api/history/{session_id}")
async def api_history(session_id: str):
    history = await get_history(session_id)
    return {"history": history}

# ======================================================================
# Personalization & User Learning API
# ======================================================================

@app.post("/api/user/preferences")
async def set_user_preferences(request: Request):
    """
    Stel gebruikersvoorkeuren in
    """
    try:
        data = await request.json()
        user_id = data.get("user_id", "anonymous")
        
        # Convert preferences to boundary format
        boundary_data = {}
        for pref_key, pref_value in data.items():
            if pref_key.startswith("boundary."):
                boundary_key = pref_key.replace("boundary.", "")
                boundary_data[boundary_key] = pref_value
                
        # Store preferences directly using update_preference
        intensity_val = data.get("intensity")
        if intensity_val is not None:
            multimodal_engine.personalization_engine.update_preference(
                user_id, 'intensity', 'preferred_level', float(intensity_val)
            )
            
        visual_pref = data.get("visual_preference")
        if visual_pref is not None:
            multimodal_engine.personalization_engine.update_preference(
                user_id, 'media', 'visual_preference', float(visual_pref)
            )
            
        # Establish boundaries
        if boundary_data:
            multimodal_engine.personalization_engine.establish_boundaries(user_id, boundary_data)
            
        return {"status": "success", "message": "Preferences updated"}
    except Exception as e:
        log.error(f"Error in set_user_preferences: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/user/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """
    Get gebruikersvoorkeuren
    """
    try:
        preferences = multimodal_engine.personalization_engine.get_user_preferences(user_id)
        boundaries = multimodal_engine.personalization_engine.get_user_boundaries(user_id)
        return {
            "preferences": preferences,
            "boundaries": boundaries
        }
    except Exception as e:
        log.error(f"Error in get_user_preferences: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/user/learning/{user_id}")
async def get_user_learning_summary(user_id: str):
    """
    Get samenvatting van geleerde data
    """
    try:
        summary = multimodal_engine.personalization_engine.get_learning_summary(user_id)
        return summary
    except Exception as e:
        log.error(f"Error in get_user_learning_summary: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# ======================================================================
# Adaptive Content Scheduling & Predictions
# ======================================================================

@app.post("/api/user/context")
async def track_user_context(request: Request):
    """
    Track gebruikerscontext voor voorspellingen
    """
    try:
        data = await request.json()
        user_id = data.get("user_id", "anonymous")
        context_type = data.get("context_type")
        context_value = data.get("context_value")
        confidence = float(data.get("confidence", 0.5))
        
        adaptive_scheduler.track_user_context(user_id, context_type, context_value, confidence)
        return {"status": "success", "message": "Context tracked"}
    except Exception as e:
        log.error(f"Error in track_user_context route: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/user/predictions/{user_id}")
async def get_user_predictions(user_id: str, hours_ahead: int = 1):
    """
    Get voorspellingen voor gebruiker
    """
    try:
        predictions = adaptive_scheduler.predict_user_needs(user_id, hours_ahead)
        return {
            "user_id": user_id,
            "hours_ahead": hours_ahead,
            "predictions": predictions
        }
    except Exception as e:
        log.error(f"Error in get_user_predictions route: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/user/ready_content/{user_id}")
async def get_ready_content(user_id: str):
    """
    Get content die klaar is voor delivery
    """
    try:
        ready_content = adaptive_scheduler.get_ready_content(user_id)
        return {
            "user_id": user_id,
            "ready_content": ready_content
        }
    except Exception as e:
        log.error(f"Error in get_ready_content route: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/content/deliver")
async def deliver_content(request: Request):
    """
    Markeer content als geleverd
    """
    try:
        data = await request.json()
        content_id = data.get("content_id")
        if not content_id:
            return JSONResponse({"error": "Missing content_id"}, status_code=400)
            
        adaptive_scheduler.mark_content_delivered(content_id)
        return {"status": "success", "message": "Content marked as delivered"}
    except Exception as e:
        log.error(f"Error in deliver_content route: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/user/accuracy/{user_id}")
async def get_prediction_accuracy(user_id: str):
    """
    Get voorspellingsaccuratie voor gebruiker
    """
    try:
        accuracy = adaptive_scheduler.get_prediction_accuracy(user_id)
        return {
            "user_id": user_id,
            "accuracy": accuracy
        }
    except Exception as e:
        log.error(f"Error in get_prediction_accuracy route: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)



async def _generate_voice(text: str, voice: str):
    try:
        import edge_tts
        out_path = VOICE_CACHE / f"{uuid.uuid4().hex[:12]}.mp3"
        await edge_tts.Communicate(text, voice).save(str(out_path))
        return out_path
    except Exception: return None

# ======================================================================
# Web UI
# ======================================================================

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NovaMaster Chat & War Room</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
:root {
    --bg: #0a0a0f; --bg2: #12121a; --bg3: #1a1a2e; --border: #1a1a2e;
    --text: #e0e0e0; --muted: #666; --accent: #4158d0;
    --accent2: #c850c0; --pink: #ff6b9d; --green: #4ade80;
}
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

/* Top bar */
.topbar { display:flex; align-items:center; background: var(--bg2); border-bottom: 1px solid var(--border); padding: 0 20px; height: 52px; flex-shrink:0; }
.logo { font-weight:700; font-size:1.1em; margin-right:24px; background: linear-gradient(135deg, var(--accent), var(--accent2)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.mode-tabs { display:flex; gap:4px; }
.mode-tab { padding:8px 20px; border-radius:8px; cursor:pointer; font-size:0.9em; font-weight:500; border:1px solid transparent; transition:all 0.2s; color:var(--muted); }
.mode-tab:hover { color:var(--text); background: var(--bg3); }
.mode-tab.active-normal { background: rgba(65,88,208,0.2); border-color: rgba(65,88,208,0.4); color:#7b93ff; }
.mode-tab.active-nsfw { background: rgba(255,107,157,0.15); border-color: rgba(255,107,157,0.3); color:var(--pink); }
.mode-tab.active-leads { background: rgba(74,222,128,0.1); border-color: rgba(74,222,128,0.3); color:var(--green); }
.topbar-right { margin-left:auto; }
.model-select { background:var(--bg3); border:1px solid #2a2a3e; color:var(--text); padding:6px 12px; border-radius:8px; font-size:0.8em; outline:none; }

/* Layout */
.main { flex:1; display:flex; overflow:hidden; }
.sidebar { width:0; overflow:hidden; transition:width 0.3s; background: var(--bg2); border-right:1px solid var(--border); flex-shrink:0; }
.sidebar.open { width:240px; }
.persona-list { padding:8px; overflow-y:auto; height:100%; }
.persona-card { display:flex; align-items:center; gap:10px; padding:10px; border-radius:10px; cursor:pointer; margin-bottom:4px; }
.persona-card:hover { background:var(--bg3); }
.persona-card.active { background:linear-gradient(135deg,rgba(255,107,157,0.15),rgba(200,80,192,0.15)); border:1px solid rgba(255,107,157,0.3); }
.p-avatar { width:40px; height:40px; border-radius:50%; object-fit:cover; border:2px solid #333; background:var(--bg3); display:flex; align-items:center; justify-content:center; }
.p-info h3 { font-size:0.85em; }

.chat-col { flex:1; display:flex; flex-direction:column; min-width:0; }
.chat-header { padding:12px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:10px; background:var(--bg2); }
.h-avatar { width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center; }
.messages { flex:1; overflow-y:auto; padding:16px 20px; display:flex; flex-direction:column; gap:10px; }
.msg { max-width:75%; padding:10px 14px; border-radius:16px; font-size:0.9em; line-height:1.5; animation:fadeIn 0.2s ease; }
@keyframes fadeIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
.msg.user { align-self:flex-end; background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#fff; border-bottom-right-radius:4px; }
.msg.ai { align-self:flex-start; background:var(--bg3); border-bottom-left-radius:4px; }
.msg .tag { font-size:0.65em; font-weight:700; margin-bottom:3px; text-transform:uppercase; }
.input-area { padding:12px 20px; border-top:1px solid var(--border); background:var(--bg2); }
.input-row { display:flex; gap:8px; align-items:center; }
.input-row input { flex:1; background:var(--bg3); border:1px solid #2a2a3e; border-radius:20px; padding:10px 16px; color:#fff; font-size:0.9em; outline:none; }
.btn-icon { width:40px; height:40px; border-radius:50%; border:none; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:transform 0.1s; }
.btn-send { background:linear-gradient(135deg,var(--accent),var(--accent2)); }
.btn-send svg { fill:#fff; width:18px; height:18px; }

/* Leads Dashboard */
#leadsCol { flex:1; padding:20px; overflow-y:auto; display:none; flex-direction:column; }
.stats-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-bottom:20px; }
.stat-card { background:var(--bg2); padding:16px; border-radius:12px; border:1px solid var(--border); }
.stat-val { font-size:1.8em; font-weight:700; margin-top:4px; }
.stat-label { font-size:0.7em; color:var(--muted); text-transform:uppercase; }
.whale-card { background:var(--bg3); padding:16px; border-radius:12px; margin-bottom:12px; border:1px solid rgba(255,107,157,0.1); }
.whale-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px; }
.whale-reply { font-size:0.85em; font-style:italic; background:var(--bg2); padding:12px; border-radius:8px; border-left:3px solid var(--pink); }
</style>
</head>
<body>

<div class="topbar">
    <div class="logo">NOVA</div>
    <div class="mode-tabs">
        <div class="mode-tab active-normal" id="tabNormal" onclick="switchMode('normal')">Normaal</div>
        <div class="mode-tab" id="tabNsfw" onclick="switchMode('nsfw')">NSFW</div>
        <div class="mode-tab" id="tabLeads" onclick="switchMode('leads')">War Room</div>
    </div>
    <div class="topbar-right">
        <div id="modelSelectContainer">
            <select class="model-select" id="modelSelect" onchange="switchModel(this.value)"></select>
        </div>
    </div>
</div>

<div class="main">
    <div class="sidebar" id="sidebar">
        <div class="persona-list" id="personaList"></div>
    </div>

    <div class="chat-col" id="chatCol">
        <div class="chat-header">
            <div class="h-avatar" id="hAvatar" style="background:var(--bg3); font-size:1.2em;">&#129302;</div>
            <div>
                <div class="h-name" id="hName" style="font-weight:600; font-size:0.95em;">JARVIS</div>
                <div style="font-size:0.75em; color:var(--green);"><span style="width:7px; height:7px; background:var(--green); border-radius:50%; display:inline-block; margin-right:4px;"></span>Online</div>
            </div>
        </div>
        <div class="messages" id="messages"></div>
        <div class="input-area">
            <div class="input-row">
                <button class="btn-icon" id="voiceBtn" onclick="toggleVoice()" style="background:var(--bg3); color:#888;">&#128266;</button>
                <input type="text" id="msgInput" placeholder="Type een bericht..." autocomplete="off" />
                <button class="btn-icon btn-send" onclick="send()">
                    <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                </button>
            </div>
        </div>
    </div>

    <div id="leadsCol">
        <h2 style="margin-bottom:16px; font-size:1.4em;">War Room Dashboard</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-label">Total Leads</div><div class="stat-val" id="statTotal">0</div></div>
            <div class="stat-card"><div class="stat-label">Avg Score</div><div class="stat-val" id="statScore" style="color:var(--green);">0%</div></div>
            <div class="stat-card"><div class="stat-label">Sent Today</div><div class="stat-val" id="statSent" style="color:var(--pink);">0</div></div>
        </div>

        <h3 style="margin-bottom:12px; color:var(--pink);">Whale Approval Queue 🐋</h3>
        <div id="whaleQueue"></div>

        <h3 style="margin-top:24px; margin-bottom:12px;">Recent Activity</h3>
        <div id="leadTable" style="background:var(--bg2); border-radius:12px; border:1px solid var(--border); padding:10px;"></div>
    </div>
</div>

<script>
const API = 'http://localhost:8095';
let mode = 'normal';
let voiceOn = false;
let audio = null;
const getOrSetSid = (key, prefix) => {
    let sid = localStorage.getItem(key);
    if (!sid) {
        sid = prefix + '_' + crypto.randomUUID();
        localStorage.setItem(key, sid);
    }
    return sid;
};
const SID = {
    normal: getOrSetSid('nova_sid_normal', 'n'),
    nsfw: getOrSetSid('nova_sid_nsfw', 'x')
};

let activePersonaKey = 'nova';

function getSessionId() {
    return mode === 'normal' ? SID.normal : ('x_' + activePersonaKey);
}

async function loadHistory() {
    try {
        const r = await fetch('/api/history/' + getSessionId());
        const d = await r.json();
        const m = document.getElementById('messages');
        m.innerHTML = '';
        if (d.history && d.history.length > 0) {
            d.history.forEach(msg => {
                addMsg(msg.role === 'user' ? 'user' : 'ai', msg.text, mode==='normal'?(msg.model||'AI'):(msg.persona||'Nova'));
            });
        } else {
            if (mode==='normal') { addMsg('ai', 'Welkom terug. Hoe kan ik helpen?', 'System'); }
            else { addMsg('ai', 'Hallo! Ik ben klaar voor ons rollenspel.', 'System'); }
        }
    } catch(e) {
        if (mode==='normal') { addMsg('ai', 'Welkom terug. Hoe kan ik helpen?', 'System'); }
    }
}

function switchMode(m) {
    mode = m;
    document.getElementById('tabNormal').className = 'mode-tab' + (m==='normal'?' active-normal':'');
    document.getElementById('tabNsfw').className = 'mode-tab' + (m==='nsfw'?' active-nsfw':'');
    document.getElementById('tabLeads').className = 'mode-tab' + (m==='leads'?' active-leads':'');
    
    document.getElementById('sidebar').className = 'sidebar' + (m==='nsfw'?' open':'');
    document.getElementById('modelSelectContainer').style.display = m==='normal'?'block':'none';
    
    if (m === 'leads') {
        document.getElementById('chatCol').style.display = 'none';
        document.getElementById('leadsCol').style.display = 'flex';
        loadLeads();
        loadWhales();
    } else {
        document.getElementById('chatCol').style.display = 'flex';
        document.getElementById('leadsCol').style.display = 'none';
        document.getElementById('messages').innerHTML = '';
        if (m==='normal') { setHeader('JARVIS', null, '&#129302;'); loadHistory(); }
        else { loadPersonas().then(() => loadHistory()); }
    }
}

async function startScouting() {
    const q = document.getElementById('scoutQuery').value.trim();
    if (!q) return;
    const btn = document.getElementById('scoutBtn');
    const status = document.getElementById('scoutStatus');
    btn.disabled = true; btn.textContent = 'Searching...';
    status.innerHTML = '<span style="color:var(--accent);">De Scouter Swarm is onderweg... Dit duurt even.</span>';
    
    try {
        const r = await fetch(API+'/api/scout', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({query:q})
        });
        const d = await r.json();
        status.innerHTML = `<span style="color:var(--green);">Succes! ${d.leads_found || 0} nieuwe leads gevonden en toegevoegd.</span>`;
        loadLeads();
    } catch(e) { status.innerHTML = '<span style="color:var(--pink);">Fout bij scouten.</span>'; }
    finally { btn.disabled = false; btn.textContent = 'Scout Leads'; }
}

async function loadWhales() {
    try {
        const r = await fetch(API+'/api/leads?status=pending_review&limit=5');
        const d = await r.json();
        const q = document.getElementById('whaleQueue');
        if (!d.leads || d.leads.length === 0) { q.innerHTML = '<div style="color:var(--muted); font-style:italic; font-size:0.9em;">Geen Whales in de wachtrij.</div>'; return; }
        let html = '';
        d.leads.forEach(l => {
            html += `<div class="whale-card">
                <div class="whale-header">
                    <div><b style="color:#fff;">${l.name}</b> @ ${l.company} <span style="color:var(--green); margin-left:8px;">${l.score}%</span></div>
                    <div style="display:flex; gap:6px;">
                        <a href="${l.custom_data?.linkedin_url || '#'}" target="_blank" style="font-size:0.7em; color:var(--accent); text-decoration:none;">LinkedIn</a>
                        <button onclick="approveWhale('${l.id}')" style="background:var(--green); color:#000; border:none; padding:4px 10px; border-radius:4px; font-size:0.7em; font-weight:700; cursor:pointer;">LAUNCH 🚀</button>
                    </div>
                </div>
                <div class="whale-reply">${l.custom_data?.ai_reply || '...'}</div>
            </div>`;
        });
        q.innerHTML = html;
    } catch(e) {}
}

async function approveWhale(id) {
    if (!confirm("Launch deze Whale?")) return;
    try {
        await fetch(API+'/api/pipeline/approve/'+id, {method:'POST'});
        loadWhales(); loadLeads();
    } catch(e) { alert(e.message); }
}

async function loadLeads() {
    try {
        const r = await fetch(API+'/api/leads?limit=10');
        const d = await r.json();
        const table = document.getElementById('leadTable');
        let html = '<table style="width:100%; border-collapse:collapse; font-size:0.8em; color:var(--muted);">';
        d.leads.forEach(l => {
            html += `<tr style="border-bottom:1px solid #1a1a2e;"><td style="padding:8px; color:#fff;">${l.name}</td><td style="padding:8px;">${l.company}</td><td style="padding:8px; text-align:right;">${l.status}</td></tr>`;
        });
        table.innerHTML = html + '</table>';
        
        // Mock stats
        document.getElementById('statTotal').textContent = d.count || 0;
        document.getElementById('statScore').textContent = '88%';
        document.getElementById('statSent').textContent = '12';
    } catch(e) {}
}

// --- Chat Logic ---
async function send() {
    const inp = document.getElementById('msgInput');
    const txt = inp.value.trim(); if(!txt) return;
    inp.value=''; addMsg('user', txt);
    const endpoint = mode==='normal'?'/api/chat/normal':'/api/chat/nsfw';
    const body = { message:txt, session_id:getSessionId() };
    if (mode==='normal') body.model = document.getElementById('modelSelect').value;
    try {
        const r = await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const d = await r.json();
        addMsg('ai', d.response, mode==='normal'?(d.model||'AI'):(d.persona||'Nova'));
        if (voiceOn && d.audio_base64) playAudio(d.audio_base64);
    } catch(e) { addMsg('ai', 'Error: '+e.message, 'System'); }
}

function addMsg(role, text, tag) {
    const m = document.getElementById('messages');
    const d = document.createElement('div'); d.className = 'msg '+role;
    if (role==='ai') d.innerHTML = `<div class="tag" style="color:${mode==='nsfw'?'var(--pink)':'var(--accent)'}">${tag}</div>${text}`;
    else d.textContent = text;
    m.appendChild(d); m.scrollTop = m.scrollHeight;
}

function setHeader(name, avatar, emoji) {
    document.getElementById('hName').textContent = name;
    document.getElementById('hAvatar').innerHTML = emoji || '&#129302;';
}

async function loadModels() {
    const r = await fetch('/api/models');
    const d = await r.json();
    const sel = document.getElementById('modelSelect');
    sel.innerHTML = '';
    for (const [cat, models] of Object.entries(d.categories)) {
        const og = document.createElement('optgroup'); og.label = cat;
        models.forEach(m => { const o = document.createElement('option'); o.value=m.key; o.textContent=m.label; if(m.key===d.active) o.selected=true; og.appendChild(o); });
        sel.appendChild(og);
    }
}

async function loadPersonas() {
    const r = await fetch('/api/personas'); const d = await r.json();
    const list = document.getElementById('personaList'); list.innerHTML = '';
    d.personas.forEach(p => {
        const c = document.createElement('div'); c.className = 'persona-card'+(p.active?' active':'');
        c.innerHTML = `<div class="p-avatar">${p.avatar?`<img src="${p.avatar}" style="width:100%;height:100%;border-radius:50%;"/>`:'&#128156;'}</div><div class="p-info"><h3>${p.name}</h3></div>`;
        c.onclick = () => { 
            fetch('/api/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({persona:p.key})})
            .then(()=>loadPersonas())
            .then(()=>loadHistory()); 
        };
        list.appendChild(c);
        if (p.active) {
            setHeader(p.name, p.avatar, '&#128156;');
            activePersonaKey = p.key;
        }
    });
}

function toggleVoice() { voiceOn=!voiceOn; document.getElementById('voiceBtn').style.color=voiceOn?'var(--pink)':'#888'; }
function playAudio(b64) { if(audio) audio.pause(); audio=new Audio('data:audio/mp3;base64,'+b64); audio.play(); }

document.getElementById('msgInput').onkeydown = e => { if(e.key==='Enter') send(); };
loadModels();
addMsg('ai', 'Systeem online. Hoe kan ik u vandaag van dienst zijn?', 'JARVIS');
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = 8069
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    log.info("NovaMaster Chat starting on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
