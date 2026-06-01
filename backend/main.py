import logging
import os
import threading
from pathlib import Path
import time
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai_agent import generate_spl, run_investigation_agent, synthesize_report
from models import (
    InvestigateRequest,
    InvestigationReport,
    QueryRequest,
    SPLResult,
)
from splunk_client import SplunkClient

logger = logging.getLogger("soc_copilot")

app = FastAPI(title="SOC Copilot API")

INDEX = os.getenv("SPLUNK_INDEX", "botsv3")

_splunk_client: Optional[SplunkClient] = None


def get_splunk() -> SplunkClient:
    """Lazily build the Splunk client so app startup never blocks on Splunk."""
    global _splunk_client
    if _splunk_client is None:
        try:
            _splunk_client = SplunkClient()
        except Exception as exc:
            logger.warning("Splunk client init failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=f"Splunk is unavailable: {exc}",
            ) from exc
    return _splunk_client

_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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


def _truthy(value: str, default: bool = False) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "on"}


def _warm_llm_in_background() -> None:
    """Start Ollama VM while Splunk queries run to reduce cold-start latency."""
    if not _truthy(os.getenv("GCE_LLM_ENABLED", "")):
        return
    if os.getenv("AI_PROVIDER", "hf").strip().lower() != "ollama":
        return
    try:
        from llm_vm import ensure_llm_ready

        ensure_llm_ready()
    except Exception as exc:
        logger.warning("Background LLM warm-up failed: %s", exc)


@app.get("/api/health")
def health():
    provider = os.getenv("AI_PROVIDER", "hf").strip().lower()
    if provider == "ollama":
        model = os.getenv(
            "OLLAMA_MODEL",
            "hf.co/mradermacher/Foundation-Sec-8B-Instruct-GGUF:Q4_K_M",
        )
    elif provider == "hf":
        model = os.getenv(
            "HF_MODEL", "fdtn-ai/Foundation-Sec-1.1-8B-Instruct:featherless-ai"
        )
    else:
        model = "mock"
    payload = {
        "status": "ok",
        "ai_provider": provider,
        "model": model,
    }
    if os.getenv("GCE_LLM_ENABLED", "").strip().lower() in {"1", "true", "yes"}:
        try:
            from llm_vm import get_instance_status

            payload["llm_vm_status"] = get_instance_status()
        except Exception as exc:
            payload["llm_vm_status"] = f"error: {exc}"
    return payload


@app.post("/api/internal/stop-llm-if-idle")
def stop_llm_if_idle(x_internal_key: Optional[str] = Header(default=None)):
    expected = os.getenv("INTERNAL_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=404, detail="Not configured")
    if x_internal_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        from llm_vm import stop_if_idle

        return stop_if_idle()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/query", response_model=SPLResult)
def natural_language_query(req: QueryRequest):
    """Convert natural language to SPL, execute, return results."""
    splunk = get_splunk()
    try:
        # Keep query endpoint stable in production by defaulting to deterministic SPL.
        # Can be overridden with QUERY_USE_LLM_SPL=true for experimentation.
        use_llm_spl = _truthy(os.getenv("QUERY_USE_LLM_SPL", ""), default=False)
        started = time.perf_counter()
        if use_llm_spl:
            spl = generate_spl(req.message, req.time_range, INDEX)
        else:
            spl = _fallback_query_for_message(req.message, req.time_range)
        results = splunk.run_query(spl)
        elapsed = time.perf_counter() - started
        logger.info(
            "Query route completed in %.2fs (llm_spl=%s, rows=%s)",
            elapsed,
            use_llm_spl,
            len(results) if isinstance(results, list) else "unknown",
        )
        has_error = bool(results and isinstance(results[0], dict) and "error" in results[0])
        no_rows = bool(results is not None and len(results) == 0)

        if (has_error or no_rows) and use_llm_spl:
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/investigate", response_model=InvestigationReport)
def investigate(req: InvestigateRequest):
    """Run autonomous investigation agent, return structured report."""
    # Touch Splunk lazily so the route returns a clean 503 if Splunk is down.
    get_splunk()
    try:
        threading.Thread(target=_warm_llm_in_background, daemon=True).start()
        started = time.perf_counter()
        agent_output = run_investigation_agent(
            entity=req.entity,
            entity_type=req.entity_type,
            time_range=req.time_range,
            index=INDEX,
        )
        logger.info(
            "Investigation Splunk phase completed in %.1fs for %s",
            time.perf_counter() - started,
            req.entity,
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
