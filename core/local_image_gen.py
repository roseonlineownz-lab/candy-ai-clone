#!/usr/bin/env python3
"""Local fictional-persona image generation via ComfyUI (SDXL/Flux).

Only generates fully fictional, AI-synthesized adult personas.
No real-person likeness, no image input, no undress/i2i of real photos.
"""
from __future__ import annotations

import json
import time
import urllib.request
import uuid
from pathlib import Path

COMFY_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_NEGATIVE = (
    "cartoon, anime, 3d render, painting, illustration, deformed, ugly, "
    "blurry, low quality, watermark, text, child, minor, underage"
)


def comfy_available(timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=timeout):
            return True
    except Exception:
        return False


def _post_json(path: str, payload: dict, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        f"{COMFY_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _get_json(path: str, timeout: float = 10.0) -> dict:
    with urllib.request.urlopen(f"{COMFY_URL}{path}", timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _build_workflow(prompt: str, negative: str, width: int, height: int,
                    steps: int, seed: int, checkpoint: str) -> dict:
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": 7.0,
            "sampler_name": "euler_ancestral", "scheduler": "normal",
            "denoise": 1.0, "model": ["4", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "candy_persona", "images": ["8", 0]}},
    }


def generate_persona_image(
    prompt: str,
    negative: str = DEFAULT_NEGATIVE,
    width: int = 512,
    height: int = 512,
    steps: int = 25,
    seed: int | None = None,
    checkpoint: str = "sd_xl_base_1.0.safetensors",
    timeout_s: int = 300,
) -> dict:
    """Queue a fictional-persona render on local ComfyUI and wait for the file."""
    if not comfy_available():
        return {"ok": False, "error": "comfyui_unavailable", "hint": "systemctl --user start comfyui"}

    safe_prompt = f"photorealistic portrait of a fictional adult woman, {prompt}, studio lighting, high detail"
    seed = seed if seed is not None else int(uuid.uuid4().int % (2**31))
    workflow = _build_workflow(safe_prompt, negative, width, height, steps, seed, checkpoint)

    queued = _post_json("/prompt", {"prompt": workflow})
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        return {"ok": False, "error": "queue_failed", "detail": queued}

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        history = _get_json(f"/history/{prompt_id}")
        entry = history.get(prompt_id)
        if entry and entry.get("status", {}).get("completed"):
            images = []
            for out in entry.get("outputs", {}).values():
                for img in out.get("images", []):
                    images.append(img)
            if images:
                img = images[0]
                url = (f"{COMFY_URL}/view?filename={img['filename']}"
                       f"&subfolder={img.get('subfolder', '')}&type={img.get('type', 'output')}")
                dest = OUTPUT_DIR / f"persona_{seed}.png"
                with urllib.request.urlopen(url, timeout=30) as resp:
                    dest.write_bytes(resp.read())
                return {"ok": True, "file": str(dest), "seed": seed, "prompt": safe_prompt}
            return {"ok": False, "error": "no_images", "prompt_id": prompt_id}
        time.sleep(2)
    return {"ok": False, "error": "timeout", "prompt_id": prompt_id}


if __name__ == "__main__":
    import sys
    result = generate_persona_image(sys.argv[1] if len(sys.argv) > 1 else "smiling, casual outfit")
    print(json.dumps(result, indent=2))
