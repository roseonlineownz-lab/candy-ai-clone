"""Higgsfield-style creative studio orchestration for the Candy app.

This module does not call third-party providers directly. It exposes the local
NovaMaster media stack as capabilities and writes deterministic job manifests
that a worker can pick up later.
"""

from __future__ import annotations

import json
import os
import hashlib
import re
import threading
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
IDEMPOTENCY_FILE = STATE_DIR / "idempotency.json"

COMFY_URL = os.getenv("CANDY_COMFY_URL", "http://127.0.0.1:8188")
NOIZ_URL = os.getenv("CANDY_NOIZ_URL", "http://127.0.0.1:7438")

ALLOWED_MODES = {"image", "video", "avatar", "campaign"}
ALLOWED_VIDEO_TASKS = {"text_to_video", "image_to_video", "lipsync"}
ALLOWED_IMAGE_FORMATS = {"1:1", "4:3", "3:4", "16:9", "9:16"}

PROVIDER_MODELS = {
    "comfyui": "sdxl-local",
    "wan-local": "wan2.1-t2v-14b-q4",
    "video-factory": "nova-video-factory",
    "noiz-voice": "noiz-v1",
    "higgsfield": "higgsfield-web",
}
JOB_ID_RE = re.compile(r"^studio-[a-f0-9]{12}$")
JOB_WRITE_LOCK = threading.Lock()


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
            "model": PROVIDER_MODELS["comfyui"],
            "execution_target": "pc",
            "state": {
                "configured": True,
                "tested": comfy_ready,
                "busy": False,
                "error": None if comfy_ready else "ComfyUI health endpoint unavailable",
            },
        },
        {
            "id": "wan-local",
            "name": "Wan local video",
            "kind": "local",
            "ready": wan_model["exists"] and wan_vae["exists"],
            "outputs": ["video"],
            "assets": [wan_model, wan_vae],
            "model": PROVIDER_MODELS["wan-local"],
            "execution_target": "vps_gpu",
            "state": {
                "configured": wan_model["exists"] or wan_vae["exists"],
                "tested": wan_model["exists"] and wan_vae["exists"],
                "busy": False,
                "error": None if (wan_model["exists"] and wan_vae["exists"]) else "Wan model assets missing",
            },
        },
        {
            "id": "video-factory",
            "name": "Nova video-factory",
            "kind": "local",
            "ready": video_factory["exists"],
            "outputs": ["video", "campaign"],
            "assets": [video_factory],
            "model": PROVIDER_MODELS["video-factory"],
            "execution_target": "vps_gpu",
            "state": {
                "configured": video_factory["exists"],
                "tested": video_factory["exists"],
                "busy": False,
                "error": None if video_factory["exists"] else "video-factory script missing",
            },
        },
        {
            "id": "noiz-voice",
            "name": "Noiz voice",
            "kind": "local",
            "ready": noiz_ready,
            "outputs": ["audio", "voice"],
            "health": f"{NOIZ_URL}/health",
            "model": PROVIDER_MODELS["noiz-voice"],
            "execution_target": "pc",
            "state": {
                "configured": True,
                "tested": noiz_ready,
                "busy": False,
                "error": None if noiz_ready else "Noiz health endpoint unavailable",
            },
        },
        {
            "id": "higgsfield",
            "name": "Higgsfield fallback",
            "kind": "hosted",
            "ready": higgsfield_key_present,
            "outputs": ["image", "video", "campaign"],
            "configured": higgsfield_key_present,
            "model": PROVIDER_MODELS["higgsfield"],
            "execution_target": "external",
            "state": {
                "configured": higgsfield_key_present,
                "tested": higgsfield_key_present,
                "busy": False,
                "error": None if higgsfield_key_present else "HIGGSFIELD_API_KEY missing",
            },
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


def _load_idempotency_map() -> dict[str, str]:
    if not IDEMPOTENCY_FILE.exists():
        return {}
    try:
        return json.loads(IDEMPOTENCY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_idempotency_map(value: dict[str, str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(IDEMPOTENCY_FILE, value)


def _normalize_job_id(job_id: str) -> str:
    value = str(job_id).strip()
    if not JOB_ID_RE.fullmatch(value):
        raise ValueError("invalid job id")
    return value


def _write_job(job_id: str, job: dict[str, Any]) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = _job_manifest_path(job_id)
    _atomic_write_json(path, job)


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _job_manifest_path(job_id: str) -> Path:
    safe_id = _normalize_job_id(job_id)
    path = (JOBS_DIR / f"{safe_id}.json").resolve()
    jobs_root = JOBS_DIR.resolve()
    if path.parent != jobs_root:
        raise ValueError("invalid job path")
    return path


def _select_provider(
    mode: str,
    preferred_provider: str | None = None,
    *,
    allow_hosted_fallback: bool = False,
) -> str:
    capabilities = studio_capabilities()
    providers = capabilities["providers"]
    if preferred_provider:
        selected = None
        for provider in providers:
            if provider["id"] == preferred_provider and mode in provider["outputs"]:
                selected = provider
                break
        if selected is None:
            raise ValueError(f"provider '{preferred_provider}' does not support mode '{mode}'")
        if selected["ready"]:
            return selected["id"]
        if allow_hosted_fallback:
            for provider in providers:
                if provider["kind"] == "hosted" and provider["ready"] and mode in provider["outputs"]:
                    return provider["id"]
        raise ValueError(f"provider '{preferred_provider}' is not ready")
    for provider in providers:
        if provider["kind"] == "local" and provider["ready"] and mode in provider["outputs"]:
            return provider["id"]
    if allow_hosted_fallback:
        for provider in providers:
            if provider["kind"] == "hosted" and provider["ready"] and mode in provider["outputs"]:
                return provider["id"]
    for provider in providers:
        if provider["kind"] == "local" and mode in provider["outputs"]:
            return provider["id"]
    raise ValueError(f"no configured provider is ready for mode '{mode}'")


def create_studio_job(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt", "")).strip()
    mode = str(payload.get("mode", "image")).strip().lower()
    preset = str(payload.get("preset", "custom")).strip() or "custom"
    persona = str(payload.get("persona", "nova")).strip() or "nova"
    preferred_provider = payload.get("provider")
    allow_hosted_fallback = bool(payload.get("allow_hosted_fallback", False))
    reference = payload.get("reference")
    video_task = str(payload.get("video_task", "text_to_video")).strip().lower()
    output_format = str(payload.get("format", "1:1")).strip()
    idempotency_key = str(
        payload.get("idempotency_key")
        or payload.get("retry_token")
        or ""
    ).strip() or None

    if not prompt:
        raise ValueError("prompt is required")
    if mode not in ALLOWED_MODES:
        raise ValueError(f"mode must be one of {', '.join(sorted(ALLOWED_MODES))}")
    if mode == "image" and output_format not in ALLOWED_IMAGE_FORMATS:
        raise ValueError(f"format must be one of {', '.join(sorted(ALLOWED_IMAGE_FORMATS))}")
    if mode == "video":
        if video_task not in ALLOWED_VIDEO_TASKS:
            raise ValueError(f"video_task must be one of {', '.join(sorted(ALLOWED_VIDEO_TASKS))}")
        if video_task in {"image_to_video", "lipsync"} and not reference:
            raise ValueError(f"reference is required for video_task '{video_task}'")

    with JOB_WRITE_LOCK:
        if idempotency_key:
            idempotency_map = _load_idempotency_map()
            known_job_id = idempotency_map.get(idempotency_key)
            if known_job_id:
                existing = get_studio_job(known_job_id)
                if existing:
                    existing = dict(existing)
                    existing["deduplicated"] = True
                    return existing
        else:
            idempotency_map = {}

        job_id = f"studio-{uuid.uuid4().hex[:12]}"
        provider = _select_provider(
            mode,
            preferred_provider,
            allow_hosted_fallback=allow_hosted_fallback,
        )
        capability_map = {p["id"]: p for p in studio_capabilities()["providers"]}
        selected_provider = capability_map.get(provider, {})
        provider_model = PROVIDER_MODELS.get(provider, "unknown")
        provider_kind = selected_provider.get("kind", "local")
        execution_target = selected_provider.get("execution_target", "pc")
        provider_error = (selected_provider.get("state") or {}).get("error")
        provider_ready = bool(selected_provider.get("ready"))
        input_digest = hashlib.sha256(
            json.dumps(
                {
                    "mode": mode,
                    "preset": preset,
                    "persona": persona,
                    "prompt": prompt,
                    "video_task": video_task if mode == "video" else None,
                    "format": output_format if mode == "image" else None,
                    "reference": bool(reference),
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        job = {
            "id": job_id,
            "task_id": job_id,
            "status": "queued" if provider_ready else "error",
            "created_at": _now(),
            "mode": mode,
            "video_task": video_task if mode == "video" else None,
            "format": output_format if mode == "image" else None,
            "preset": preset,
            "persona": persona,
            "provider": provider,
            "model": provider_model,
            "execution_target": execution_target,
            "prompt": prompt,
            "reference": reference if reference else None,
            "outputs": [],
            "input_digest": input_digest,
            "error": None if provider_ready else (provider_error or f"provider '{provider}' not ready"),
            "progress": {
                "percent": 0,
                "stage": "queued" if provider_ready else "blocked",
            },
            "provider_state": {
                "configured": bool((selected_provider.get("state") or {}).get("configured", selected_provider.get("ready"))),
                "tested": bool((selected_provider.get("state") or {}).get("tested", selected_provider.get("ready"))),
                "busy": False,
                "error": (selected_provider.get("state") or {}).get("error"),
            },
            "routing": {
                "local_first": True,
                "fallback_allowed": allow_hosted_fallback,
                "provider_kind": provider_kind,
                "notes": [
                    "Generated as a manifest; media workers can pick this job up later.",
                    "No provider secrets are stored in the job file.",
                ],
            },
        }
        _write_job(job_id, job)
        if idempotency_key:
            idempotency_map[idempotency_key] = job_id
            _save_idempotency_map(idempotency_map)
        return job


def get_studio_job(job_id: str) -> dict[str, Any] | None:
    try:
        safe_id = _normalize_job_id(job_id)
    except ValueError:
        return None
    if not JOBS_DIR.exists():
        return None
    for path in JOBS_DIR.glob("studio-*.json"):
        if path.stem != safe_id:
            continue
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def cancel_studio_job(job_id: str) -> dict[str, Any] | None:
    job = get_studio_job(job_id)
    if not job:
        return None
    if job.get("status") in {"completed", "failed", "cancelled"}:
        return job
    job["status"] = "cancelled"
    job["cancelled_at"] = _now()
    progress = dict(job.get("progress") or {})
    progress.update({"stage": "cancelled"})
    job["progress"] = progress
    _write_job(_normalize_job_id(str(job["id"])), job)
    return job


def list_studio_jobs(*, limit: int = 50) -> list[dict[str, Any]]:
    if not JOBS_DIR.exists():
        return []
    jobs: list[dict[str, Any]] = []
    for path in JOBS_DIR.glob("studio-*.json"):
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return jobs[: max(1, min(limit, 200))]


def get_studio_gallery(*, limit: int = 50, persona: str | None = None) -> list[dict[str, Any]]:
    jobs = list_studio_jobs(limit=limit * 2)
    gallery: list[dict[str, Any]] = []
    for job in jobs:
        if job.get("mode") not in {"image", "video"}:
            continue
        if persona and job.get("persona") != persona:
            continue
        gallery.append(
            {
                "id": job.get("id"),
                "task_id": job.get("task_id"),
                "status": job.get("status"),
                "mode": job.get("mode"),
                "video_task": job.get("video_task"),
                "format": job.get("format"),
                "provider": job.get("provider"),
                "model": job.get("model"),
                "execution_target": job.get("execution_target"),
                "prompt": job.get("prompt"),
                "created_at": job.get("created_at"),
                "outputs": job.get("outputs", []),
                "error": job.get("error"),
            }
        )
        if len(gallery) >= limit:
            break
    return gallery


def studio_health() -> dict[str, Any]:
    capabilities = studio_capabilities()
    return {
        "status": capabilities["status"],
        "providers_ready": sum(1 for p in capabilities["providers"] if p["ready"]),
        "providers_total": len(capabilities["providers"]),
        "jobs_dir": str(JOBS_DIR),
    }
