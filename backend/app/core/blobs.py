"""File storage: local folder (dev) or Cloud Storage (cloud)."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import settings


class LocalBlobs:
    def __init__(self) -> None:
        self.root = settings.local_dir / "blobs"
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key: str) -> Path:
        return self.root / key.replace("/", "__")

    def put(self, key: str, data: bytes, mime: str) -> str:
        self._p(key).write_bytes(data)
        self._p(key).with_suffix(".meta").write_text(json.dumps({"mime": mime}))
        return f"local://{key}"

    def get(self, key: str) -> tuple[bytes, str]:
        mime = json.loads(self._p(key).with_suffix(".meta").read_text())["mime"]
        return self._p(key).read_bytes(), mime


class GcsBlobs:
    def __init__(self) -> None:
        from google.cloud import storage

        self.bucket = storage.Client(project=settings.project).bucket(settings.bucket)

    def put(self, key: str, data: bytes, mime: str) -> str:
        self.bucket.blob(key).upload_from_string(data, content_type=mime)
        return f"gs://{self.bucket.name}/{key}"

    def get(self, key: str) -> tuple[bytes, str]:
        b = self.bucket.blob(key)
        data = b.download_as_bytes()
        return data, b.content_type or "application/octet-stream"


_blobs: LocalBlobs | GcsBlobs | None = None


def blobs() -> LocalBlobs | GcsBlobs:
    global _blobs
    if _blobs is None:
        _blobs = GcsBlobs() if settings.blob_backend == "gcs" else LocalBlobs()
    return _blobs
