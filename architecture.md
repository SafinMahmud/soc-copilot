```
┌─────────────────────────────────────────────────────────────┐
│                    SOC Copilot Architecture                  │
└─────────────────────────────────────────────────────────────┘

User Browser
│
│  HTTP (port 3000)
▼
┌─────────────────────────────────┐
│   Next.js 14 Frontend           │
│   TypeScript + Tailwind CSS     │
│                                 │
│  ┌─────────┐  ┌──────────────┐  │
│  │ChatPanel│  │Investigation │  │
│  │         │  │Report        │  │
│  └─────────┘  ├──────────────┤  │
│               │ AttackTimeline│  │
│               ├──────────────┤  │
│               │ MitreCards   │  │
│               ├──────────────┤  │
│               │ Remediation  │  │
│               └──────────────┘  │
└──────────┬──────────────────────┘
           │ REST API (port 8000)
           ▼
┌─────────────────────────────────┐
│   FastAPI Backend (Python)      │
│                                 │
│  POST /api/query                │
│  POST /api/investigate          │
│                                 │
│  ┌──────────────────────────┐   │
│  │ Gemini Agent Loop        │   │
│  │                          │   │
│  │  1. Plan queries         │   │──────────┐
│  │  2. Run tool calls       │   │          │
│  │  3. Interpret results    │   │          │
│  │  4. Decide next queries  │   │          │
│  │  5. Synthesize report    │   │          │
│  └──────────────────────────┘   │          │
└──────────┬──────────────────────┘          │
           │ Google AI API (HTTPS)            │
           ▼                                  │
┌──────────────────────┐                      │
│  Gemini API          │                      │
│  (gemini-1.5-flash)  │                      │
│                      │                      │
│  - SPL generation    │                      │
│  - Agent tool_use    │                      │
│  - MITRE mapping     │                      │
│  - Report synthesis  │                      │
└──────────────────────┘                      │
                                              │ Splunk Python SDK
                                              │ (port 8089, HTTPS)
                                              ▼
                               ┌─────────────────────────┐
                               │  Splunk Enterprise       │
                               │  (local installation)    │
                               │                          │
                               │  Index: botsv3 or main  │
                               │  Data: security events   │
                               │  (auth, network, process)│
                               └─────────────────────────┘

Data Flow — Investigation:
User Input → detect entity → POST /investigate → agent loop starts →
Gemini decides query 1 → run_splunk_query tool → Splunk returns results →
Gemini interprets → decides query 2 → ... → up to 8 queries →
Gemini synthesizes raw findings → structured JSON report →
Frontend renders: summary + timeline + MITRE cards + remediation
```
