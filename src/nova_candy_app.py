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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

AVATAR_DIR = Path("/home/faramix/avatar_engine/identities")
VOICE_CACHE = Path("/tmp/nova_voice_cache")
VOICE_CACHE.mkdir(exist_ok=True)

_sessions: dict[str, list] = {}

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
    if session_id not in _sessions: _sessions[session_id] = []
    _sessions[session_id].append({"role": "user", "text": message})

    response_text, model_used = route_chat(message, force_model=model)
    _sessions[session_id].append({"role": "ai", "text": response_text, "model": model_used})

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

    if not message: return JSONResponse({"error": "empty"}, status_code=400)
    key, persona = get_active_persona()
    if session_id not in _sessions: _sessions[session_id] = []
    _sessions[session_id].append({"role": "user", "text": message})

    full_prompt = f"{persona['system_prompt']}\n\nUser: {message}\n\n{persona['name']}:"
    response_text, model_used = route_chat(full_prompt, voice_uncensored=True)
    
    response_text = response_text.strip()
    if response_text.startswith(f"{persona['name']}:"):
        response_text = response_text[len(persona['name']) + 1:].strip()
    
    _sessions[session_id].append({"role": "ai", "text": response_text, "persona": persona['name']})

    result = {"response": response_text, "persona": persona['name'], "session_id": session_id}
    try:
        voice_path = await _generate_voice(response_text, persona.get("voice", "nl-BE-DenaNeural"))
        if voice_path:
            result["audio_base64"] = base64.b64encode(voice_path.read_bytes()).decode()
    except Exception: pass
    return result

@app.post("/api/clear/{session_id}")
def api_clear(session_id: str):
    _sessions.pop(session_id, None)
    return {"status": "cleared"}

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
const SID = { normal: 'n_'+crypto.randomUUID(), nsfw: 'x_'+crypto.randomUUID() };

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
        if (m==='normal') { setHeader('JARVIS', null, '&#129302;'); addMsg('ai', 'Welkom terug. Hoe kan ik helpen?', 'System'); }
        else loadPersonas();
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
    const body = { message:txt, session_id:SID[mode] };
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
        c.onclick = () => { fetch('/api/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({persona:p.key})}).then(()=>loadPersonas()); };
        list.appendChild(c);
        if (p.active) setHeader(p.name, p.avatar, '&#128156;');
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
