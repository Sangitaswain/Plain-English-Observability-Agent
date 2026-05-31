# agent.py
# Transport: Dynatrace Grail REST API — MCP gateway not available on trial tenants.

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.txt")

def _load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, encoding="utf-8") as f:
        return f.read()

def _expand_timeseries(row: dict) -> list:
    """Convert makeTimeseries single-row format to individual timestamped records."""
    start = datetime.fromisoformat(row["timeframe"]["start"].replace("Z", "+00:00"))
    interval_s = int(row["interval"]) / 1e9
    metric_key = next((k for k, v in row.items() if isinstance(v, list)), None)
    if not metric_key:
        return []
    result = []
    for i, val in enumerate(row[metric_key]):
        if val is None:
            continue
        t = start + timedelta(seconds=i * interval_s)
        hour = int(t.strftime("%I"))
        minute = t.strftime("%M")
        ampm = t.strftime("%p")
        result.append({"timestamp": f"{hour}:{minute} {ampm}", "count": int(val)})
    return result


@asynccontextmanager
async def get_agent_and_tools(
    tenant_url: Optional[str] = None,
    token: Optional[str] = None,
):
    """Yields an LlmAgent with Dynatrace query tools.

    If tenant_url / token are provided (user-supplied credentials), those are
    used instead of the server environment variables.
    """
    _url   = (tenant_url or os.environ["DT_TENANT_URL"]).rstrip("/")
    _token = (token or os.environ["DT_PLATFORM_TOKEN"]).strip()

    async def run_dql(query: str) -> dict:
        """Execute a DQL query against Dynatrace Grail and return results."""
        url = f"{_url}/platform/storage/query/v1/query:execute"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {_token}"},
                json={"query": query, "requestTimeoutMilliseconds": 25000},
            )
            if resp.status_code >= 400:
                return {"error": f"Query failed ({resp.status_code})", "records": []}
            data = resp.json()
            records = data.get("result", data).get("records", data.get("records", []))
            # Normalize makeTimeseries single-row array format into per-row records
            if len(records) == 1 and "timeframe" in records[0] and "interval" in records[0]:
                records = _expand_timeseries(records[0])
                return {"records": records}
            return data

    async def get_problems() -> dict:
        """Fetch active Dynatrace problems via DQL event query."""
        return await run_dql(
            'fetch events'
            ' | filter event.type == "DAVIS_PROBLEM"'
            ' | filter event.status == "ACTIVE"'
            ' | sort timestamp desc | limit 20'
        )

    agent = LlmAgent(
        name="observability_assistant",
        model="gemini-2.5-flash",
        instruction=_load_system_prompt(),
        tools=[FunctionTool(run_dql), FunctionTool(get_problems)],
    )
    yield agent
