from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .core.events import bus
from .core.gemini import call_log

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .trustshield import data as ts_data

    ts_data.seed()
    yield


app = FastAPI(title="TrustShield - Pre-payment Scam Protection", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

from .trustshield.router import router as ts_router  # noqa: E402

app.include_router(ts_router)


@app.get("/api/health")
def health():
    return {"ok": True, "config": settings.public()}


@app.get("/api/system/gemini-calls")
def gemini_calls(n: int = 30):
    return call_log.recent(n)


@app.get("/api/system/events")
def events(n: int = 40, prefix: str | None = None):
    return bus().recent(n, prefix)


# ---- serve the built React app (single-container deploy) ----
if settings.static_dir.exists():
    app.mount("/assets", StaticFiles(directory=settings.static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        f = settings.static_dir / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(settings.static_dir / "index.html")
