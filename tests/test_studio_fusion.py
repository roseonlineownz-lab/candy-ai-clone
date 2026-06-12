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
    assert job["status"] == "queued"
    assert job["provider"] in {"wan-local", "video-factory", "higgsfield", "manual"}
    assert json.loads(manifest.read_text())["prompt"].startswith("cinematic")


def test_create_studio_job_validates_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr(studio_fusion, "STATE_DIR", tmp_path)
    monkeypatch.setattr(studio_fusion, "JOBS_DIR", tmp_path / "jobs")

    with pytest.raises(ValueError):
        studio_fusion.create_studio_job({"mode": "image", "prompt": ""})
