# TrustShield POC

TrustShield is a hackathon proof of concept for intervening in scam payments before money leaves a customer's account. It evaluates a simulated payment together with message or screenshot evidence and returns **PASS**, **WARN**, or **HOLD**, with separate customer and analyst explanations.

The core product idea is: fraud systems ask whether a transaction looks unusual; TrustShield asks what may be influencing the customer to make it.

## Demo

The app starts on the simulated payment flow. Use the seeded customers and evidence samples to try a suspicious payment, review the decision, then open the analyst, scam intelligence, or insights screens. All people, banks, indicators, evidence, and metrics are synthetic. No real payment is initiated.

```powershell
Copy-Item .env.example .env
.\run_local.ps1
```

Open <http://localhost:8080>. Local defaults use heuristic Gemini stand-ins, in-memory storage, local evidence files, and no authentication, so the demo runs without Google Cloud credentials. On Windows, the launcher uses `npm.cmd` to work with the default PowerShell execution policy.

### Manual setup

Prerequisites: Python 3.11+ and Node.js 18+.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Push-Location web
npm.cmd install
npm.cmd run build
Pop-Location
Push-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8080
```

Run backend tests with:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

For frontend hot reload, leave the backend running and start `npm.cmd run dev` from `web`; Vite serves on port 5173 and proxies `/api` to port 8080.

## What the POC does

- Combines deterministic payment-behavior signals, scam-content signals, and hashed indicator intelligence.
- Uses Gemini for structured multimodal evidence analysis and language-aware explanations; the deterministic policy owns the final decision.
- Presents a customer payment flow, safety checks, analyst case queue, linked-indicator graph, and synthetic evaluation/ablation view.
- Includes prompt-injection and legitimate-message samples to exercise both scam and false-positive paths.
- Redacts evidence transcripts and HMAC-hashes extracted identifiers before they are used as shared intelligence.

This is a prototype decision-support experience, not a bank integration or production fraud control.

## Google Cloud path

The backend has optional adapters for **Gemini on Vertex AI**, **Firestore**, **Cloud Storage**, **Pub/Sub**, **Sensitive Data Protection (DLP)**, and **Web Risk**. The container is suitable for **Cloud Run**; Firebase Hosting and Firebase Authentication are optional. Keep local mode for development and provision these services only in a dedicated hackathon project.

1. Create a dedicated Google Cloud project, enable billing, and authenticate with `gcloud auth application-default login`.
2. Provision Vertex AI, Firestore, Cloud Storage, Pub/Sub, DLP, and Web Risk. Create the Pub/Sub topics `ts-assessment-completed`, `ts-case-resolved`, and `ts-intel-shared`.
3. Install cloud dependencies with `python -m pip install -r backend/requirements-gcp.txt` and build the container with `docker build -t trustshield-poc .`.
4. Deploy to Cloud Run with a service account that has only the required roles. Configure `GEMINI_BACKEND=vertex`, `GOOGLE_CLOUD_PROJECT`, and `VERTEX_LOCATION`; enable individual storage, event, auth, DLP, and Web Risk adapters in `.env` or Cloud Run settings.
5. Bind `INDICATOR_HMAC_SALT` from Secret Manager in Cloud Run. Do not use the demo salt or real customer evidence in this POC.

For hosted Firebase auth, fill in `web/.env.local` from `web/.env.example`, build the frontend, and set backend `AUTH_MODE=firebase`. The Cloud Run service must be reachable by Firebase Hosting; Firebase ID tokens are verified by the API.

BigQuery is a natural next step for event analytics: Pub/Sub topics can feed BigQuery subscriptions, while the current insights page evaluates synthetic benchmark cases locally. The GCP adapters and deployment path have not been validated against a live project yet.

## Main folders

- `backend/app/trustshield/`: evidence analysis, behavior features, risk fusion, decisions, analyst cases, and evaluation.
- `backend/app/core/`: Gemini, Firestore, Pub/Sub, Cloud Storage, privacy, auth, and shared utilities.
- `web/src/trustshield/`: payment, analyst, intelligence, graph, and insights experiences.
- `docs/trustshield-design.md`: detailed proposal and design reference from the original project.

All benchmark metrics are synthetic and should be presented as prototype evaluation, not real-world performance.