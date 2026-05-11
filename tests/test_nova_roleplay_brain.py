"""Tests for the persona loader vault-override path.

These tests run without any real vault present. They monkey-patch
UNCENSORED_VAULT_PATH and re-import the module to exercise the loader.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def _reload_brain():
    # Drop any cached import so the module-level _load_external_personas() runs again.
    sys.modules.pop("avatar_engine.nova_roleplay_brain", None)
    return importlib.import_module("avatar_engine.nova_roleplay_brain")


def test_builtin_personas_when_env_unset(monkeypatch):
    monkeypatch.delenv("UNCENSORED_VAULT_PATH", raising=False)
    brain = _reload_brain()
    assert brain.PERSONAS is brain._BUILTIN_PERSONAS
    assert "nova" in brain.PERSONAS
    assert brain.personas_source() == "builtin"


def test_vault_override_replaces_personas(monkeypatch, tmp_path: Path):
    vault = tmp_path / "vault"
    repo_dir = vault / "candy-ai-clone"
    repo_dir.mkdir(parents=True)
    payload = {
        "alpha": {
            "name": "Alpha",
            "type": "test",
            "system_prompt": "You are Alpha.",
            "voice": "nl-BE-DenaNeural",
            "avatar": "alpha.jpg",
        }
    }
    (repo_dir / "personas.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("UNCENSORED_VAULT_PATH", str(vault))
    brain = _reload_brain()

    # Vault wins entirely — built-in personas are not merged in.
    assert set(brain.PERSONAS) == {"alpha"}
    assert brain.PERSONAS["alpha"]["system_prompt"] == "You are Alpha."
    assert brain.personas_source().startswith("vault:")


def test_vault_missing_file_falls_back(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("UNCENSORED_VAULT_PATH", str(tmp_path / "does-not-exist"))
    brain = _reload_brain()
    assert brain.PERSONAS is brain._BUILTIN_PERSONAS


def test_vault_invalid_json_falls_back(monkeypatch, tmp_path: Path):
    repo_dir = tmp_path / "candy-ai-clone"
    repo_dir.mkdir(parents=True)
    (repo_dir / "personas.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("UNCENSORED_VAULT_PATH", str(tmp_path))
    brain = _reload_brain()
    assert brain.PERSONAS is brain._BUILTIN_PERSONAS


def test_vault_skips_invalid_entries(monkeypatch, tmp_path: Path):
    repo_dir = tmp_path / "candy-ai-clone"
    repo_dir.mkdir(parents=True)
    payload = {
        "ok": {"name": "Ok", "type": "t", "system_prompt": "valid"},
        "no_prompt": {"name": "X", "type": "t"},
        "not_a_dict": "string",
    }
    (repo_dir / "personas.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("UNCENSORED_VAULT_PATH", str(tmp_path))
    brain = _reload_brain()
    assert set(brain.PERSONAS) == {"ok"}


def test_vault_empty_after_validation_falls_back(monkeypatch, tmp_path: Path):
    repo_dir = tmp_path / "candy-ai-clone"
    repo_dir.mkdir(parents=True)
    (repo_dir / "personas.json").write_text(json.dumps({"bad": {}}), encoding="utf-8")
    monkeypatch.setenv("UNCENSORED_VAULT_PATH", str(tmp_path))
    brain = _reload_brain()
    assert brain.PERSONAS is brain._BUILTIN_PERSONAS
