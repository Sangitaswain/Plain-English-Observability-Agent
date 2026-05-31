# agent.py
# Transport: Dynatrace Grail REST API — MCP gateway not available on trial tenants.

import os
from contextlib import asynccontextmanager
import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "system_prompt.txt")

def _load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, encoding="utf-8") as f:
        return f.read()

async def run_dql(query: str) -> dict:
    """Execute a DQL query against Dynatrace Grail and return results."""
    base = os.environ["DT_TENANT_URL"].rstrip("/")
    token = os.environ["DT_PLATFORM_TOKEN"].strip()
    url = f"{base}/platform/storage/query/v1/query:execute"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"query": query, "requestTimeoutMilliseconds": 25000},
        )
        if resp.status_code >= 400:
            return {"error": f"Query failed ({resp.status_code})", "records": []}
        return resp.json()

async def get_problems() -> dict:
    """Fetch active Dynatrace problems via DQL event query."""
    return await run_dql(
        'fetch events'
        ' | filter event.type == "DAVIS_PROBLEM"'
        ' | filter event.status == "ACTIVE"'
        ' | sort timestamp desc | limit 20'
    )

@asynccontextmanager
async def get_agent_and_tools():
    """Yields an LlmAgent with live Dynatrace query tools."""
    agent = LlmAgent(
        name="observability_assistant",
        model="gemini-2.5-flash",
        instruction=_load_system_prompt(),
        tools=[FunctionTool(run_dql), FunctionTool(get_problems)],
    )
    yield agent
