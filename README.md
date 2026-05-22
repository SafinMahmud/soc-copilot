# AI SOC Investigation Copilot

**Splunk AI Hackathon — Security Track**

An autonomous AI agent that investigates security incidents from Splunk data,
builds attack timelines, maps to MITRE ATT&CK, and generates remediation playbooks.

## Demo

[VIDEO LINK HERE]

## Architecture

See `architecture.md` for full data flow diagram.

## Requirements

- Python 3.11+
- Node.js 18+
- Splunk Enterprise (free developer license)
- Anthropic API key (pay-as-you-go)

## Setup

### 1. Splunk Setup

1. Download Splunk Enterprise from splunk.com (free trial → apply developer license)
2. Install locally, start on localhost:8089
3. Load sample data:
   - **Option A (recommended):** Download BOTS v3: https://github.com/splunk/botsv3
   - **Option B:** Run `python data/generate_sample_data.py` after enabling HEC

### 2. Backend Setup

```bash
cd backend
cp .env.example .env
# Fill in your ANTHROPIC_API_KEY and Splunk credentials
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
# Opens on http://localhost:3000
```

## Usage

1. Open http://localhost:3000
2. Try: "Show me failed logins in the last 6 hours"
3. Try: "Investigate IP 23.20.239.12" (or any IP in your dataset)
4. Try: "Find all port scanning activity"

## License

MIT
