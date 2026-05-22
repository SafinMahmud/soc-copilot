import json
import os

import anthropic

from prompts import (
    INVESTIGATION_SYNTHESIS_PROMPT,
    INVESTIGATION_SYSTEM,
    SPL_GENERATION_SYSTEM,
)
from splunk_client import SplunkClient

splunk = SplunkClient()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

INVESTIGATION_TOOLS = [
    {
        "name": "run_splunk_query",
        "description": "Execute a SPL query against Splunk and return results as a list of dicts. Use this to search logs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spl": {
                    "type": "string",
                    "description": "The complete SPL query to execute",
                },
                "description": {
                    "type": "string",
                    "description": "One sentence describing what this query is looking for",
                },
            },
            "required": ["spl", "description"],
        },
    },
    {
        "name": "get_field_values",
        "description": "Get the top unique values for a specific field in Splunk. Use to discover what data is available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": "Field name to get values for",
                },
                "index": {
                    "type": "string",
                    "description": "Splunk index to search",
                },
            },
            "required": ["field", "index"],
        },
    },
]

MAX_TOOL_CALLS = 8


def run_investigation_agent(
    entity: str, entity_type: str, time_range: str, index: str
) -> dict:
    """Autonomous investigation agent loop."""
    messages = [
        {
            "role": "user",
            "content": (
                f"Investigate this entity from our Splunk SIEM.\n"
                f"Entity: {entity}\n"
                f"Type: {entity_type}\n"
                f"Time range: {time_range}\n"
                f"Index: {index}\n\n"
                "Run queries to build a complete picture of this entity's activity. "
                "Focus on finding suspicious patterns."
            ),
        }
    ]

    raw_findings = {}
    queries_run = []
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=INVESTIGATION_SYSTEM,
            tools=INVESTIGATION_TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            break

        tool_calls_in_response = [
            b for b in response.content if b.type == "tool_use"
        ]
        if not tool_calls_in_response:
            break

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tool_call in tool_calls_in_response:
            if tool_call_count >= MAX_TOOL_CALLS:
                break
            tool_call_count += 1
            result = execute_tool(tool_call.name, tool_call.input, time_range)

            query_key = f"query_{tool_call_count}"
            raw_findings[query_key] = {
                "description": tool_call.input.get("description", tool_call.name),
                "spl": tool_call.input.get("spl", ""),
                "results": result,
            }
            if tool_call.input.get("spl"):
                queries_run.append(tool_call.input["spl"])

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": json.dumps(
                        result[:20] if isinstance(result, list) else result
                    ),
                }
            )

        messages.append({"role": "user", "content": tool_results})

    return {"raw_findings": raw_findings, "queries_run": queries_run}


def execute_tool(tool_name: str, tool_input: dict, time_range: str = "-24h"):
    """Route tool calls to Splunk client."""
    if tool_name == "run_splunk_query":
        return splunk.run_query(tool_input["spl"])
    if tool_name == "get_field_values":
        return splunk.get_field_values(
            tool_input["field"],
            tool_input["index"],
            time_range=time_range,
        )
    return {"error": f"Unknown tool: {tool_name}"}


def synthesize_report(
    entity: str, entity_type: str, time_range: str, agent_output: dict
) -> dict:
    """Synthesize raw findings into structured report JSON."""
    prompt = INVESTIGATION_SYNTHESIS_PROMPT.format(
        entity=entity,
        entity_type=entity_type,
        time_range=time_range,
        queries_run=json.dumps(agent_output["queries_run"], indent=2),
        raw_findings=json.dumps(agent_output["raw_findings"], indent=2),
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def generate_spl(natural_language: str, time_range: str, index: str) -> str:
    """Single Claude call to convert natural language to SPL."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SPL_GENERATION_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Convert to SPL. Index: {index}. Time range: {time_range}.\n"
                    f"Question: {natural_language}"
                ),
            }
        ],
    )
    spl = response.content[0].text.strip()
    if spl.startswith("```"):
        spl = spl.split("```")[1]
        if spl.startswith("spl"):
            spl = spl[3:]
        spl = spl.strip()
    return spl
