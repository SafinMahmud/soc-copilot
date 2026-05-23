import json
import os
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
    return os.getenv("AI_PROVIDER", "gemini").strip().lower()


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


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


def _extract_gemini_text(payload: Dict[str, Any]) -> str:
    candidates = payload.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini response missing candidates: {payload}")
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    text = "".join(part.get("text", "") for part in parts if "text" in part)
    if not text:
        raise RuntimeError(f"Gemini response missing text content: {payload}")
    return text


def _gemini_generate(
    user_prompt: str,
    system_prompt: str = "",
    max_tokens: int = 2048,
    temperature: float = 0.2,
) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to backend/.env.")

    requested_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    model_candidates = [
        requested_model,
        "gemini-2.0-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-2.0-flash-lite",
    ]

    body: Dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        body["system_instruction"] = {"parts": [{"text": system_prompt}]}

    with httpx.Client(timeout=90.0) as client:
        last_error: Optional[str] = None
        for model in model_candidates:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent"
            )
            response = client.post(url, params={"key": api_key}, json=body)
            if response.status_code == 404:
                last_error = f"Model '{model}' not found on this API key/project."
                continue
            if response.status_code == 429:
                raise RuntimeError(
                    "Gemini quota exceeded for this API key/project. "
                    "Create a new Google AI Studio key with available quota, "
                    "or switch AI_PROVIDER=mock for offline demo mode."
                )
            if response.is_error:
                raise RuntimeError(
                    f"Gemini API error {response.status_code}: {response.text[:400]}"
                )
            return _extract_gemini_text(response.json()).strip()
        raise RuntimeError(
            last_error
            or "Unable to find an available Gemini model for this API key."
        )


def execute_tool(tool_name: str, tool_input: Dict[str, Any], time_range: str = "-24h"):
    """Route tool calls to Splunk client."""
    if tool_name == "run_splunk_query":
        return _get_splunk().run_query(tool_input["spl"])
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
        return (
            f"(index={configured} OR index=main OR index=botsv3 "
            "OR index=_internal OR index=_audit)"
        )
    return "(index=main OR index=botsv3 OR index=_internal OR index=_audit)"


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


def _mock_synthesize_report(
    entity: str, entity_type: str, agent_output: Dict[str, Any]
) -> Dict[str, Any]:
    raw_findings = agent_output["raw_findings"]
    timeline = []
    failure_count = 0
    success_count = 0
    transfer_count = 0
    for query in raw_findings.values():
        description = query.get("description", "Investigation event")
        for row in (query.get("results") or [])[:8]:
            if not isinstance(row, dict) or "error" in row:
                continue
            row_text = json.dumps(row, default=str).lower()
            if "4625" in row_text or '"failure"' in row_text:
                failure_count += 1
            if "4624" in row_text or '"success"' in row_text:
                success_count += 1
            if "bytes_out" in row and str(row.get("bytes_out", "0")).isdigit():
                if int(row.get("bytes_out", 0)) > 1_000_000:
                    transfer_count += 1
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

    timeline.sort(key=lambda x: x["timestamp"])
    if not timeline:
        timeline = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "network",
                "description": "No matching events found in current index/time range.",
                "raw_log": "{}",
                "severity": "low",
            }
        ]

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

    mitre_techniques = [
        {
            "technique_id": "T1110",
            "name": "Brute Force",
            "tactic": "Credential Access",
            "description": "Repeated failed logins may indicate password guessing attempts.",
        },
        {
            "technique_id": "T1021",
            "name": "Remote Services",
            "tactic": "Lateral Movement",
            "description": "Remote authentication and service access activity observed.",
        },
    ]
    if transfer_count > 0:
        mitre_techniques.append(
            {
                "technique_id": "T1048",
                "name": "Exfiltration Over Alternative Protocol",
                "tactic": "Exfiltration",
                "description": "Large outbound transfer patterns may indicate data exfiltration.",
            }
        )

    remediation_steps = [
        {
            "priority": "Critical" if severity in ("Critical", "High") else "High",
            "action": f"Contain entity {entity} and rotate potentially exposed credentials.",
            "rationale": "Immediate containment limits attacker dwell time and reuse.",
        },
        {
            "priority": "High",
            "action": "Block suspicious source IPs and enforce MFA for privileged access.",
            "rationale": "Reduces ongoing brute-force and unauthorized remote access risk.",
        },
        {
            "priority": "Medium",
            "action": "Increase detections for repeated auth failures and anomalous transfers.",
            "rationale": "Improves early detection of similar attack patterns.",
        },
    ]

    summary = (
        f"Mock provider investigation reviewed {len(raw_findings)} query groups for "
        f"{entity_type} '{entity}'. Findings show {failure_count} suspicious auth failures, "
        f"{success_count} successful auth events, and {transfer_count} potential transfer indicators."
    )

    return {
        "severity": severity,
        "severity_rationale": severity_rationale,
        "summary": summary,
        "timeline": timeline[:40],
        "mitre_techniques": mitre_techniques[:6],
        "remediation_steps": remediation_steps,
    }


