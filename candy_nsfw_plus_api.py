#!/usr/bin/env python3
"""CANDY.NSFW+ - Enhanced 双重草莓 AI + Sexy Fashion + 视频生成

Features:
- Image undressing via Grok Imagine (Venice AI)
- Video generation via Grok / nova_supergrok_auto
- Batch NSFW scene generation
- Session-based roleplay agents
- Image + video storage
"""

import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import (
    API_KEY_NAMES,
    DEFAULT_IMAGE_PATHS,
    EXTRA_ENV_PATHS,
    GROK_IMAGINE_SCRIPT,
    OUTPUT_DIR,
    RATE_LIMIT_BATCH,
    RATE_LIMIT_GENERATE,
    SUPERGROK_SCRIPT,
    VENICE_AUTO_SCRIPT,
)

import os

# ===== RATE LIMITER =====
limiter = Limiter(key_func=get_remote_address)

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="CANDY.NSFW+ Enhanced", version="2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated outputs statically
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

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
def _load_keys_candy() -> None:
    for path in EXTRA_ENV_PATHS:
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
    for key in API_KEY_NAMES:
        if key in os.environ:
            return os.environ[key]
    return None

def generate_session_id() -> str:
    """Generate unique session ID."""
    return f"ccc_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

def generate_video(scene_id: str, prompt: str) -> str:
    """Generate 10-second NSFW video via Grok.

    Delegates to nova_supergrok_auto.py for Grok Imagine.
    Uses subprocess.Popen with list args to prevent shell injection.
    """
    out_dir = OUTPUT_DIR / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)

    video_file = out_dir / f"{scene_id}_{uuid.uuid4().hex[:8]}.mp4"
    logging_file = video_file.with_suffix(".log")

    with open(logging_file, "w") as log_fh:
        subprocess.Popen(
            [
                "python3",
                str(SUPERGROK_SCRIPT),
                "--prompt", prompt or "default scene",
                "--output", str(video_file),
            ],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    return str(video_file)


def generate_image_venice(scene_id: str, prompt: str) -> str:
    """Generate NSFW image via Venice browser bypass.

    Delegates to nova_venice_auto.py.
    """
    out_dir = OUTPUT_DIR / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    image_file = out_dir / f"{scene_id}_{uuid.uuid4().hex[:8]}.png"
    logging_file = image_file.with_suffix(".log")

    with open(logging_file, "w") as log_fh:
        subprocess.Popen(
            [
                "python3",
                str(VENICE_AUTO_SCRIPT),
                "--prompt", prompt or "default scene",
                "--output", str(image_file),
                "--headless",
            ],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    return str(image_file)



def _generate_image_subprocess(
    image_path: str,
    prompt: str,
    out_dir: Path,
    logging_file: Path,
) -> None:
    """Launch Grok Imagine as a detached subprocess (no shell)."""
    with open(logging_file, "w") as log_fh:
        subprocess.Popen(
            [
                "python3",
                str(GROK_IMAGINE_SCRIPT),
                str(image_path),
                prompt,
                str(out_dir),
            ],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def _batch_generate_video(category: str, prompt: str) -> dict:
    """Thin wrapper used by the /batch endpoint's background tasks."""
    video_path = generate_video(category, prompt)
    return {
        "scene_id": category,
        "mode": "batch",
        "video_file": video_path,
        "status": "queued",
    }


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
    import sys
    sys.path.append("/home/faramix/candy-ai-clone")
    try:
        from src.grok_batch_nsfw import SCENES
        return {
            "scenes": list(SCENES.keys()),
            "count": len(SCENES),
            "message": f"{len(SCENES)} nsfw scenes available"
        }
    except Exception:
        return {
            "scenes": ["dans", "glimlach", "dichterbij", "strip", "ahegao", "kont", "striptease", "aftrekken", "bj", "spanking", "kutje", "aanraken", "dildo", "squirt", "voeten", "sex", "anaal", "trio", "doggy"],
            "count": 19,
            "message": "19 nsfw scenes available (fallback)"
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
@limiter.limit(RATE_LIMIT_GENERATE)
async def generate_scene(payload: GenerateRequest, request: Request, background_tasks: BackgroundTasks):
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

    scene_id = payload.scene_id

    # Map scene_id -> Grok prompt (from grok_batch_nsfw.py)
    groove_prompt = None

    import sys
    sys.path.append("/home/faramix/candy-ai-clone")
    try:
        from src.grok_batch_nsfw import SCENES
        groove_prompt = SCENES.get(scene_id)
    except Exception:
        pass

    if not groove_prompt:
        script = Path("/home/faramix/candy-ai-clone/src/grok_batch_nsfw.py")
        if script.exists():
            with open(script) as f:
                content = f.read()
                for line in content.split("\n"):
                    if f"\"{scene_id}\": " in line:
                        groove_prompt = line.split(":", 1)[1].strip().strip('",')
                        break

    # Generate output
    if payload.mode == "video" or payload.mode == "batch":
        # Fire async video generation (uses nova_supergrok_auto.py)
        video_path = generate_video(scene_id, groove_prompt)

        return {
            "scene_id": scene_id,
            "mode": payload.mode,
            "video_file": video_path,
            "status": "queued",
        }

    elif payload.mode == "image":
        # Image generation via Venice browser bypass
        image_file = generate_image_venice(scene_id, groove_prompt)

        return {
            "scene_id": scene_id,
            "mode": payload.mode,
            "image_file": image_file,
            "status": "queued",
        }

    elif payload.mode == "image_undress":
        # Image undressing via Grok Imagine / Venice API edit
        out_dir = OUTPUT_DIR / "images"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Determine input image for undressing
        image_path = payload.parameters.get("image_path")
        image_base64 = payload.parameters.get("image") or payload.parameters.get("image_base64")

        if image_base64:
            import base64
            # Strip base64 headers if present
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            temp_input = out_dir / f"input_{uuid.uuid4().hex[:8]}.png"
            with open(temp_input, "wb") as f:
                f.write(base64.b64decode(image_base64))
            image_path = str(temp_input)

        if not image_path:
            # Look for default avatar/images in workspace
            for d in DEFAULT_IMAGE_PATHS:
                if os.path.exists(d):
                    image_path = d
                    break

        # If no input image can be found at all, create a tiny red PNG as placeholder
        if not image_path or not os.path.exists(image_path):
            placeholder = out_dir / "placeholder.png"
            if not placeholder.exists():
                try:
                    import base64
                    # 1x1 red pixel png base64
                    red_pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
                    with open(placeholder, "wb") as f:
                        f.write(red_pixel)
                except Exception:
                    pass
            image_path = str(placeholder)

        image_file = out_dir / f"{scene_id}_{uuid.uuid4().hex[:8]}.png"
        logging_file = image_file.with_suffix(".log")

        # Launch Grok Imagine via subprocess (no shell)
        _generate_image_subprocess(
            image_path=image_path,
            prompt=groove_prompt or "undress in natural style",
            out_dir=out_dir,
            logging_file=logging_file,
        )

        return {
            "scene_id": scene_id,
            "mode": payload.mode,
            "image_file": str(image_file),
            "status": "queued",
            "input_file": image_path
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {payload.mode}")

@app.post("/batch")
@limiter.limit(RATE_LIMIT_BATCH)
async def batch_generate(payload: BatchRequest, request: Request, background_tasks: BackgroundTasks):
    """Batch generate multiple scenes."""
    api_key = check_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="API key not configured")

    if payload.parallel:
        # Run each scene as a background task using the correct helper
        for scene in payload.scenes:
            background_tasks.add_task(
                _batch_generate_video, scene.category, scene.prompt,
            )

        return {"status": "queued", "scenes_done": len(payload.scenes)}
    else:
        # Run sequentially
        results = []
        for scene in payload.scenes:
            result = _batch_generate_video(scene.category, scene.prompt)
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
    from config import NSFW_API_PORT
    uvicorn.run(app, host="0.0.0.0", port=NSFW_API_PORT)
