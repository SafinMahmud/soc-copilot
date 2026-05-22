import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from claude_agent import generate_spl, run_investigation_agent, synthesize_report
from models import (
    InvestigateRequest,
    InvestigationReport,
    QueryRequest,
    SPLResult,
)
from splunk_client import SplunkClient

load_dotenv()
app = FastAPI(title="SOC Copilot API")
splunk = SplunkClient()

INDEX = os.getenv("SPLUNK_INDEX", "botsv3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/query", response_model=SPLResult)
def natural_language_query(req: QueryRequest):
    """Convert natural language to SPL, execute, return results."""
    try:
        spl = generate_spl(req.message, req.time_range, INDEX)
        results = splunk.run_query(spl)
        if results and len(results) > 0 and "error" in results[0]:
            return SPLResult(
                spl=spl,
                results=[],
                result_count=0,
                error=results[0]["error"],
            )
        return SPLResult(
            spl=spl,
            results=results[:100],
            result_count=len(results),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/investigate", response_model=InvestigationReport)
def investigate(req: InvestigateRequest):
    """Run autonomous investigation agent, return structured report."""
    try:
        agent_output = run_investigation_agent(
            entity=req.entity,
            entity_type=req.entity_type,
            time_range=req.time_range,
            index=INDEX,
        )
        report_json = synthesize_report(
            req.entity,
            req.entity_type,
            req.time_range,
            agent_output,
        )

        return InvestigationReport(
            entity=req.entity,
            entity_type=req.entity_type,
            queries_run=agent_output["queries_run"],
            raw_findings=agent_output["raw_findings"],
            **report_json,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
