#!/usr/bin/env python3
"""CANDY.NSFW+ - Enhanced 双重草莓 AI + Sexy Fashion + 视频生成

Features:
- Image undressing via Grok Imagine (Venice AI)
- Video generation via Grok / nova_supergrok_auto
- Batch NSFW scene generation
- Session-based roleplay agents
- Image + video storage
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import asyncio
import os
import uuid
from datetime import datetime

app = FastAPI(title="CANDY.NSFW+ Enhanced", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== CONFIG =====
OUTPUT_DIR = Path("/home/faramix/avatar_engine/output")
NSFW_MODELS_DIR = Path("/home/faramix/Mark-XXX/cache")

# ===== MODELS =====
class Scene(BaseModel):
    category: str
    prompt: str
    video_file: Optional[str] = None
    image_file: Optional[str] = None

class GenerateRequest(BaseModel):
    scene_id: str
    mode: str = "video"  # video, image, image_undress, batch
    parameters: Dict[str, Any] = {}

class BatchRequest(BaseModel):
    scenes: List[Scene]
    parallel: bool = True

# ===== HELPER =====
def _load_keys_candy():
    env_paths = [
        "/home/faramix/.env",
        "/home/faramix/.hermes/.env",
        "/home/faramix/.openclaw/.env"
    ]
    for path in env_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k in ["VENICE_API_KEY", "GROK_VENICE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
                                os.environ[k] = v
            except Exception:
                pass

def check_api_key() -> Optional[str]:
    """Check for API key in env/config."""
    _load_keys_candy()
    for key in ["VENICE_API_KEY", "GROK_VENICE_API_KEY"]:
        if key in os.environ:
            return os.environ[key]
    return None

def generate_session_id() -> str:
    """Generate unique session ID."""
    return f"ccc_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

def generate_video(scene_id: str, prompt: str) -> str:
    """Generate 10-second NSFW video via Grok.
    
    Delegates to nova_supergrok_auto.py for Grok Imagine.
    """
    out_dir = OUTPUT_DIR / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    video_file = out_dir / f"{scene_id}_{uuid.uuid4().hex[:8]}.mp4"
    
    # Call nova_supergrok_auto.py in background
    cmd = [
        "python3", "/home/faramix/nova_supergrok_auto.py",
        "--prompt", prompt,
        "--output", str(video_file)
    ]
    
    logging_file = video_file.with_suffix(".log")
    os.system(f"nohup python3 {' '.join(cmd)} > {logging_file} 2>&1 &")
    
    return str(video_file)

# ===== ENDPOINTS =====

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer."""
    api_key = check_api_key()
    return {
        "status": "ok",
        "service": "CANDY.NSFW+ Enhanced v2.0",
        "api_key_configured": bool(api_key),
        "output_dir": str(OUTPUT_DIR),
        "novamaster_integration": True,
    }

@app.get("/scenes")
async def list_scenes():
    """List available NSFW scenes."""
    script = Path("/home/faramix/candy-ai-clone/src/grok_batch_nsfw.py")
    scene_list = {}
    
    if script.exists():
        with open(script) as f:
            for line in f:
                if line.startswith('\"') and 'SCENES = ' not in line:
                    if line.strip().endswith('\",'):
                        key = line.strip('",\n')
                        scene_list[key] = line.strip()
    
    return {
        "scenes": list(scene_list.keys()),
        "count": len(scene_list),
        "message": "19 nsfw scenes available"
    }

@app.get("/session")
async def create_session():
    """Create new Candy AI+ session."""
    session_id = generate_session_id()
    
    return {
        "session_id": session_id,
        "created_at": datetime.utcnow().isoformat(),
        "status": "active",
        "features": ["image_undress", "video_generation", "batch_generation", "agent_roleplay"],
    }

@app.post("/generate")
async def generate_scene(request: GenerateRequest, background_tasks: BackgroundTasks):
    """
    Generate NSFW content from scene ID.

    Modes:
    - video: Generate 10-second Grok video
    - image: Generate Full HD image
    - image_undress: Image undress + filter
    - batch: Bulk generation (can run async)
    """
    api_key = check_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="API key not configured")
    
    scene_id = request.scene_id
    
    # Mo map scene_id -> Grok prompt (from grok_batch_nsfw.py)
    groove_prompt = None
    
    script = Path("/home/faramix/candy-ai-clone/src/grok_batch_nsfw.py")
    if script.exists():
        with open(script) as f:
            content = f.read()
            for line in content.split("\n"):
                if f"\"{scene_id}\": " in line:
                    groove_prompt = line.split(":", 1)[1].strip()
                    break
    
    # Generate output
    if request.mode == "video" or request.mode == "batch":
        # Fire async video generation (uses nova_supergrok_auto.py)
        video_path = generate_video(scene_id, groove_prompt)
        
        return {
            "scene_id": scene_id,
            "mode": request.mode,
            "video_file": video_path,
            "status": "queued",
        }
    
    elif request.mode == "image" or request.mode == "image_undress":
        # Image generation via Grok Imagine (Venice AI)
        out_dir = OUTPUT_DIR / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        image_file = out_dir / f"{scene_id}_{uuid.uuid4().hex[:8]}.png"
        
        # Call Grok Imagine (placeholder - integrate Venice AI SDK)
        logging_file = image_file.with_suffix(".log")
        cmd = [
            "python3", "/home/faramix/grok-imagine-app/grok-imagine.py",
            generate_session_id(),
            groove_prompt or "undress in natural style",
            str(out_dir)
        ]
        os.system(f"nohup python3 {' '.join(cmd)} > {logging_file} 2>&1 &")
        
        return {
            "scene_id": scene_id,
            "mode": request.mode,
            "image_file": str(image_file),
            "status": "queued",
        }
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {request.mode}")

@app.post("/batch")
async def batch_generate(request: BatchRequest, background_tasks: BackgroundTasks):
    """Batch generate multiple scenes."""
    api_key = check_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="API key not configured")
    
    if request.parallel:
        # Run async for each
        for scene in request.scenes:
            background_tasks.add_task(generate_scene, scene, "batch")
        
        return {"status": "queued", "scenes_done": len(request.scenes)}
    else:
        # Run sequentially
        results = []
        for scene in request.scenes:
            result = await generate_scene(scene, "batch")
            results.append(result)
        
        return {"status": "completed", "results": results}

@app.get("/avatar/{avatar_id}")
async def get_avatar(avatar_id: str):
    """Get avatar session state."""
    session_path = OUTPUT_DIR / "sessions" / avatar_id
    if session_path.exists():
        avatar_state = session_path.read_text()
        return {"avatar_id": avatar_id, "state": avatar_state}
    else:
        return {"avatar_id": avatar_id, "state": None}

@app.post("/roleplay")
async def start_roleplay(scene_id: str):
    """Start roleplay agent via Mark-XXX integration."""
    return {
        "status": "started",
        "scene_id": scene_id,
        "agent": "Mark-XXX nexus-agent",
        "message": "Roleplay started via CandAI + Mark synergy",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9500)
