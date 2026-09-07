import json

import pytest

from src import studio_fusion


def test_studio_capabilities_reports_local_first_stack(monkeypatch, tmp_path):
    monkeypatch.setattr(studio_fusion, "STATE_DIR", tmp_path)
    monkeypatch.setattr(studio_fusion, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(studio_fusion, "_http_ok", lambda url, timeout=0.5: False)

    data = studio_fusion.studio_capabilities()

    assert data["status"] in {"ready", "degraded"}
    assert any(provider["id"] == "video-factory" for provider in data["providers"])
    assert any(preset["id"] == "campaign-pack" for preset in data["presets"])


def test_create_studio_job_writes_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(studio_fusion, "STATE_DIR", tmp_path)
    monkeypatch.setattr(studio_fusion, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(studio_fusion, "_http_ok", lambda url, timeout=0.5: False)

    job = studio_fusion.create_studio_job({
        "mode": "video",
        "preset": "cinematic-scene",
        "persona": "nova",
        "prompt": "cinematic neon portrait, rain, soft camera move",
    })

    manifest = tmp_path / "jobs" / f"{job['id']}.json"
    assert manifest.exists()
    assert job["status"] in {"queued", "error"}
    assert job["provider"] in {"wan-local", "video-factory", "higgsfield", "comfyui"}
    assert job["task_id"] == job["id"]
    assert job["video_task"] == "text_to_video"
    assert job["execution_target"] in {"pc", "vps_gpu", "external"}
    assert json.loads(manifest.read_text())["prompt"].startswith("cinematic")


def test_create_studio_job_validates_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr(studio_fusion, "STATE_DIR", tmp_path)
    monkeypatch.setattr(studio_fusion, "JOBS_DIR", tmp_path / "jobs")

    with pytest.raises(ValueError):
        studio_fusion.create_studio_job({"mode": "image", "prompt": ""})


def test_create_studio_job_requires_reference_for_image_to_video(monkeypatch, tmp_path):
    monkeypatch.setattr(studio_fusion, "STATE_DIR", tmp_path)
    monkeypatch.setattr(studio_fusion, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(studio_fusion, "_http_ok", lambda url, timeout=0.5: False)

    with pytest.raises(ValueError):
        studio_fusion.create_studio_job({
            "mode": "video",
            "video_task": "image_to_video",
            "prompt": "animate this portrait",
        })


def test_studio_job_idempotency_returns_existing_job(monkeypatch, tmp_path):
    monkeypatch.setattr(studio_fusion, "STATE_DIR", tmp_path)
    monkeypatch.setattr(studio_fusion, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(studio_fusion, "IDEMPOTENCY_FILE", tmp_path / "idempotency.json")
    monkeypatch.setattr(studio_fusion, "_http_ok", lambda url, timeout=0.5: False)

    payload = {
        "mode": "image",
        "prompt": "companion portrait",
        "idempotency_key": "retry-key-123",
    }
    first = studio_fusion.create_studio_job(payload)
    second = studio_fusion.create_studio_job(payload)

    assert first["id"] == second["id"]
    assert second["deduplicated"] is True
    assert len(list((tmp_path / "jobs").glob("*.json"))) == 1


def test_cancel_and_gallery(monkeypatch, tmp_path):
    monkeypatch.setattr(studio_fusion, "STATE_DIR", tmp_path)
    monkeypatch.setattr(studio_fusion, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(studio_fusion, "IDEMPOTENCY_FILE", tmp_path / "idempotency.json")
    monkeypatch.setattr(studio_fusion, "_http_ok", lambda url, timeout=0.5: False)

    image_job = studio_fusion.create_studio_job({"mode": "image", "prompt": "portrait prompt"})
    video_job = studio_fusion.create_studio_job({"mode": "video", "video_task": "text_to_video", "prompt": "video prompt"})
    cancelled = studio_fusion.cancel_studio_job(image_job["id"])

    assert cancelled is not None
    assert cancelled["status"] == "cancelled"
    assert cancelled["progress"]["stage"] == "cancelled"

    gallery = studio_fusion.get_studio_gallery(limit=10)
    assert len(gallery) >= 2
    ids = {item["id"] for item in gallery}
    assert image_job["id"] in ids
    assert video_job["id"] in ids
