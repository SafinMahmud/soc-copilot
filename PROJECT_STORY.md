# SOC Copilot - Project Story

**Splunk AI Hackathon - Security Track**

## Inspiration

SOC analysts spend hours on work that is necessary but repetitive: writing SPL, running isolated searches, pivoting across auth and network logs, and manually turning raw events into something actionable. That usually means a severity rating, a timeline, MITRE mapping, and remediation steps.

I built **SOC Copilot** to compress that workflow without sacrificing trust. The goal was never "an AI that guesses attacks." It was an assistant that **queries Splunk first**, uses real evidence from the SIEM, and applies AI only where it adds clear value: synthesizing findings into a structured incident report analysts can review and act on.

Splunk's **Foundation-Sec** model family was a natural fit. Security-tuned AI should sit on top of real log data, not replace it. That principle guided every design decision in the project.

## What it does

SOC Copilot is a chat-style investigation assistant with two modes:

**Query mode.** Analysts ask questions in plain English (e.g. "show top sourcetypes in the last 24 hours" or "show failed logins"). The backend converts the request to Splunk SPL, executes it against live indexes, and returns transparent results with the exact query shown.

**Investigate mode.** Analysts name a suspicious entity: an IP, user, or hostname (e.g. "Investigate IP 23.20.239.12"). The system runs an autonomous, deterministic Splunk playbook: correlated searches for authentication failures, successful logins, network activity, and raw evidence. **Foundation-Sec** (via Ollama) then produces a structured report:

- Severity rating and rationale
- Executive summary
- Chronological attack timeline
- MITRE ATT&CK technique mapping
- Prioritized remediation playbook

All evidence comes from Splunk indexes (`botsv3`, `main`) with BOTS v3-style telemetry: Windows security events, network flows, web logs, and Linux authentication. The AI interprets what Splunk returns; it does not invent attack data.

**Live demo:** https://soc-frontend-v5upnophmq-uc.a.run.app  
**Demo video:** https://youtu.be/RzBp3Caarh8

## How I built it

```
Browser → Next.js (Cloud Run) → FastAPI (Cloud Run) → Splunk Enterprise (:8089)
                                                    → Ollama / Foundation-Sec (:11434)
```

**Frontend (Next.js)**  
Chat UI, query results table, and a structured investigation report with timeline, MITRE cards, remediation list, and section navigation. A same-origin API proxy forwards `/api/*` to the backend so production never hardcodes localhost.

**Backend (FastAPI)**  
REST endpoints: `/api/query`, `/api/investigate`, `/api/health`. Splunk access uses the official SDK on the management API. The investigation agent runs a fixed, repeatable SPL plan (auditable, not LLM-chosen). Raw findings go to Foundation-Sec for JSON synthesis. Deterministic fallbacks keep the app working when the LLM is cold or unavailable.

**Data & infrastructure**  
Splunk Enterprise on a private GCE VM holds security telemetry. Ollama on a separate VM hosts Foundation-Sec 8B (GGUF). Cloud Run reaches both through a VPC connector. A sample data generator (`data/generate_sample_data.py`) seeds a brute-force demo scenario. Cloud Scheduler stops the LLM VM when idle to control cost.

To cut investigate latency, the backend warms the Ollama VM in parallel while Splunk queries run:

\[
T_{\text{investigate}} \approx T_{\text{splunk}} + T_{\text{llm}}
\]

Parallel warm-up lowers effective wait time on cold starts.

See [architecture_diagram.md](./architecture_diagram.md) for the full Mermaid diagram and data-flow documentation.

## Challenges I ran into

**Splunk auth in production**  
Locally everything worked. On Cloud Run, every query initially failed with `Session is not logged in`. I had to fix the password secret binding and session reconnect logic before the live demo was credible.

**Empty data vs. convincing UI**  
When Splunk returned no events, fallback logic still showed MITRE techniques like brute force and remediation steps, with an empty or placeholder timeline. That was confusing and untrustworthy. I reworked synthesis to be evidence-driven: no Splunk rows means no attack claims.

**Timeline inconsistency**  
Foundation-Sec sometimes returned an empty timeline while Splunk had results. Other runs pulled in Splunk audit noise instead of real attack events. I narrowed index filters, removed audit-index pollution from entity searches, and backfilled timelines from Splunk rows when the model omitted them.

**Cold-start latency**  
The first investigate after the Ollama VM boots can take several minutes. Background VM warm-up, health checks, and a demo runbook ("warm one investigate off-camera") made live recording practical.

**Cost vs. reliability**  
VPC connectors, always-on VMs, and GPU inference add up quickly. I used scale-to-zero Cloud Run, on-demand LLM VM start, and scheduled idle shutdown. That meant accepting some cold-start pain to stay within a hackathon budget.

## Accomplishments I'm proud of

- A **live, end-to-end deployment** on GCP: frontend, backend, Splunk, and Foundation-Sec connected over a private VPC
- **Splunk-native evidence** with transparent SPL in query mode and a deterministic, auditable investigation playbook
- **Foundation-Sec integration** for real security report synthesis, not a generic chatbot wrapper
- A **structured analyst UX** with severity, summary, queries run, timeline, MITRE, remediation, loading states, and report navigation
- **Open-source submission readiness**: MIT license, README, architecture diagram, env examples, sample data generator, and demo runbook
- **Honest failure modes**. When Splunk has no data, the app says so instead of fabricating an incident

## What I learned

**Splunk should own the evidence layer.** Investigation queries are deterministic; the LLM synthesizes after the fact. That separation makes the system more trustworthy and easier to debug.

**AI demos fail for operational reasons, not just model reasons.** Secrets, VPC routing, session expiry, and empty indexes broke demos before the model ever got involved.

**Security UX needs structure.** Analysts want predictable report sections and visible SPL, not a wall of unstructured text.

**Production is half platform engineering.** Cloud Run, GCE, Secret Manager, VPC connectors, and cost controls matter as much as the application code for a credible hackathon submission.

## What's next for soc-copilot

- **Richer entity pivoting**: automatic follow-up queries when the agent finds related users, hosts, or parent processes
- **Case management hooks**: export reports to ticketing/SOAR (ServiceNow, Jira, Splunk SOAR)
- **Analyst feedback loop**: thumbs up/down on report sections to tune prompts and severity calibration
- **BOTS v3 deep integration**: pre-built playbooks aligned to known BOTS attack scenarios and datasets
- **Streaming synthesis**: progressive report rendering as Splunk queries complete, instead of waiting for the full pipeline
- **Multi-tenant Splunk**: support multiple indexes/tenants and role-based query scoping for enterprise deployments

---

*Open source under [MIT](./LICENSE). Repository: https://github.com/SafinMahmud/soc-copilot*
