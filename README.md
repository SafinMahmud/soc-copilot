# AI SOC Investigation Copilot

**Splunk AI Hackathon — Security Track**

An autonomous AI copilot that helps security analysts investigate incidents using Splunk data. It converts natural language to SPL, runs multi-step investigations, and produces structured outputs: severity, attack timeline, MITRE ATT&CK mapping, and prioritized remediation steps.

## Problem and value

SOC analysts spend hours pivoting across logs, writing SPL, and documenting findings. This project compresses that workflow:

- **Query mode:** English question → SPL → Splunk results (transparent, editable SPL shown).
- **Investigate mode:** Entity (IP, user, host) → autonomous multi-query Splunk investigation → AI-synthesized incident report.

Built for Splunk environments with **Foundation-Sec** (Splunk’s security-tuned model family) via self-hosted Ollama, with deterministic fallbacks for reliable demos.

## Features

| Feature | Description |
|---------|-------------|
| Natural language → SPL | Ask questions in plain English; backend executes SPL against Splunk |
| Autonomous investigation | Deterministic agent runs 5+ correlated SPL queries per entity |
| Structured report | Severity, rationale, timeline, MITRE techniques, remediation playbook |
| Splunk-native evidence | All findings sourced from real Splunk search results |
| AI synthesis | Foundation-Sec 8B (Ollama) generates report JSON from raw query results |
| Demo-safe fallbacks | `AI_PROVIDER=mock` and template SPL when LLM is unavailable |
| GCP deployment | Cloud Run frontend/backend, Splunk + Ollama on GCE, cost-aware VM auto-stop |

## Architecture

See **[architecture.md](./architecture.md)** for the full diagram (Mermaid + ASCII), Splunk integration, AI/agent flow, and data paths between browser, API, Splunk, and Ollama.

## Demo

- **Live app:** https://soc-frontend-v5upnophmq-uc.a.run.app  
- **Demo video:** *[Add your YouTube/Vimeo/Youku link before submission]*

**Before demo:** ensure Splunk and (for investigate) Ollama VMs are running if using the GCP deployment.

## Requirements

- Python 3.11+
- Node.js 18+
- Splunk Enterprise (developer license) with security sample data ([BOTS v3](https://github.com/splunk/botsv3) recommended)
- For AI synthesis: Ollama with Foundation-Sec GGUF, or Hugging Face token (`AI_PROVIDER=hf`), or `AI_PROVIDER=mock` for no LLM

## Quick start (local)

### 1. Splunk

1. Install Splunk Enterprise and start the management port (`8089`).
2. Load data:
   - **Recommended:** [BOTS v3](https://github.com/splunk/botsv3)
   - **Alternative:** `python data/generate_sample_data.py` (requires HEC on `8088`, set `SPLUNK_HEC_TOKEN`)

### 2. Backend

```bash
cd backend
cp .env.example .env
# Edit: SPLUNK_*, AI_PROVIDER (ollama | hf | mock), OLLAMA_* if using Ollama
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Health check: http://localhost:8001/api/health

### 3. Frontend

```bash
cd frontend
cp .env.local.example .env.local
# BACKEND_URL=http://localhost:8001
npm install
npm run dev
```

Open http://localhost:3000

## Usage examples

1. **Query:** `Show top sourcetypes in the last 24 hours`
2. **Investigate:** `Investigate IP 23.20.239.12`
3. **Investigate:** `Investigate user administrator`

## AI providers

| `AI_PROVIDER` | Behavior |
|---------------|----------|
| `ollama` | Foundation-Sec via local or GCE Ollama (production default on GCP) |
| `hf` | Hugging Face serverless inference |
| `mock` | Deterministic SPL + template reports (no external LLM, best for dry runs) |

Query endpoint uses **deterministic SPL by default** for speed and stability. Set `QUERY_USE_LLM_SPL=true` to enable LLM SPL generation.

## Project structure

```
soc-copilot/
├── architecture.md      # Required architecture diagram (this repo)
├── LICENSE              # MIT
├── README.md
├── backend/             # FastAPI + Splunk SDK + agent
├── frontend/            # Next.js UI
├── data/                # Sample HEC data generator
└── DEMO_RUNBOOK.md      # Step-by-step demo guide
```

## Dependencies

- **Backend:** `backend/requirements.txt` (FastAPI, splunk-sdk, httpx, google-cloud-compute, …)
- **Frontend:** `frontend/package.json` (Next.js 14, React, Tailwind)
- **Data script:** `data/requirements.txt` (requests)

## Configuration

- `backend/.env.example` — Splunk, Ollama, GCE LLM lifecycle, CORS, HF fallback
- `frontend/.env.local.example` — `BACKEND_URL` for API proxy

Never commit `.env` files or secrets.

## GCP deployment (optional)

Cloud Run services with Splunk and Ollama on private GCE VMs. See local-only deploy notes if you have `DEPLOY_GCP_LOCAL.md` (gitignored).

## License

MIT — see [LICENSE](./LICENSE).
