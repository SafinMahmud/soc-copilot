# SOC Copilot Demo Runbook (Step by Step)

Use this for hackathon recording and live demos.

## 1) Pre-demo checklist (5-10 min before)

1. Open Splunk and confirm data exists:
  - index: `botsv3` (or `main` if synthetic data)
2. Start backend:
  ```bash
   cd backend
   source venv/bin/activate
   uvicorn main:app --reload --port 8001
  ```
3. Start frontend:
  ```bash
   cd frontend
   npm run dev
  ```
4. Open app: `http://localhost:3000`
5. Confirm backend health:
  - `http://localhost:8001/api/health` returns `{"status":"ok"}`

## 2) Choose provider mode

Edit `backend/.env` and set one:

- **Preferred (real AI):**
  ```env
  AI_PROVIDER=gemini
  GEMINI_MODEL=gemini-2.0-flash
  ```
- **Fallback (reliable for demo if Gemini quota fails):**
  ```env
  AI_PROVIDER=mock
  ```

After changing provider, restart backend.

## 3) Demo flow (what to type on screen)

### Part A - Natural language query (30-40s)

Type:
`Show recent events from Splunk internal logs`

Point out:

- Generated SPL is visible (transparency)
- Results table is rendered

Follow-up type:
`Show top sourcetypes in the last 24 hours`

### Part B - Autonomous investigation (45-60s)

Type:
`Investigate IP 23.20.239.12`

Point out:

- Investigation started message
- Severity badge
- Summary and queries run

### Part C - Timeline + MITRE + Remediation (45-60s)

Scroll to:

- **Attack Timeline**: click one event and show raw log
- **MITRE ATT&CK cards**
- **Remediation Playbook** with priorities

If asked, explain:

- In `gemini` mode: decisions/synthesis are model-driven
- In `mock` mode: Splunk queries are real, AI narrative is template-driven fallback

## 4) Backup script if Gemini quota fails mid-demo

1. Stop backend (`Ctrl+C`)
2. Set in `backend/.env`:
  ```env
   AI_PROVIDER=mock
  ```
3. Restart backend:
  ```bash
   uvicorn main:app --reload --port 8001
  ```
4. Refresh frontend and continue demo

Suggested one-line narration:

> "I’m switching to deterministic mock AI mode so the investigation flow remains fully demonstrable even when external LLM quotas are exhausted."

## 5) Quick troubleshooting

- **Port conflict:** keep backend on `8001` (Splunk uses `8000`)
- **500 from backend:** check backend terminal traceback first
- **Splunk auth error:** verify `SPLUNK_USERNAME` / `SPLUNK_PASSWORD` in `backend/.env`
- **No results:** confirm `SPLUNK_INDEX` and time range include your data
- **Gemini 429 quota:** use `AI_PROVIDER=mock`

## 6) Suggested 3-minute narration outline

1. Problem: SOC investigations are manual and slow.
2. Query feature: English -> SPL -> results.
3. Investigation feature: entity-driven multi-step investigation.
4. Outcome: severity, timeline, MITRE mapping, remediation.
5. Close: "Compresses triage/investigation time and is demo-safe with fallback mode."

