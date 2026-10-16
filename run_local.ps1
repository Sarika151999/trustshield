# Runs the TrustShield POC locally (offline mock Gemini by default).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt
Push-Location web
if (-not (Test-Path node_modules)) { npm.cmd install }
npm.cmd run build
Pop-Location
Set-Location backend
Write-Host "Open http://localhost:8080"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8080