def run_investigation_agent(
    entity: str, entity_type: str, time_range: str, index: str
) -> Dict[str, Any]:
    """
    Autonomous investigation loop using Gemini planning or mock fallback.
    """
    provider = _provider()
    if provider == "mock":
        return _run_mock_investigation_agent(entity, entity_type, time_range, index)
    if provider != "gemini":
        raise RuntimeError(f"Unsupported AI_PROVIDER '{provider}'. Use gemini or mock.")

    raw_findings: Dict[str, Any] = {}
    queries_run = []
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        findings_snapshot = json.dumps(raw_findings, default=str)[-25000:]
        decision_prompt = f"""
Entity: {entity}
Entity type: {entity_type}
Time range: {time_range}
Index: {index}
Tool calls used: {tool_call_count}/{MAX_TOOL_CALLS}

Current findings JSON:
{findings_snapshot}

Choose exactly one next action and return ONLY valid JSON in one of these formats:
1) {{
  "action": "run_splunk_query",
  "description": "what this query checks",
  "spl": "search index={index} earliest={time_range} ..."
}}
2) {{
  "action": "get_field_values",
  "field": "field_name",
  "index": "{index}"
}}
3) {{
  "action": "finish",
  "reason": "why investigation is complete"
}}

Rules:
- Run at least 4 query actions before finish unless data is unavailable.
- Use concrete SPL, not placeholders.
- Keep responses JSON only.
""".strip()

        decision_raw = _gemini_generate(
            user_prompt=decision_prompt,
            system_prompt=INVESTIGATION_SYSTEM,
            max_tokens=1024,
            temperature=0.1,
        )
        decision = _extract_json_object(decision_raw)
        action = decision.get("action")

        if action == "finish":
            break

        if action == "run_splunk_query":
            spl = decision.get("spl", "").strip()
            description = decision.get("description", "Investigation query")
            if not spl:
                break
            tool_call_count += 1
            result = execute_tool(
                "run_splunk_query",
                {"spl": spl, "description": description},
                time_range=time_range,
            )
            query_key = f"query_{tool_call_count}"
            raw_findings[query_key] = {
                "description": description,
                "spl": spl,
                "results": result,
            }
            queries_run.append(spl)
            continue

        if action == "get_field_values":
            field = decision.get("field", "").strip()
            tool_index = decision.get("index", index)
            if not field:
                break
            tool_call_count += 1
            result = execute_tool(
                "get_field_values",
                {"field": field, "index": tool_index},
                time_range=time_range,
            )
            query_key = f"query_{tool_call_count}"
            raw_findings[query_key] = {
                "description": f"Top values for field: {field}",
                "spl": "",
                "results": result,
            }
            continue

        break

    return {"raw_findings": raw_findings, "queries_run": queries_run}


def synthesize_report(
    entity: str, entity_type: str, time_range: str, agent_output: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Synthesize raw findings into structured report JSON.
    """
    provider = _provider()
    if provider == "mock":
        return _mock_synthesize_report(entity, entity_type, agent_output)
    if provider != "gemini":
        raise RuntimeError(f"Unsupported AI_PROVIDER '{provider}'. Use gemini or mock.")

    prompt = INVESTIGATION_SYNTHESIS_PROMPT.format(
        entity=entity,
        entity_type=entity_type,
        time_range=time_range,
        queries_run=json.dumps(agent_output["queries_run"], indent=2),
        raw_findings=json.dumps(agent_output["raw_findings"], indent=2),
    )
    response_text = _gemini_generate(
        user_prompt=prompt,
        system_prompt="Return only valid JSON. No markdown.",
        max_tokens=4096,
        temperature=0.1,
    )
    return _extract_json_object(response_text)


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
    Convert natural language to SPL using Gemini or mock fallback.
    """
    provider = _provider()
    if provider == "mock":
        return _mock_generate_spl(natural_language, time_range, index)
    if provider != "gemini":
        raise RuntimeError(f"Unsupported AI_PROVIDER '{provider}'. Use gemini or mock.")

    prompt = (
        f"Convert to SPL. Index: {index}. Time range: {time_range}.\n"
        f"Question: {natural_language}"
    )
    spl = _gemini_generate(
        user_prompt=prompt,
        system_prompt=SPL_GENERATION_SYSTEM,
        max_tokens=512,
        temperature=0.1,
    )
    return _strip_markdown_fences(spl)
