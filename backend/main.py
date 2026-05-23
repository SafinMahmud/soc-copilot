import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai_agent import generate_spl, run_investigation_agent, synthesize_report
from models import (
    InvestigateRequest,
    InvestigationReport,
    QueryRequest,
    SPLResult,
)
from splunk_client import SplunkClient

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
    provider = os.getenv("AI_PROVIDER", "gemini").strip().lower()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return {
        "status": "ok",
        "ai_provider": provider,
        "model": model if provider == "gemini" else "mock",
    }


@app.post("/api/query", response_model=SPLResult)
def natural_language_query(req: QueryRequest):
    """Convert natural language to SPL, execute, return results."""
    try:
        spl = generate_spl(req.message, req.time_range, INDEX)
        results = splunk.run_query(spl)
        provider = os.getenv("AI_PROVIDER", "gemini").strip().lower()
        if (
            provider == "mock"
            and (not results or (isinstance(results[0], dict) and "error" not in results[0]))
            and len(results) == 0
        ):
            fallback_spl = (
                f"search (index={INDEX} OR index=main OR index=botsv3 OR index=_internal OR index=_audit) "
                "earliest=-90d | head 100"
            )
            fallback_results = splunk.run_query(fallback_spl)
            if fallback_results and not (
                isinstance(fallback_results[0], dict)
                and "error" in fallback_results[0]
            ):
                spl = fallback_spl
                results = fallback_results
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
