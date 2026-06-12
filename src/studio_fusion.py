"""Higgsfield-style creative studio orchestration for the Candy app.

This module does not call third-party providers directly. It exposes the local
NovaMaster media stack as capabilities and writes deterministic job manifests
that a worker can pick up later.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


STATE_DIR = Path(os.getenv(
    "CANDY_STUDIO_STATE_DIR",
    str(Path.home() / ".local/state/novamaster/candy-studio"),
))
JOBS_DIR = STATE_DIR / "jobs"

COMFY_URL = os.getenv("CANDY_COMFY_URL", "http://127.0.0.1:8188")
NOIZ_URL = os.getenv("CANDY_NOIZ_URL", "http://127.0.0.1:7438")

ALLOWED_MODES = {"image", "video", "avatar", "campaign"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_status(path: str) -> dict[str, Any]:
    target = Path(path).expanduser()
    return {"path": str(target), "exists": target.exists()}


def _http_ok(url: str, timeout: float = 0.5) -> bool:
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (OSError, URLError, TimeoutError):
        return False


def studio_capabilities() -> dict[str, Any]:
    """Return the current media/agent capability map without exposing secrets."""
    comfy_ready = _http_ok(f"{COMFY_URL}/")
    noiz_ready = _http_ok(f"{NOIZ_URL}/health")
    video_factory = _path_status("/home/faramix/video-factory/video_factory.py")
    wan_model = _path_status("/home/faramix/ComfyUI/models/diffusion_models/wan2.1-t2v-14b-Q4_K_M.gguf")
    wan_vae = _path_status("/home/faramix/ComfyUI/models/vae/wan2.2_vae.safetensors")
    higgsfield_key_present = bool(os.getenv("HIGGSFIELD_API_KEY"))

    providers = [
        {
            "id": "comfyui",
            "name": "ComfyUI",
            "kind": "local",
            "ready": comfy_ready,
            "outputs": ["image", "video"],
            "health": COMFY_URL,
        },
        {
            "id": "wan-local",
            "name": "Wan local video",
            "kind": "local",
            "ready": wan_model["exists"] and wan_vae["exists"],
            "outputs": ["video"],
            "assets": [wan_model, wan_vae],
        },
        {
            "id": "video-factory",
            "name": "Nova video-factory",
            "kind": "local",
            "ready": video_factory["exists"],
            "outputs": ["video", "campaign"],
            "assets": [video_factory],
        },
        {
            "id": "noiz-voice",
            "name": "Noiz voice",
            "kind": "local",
            "ready": noiz_ready,
            "outputs": ["audio", "voice"],
            "health": f"{NOIZ_URL}/health",
        },
        {
            "id": "higgsfield",
            "name": "Higgsfield fallback",
            "kind": "hosted",
            "ready": higgsfield_key_present,
            "outputs": ["image", "video", "campaign"],
            "configured": higgsfield_key_present,
        },
    ]

    return {
        "status": "ready" if any(p["ready"] for p in providers) else "degraded",
        "generated_at": _now(),
        "providers": providers,
        "presets": [
            {
                "id": "cinematic-scene",
                "label": "Cinematic scene",
                "mode": "video",
                "preferred_provider": "wan-local",
            },
            {
                "id": "companion-portrait",
                "label": "Companion portrait",
                "mode": "image",
                "preferred_provider": "comfyui",
            },
            {
                "id": "talking-avatar",
                "label": "Talking avatar",
                "mode": "avatar",
                "preferred_provider": "noiz-voice",
            },
            {
                "id": "campaign-pack",
                "label": "Campaign pack",
                "mode": "campaign",
                "preferred_provider": "video-factory",
            },
        ],
    }


def _select_provider(mode: str, preferred_provider: str | None = None) -> str:
    capabilities = studio_capabilities()
    providers = capabilities["providers"]
    if preferred_provider:
        for provider in providers:
            if provider["id"] == preferred_provider and mode in provider["outputs"]:
                return provider["id"]
    for provider in providers:
        if provider["ready"] and mode in provider["outputs"]:
            return provider["id"]
    for provider in providers:
        if mode in provider["outputs"]:
            return provider["id"]
    return "manual"


def create_studio_job(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt", "")).strip()
    mode = str(payload.get("mode", "image")).strip().lower()
    preset = str(payload.get("preset", "custom")).strip() or "custom"
    persona = str(payload.get("persona", "nova")).strip() or "nova"
    preferred_provider = payload.get("provider")

    if not prompt:
        raise ValueError("prompt is required")
    if mode not in ALLOWED_MODES:
        raise ValueError(f"mode must be one of {', '.join(sorted(ALLOWED_MODES))}")

    job_id = f"studio-{uuid.uuid4().hex[:12]}"
    provider = _select_provider(mode, preferred_provider)
    job = {
        "id": job_id,
        "status": "queued",
        "created_at": _now(),
        "mode": mode,
        "preset": preset,
        "persona": persona,
        "provider": provider,
        "prompt": prompt,
        "outputs": [],
        "routing": {
            "local_first": True,
            "fallback_allowed": bool(payload.get("allow_hosted_fallback", False)),
            "notes": [
                "Generated as a manifest; media workers can pick this job up later.",
                "No provider secrets are stored in the job file.",
            ],
        },
    }
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    (JOBS_DIR / f"{job_id}.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    return job


def get_studio_job(job_id: str) -> dict[str, Any] | None:
    safe_id = "".join(ch for ch in job_id if ch.isalnum() or ch in "-_")
    path = JOBS_DIR / f"{safe_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def studio_health() -> dict[str, Any]:
    capabilities = studio_capabilities()
    return {
        "status": capabilities["status"],
        "providers_ready": sum(1 for p in capabilities["providers"] if p["ready"]),
        "providers_total": len(capabilities["providers"]),
        "jobs_dir": str(JOBS_DIR),
    }
