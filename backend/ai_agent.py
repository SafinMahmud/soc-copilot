import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from prompts import (
    INVESTIGATION_SYNTHESIS_PROMPT,
    INVESTIGATION_SYSTEM,
    SPL_GENERATION_SYSTEM,
)
from splunk_client import SplunkClient

_splunk_client: Optional[SplunkClient] = None
MAX_TOOL_CALLS = 8


def _get_splunk() -> SplunkClient:
    global _splunk_client
    if _splunk_client is None:
        _splunk_client = SplunkClient()
    return _splunk_client


def _provider() -> str:
    return os.getenv("AI_PROVIDER", "hf").strip().lower()


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def _sanitize_spl(spl: str) -> str:
    """Normalize model output into executable SPL."""
    cleaned = _strip_markdown_fences(spl).strip()
    if not cleaned:
        return cleaned

    lines = [ln for ln in cleaned.splitlines() if ln.strip()]
    while lines and lines[0].strip().lower() in {"sql", "spl"}:
        lines.pop(0)
    cleaned = "\n".join(lines).strip()

    # Remove common invalid placeholders that models sometimes invent.
    cleaned = cleaned.replace("latest=@timestamp", "").replace("earliest=@timestamp", "")
    cleaned = cleaned.replace("@timestamp NOT NULL", "")
    cleaned = re.sub(r"\blatest=@[A-Za-z0-9_]+\b", "", cleaned)
    cleaned = re.sub(r"\bearliest=@[A-Za-z0-9_]+\b", "", cleaned)

    # Drop leading SQL markers and SQL-style punctuation.
    cleaned = re.sub(r"^\s*(sql|spl)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(";", " ")

    # Remove placeholder-based predicates that make SPL invalid.
    cleaned = re.sub(r"\b\w+\s+IN\s+\(list_of_[^)]+\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(list_of_[A-Za-z0-9_]+)\b", "", cleaned)

    # Remove impossible aggregate predicates from base search terms.
    cleaned = re.sub(
        r"\b(avg|min|max|sum|count)\s*\([^)]*\)\s*[<>=!]+\s*[^\s|]+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # In post-stats where clauses, rewrite aggregate expressions to plain fields
    # to avoid malformed expressions like where sum(bytes_in) > 1000.
    cleaned = re.sub(r"\bsum\(([^)]+)\)", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bavg\(([^)]+)\)", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmin\(([^)]+)\)", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmax\(([^)]+)\)", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bcount\(([^)]*)\)", "count", cleaned, flags=re.IGNORECASE)

    # Collapse redundant whitespace after removals.
    cleaned = " ".join(cleaned.split())

    if cleaned and not cleaned.lower().startswith(("search ", "|", "index=")):
        cleaned = f"search {cleaned}"
    return cleaned.strip()


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = _strip_markdown_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _extract_hf_text(payload: Any) -> str:
    if isinstance(payload, dict):
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {})
            if isinstance(msg, dict) and msg.get("content"):
                return str(msg["content"]).strip()
            if choices[0].get("text"):
                return str(choices[0]["text"]).strip()

        for key in ("generated_text", "response", "text", "output"):
            if payload.get(key):
                return str(payload[key]).strip()

        outputs = payload.get("outputs")
        if isinstance(outputs, list) and outputs and isinstance(outputs[0], dict):
            if outputs[0].get("text"):
                return str(outputs[0]["text"]).strip()

    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            if first.get("generated_text"):
                return str(first["generated_text"]).strip()
            if first.get("text"):
                return str(first["text"]).strip()

    raise RuntimeError("Hugging Face response did not contain readable text output.")


