# SOC Copilot Demo Runbook

Step-by-step guide for live demos and hackathon video recording.

## Live deployment (GCP)

- **Frontend:** https://soc-frontend-v5upnophmq-uc.a.run.app  
- **Backend health:** https://soc-backend-v5upnophmq-uc.a.run.app/api/health  

### Pre-demo (5–10 min before)

```bash
gcloud compute instances start splunk-demo --zone=us-central1-a
gcloud compute instances start ollama-llm --zone=us-central1-a
```

Wait ~3–5 minutes, then run one investigation in the UI to warm up Ollama.

### After demo (save credits)

```bash
gcloud compute instances stop splunk-demo --zone=us-central1-a
gcloud compute instances stop ollama-llm --zone=us-central1-a
```

## Local demo

### 1. Pre-demo checklist

1. Splunk running with data in `botsv3` or `main`
2. Backend: `cd backend && uvicorn main:app --reload --port 8001`
3. Frontend: `cd frontend && npm run dev`
4. Health: http://localhost:8001/api/health → `{"status":"ok"}`

### 2. Provider mode (`backend/.env`)

| Mode | Config |
|------|--------|
| **Ollama (recommended)** | `AI_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434` |
| **Hugging Face** | `AI_PROVIDER=hf`, `HF_TOKEN=...` |
| **Reliable fallback** | `AI_PROVIDER=mock` |

Restart backend after changing `.env`.

### 3. Demo flow

**Part A — Query (~30s)**  
- `Show top sourcetypes in the last 24 hours`  
- Highlight SPL transparency + results table

**Part B — Investigate (~60–120s)**  
- `Investigate IP 23.20.239.12`  
- Highlight severity, summary, queries run

**Part C — Report (~45s)**  
- Timeline → MITRE cards → Remediation playbook

### 4. Backup if LLM fails

Set `AI_PROVIDER=mock`, restart backend, refresh UI.

> “Splunk queries remain real; report synthesis uses deterministic fallback.”

### 5. Troubleshooting

| Issue | Fix |
|-------|-----|
| Failed to fetch | Check `BACKEND_URL` / frontend proxy; hard refresh |
| Splunk 503 | Start Splunk VM or local Splunk |
| Investigate timeout | Warm Ollama VM first; first cold run can take several minutes |
| Port conflict | Backend on `8001` (Splunk web uses `8000`) |

Full video script: see `HACKATHON_DEMO_SCRIPT_LOCAL.md` (local only, gitignored).
