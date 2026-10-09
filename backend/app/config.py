"""Runtime configuration. Everything is driven by environment variables so the same
code runs fully offline (mock Gemini, in-memory store) or on Google Cloud."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str | None = None) -> str | None:
    v = os.environ.get(key)
    return v if v not in (None, "") else default


def _flag(key: str, default: bool) -> bool:
    return (_env(key, str(default)) or "").lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        # Gemini: mock | vertex | apikey
        self.gemini_backend = _env("GEMINI_BACKEND", "mock")
        self.project = _env("GOOGLE_CLOUD_PROJECT")
        self.vertex_location = _env("VERTEX_LOCATION", "us-central1")
        self.gemini_api_key = _env("GEMINI_API_KEY")
        self.fast_model = _env("GEMINI_FAST_MODEL", "gemini-2.5-flash")
        self.deep_model = _env("GEMINI_DEEP_MODEL", "gemini-2.5-pro")
        # If a live Gemini call fails, fall back to the deterministic mock so a demo never dies.
        self.gemini_fallback = _flag("GEMINI_FALLBACK_TO_MOCK", True)

        # Persistence / events / files
        self.store_backend = _env("STORE_BACKEND", "memory")      # memory | firestore
        self.firestore_db = _env("FIRESTORE_DATABASE", "(default)")
        self.events_backend = _env("EVENTS_BACKEND", "log")       # log | pubsub
        self.blob_backend = _env("BLOB_BACKEND", "local")         # local | gcs
        self.bucket = _env("EVIDENCE_BUCKET")
        self.local_dir = Path(_env("LOCAL_DATA_DIR", str(Path(__file__).resolve().parents[1] / ".data")))

        # Auth: none (demo role header) | firebase (verify ID tokens)
        self.auth_mode = _env("AUTH_MODE", "none")

        # Privacy / intel
        self.hmac_salt = _env("INDICATOR_HMAC_SALT", "demo-consortium-salt-change-me")
        self.dlp_enabled = _flag("DLP_ENABLED", False)
        self.webrisk_enabled = _flag("WEBRISK_ENABLED", False)

        # Static frontend (built web/dist) served by the API container
        self.static_dir = Path(_env("STATIC_DIR", str(Path(__file__).resolve().parents[2] / "web" / "dist")))

    def public(self) -> dict:
        return {
            "gemini_backend": self.gemini_backend,
            "fast_model": self.fast_model if self.gemini_backend != "mock" else "mock-heuristic",
            "deep_model": self.deep_model if self.gemini_backend != "mock" else "mock-heuristic",
            "store_backend": self.store_backend,
            "events_backend": self.events_backend,
            "blob_backend": self.blob_backend,
            "auth_mode": self.auth_mode,
        }


settings = Settings()
