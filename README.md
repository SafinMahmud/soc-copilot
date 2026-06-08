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

## Hackathon submission checklist

| Requirement | Location |
|-------------|----------|
| Open source license (MIT) | [LICENSE](./LICENSE) |
| Source code | `backend/`, `frontend/` |
| Setup and run instructions | This README + [DEMO_RUNBOOK.md](./DEMO_RUNBOOK.md) |
| Dependencies | [backend/requirements.txt](./backend/requirements.txt), [frontend/package.json](./frontend/package.json), [data/requirements.txt](./data/requirements.txt) |
| Example configuration | [backend/.env.example](./backend/.env.example), [frontend/.env.local.example](./frontend/.env.local.example) |
| Example dataset generator | [data/generate_sample_data.py](./data/generate_sample_data.py) |
| Architecture diagram (repo root) | [architecture_diagram.md](./architecture_diagram.md) — Splunk integration, AI/agent flow, service data paths ([architecture.md](./architecture.md) alias) |

## Architecture

See **[architecture_diagram.md](./architecture_diagram.md)** for the required diagram (Mermaid + ASCII) showing:

- How the app queries Splunk via the management API (`8089`)
- How Foundation-Sec (Ollama) synthesizes investigation reports
- Data flow: browser → Next.js → FastAPI → Splunk / Ollama

## Demo

- **Live app:** https://soc-frontend-v5upnophmq-uc.a.run.app  
- **Demo video:** https://youtu.be/RzBp3Caarh8

**Before demo:** ensure Splunk and (for investigate) Ollama VMs are running if using the GCP deployment.

## Project description

SOC Copilot is an AI-powered security investigation assistant built for the Splunk AI Hackathon. It helps SOC analysts move from raw logs to actionable incident reports in minutes instead of hours.

Analysts interact through a chat-style web UI in two modes. In **query mode**, they ask questions in plain English—such as “show top sourcetypes in the last 24 hours”—and the backend converts the request to Splunk SPL, runs it against live indexes, and returns transparent results with the exact query shown. In **investigate mode**, they name a suspicious entity—an IP, user, or hostname—and the system runs an autonomous, deterministic investigation playbook: correlated Splunk searches for authentication failures, successful logins, network activity, and raw evidence. Those findings are then synthesized by **Foundation-Sec**, Splunk’s security-tuned language model (via Ollama), into a structured incident report with severity rating, executive summary, chronological attack timeline, MITRE ATT&CK technique mapping, and a prioritized remediation playbook.

All evidence comes from real Splunk data—primarily **BOTS v3**-style telemetry in `botsv3` and `main` indexes, including Windows security events, network flows, web logs, and Linux authentication. The AI does not invent attack data; it interprets what Splunk returns. The architecture separates concerns cleanly: Splunk is the source of truth, the FastAPI backend orchestrates queries and agents, and Foundation-Sec handles natural-language synthesis. The stack deploys on GCP with a Next.js frontend and FastAPI backend on Cloud Run, Splunk Enterprise on a private VM, and Ollama hosting Foundation-Sec in the same VPC—with cost-aware auto-stop for idle LLM infrastructure.

Open source under MIT. Full setup instructions, sample data generator, and architecture diagram are included in this repository.

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

## Data sources

Evidence is read from Splunk indexes **`botsv3`** and **`main`** (BOTS v3 recommended):

| Source | Sourcetype | Fields used |
|--------|------------|-------------|
| Windows authentication | `WinEventLog:Security` | `EventCode` 4625/4624, `src_ip`, `user`, `dest` |
| Network flows | `stream:tcp` | `src_ip`, `dest_ip`, `dest_port`, `bytes_in`, `bytes_out` |
| Web access | `iis` | `c_ip`, `cs_uri_stem`, `sc_status` |
| Linux authentication | `linux_secure` | `user`, `src`, `action` |

Load data with [BOTS v3](https://github.com/splunk/botsv3) or run `python data/generate_sample_data.py` (synthetic brute-force scenario for IP `23.20.239.12`).

## Usage examples

**Query mode** (ad-hoc Splunk questions):

- `Show top sourcetypes in the last 24 hours`
- `Show recent events`
- `Show failed logins in the last 24 hours`

**Investigate mode** (autonomous entity investigation):

- `Investigate IP 23.20.239.12`
- `Investigate user administrator`
- `Investigate host wrk-splunk`

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
├── architecture_diagram.md # Required architecture diagram (hackathon filename)
├── architecture.md       # Same content as architecture_diagram.md
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