def _ollama_base_url() -> str:
    """Build Ollama base URL from OLLAMA_HOST or fall back to OLLAMA_BASE_URL."""
    host = os.getenv("OLLAMA_HOST", "").strip()
    if host:
        if host.startswith(("http://", "https://")):
            return host.rstrip("/")
        scheme = os.getenv("OLLAMA_SCHEME", "http").strip() or "http"
        port = os.getenv("OLLAMA_PORT", "11434").strip() or "11434"
        return f"{scheme}://{host}:{port}".rstrip("/")
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _ollama_generate(
    user_prompt: str,
    system_prompt: str = "",
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str:
    from llm_vm import ensure_llm_ready, get_instance_status, touch_llm_activity

    # Investigation may already be warming the VM in a background thread.
    if get_instance_status() == "RUNNING":
        ensure_llm_ready(timeout_seconds=60)
    else:
        synthesis_wait = int(os.getenv("OLLAMA_SYNTHESIS_WAIT_SECONDS", "180"))
        ensure_llm_ready(timeout_seconds=synthesis_wait)
    touch_llm_activity()

    base = _ollama_base_url()
    model = os.getenv(
        "OLLAMA_MODEL",
        "hf.co/mradermacher/Foundation-Sec-8B-Instruct-GGUF:Q4_K_M",
    ).strip()
    url = f"{base}/v1/chat/completions"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    with httpx.Client(timeout=180.0) as client:
        resp = client.post(url, json=payload)
        if resp.is_error:
            raise RuntimeError(
                f"Ollama request failed ({resp.status_code}): {resp.text[:400]}"
            )
        return _extract_hf_text(resp.json())


def _llm_generate(
    user_prompt: str,
    system_prompt: str = "",
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str:
    provider = _provider()
    if provider == "ollama":
        return _ollama_generate(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    return _hf_generate(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _hf_generate(
    user_prompt: str,
    system_prompt: str = "",
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str:
    model_url = os.getenv(
        "HF_API_URL", "https://router.huggingface.co/v1/chat/completions"
    ).strip()
    hf_token = os.getenv("HF_TOKEN", "").strip()
    model_name = os.getenv(
        "HF_MODEL", "fdtn-ai/Foundation-Sec-1.1-8B-Instruct:featherless-ai"
    ).strip()
    if not hf_token:
        raise RuntimeError("HF_TOKEN is not set in backend/.env.")

    headers = {
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    prompt = (
        f"{system_prompt}\n\nUser request:\n{user_prompt}"
        if system_prompt
        else user_prompt
    )

    chat_payload: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    with httpx.Client(timeout=90.0) as client:
        chat_resp = client.post(model_url, headers=headers, json=chat_payload)
        if chat_resp.status_code == 429:
            raise RuntimeError(
                "Hugging Face quota/rate limit reached. Retry later or use AI_PROVIDER=mock."
            )
        if not chat_resp.is_error:
            return _extract_hf_text(chat_resp.json())
        # Router may reject model/provider combos for chat completions. Fallback to
        # the standard serverless inference API for the same model.
        base_model = model_name.split(":")[0]
        fallback_url = os.getenv(
            "HF_FALLBACK_API_URL",
            f"https://api-inference.huggingface.co/models/{base_model}",
        ).strip()
        fallback_payload: Dict[str, Any] = {
            "inputs": prompt,
            "parameters": {
                "temperature": temperature,
                "max_new_tokens": max_tokens,
                "return_full_text": False,
            },
        }
        fallback_resp = client.post(fallback_url, headers=headers, json=fallback_payload)
        if fallback_resp.status_code == 429:
            raise RuntimeError(
                "Hugging Face quota/rate limit reached. Retry later or use AI_PROVIDER=mock."
            )
        if not fallback_resp.is_error:
            return _extract_hf_text(fallback_resp.json())
        raise RuntimeError(
            "Hugging Face model request failed "
            f"(router status {chat_resp.status_code}, fallback status {fallback_resp.status_code}). "
            "Check HF_MODEL/HF_TOKEN and model access in your Hugging Face account."
        )


def execute_tool(tool_name: str, tool_input: Dict[str, Any], time_range: str = "-24h"):
    """Route tool calls to Splunk client."""
    if tool_name == "run_splunk_query":
        return _get_splunk().run_query(_sanitize_spl(tool_input["spl"]))
    if tool_name == "get_field_values":
        return _get_splunk().get_field_values(
            tool_input["field"],
            tool_input["index"],
            time_range=time_range,
        )
    return {"error": f"Unknown tool: {tool_name}"}


def _mock_index_filter(index: str) -> str:
    configured = (index or "").strip()
    if configured:
        return f"(index={configured} OR index=main OR index=botsv3)"
    return "(index=main OR index=botsv3)"


def _run_query_with_fallbacks(
    description: str, strict_spl: str, broad_spl: str
) -> Dict[str, Any]:
    strict_results = _get_splunk().run_query(strict_spl)
    if strict_results and not (isinstance(strict_results[0], dict) and "error" in strict_results[0]):
        if len(strict_results) > 0:
            return {
                "description": description,
                "spl": strict_spl,
                "results": strict_results,
                "mock_strategy": "strict",
            }

    broad_results = _get_splunk().run_query(broad_spl)
    return {
        "description": description,
        "spl": broad_spl,
        "results": broad_results,
        "mock_strategy": "broad_fallback",
        "strict_spl_attempted": strict_spl,
    }


def _run_mock_investigation_agent(
    entity: str, entity_type: str, time_range: str, index: str
) -> Dict[str, Any]:
    idx_filter = _mock_index_filter(index)
    if entity_type == "ip":
        planned_queries = [
            (
                "Failed authentication attempts from IP",
                f'search {idx_filter} earliest={time_range} (src_ip="{entity}" OR src="{entity}" OR c_ip="{entity}") (EventCode=4625 OR action="failure") | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d (src_ip="{entity}" OR src="{entity}" OR c_ip="{entity}") ("failure" OR EventCode=4625 OR login OR auth) | sort 0 _time | head 200',
            ),
            (
                "Successful authentication activity from IP",
                f'search {idx_filter} earliest={time_range} (src_ip="{entity}" OR src="{entity}" OR c_ip="{entity}") (EventCode=4624 OR action="success") | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d (src_ip="{entity}" OR src="{entity}" OR c_ip="{entity}") ("success" OR EventCode=4624 OR login OR auth) | sort 0 _time | head 200',
            ),
            (
                "Network activity involving IP",
                f'search {idx_filter} earliest={time_range} (src_ip="{entity}" OR dest_ip="{entity}" OR c_ip="{entity}") sourcetype=stream:tcp | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d (src_ip="{entity}" OR dest_ip="{entity}" OR c_ip="{entity}") (stream OR tcp OR network OR dest_port) | sort 0 _time | head 200',
            ),
            (
                "Potential data transfer involving IP",
                f'search {idx_filter} earliest={time_range} (src_ip="{entity}" OR dest_ip="{entity}") sourcetype=stream:tcp | eval total_bytes=coalesce(bytes_out,0)+coalesce(bytes_in,0) | where total_bytes > 1000000 | sort 0 - total_bytes | head 100',
                f'search {idx_filter} earliest=-90d (src_ip="{entity}" OR dest_ip="{entity}") (bytes_out=* OR bytes_in=* OR transfer OR exfil) | sort 0 _time | head 120',
            ),
        ]
    elif entity_type == "user":
        planned_queries = [
            (
                "Authentication events for user",
                f'search {idx_filter} earliest={time_range} user="{entity}" | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d (user="{entity}" OR account="{entity}") (login OR auth OR EventCode=*) | sort 0 _time | head 200',
            ),
            (
                "Failed logins for user",
                f'search {idx_filter} earliest={time_range} user="{entity}" (EventCode=4625 OR action="failure") | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d (user="{entity}" OR account="{entity}") ("failure" OR EventCode=4625 OR auth) | sort 0 _time | head 200',
            ),
            (
                "Successful logins for user",
                f'search {idx_filter} earliest={time_range} user="{entity}" (EventCode=4624 OR action="success") | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d (user="{entity}" OR account="{entity}") ("success" OR EventCode=4624 OR auth) | sort 0 _time | head 200',
            ),
            (
                "Network or web activity tied to user",
                f'search {idx_filter} earliest={time_range} user="{entity}" (sourcetype=stream:tcp OR sourcetype=iis OR sourcetype=syslog) | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d (user="{entity}" OR account="{entity}") (stream OR iis OR syslog OR network OR web) | sort 0 _time | head 200',
            ),
        ]
    else:
        planned_queries = [
            (
                "Host security events",
                f'search {idx_filter} earliest={time_range} (host="{entity}" OR dest="{entity}") | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d (host="{entity}" OR dest="{entity}") (EventCode=* OR auth OR process OR network) | sort 0 _time | head 200',
            ),
            (
                "Host authentication failures",
                f'search {idx_filter} earliest={time_range} (host="{entity}" OR dest="{entity}") (EventCode=4625 OR action="failure") | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d (host="{entity}" OR dest="{entity}") ("failure" OR EventCode=4625 OR auth) | sort 0 _time | head 200',
            ),
            (
                "Host process or command activity",
                f'search {idx_filter} earliest={time_range} host="{entity}" (process OR command OR cmdline) | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d host="{entity}" (process OR command OR cmdline OR powershell OR exec) | sort 0 _time | head 200',
            ),
            (
                "Host network activity",
                f'search {idx_filter} earliest={time_range} host="{entity}" sourcetype=stream:tcp | sort 0 _time | head 200',
                f'search {idx_filter} earliest=-90d host="{entity}" (stream OR tcp OR network OR dest_port) | sort 0 _time | head 200',
            ),
        ]

    raw_findings: Dict[str, Any] = {}
    queries_run: List[str] = []
    for i, (description, strict_spl, broad_spl) in enumerate(
        planned_queries[:MAX_TOOL_CALLS], start=1
    ):
        query_out = _run_query_with_fallbacks(description, strict_spl, broad_spl)
        raw_findings[f"query_{i}"] = {
            **query_out,
        }
        queries_run.append(query_out["spl"])
    return {"raw_findings": raw_findings, "queries_run": queries_run}


def _deterministic_investigation_plan(
    entity: str, entity_type: str, time_range: str, index: str
) -> List[tuple]:
    idx_filter = _mock_index_filter(index)
    if entity_type == "ip":
        return [
            (
                "Authentication failures tied to IP",
                f'search {idx_filter} earliest={time_range} (src_ip="{entity}" OR src="{entity}" OR c_ip="{entity}") (EventCode=4625 OR action="failure" OR "failed login") | sort 0 - _time | head 200',
                f'search {idx_filter} earliest=-90d (src_ip="{entity}" OR src="{entity}" OR c_ip="{entity}") ("failure" OR EventCode=4625 OR login OR auth) | sort 0 - _time | head 200',
            ),
            (
                "Authentication successes tied to IP",
                f'search {idx_filter} earliest={time_range} (src_ip="{entity}" OR src="{entity}" OR c_ip="{entity}") (EventCode=4624 OR action="success" OR "login succeeded") | sort 0 - _time | head 200',
                f'search {idx_filter} earliest=-90d (src_ip="{entity}" OR src="{entity}" OR c_ip="{entity}") ("success" OR EventCode=4624 OR login OR auth) | sort 0 - _time | head 200',
            ),
            (
                "Network activity involving IP",
                f'search {idx_filter} earliest={time_range} (src_ip="{entity}" OR dest_ip="{entity}" OR c_ip="{entity}" OR src="{entity}") (stream OR tcp OR network OR dest_port OR bytes_in OR bytes_out) | sort 0 - _time | head 200',
                f'search {idx_filter} earliest=-90d (src_ip="{entity}" OR dest_ip="{entity}" OR c_ip="{entity}" OR src="{entity}") (stream OR tcp OR network OR dest_port) | sort 0 - _time | head 200',
            ),
            (
                "Recent raw events for entity evidence",
                f'search {idx_filter} earliest={time_range} ("{entity}") | table _time host source sourcetype user action src src_ip c_ip dest_ip EventCode bytes_in bytes_out | sort 0 - _time | head 120',
                f'search {idx_filter} earliest=-90d ("{entity}") | table _time host source sourcetype user action src src_ip c_ip dest_ip EventCode bytes_in bytes_out | sort 0 - _time | head 120',
            ),
        ]
    if entity_type == "user":
        return [
            (
                "Authentication activity for user",
                f'search {idx_filter} earliest={time_range} (user="{entity}" OR account="{entity}") (login OR auth OR EventCode=*) | sort 0 - _time | head 200',
                f'search {idx_filter} earliest=-90d (user="{entity}" OR account="{entity}") (login OR auth OR EventCode=*) | sort 0 - _time | head 200',
            ),
            (
                "Failed authentication for user",
                f'search {idx_filter} earliest={time_range} (user="{entity}" OR account="{entity}") (EventCode=4625 OR action="failure" OR "failed login") | sort 0 - _time | head 200',
                f'search {idx_filter} earliest=-90d (user="{entity}" OR account="{entity}") ("failure" OR EventCode=4625 OR auth) | sort 0 - _time | head 200',
            ),
            (
                "Successful authentication for user",
                f'search {idx_filter} earliest={time_range} (user="{entity}" OR account="{entity}") (EventCode=4624 OR action="success") | sort 0 - _time | head 200',
                f'search {idx_filter} earliest=-90d (user="{entity}" OR account="{entity}") ("success" OR EventCode=4624 OR auth) | sort 0 - _time | head 200',
            ),
            (
                "User activity from audit logs",
                f'search index=_audit earliest={time_range} user="{entity}" | stats count by action info app src c_ip | sort - count | head 100',
                f'search index=_audit earliest=-90d user="{entity}" | stats count by action info app src c_ip | sort - count | head 100',
            ),
            (
                "Recent raw events for user evidence",
                f'search {idx_filter} earliest={time_range} (user="{entity}" OR account="{entity}") | table _time host source sourcetype user action src src_ip c_ip dest_ip EventCode | sort 0 - _time | head 120',
                f'search {idx_filter} earliest=-90d (user="{entity}" OR account="{entity}") | table _time host source sourcetype user action src src_ip c_ip dest_ip EventCode | sort 0 - _time | head 120',
            ),
        ]
    return [
        (
            "Host security events",
            f'search {idx_filter} earliest={time_range} (host="{entity}" OR dest="{entity}") (EventCode=* OR auth OR process OR network) | sort 0 - _time | head 200',
            f'search {idx_filter} earliest=-90d (host="{entity}" OR dest="{entity}") (EventCode=* OR auth OR process OR network) | sort 0 - _time | head 200',
        ),
        (
            "Host authentication failures",
            f'search {idx_filter} earliest={time_range} (host="{entity}" OR dest="{entity}") (EventCode=4625 OR action="failure" OR "failed login") | sort 0 - _time | head 200',
            f'search {idx_filter} earliest=-90d (host="{entity}" OR dest="{entity}") ("failure" OR EventCode=4625 OR auth) | sort 0 - _time | head 200',
        ),
        (
            "Host process and command activity",
            f'search {idx_filter} earliest={time_range} host="{entity}" (process OR command OR cmdline OR powershell OR exec) | sort 0 - _time | head 200',
            f'search {idx_filter} earliest=-90d host="{entity}" (process OR command OR cmdline OR powershell OR exec) | sort 0 - _time | head 200',
        ),
        (
            "Host network activity",
            f'search {idx_filter} earliest={time_range} (host="{entity}" OR dest="{entity}") (stream OR tcp OR network OR dest_port OR bytes_in OR bytes_out) | sort 0 - _time | head 200',
            f'search {idx_filter} earliest=-90d (host="{entity}" OR dest="{entity}") (stream OR tcp OR network OR dest_port) | sort 0 - _time | head 200',
        ),
        (
            "Recent raw events for host evidence",
            f'search {idx_filter} earliest={time_range} (host="{entity}" OR dest="{entity}") | table _time host source sourcetype user action src src_ip c_ip dest_ip EventCode process command | sort 0 - _time | head 120',
            f'search {idx_filter} earliest=-90d (host="{entity}" OR dest="{entity}") | table _time host source sourcetype user action src src_ip c_ip dest_ip EventCode process command | sort 0 - _time | head 120',
        ),
    ]


def _run_deterministic_investigation_agent(
    entity: str, entity_type: str, time_range: str, index: str
) -> Dict[str, Any]:
    planned_queries = _deterministic_investigation_plan(
        entity=entity,
        entity_type=entity_type,
        time_range=time_range,
        index=index,
    )
    raw_findings: Dict[str, Any] = {}
    queries_run: List[str] = []
    for i, (description, strict_spl, broad_spl) in enumerate(
        planned_queries[:MAX_TOOL_CALLS], start=1
    ):
        query_out = _run_query_with_fallbacks(description, strict_spl, broad_spl)
        raw_findings[f"query_{i}"] = {**query_out}
        queries_run.append(query_out["spl"])
    return {"raw_findings": raw_findings, "queries_run": queries_run}


def _infer_event_type(description: str, row: Dict[str, Any]) -> str:
    text = f"{description} {json.dumps(row, default=str)}".lower()
    if "eventcode" in text or "logon" in text or "auth" in text:
        return "auth"
    if "process" in text or "cmd" in text or "command" in text:
        return "process"
    if "file" in text:
        return "file"
    return "network"


def _extract_timestamp(row: Dict[str, Any]) -> str:
    for key in ("_time", "timestamp", "time"):
        value = row.get(key)
        if value:
            return str(value)
    return datetime.now(timezone.utc).isoformat()


def _is_audit_noise_row(row: Dict[str, Any]) -> bool:
    row_text = json.dumps(row, default=str).lower()
    if (
        "action=search" in row_text
        or "search_id=" in row_text
        or row.get("index") == "_audit"
        or row.get("sourcetype") == "audittrail"
        or row.get("source") == "audittrail"
    ):
        return True
    # Aggregated audit stats are not attack evidence.
    if "count" in row and not any(
        key in row for key in ("EventCode", "src_ip", "src", "c_ip", "bytes_out")
    ):
        return True
    return False


def _summarize_findings(agent_output: Dict[str, Any]) -> Dict[str, int]:
    raw_findings = agent_output.get("raw_findings") or {}
    summary = {
        "query_count": 0,
        "error_count": 0,
        "evidence_rows": 0,
        "failure_count": 0,
        "success_count": 0,
        "transfer_count": 0,
    }
    for query in raw_findings.values():
        if not isinstance(query, dict):
            continue
        summary["query_count"] += 1
        for row in query.get("results") or []:
            if not isinstance(row, dict):
                continue
            if "error" in row:
                summary["error_count"] += 1
                continue
            if _is_audit_noise_row(row):
                continue
            summary["evidence_rows"] += 1
            row_text = json.dumps(row, default=str).lower()
            if "4625" in row_text or '"failure"' in row_text:
                summary["failure_count"] += 1
            if "4624" in row_text or '"success"' in row_text:
                summary["success_count"] += 1
            if "bytes_out" in row and str(row.get("bytes_out", "0")).isdigit():
                if int(row.get("bytes_out", 0)) > 1_000_000:
                    summary["transfer_count"] += 1
    return summary


def _build_timeline_from_findings(agent_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    timeline: List[Dict[str, Any]] = []
    for query in (agent_output.get("raw_findings") or {}).values():
        if not isinstance(query, dict):
            continue
        description = query.get("description", "Investigation event")
        for row in (query.get("results") or [])[:8]:
            if not isinstance(row, dict) or "error" in row or _is_audit_noise_row(row):
                continue
            event_type = _infer_event_type(description, row)
            timeline.append(
                {
                    "timestamp": _extract_timestamp(row),
                    "event_type": event_type,
                    "description": description,
                    "raw_log": json.dumps(row, default=str)[:500],
                    "severity": "high" if event_type == "auth" else "medium",
                }
            )
    timeline.sort(key=lambda item: item["timestamp"])
    return timeline[:40]


def _insufficient_evidence_report(
    entity: str, entity_type: str, agent_output: Dict[str, Any]
) -> Dict[str, Any]:
    stats = _summarize_findings(agent_output)
    query_count = stats["query_count"]
    error_count = stats["error_count"]

    if query_count > 0 and error_count == query_count:
        summary = (
            f"Splunk queries for {entity_type} '{entity}' could not be completed "
            f"({error_count}/{query_count} failed). Check Splunk connectivity and credentials."
        )
        severity_rationale = "Severity is low because no log evidence was retrieved."
        remediation_steps = [
            {
                "priority": "High",
                "action": "Verify Splunk host, credentials, and index coverage before re-running.",
                "rationale": "Investigation conclusions require queryable security telemetry.",
            },
            {
                "priority": "Medium",
                "action": "Confirm botsv3/main indexes contain events for the investigated entity.",
                "rationale": "Empty indexes produce no attack timeline or corroborating evidence.",
            },
        ]
    else:
        summary = (
            f"No matching security events were found for {entity_type} '{entity}' "
            f"in the configured indexes and time range."
        )
        severity_rationale = (
            "Severity is low because no corroborating attack activity was observed in Splunk."
        )
        remediation_steps = [
            {
                "priority": "Medium",
                "action": "Validate data ingest and expand the search window if the entity is expected.",
                "rationale": "Absence of evidence may reflect coverage gaps rather than a benign entity.",
            },
            {
                "priority": "Low",
                "action": "Re-run after confirming the entity value and relevant sourcetypes are indexed.",
                "rationale": "Keeps triage open without assuming a specific attack technique.",
            },
        ]

    return {
        "severity": "Low",
        "severity_rationale": severity_rationale,
        "summary": summary,
        "timeline": [],
        "mitre_techniques": [],
        "remediation_steps": remediation_steps,
    }


def _mock_synthesize_report(
    entity: str, entity_type: str, agent_output: Dict[str, Any]
) -> Dict[str, Any]:
    stats = _summarize_findings(agent_output)
    timeline = _build_timeline_from_findings(agent_output)
    if stats["evidence_rows"] == 0:
        return _insufficient_evidence_report(entity, entity_type, agent_output)

    failure_count = stats["failure_count"]
    success_count = stats["success_count"]
    transfer_count = stats["transfer_count"]

    if failure_count > 20 and success_count > 0:
        severity = "Critical"
        severity_rationale = (
            "Large volume of failed authentication followed by successful access "
            "suggests likely credential compromise."
        )
    elif failure_count > 10 or transfer_count > 0:
        severity = "High"
        severity_rationale = (
            "Suspicious authentication or transfer activity warrants urgent review."
        )
    elif len(timeline) > 5:
        severity = "Medium"
        severity_rationale = (
            "Multiple correlated events were detected and should be investigated."
        )
    else:
        severity = "Low"
        severity_rationale = (
            "Limited suspicious evidence found in current data and time range."
        )

    mitre_techniques: List[Dict[str, str]] = []
    if failure_count > 0:
        mitre_techniques.append(
            {
                "technique_id": "T1110",
                "name": "Brute Force",
                "tactic": "Credential Access",
                "description": "Repeated failed logins may indicate password guessing attempts.",
            }
        )
    if success_count > 0 or any(
        item.get("event_type") == "network" for item in timeline
    ):
        mitre_techniques.append(
            {
                "technique_id": "T1021",
                "name": "Remote Services",
                "tactic": "Lateral Movement",
                "description": "Remote authentication and service access activity observed.",
            }
        )
    if transfer_count > 0:
        mitre_techniques.append(
            {
                "technique_id": "T1048",
                "name": "Exfiltration Over Alternative Protocol",
                "tactic": "Exfiltration",
                "description": "Large outbound transfer patterns may indicate data exfiltration.",
            }
        )

    remediation_steps = []
    if severity in ("Critical", "High"):
        remediation_steps.append(
            {
                "priority": "Critical" if severity == "Critical" else "High",
                "action": f"Contain entity {entity} and rotate potentially exposed credentials.",
                "rationale": "Immediate containment limits attacker dwell time and reuse.",
            }
        )
    if failure_count > 0:
        remediation_steps.append(
            {
                "priority": "High",
                "action": "Block suspicious source IPs and enforce MFA for privileged access.",
                "rationale": "Reduces ongoing brute-force and unauthorized remote access risk.",
            }
        )
    if transfer_count > 0:
        remediation_steps.append(
            {
                "priority": "High",
                "action": "Review large outbound transfers and isolate affected hosts.",
                "rationale": "Helps confirm or rule out data exfiltration activity.",
            }
        )
    remediation_steps.append(
        {
            "priority": "Medium",
            "action": "Increase detections for repeated auth failures and anomalous transfers.",
            "rationale": "Improves early detection of similar attack patterns.",
        }
    )

    summary = (
        f"Investigation reviewed {stats['query_count']} query groups for "
        f"{entity_type} '{entity}'. Findings show {failure_count} suspicious auth failures, "
        f"{success_count} successful auth events, and {transfer_count} potential transfer indicators."
    )

    return {
        "severity": severity,
        "severity_rationale": severity_rationale,
        "summary": summary,
        "timeline": timeline,
        "mitre_techniques": mitre_techniques[:6],
        "remediation_steps": remediation_steps,
    }


def _normalize_report_json(report_json: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce model output into schema-safe report payload."""
    normalized: Dict[str, Any] = dict(report_json or {})

    def _safe_str(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, default=str)

    timeline = normalized.get("timeline")
    if not isinstance(timeline, list):
        timeline = []
    clean_timeline: List[Dict[str, Any]] = []
    for item in timeline:
        if not isinstance(item, dict):
            continue
        clean_timeline.append(
            {
                "timestamp": _safe_str(
                    item.get("timestamp", datetime.now(timezone.utc).isoformat())
                ),
                "event_type": _safe_str(item.get("event_type", "network")),
                "description": _safe_str(item.get("description", "Investigation event")),
                "raw_log": _safe_str(item.get("raw_log", "")),
                "severity": _safe_str(item.get("severity", "medium")),
            }
        )
    normalized["timeline"] = clean_timeline

    mitre = normalized.get("mitre_techniques")
    if not isinstance(mitre, list):
        mitre = []
    clean_mitre: List[Dict[str, Any]] = []
    for item in mitre:
        if not isinstance(item, dict):
            continue
        clean_mitre.append(
            {
                "technique_id": _safe_str(item.get("technique_id", "T0000")),
                "name": _safe_str(item.get("name", "Unknown")),
                "tactic": _safe_str(item.get("tactic", "Unknown")),
                "description": _safe_str(item.get("description", "")),
            }
        )
    normalized["mitre_techniques"] = clean_mitre

    remediation = normalized.get("remediation_steps")
    if not isinstance(remediation, list):
        remediation = []
    clean_remediation: List[Dict[str, Any]] = []
    for item in remediation:
        if not isinstance(item, dict):
            continue
        clean_remediation.append(
            {
                "priority": _safe_str(item.get("priority", "Medium")),
                "action": _safe_str(item.get("action", "Review related alerts.")),
                "rationale": _safe_str(item.get("rationale", "")),
            }
        )
    normalized["remediation_steps"] = clean_remediation

    normalized["severity"] = _safe_str(normalized.get("severity", "Medium"))
    normalized["severity_rationale"] = _safe_str(
        normalized.get("severity_rationale", "Severity inferred from available findings.")
    )
    normalized["summary"] = _safe_str(
        normalized.get("summary", "Investigation completed using available evidence.")
    )

    return normalized


def run_investigation_agent(
    entity: str, entity_type: str, time_range: str, index: str
) -> Dict[str, Any]:
    """
    Deterministic investigation plan with provider-specific synthesis.
    """
    provider = _provider()
    if provider not in {"hf", "mock", "ollama"}:
        raise RuntimeError(
            f"Unsupported AI_PROVIDER '{provider}'. Use hf, ollama, or mock."
        )
    return _run_deterministic_investigation_agent(entity, entity_type, time_range, index)


def synthesize_report(
    entity: str, entity_type: str, time_range: str, agent_output: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Synthesize raw findings into structured report JSON.
    """
    provider = _provider()
    if provider == "mock":
        return _normalize_report_json(
            _mock_synthesize_report(entity, entity_type, agent_output)
        )
    if provider not in {"hf", "ollama"}:
        raise RuntimeError(
            f"Unsupported AI_PROVIDER '{provider}'. Use hf, ollama, or mock."
        )

    prompt = INVESTIGATION_SYNTHESIS_PROMPT.format(
        entity=entity,
        entity_type=entity_type,
        time_range=time_range,
        queries_run=json.dumps(agent_output["queries_run"], indent=2),
        raw_findings=json.dumps(agent_output["raw_findings"], indent=2),
    )
    stats = _summarize_findings(agent_output)
    if stats["evidence_rows"] == 0:
        return _normalize_report_json(
            _insufficient_evidence_report(entity, entity_type, agent_output)
        )

    try:
        response_text = _llm_generate(
            user_prompt=prompt,
            system_prompt="Return only valid JSON. No markdown.",
            max_tokens=4096,
            temperature=0.1,
        )
        report = _normalize_report_json(_extract_json_object(response_text))
        if not report.get("timeline"):
            report["timeline"] = _build_timeline_from_findings(agent_output)
        if stats["failure_count"] == 0 and stats["transfer_count"] == 0:
            report["mitre_techniques"] = [
                item
                for item in report.get("mitre_techniques", [])
                if item.get("technique_id") not in {"T1110", "T1048"}
            ]
        return report
    except Exception:
        return _normalize_report_json(
            _mock_synthesize_report(entity, entity_type, agent_output)
        )


def _mock_generate_spl(natural_language: str, time_range: str, index: str) -> str:
    text = natural_language.lower()
    base = f"search {_mock_index_filter(index)} earliest={time_range}"
    broad_base = f"search {_mock_index_filter(index)} earliest=-90d"
    if "internal" in text or "splunk logs" in text:
        return (
            f'search (index=_internal OR index=_audit) earliest={time_range} '
            "| stats count by host source sourcetype "
            "| sort - count | head 50"
        )
    if "top sourcetypes" in text or "sourcetypes" in text:
        return (
            base
            + " | stats count by sourcetype | sort - count | head 20"
        )
    if "recent events" in text or "show events" in text:
        return (
            f'search (index=_internal OR index=_audit OR index=main OR index=botsv3) earliest={time_range} '
            "| stats count by index sourcetype host | sort - count | head 60"
        )
    if "failed" in text and ("login" in text or "ssh" in text or "auth" in text):
        return (
            base
            + ' (EventCode=4625 OR action="failure" OR login OR auth) '
            + "| stats count by src_ip user dest | sort - count | head 100"
        )
    if "port scan" in text or "scan" in text:
        return (
            base
            + " (sourcetype=stream:tcp OR stream OR tcp OR dest_port=*) "
            + "| stats dc(dest_port) as unique_ports values(dest_port) as ports by src_ip "
            + "| where unique_ports > 20 | sort - unique_ports | head 100"
        )
    if "group by source ip" in text or "group by src_ip" in text:
        return (
            base
            + " (src_ip=* OR c_ip=* OR src=*) "
            + "| eval source_ip=coalesce(src_ip,c_ip,src) "
            + "| stats count by source_ip | sort - count | head 100"
        )
    if "show any events" in text or "any events" in text:
        return broad_base + " | head 100"
    return broad_base + " | head 100"


def generate_spl(natural_language: str, time_range: str, index: str) -> str:
    """
    Convert natural language to SPL using HF model or mock fallback.
    """
    provider = _provider()
    if provider == "mock":
        return _mock_generate_spl(natural_language, time_range, index)
    if provider not in {"hf", "ollama"}:
        raise RuntimeError(
            f"Unsupported AI_PROVIDER '{provider}'. Use hf, ollama, or mock."
        )

    prompt = (
        f"Convert to SPL. Index: {index}. Time range: {time_range}.\n"
        f"Question: {natural_language}"
    )
    spl = _llm_generate(
        user_prompt=prompt,
        system_prompt=SPL_GENERATION_SYSTEM,
        max_tokens=512,
        temperature=0.1,
    )
    return _sanitize_spl(spl)
