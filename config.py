#!/usr/bin/env python3
"""Centralized configuration for CANDY.NSFW+ and NovaMaster Chat.

All paths and tunables live here.  Values come from env vars with
sensible defaults so the app works out-of-the-box on the dev machine.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env files in priority order (first found wins per key)
for _env in (
    Path(__file__).resolve().parent / ".env",
    Path.home() / ".env",
):
    if _env.exists():
        load_dotenv(_env, override=False)

# ── directories ──────────────────────────────────────────────────────
OUTPUT_DIR: Path = Path(os.getenv("CANDY_OUTPUT_DIR", "/home/faramix/avatar_engine/output"))
NSFW_MODELS_DIR: Path = Path(os.getenv("CANDY_NSFW_MODELS_DIR", "/home/faramix/Mark-XXX/cache"))
AVATAR_DIR: Path = Path(os.getenv("CANDY_AVATAR_DIR", "/home/faramix/avatar_engine/identities"))
VOICE_CACHE_DIR: Path = Path(os.getenv("CANDY_VOICE_CACHE_DIR", "/tmp/nova_voice_cache"))

# ── external scripts ────────────────────────────────────────────────
SUPERGROK_SCRIPT: Path = Path(os.getenv(
    "CANDY_SUPERGROK_SCRIPT", "/home/faramix/nova_supergrok_auto.py",
))
GROK_IMAGINE_SCRIPT: Path = Path(os.getenv(
    "CANDY_GROK_IMAGINE_SCRIPT", "/home/faramix/grok-imagine-app/grok-imagine.py",
))
VENICE_AUTO_SCRIPT: Path = Path(os.getenv(
    "CANDY_VENICE_AUTO_SCRIPT", "/home/faramix/nova_venice_auto.py",
))

# ── default avatar / input images (tried in order) ──────────────────
DEFAULT_IMAGE_PATHS: list[str] = [
    os.getenv("CANDY_DEFAULT_IMAGE", "/home/faramix/Downloads/download.jpg"),
    str(Path(__file__).resolve().parent / "assets" / "candy_face.jpg"),
    str(Path(__file__).resolve().parent / "avatar_engine" / "candy_face.jpg"),
]

# ── API key names to look for ───────────────────────────────────────
API_KEY_NAMES: list[str] = [
    "VENICE_API_KEY",
    "GROK_VENICE_API_KEY",
]

# ── env files to search for extra keys ──────────────────────────────
EXTRA_ENV_PATHS: list[str] = [
    os.getenv("CANDY_EXTRA_ENV_1", "/home/faramix/.env"),
    os.getenv("CANDY_EXTRA_ENV_2", "/home/faramix/.hermes/.env"),
    os.getenv("CANDY_EXTRA_ENV_3", "/home/faramix/.openclaw/.env"),
]

# ── SQLite database ─────────────────────────────────────────────────
DB_PATH: Path = Path(os.getenv(
    "CANDY_DB_PATH",
    str(Path(__file__).resolve().parent / "candy_chat.db"),
))

# ── rate limits ──────────────────────────────────────────────────────
RATE_LIMIT_GENERATE: str = os.getenv("CANDY_RATE_LIMIT_GENERATE", "10/minute")
RATE_LIMIT_BATCH: str = os.getenv("CANDY_RATE_LIMIT_BATCH", "2/minute")

# ── server ports ─────────────────────────────────────────────────────
NSFW_API_PORT: int = int(os.getenv("CANDY_NSFW_API_PORT", "9500"))
CHAT_API_PORT: int = int(os.getenv("CANDY_CHAT_API_PORT", "8069"))
