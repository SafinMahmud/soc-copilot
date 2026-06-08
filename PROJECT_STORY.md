# SOC Copilot

**Splunk AI Hackathon, Security Track**

---

**Inspiration**

SOC analysts waste hours on repetitive work: writing SPL, running isolated searches, pivoting across logs, and manually assembling incident reports. The problem is not the analysis itself, it is the overhead before any real thinking happens.

SOC Copilot compresses that overhead. It queries Splunk first, builds evidence from real SIEM data, and uses AI only where it earns its place: synthesizing findings into a structured report analysts can act on immediately. Splunk's Foundation-Sec model family was the right fit for that principle. Security-tuned AI belongs on top of real log data, not as a replacement for it.

---

**What It Does**

Two modes, one chat interface.

**Query mode.** Plain-English questions ("show failed logins in the last 24 hours") get converted to SPL, executed against live indexes, and returned with the exact query shown. No black box.

**Investigate mode.** Analysts name a suspicious entity: IP, user, or hostname. The backend runs a deterministic Splunk playbook across auth, network, and raw event indexes. Foundation-Sec then synthesizes a structured incident report covering severity rating, executive summary, chronological attack timeline, MITRE ATT&CK mapping, and a prioritized remediation playbook.

All evidence comes from Splunk. The AI interprets it; it does not invent it.

Live demo: [https://soc-frontend-v5upnophmq-uc.a.run.app](https://soc-frontend-v5upnophmq-uc.a.run.app) Demo video: [https://youtu.be/RzBp3Caarh8](https://youtu.be/RzBp3Caarh8)

---

**How I Built It**

```
Browser → Next.js (Cloud Run) → FastAPI (Cloud Run) → Splunk Enterprise
                                                     → Ollama / Foundation-Sec

```

The Next.js frontend handles the chat UI, query results table, and structured report rendering (timeline, MITRE cards, remediation steps, section navigation). A same-origin API proxy keeps backend URLs out of the client bundle.

The FastAPI backend exposes three endpoints: `/api/query`, `/api/investigate`, `/api/health`. Splunk access uses the official SDK against the management API. The investigation playbook is fixed and repeatable, not LLM-chosen, making it auditable by design. Raw findings go to Foundation-Sec for JSON synthesis, with deterministic fallbacks when the model is unavailable.

Infrastructure runs on GCP: Splunk Enterprise on a private GCE VM, Ollama on a separate VM hosting Foundation-Sec 8B (GGUF), Cloud Run reaching both via VPC connector. To cut latency, the backend warms the Ollama VM in parallel with Splunk queries, so cold-start wait is the longer of the two, not the sum.

---

**Challenges**

**Splunk auth in production.** Worked locally, failed on Cloud Run with `Session is not logged in` on every request. Required fixing secret binding and adding session reconnect logic before the live demo was stable.

**Evidence-first synthesis.** Early fallback logic still produced MITRE mappings and remediation steps when Splunk returned no events, which looked confident and was wrong. Reworked the synthesis layer so no Splunk rows means no attack claims, period.

**Timeline consistency.** Foundation-Sec sometimes returned an empty timeline despite valid Splunk results, or pulled in audit-index noise instead of attack events. Fixed with tighter index filters and a Splunk-row backfill when the model omits timeline entries.

**Cost control.** VPC connectors, persistent VMs, and GPU inference add up fast. Used scale-to-zero Cloud Run, on-demand LLM VM start, and scheduled idle shutdown to stay within hackathon budget, accepting some cold-start latency as the tradeoff.

---

**What I'm Proud Of**

- A fully connected GCP deployment: frontend, backend, Splunk, and Foundation-Sec over a private VPC, live and working
- Deterministic investigation playbook with transparent SPL, not a prompt-driven agent guessing queries
- Honest failure modes: when Splunk has no data, the app says so instead of fabricating an incident
- Open-source ready: MIT license, README, architecture diagram, env examples, sample data generator, demo runbook

---

**What I Learned**

Splunk owns the evidence layer. The LLM synthesizes after the fact. That separation is what makes the system trustworthy and debuggable.

AI demos fail for operational reasons before they fail for model reasons. Secrets, VPC routing, session expiry, and empty indexes caused every near-miss in this project.

Production is half platform engineering. Cloud Run, Secret Manager, VPC connectors, and cost controls mattered as much as the application code.

---

**What's Next**

- Entity pivoting: automatic follow-up queries when the agent finds related users, hosts, or processes
- SOAR/ticketing export: push reports to ServiceNow, Jira, or Splunk SOAR
- Streaming synthesis: progressive report rendering as Splunk queries complete
- Analyst feedback loop: thumbs up/down on report sections to tune severity calibration
- Multi-tenant support: multiple indexes and role-based query scoping for enterprise deployments

---

*Open source under [MIT](./LICENSE). Repository: https://github.com/SafinMahmud/soc-copilot*