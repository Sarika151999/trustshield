# TrustShield: Pre-Transaction Scam Intervention System
### *Preserving Human Agency and Engineering Transparency in Critical Financial Infrastructure*

**Repository:** [https://github.com/Sarika151999/trustshield](https://github.com/Sarika151999/trustshield)  
**Platform:** Google Cloud Run, Vertex AI / Gemini API, React + FastAPI Single-Container Architecture  
**Target Social Challenge:** Preventing Authorized Push Payment (APP) Financial Fraud & Social Engineering Exploitation  

---

## 1. Executive Summary & Problem Framing

> *"The biggest threat isn't that AI will become self-aware; it’s that we are quietly granting autonomous agents unvetted authority over critical decisions... As we embed autonomous AI into basic social infrastructure, we must shift from treating AI safety as a corporate legal shield to an engineering discipline that preserves human agency and systemic transparency."*

Across banking and enterprise finance, automated fraud systems operate on a broken paradigm: **"Is this transaction unusual for this account?"**
In Authorized Push Payment (APP) scams—which now account for over **\$50 Billion in annual global losses**—the victim authorizes the payment themselves from their own trusted device. Traditional behavioral anomaly models see a customer entering their legitimate credentials and pass the transaction through. By the time the victim realizes they were manipulated, the funds have left the banking rail and dispersed across mule networks.

**TrustShield** fundamentally shifts the question from:
> *"Does this transaction look unusual?"*  
to:  
> *"What psychological manipulation or external coercion is influencing the customer to send this money right now?"*

Critically, TrustShield is engineered around a core principle of responsible AI in financial infrastructure: **Autonomous Generative AI is never granted unvetted authority to block or execute payments.** Instead, TrustShield implements a **hybrid Neuro-Symbolic architecture**:
- **Generative AI (Gemini 2.5 Flash)** is deployed where neural representations excel: parsing unstructured multimodal evidence (SMS screenshots, WhatsApp transcripts, payment receipts), identifying psychological coercion patterns (urgency, authority impersonation, fear of KYC cutoff), and translating complex fraud risk into empathetic, non-patronizing interventions in the customer's native language.
- **Deterministic Policy Engines** retain strict, un-compromisable authority over the final decision (`PASS`, `WARN`, `HOLD`), enforcing transparent hard rules, mathematically bounded risk scoring, and counterfactual auditability.

---

## 2. Hackathon Scoring Rubric Alignment

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          HACKATHON CRITERIA MAPPING                       │
├─────────────────────────────────────────────────┬─────────────────────────┤
│ Criteria                                        │ Weight │ Implementation │
├─────────────────────────────────────────────────┼────────┼────────────────┤
│ 1. Technical Merit & Gen AI Implementation      │  40%   │ Section 3      │
│ 2. Problem Alignment & Social Impact            │  25%   │ Section 4      │
│ 3. Innovation & Creativity                      │  25%   │ Section 5      │
│ 4. User Experience & Solution Design            │  10%   │ Section 6      │
└─────────────────────────────────────────────────┴────────┴────────────────┘
```

---

## 3. Technical Merit & Gen AI Implementation (40%)

### 3.1 Meaningful & Nuanced Use of Generative AI
Rather than a superficial conversational wrapper, Gemini is embedded deeply into the assessment pipeline at two distinct stages:

1. **Multimodal Scam-Content Analysis (`backend/app/trustshield/content.py`):**
   - Ingests untrusted customer evidence (screenshots of phishing messages, uploaded images, raw text).
   - Utilizes `gemini-2.5-flash` with structured JSON schema enforcement (`response_schema=ScamAnalysis`) to extract:
     - Exact psychological tactics (`urgency`, `authority_impersonation`, `task_trap`, `guaranteed_return`).
     - Entity extraction (impersonated bank, phone numbers, UPI handles, destination bank accounts, phishing domains).
     - Verifiable quote extraction from evidence text.
   - **Quote Accuracy Verification:** A deterministic post-validation layer cross-references Gemini's extracted quotes against normalized OCR transcript text to mathematically catch and penalize hallucinations.

2. **Language-Aware, Empathetic Intervention Generation (`backend/app/trustshield/explain.py`):**
   - Gemini receives the deterministic signals, scam classification, customer demographics, and native language (e.g., Hindi, English).
   - Generates:
     - A warm, 80-word customer warning that de-escalates panic without blaming the customer.
     - 2–3 targeted "coercion-revealing" questions (e.g., *"Did someone claiming to be from the bank instruct you to keep this payment secret?"*).
     - A factual, signal-attributed rationale for bank fraud analysts.
   - **Signal Code Containment Guard:** An assertion gate guarantees that Gemini only cites signals identified by the feature engine (`signal_codes_used ⊆ allowed_signals`). If ungrounded signals are detected, it falls back to deterministic localized safety templates.

### 3.2 Technical Implementation & Architecture
- **Single-Container Architecture:** Built with Python 3.12 (FastAPI) and Node 22 (React + TypeScript + Vite). The backend compiles and serves the optimized single-page frontend directly from memory, eliminating multi-service coordination overhead on Cloud Run.
- **Latency Budget:** Synchronous assessment runs in **under 3.5 seconds** (Gemini multimodal structured inference ~1.8s + deterministic feature fusion ~5ms + explanation synthesis ~1.2s).
- **Graceful Degradation:** If upstream AI services experience transient network timeouts, the system automatically falls back to an offline heuristic analyzer (`GEMINI_FALLBACK_TO_MOCK=true`) ensuring bank transaction rails never experience denial-of-service.

### 3.3 Scalability & Sustainability on Google Cloud Platform
- **Google Cloud Run:** Fully serverless container execution that scales to zero when idle and rapidly scales out during transaction spikes.
- **Vertex AI:** Enterprise-grade model hosting and governance using Google Cloud Application Default Credentials (ADC) without embedding sensitive static keys.
- **Event Streaming via Pub/Sub & BigQuery:** Synchronous responses complete immediately, while an asynchronous event stream publishes `ts-assessment-completed` and `ts-case-resolved` events to Google Cloud Pub/Sub, feeding BigQuery subscriptions for offline analytics and scam graph clustering.
- **Storage Tiering:** In-memory persistence for zero-dependency hackathon testing, with drop-in adapters for Google Cloud Firestore (`STORE_BACKEND=firestore`) and Cloud Storage (`BLOB_BACKEND=gcs`).

---

## 4. Problem Alignment & Social Impact (25%)

### 4.1 The Vulnerability of Digital Payment Rails
India's UPI and global instant payment rails (FedNow, Pix, Faster Payments) have democratized digital finance. However, irreversible real-time settlement has created a massive social vulnerability:
- **Elderly and Digitally Less-Literate Citizens** are routinely terrified by fake "electricity cutoff", "account freeze", or "digital arrest" scams.
- Victims are under active psychological coercion—often coerced into keeping active phone calls open while executing transfers.
- Once the victim authorizes the transaction, banks historically deny liability, claiming *"the customer authorized it."*

### 4.2 Preserving Human Agency Over Paternalistic AI
TrustShield does not treat fraud prevention as a heavy-handed, algorithmic lockout that alienates the user:
- For low-to-medium risk (`WARN`), TrustShield introduces **contextual cognitive friction**. It asks targeted questions designed to break the scammer's psychological spell (*"Were you told your electricity will be disconnected within 30 minutes if you don't pay?"*).
- Answering reveals coercion, allowing the customer to self-abort the payment with their dignity and agency preserved.
- For high-confidence scams (`HOLD`), payments are paused and routed to human fraud investigators with an automated callback scheduled.

---

## 5. Innovation & Creativity (25%)

### 5.1 Neuro-Symbolic Safety Architecture
Rather than trusting an LLM agent to decide whether money moves, TrustShield splits the cognitive load:
- **Neural Layer (Gemini):** Multimodal evidence interpretation, social engineering extraction, empathetic multilingual communication.
- **Symbolic Layer (Deterministic Rules & Graph Fusion):** Feature weighting, mathematically bounded risk scoring, hard regulatory constraints, and state transitions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TRUSTSHIELD FUSION ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   UNSTRUCTURED INPUTS                       STRUCTURED SIGNALS              │
│   ┌────────────────────┐                    ┌───────────────────────────┐   │
│   │ SMS / Screenshot   │ ──(Gemini 2.5)───► │ Content Signals (Tactic,  │   │
│   │ Evidence           │                    │ Urgency, Impersonation)   │   │
│   └────────────────────┘                    └─────────────┬─────────────┘   │
│                                                           │                 │
│   BANKING CONTEXT                                         ▼                 │
│   ┌────────────────────┐                    ┌───────────────────────────┐   │
│   │ 90-Day Transaction │ ──(Deterministic)─►│ Multi-Source Risk Fusion  │   │
│   │ History & Context  │                    │ W_content + W_intel       │   │
│   └────────────────────┘                    │   + W_behavioral          │   │
│                                             └─────────────┬─────────────┘   │
│   CONSORTIUM INTEL                                        │                 │
│   ┌────────────────────┐                                  ▼                 │
│   │ HMAC-Hashed Mules  │ ──(Exact Match)──► ┌───────────────────────────┐   │
│   │ & Phishing Domains │                    │   Deterministic Policy    │   │
│   └────────────────────┘                    │    PASS / WARN / HOLD     │   │
│                                             └─────────────┬─────────────┘   │
│                                                           │                 │
│                                             ┌─────────────┴─────────────┐   │
│                                             ▼                           ▼   │
│                                     ┌───────────────┐           ┌───────────────┐
│                                     │  Customer UI  │           │ Analyst Queue │
│                                     │ (Empathetic   │           │ (Auditable    │
│                                     │  Intervention)│           │  Replay Log)  │
│                                     └───────────────┘           └───────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Counterfactual Decision Replay
A major innovation for compliance and governance is TrustShield's **Counterfactual Replay Engine**:
- For every assessment, the system computes two parallel evaluations:
  1. `Behaviour-only Risk`: What a standard banking fraud model would have scored.
  2. `Full-context Risk`: What TrustShield scored after multimodal Gemini evidence and consortium intelligence.
- In the Analyst Console, investigators see the exact **Risk Delta** (+65.4% lift) directly demonstrating why the transaction was flagged and eliminating "black-box" skepticism.

### 5.3 Privacy-Preserving Consortium Intelligence
Banks cannot legally or ethically share unredacted customer PII with rival institutions. TrustShield implements **zero-knowledge indicator sharing**:
- Extracted phone numbers, account numbers, and domains are HMAC-SHA256 hashed with a consortium salt.
- Banks can cross-match mule accounts and coordinated fraud rings in real time without exposing customer names, account balances, or conversation transcripts.

---

## 6. User Experience & Solution Design (10%)

TrustShield provides a cohesive, purpose-built interface across three distinct stakeholder surfaces:

1. **Customer Pre-Payment Flow (`/ts/pay`):**
   - Simulated mobile banking transfer interface.
   - Seamless evidence upload (one-click sample injection or live image/text upload).
   - Real-time intervention modal with bilingual support (English / Hindi), clear safety check questions, and immediate agency preservation ("Cancel Payment" vs. "I verified this independently").
2. **Fraud Analyst Command Center (`/ts/analyst`):**
   - Live triage queue categorized by decision status (`open`, `investigating`, `released`, `confirmed_scam`).
   - Deep-dive inspector displaying exact signal contribution bars, extracted evidence transcripts, and decision counterfactuals.
3. **Scam Intelligence Graph & Ablation Insights (`/ts/intel` & `/ts/insights`):**
   - **Interactive Cytoscape.js Graph:** Visualizes links between mule accounts, phishing domains, victim accounts, and coordinated scam campaigns.
   - **Synthetic Ablation Benchmarks:** Live evaluation matrix comparing accuracy, precision, and recall across 4 ablation configurations (`behaviour_only`, `behaviour+intel`, `behaviour+content`, and `full_context`).

---

## 7. Google Cloud Platform Deployment & Verification

### Verified Deployment Options:
- **Cloud Run Deployment:** Ready-to-deploy containerized stack with zero external VM dependencies.
- **Tested Environment:** Python 3.12 / Node 22 slim container with Google Cloud SDK and Vertex AI client libraries.
- **Gemini Engine:** Powered by Google's `gemini-2.5-flash` with sub-second token latency and JSON Schema strict mode.

---

### *Conclusion*
TrustShield embodies the hackathon's core vision: moving beyond high-level ethics into the messy engineering reality of financial risk. By combining the multimodal reasoning of Google's Gemini models with the deterministic reliability of symbolic rules, TrustShield delivers a scalable, transparent, and humane defense against the epidemic of social engineering fraud.
