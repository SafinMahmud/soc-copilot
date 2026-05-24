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


def _fallback_query_for_message(message: str, time_range: str) -> str:
    lower = message.lower()
    tr = time_range or "-24h"

    if "sourcetype" in lower:
        return (
            f"search (index=_internal OR index=_audit) earliest={tr} "
            "| stats count by sourcetype source | sort - count | head 50"
        )
    if "failed login" in lower or "login failure" in lower:
        return (
            f"search (index=_audit OR index=_internal) earliest={tr} "
            '(EventCode=4625 OR action="failure" OR "failed login") '
            "| stats count by user src c_ip host | sort - count | head 50"
        )
    if "audit" in lower or "search activity" in lower:
        return (
            f"search index=_audit earliest={tr} action=search "
            "| stats count by user app info | sort - count | head 50"
        )
    if "internal" in lower or "recent events" in lower:
        return (
            f"search (index=_internal OR index=_audit) earliest={tr} "
            "| table _time host source sourcetype action user info "
            "| sort - _time | head 100"
        )
    return (
        f"search (index=_internal OR index=_audit OR index={INDEX}) earliest={tr} "
        "| table _time host source sourcetype action user info "
        "| sort - _time | head 100"
    )


@app.get("/api/health")
def health():
    provider = os.getenv("AI_PROVIDER", "hf").strip().lower()
    model = os.getenv(
        "HF_MODEL", "fdtn-ai/Foundation-Sec-1.1-8B-Instruct:featherless-ai"
    )
    return {
        "status": "ok",
        "ai_provider": provider,
        "model": model if provider == "hf" else "mock",
    }


@app.post("/api/query", response_model=SPLResult)
def natural_language_query(req: QueryRequest):
    """Convert natural language to SPL, execute, return results."""
    try:
        spl = generate_spl(req.message, req.time_range, INDEX)
        results = splunk.run_query(spl)
        has_error = bool(results and isinstance(results[0], dict) and "error" in results[0])
        no_rows = bool(results is not None and len(results) == 0)

        if has_error or no_rows:
            fallback_spl = _fallback_query_for_message(req.message, req.time_range)
            fallback_results = splunk.run_query(fallback_spl)
            fallback_ok = bool(
                fallback_results
                and not (
                    isinstance(fallback_results[0], dict) and "error" in fallback_results[0]
                )
            )
            if fallback_ok:
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
