#!/usr/bin/env bash
# Runs the TrustShield POC locally (offline mock Gemini by default).
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
PY=.venv/bin/python; [ -f "$PY" ] || PY=.venv/Scripts/python
"$PY" -m pip install -q -r backend/requirements.txt
(cd web && { [ -d node_modules ] || npm install; })
(cd web && npm run build)
cd backend && echo "Open http://localhost:8080" && "../$PY" -m uvicorn app.main:app --port 8080
