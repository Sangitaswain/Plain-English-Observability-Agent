import os
import logging
import time
from collections import defaultdict, deque

from dotenv import load_dotenv
load_dotenv()

import re
from fastapi import FastAPI, HTTPException, Request, Header
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware

_DT_URL_RE = re.compile(r'^https://[a-zA-Z0-9-]+\.apps\.dynatrace\.com$')
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import get_agent_and_tools
from answer_parser import parse_agent_output, ChartData

try:
    import google.cloud.logging
    google.cloud.logging.Client().setup_logging()
except Exception:
    pass

log = logging.getLogger("observability_agent")
import sys as _sys
if not log.handlers:
    _h = logging.StreamHandler(_sys.stdout)
    _h.setLevel(logging.DEBUG)
    log.addHandler(_h)
log.setLevel(logging.DEBUG)

app = FastAPI()

# Security headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-DT-Tenant-URL", "X-DT-Token"],
    allow_credentials=False,
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Rate limiting: 20 requests per IP per 60 seconds
_rate_buckets: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))

def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    bucket = _rate_buckets[ip]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= 20:
        return True
    bucket.append(now)
    return False

# Schemas
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    prev_question: Optional[str] = Field(None, max_length=500)

class AskResponse(BaseModel):
    headline: str
    paragraph: str
    chart_data: Optional[ChartData] = None
    uncertainty: bool
    needs_clarification: bool
    followup_questions: list[str] = []

APP_NAME = "observability_agent"

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.post("/ask", response_model=AskResponse)
async def ask(
    req: AskRequest,
    request: Request,
    x_dt_tenant_url: Optional[str] = Header(None, alias="X-DT-Tenant-URL"),
    x_dt_token: Optional[str] = Header(None, alias="X-DT-Token"),
):
    ip = request.client.host or "unknown"

    if _is_rate_limited(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many questions. Please wait a moment before asking again."
        )

    # Validate custom tenant URL if provided
    if x_dt_tenant_url:
        if not _DT_URL_RE.match(x_dt_tenant_url.rstrip("/")):
            raise HTTPException(status_code=400, detail="Invalid tenant URL format.")

    log.info(f"question received | ip={ip} | q={req.question!r}")

    async with get_agent_and_tools(
        tenant_url=x_dt_tenant_url or None,
        token=x_dt_token or None,
    ) as agent:
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=ip,
        )
        question_text = req.question
        if req.prev_question:
            question_text = f"Follow-up to: '{req.prev_question}'. New question: '{req.question}'"

        content = types.Content(
            role="user",
            parts=[types.Part(text=question_text)],
        )

        raw_answer = ""
        tool_call_count = 0

        try:
            async for event in runner.run_async(
                user_id=ip,
                session_id=session.id,
                new_message=content,
            ):
                if getattr(event, "tool_call", None):
                    tool_call_count += 1
                    if tool_call_count > 5:
                        raise RuntimeError("agent_loop_exceeded")

                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            raw_answer += part.text

        except RuntimeError as e:
            if "agent_loop_exceeded" in str(e):
                log.warning(f"runaway loop aborted | ip={ip}")
                return AskResponse(
                    headline="Something went wrong while answering your question.",
                    paragraph="The system took too many steps. Please try rephrasing your question.",
                    uncertainty=True,
                    needs_clarification=False,
                    followup_questions=[],
                )
            raise

        except Exception as e:
            log.exception(f"agent error | ip={ip}")
            return AskResponse(
                headline="Something went wrong.",
                paragraph="I couldn't retrieve that information right now. Please try again in a moment.",
                uncertainty=True,
                needs_clarification=False,
                followup_questions=[],
            )

    parsed = parse_agent_output(raw_answer)
    log.info(f"answer sent | ip={ip} | headline={parsed['headline']!r}")
    return AskResponse(**parsed)
