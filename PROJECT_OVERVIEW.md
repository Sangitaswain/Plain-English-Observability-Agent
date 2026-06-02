# Signal AI — Complete Project Overview

**Google Cloud x Dynatrace AI Challenge**
**Built by:** Sushri Sangita Swain
**Final eval score:** 18/20 against live Cloud Run
**Live URL:** https://observability-agent-601086227447.us-central1.run.app

---

## The Problem

Dynatrace is one of the most powerful observability platforms available. It captures real-time data about errors, latency, traffic, and system health across entire applications.

Most of the people who care about that data cannot read it.

A non-technical founder whose checkout is slow cannot open Dynatrace. She does not know what a DQL query is, how to read a dashboard, or which metric to look at. Her only option is to wait for an engineer to translate the data into a sentence she can act on.

This project closes that gap. Instead of learning the tool, the user just asks a question in plain English and gets one clear answer backed by real monitoring data.

---

## What It Does

Signal AI is a web application where a user types a plain-English question about their system:

> "Were there any errors last night?"

And gets back a direct, human-readable answer:

> **"Yes. 224 errors were recorded overnight."**
> "Most errors relate to application restarts and SSL handshake failures. These often resolve on their own and do not require immediate action. Worth monitoring over the next hour."

No query language. No dashboards. No engineering knowledge required.

Every answer consists of:
- A **headline** — starts with YES/NO or a key number, maximum 20 words
- A **paragraph** — context, severity judgement, and a recommendation
- An optional **chart** — time-series line chart or bar chart for comparisons
- An **uncertainty flag** — shown when the data looks implausible
- **Follow-up chips** — 2-3 contextual next questions generated from the actual data returned

---

## Architecture

```
Browser → FastAPI (Cloud Run) → ADK Runner → Gemini 2.5 Flash (Vertex AI) → Dynatrace Grail REST API
```

| Layer | Technology | Role |
|---|---|---|
| Frontend | HTML + CSS + JS + Chart.js 4.4.2 | Two-screen SPA: connect screen → question interface |
| Backend | FastAPI 0.136.3 on Cloud Run | Receives questions, rate limits, returns structured JSON |
| Agent | Google ADK 1.10.0 (LlmAgent + Runner) | Runs the 5-step reasoning loop |
| AI model | Gemini 2.5 Flash via Vertex AI | Understands intent, writes queries, produces answers |
| Data | Dynatrace Grail REST API v1 | Executes DQL against real log and event data |
| Secrets | GCP Secret Manager | Stores the Dynatrace Platform Token at rest |

---

## How the Agent Works

Every question goes through a fixed 5-step reasoning loop defined in `system_prompt.txt`:

**Step 1 — Extract intent:** The agent identifies the metric type (errors, latency, traffic, security, comparison, breakdown), the entity (which service or page), and the time window. Natural language phrases like "last night", "this morning", "earlier" are mapped to exact DQL timestamp expressions.

**Step 2 — Write the query:** Based on question type, the agent selects the right DQL pattern. A summary question runs three queries (errors, activity, problems). A comparison question runs two queries for separate time windows. A breakdown question fetches sample error content to name error types.

**Step 3 — Execute:** The agent calls one of two tools:
- `run_dql(query)` — runs a DQL query against the Dynatrace Grail endpoint
- `get_problems()` — fetches active Davis AI-detected problems

**Step 4 — Validate:** The agent checks that results make sense. Zero results, obviously wrong numbers, or suspicious patterns trigger a corrected retry. If the second attempt also fails, the agent flags uncertainty.

**Step 5 — Translate:** The agent produces structured output in a fixed format: HEADLINE, PARAGRAPH, optional CHART JSON, optional FOLLOWUP list. The `answer_parser.py` module parses this into the typed JSON response that the frontend renders.

---

## Features Built

### Core features
- Plain-English question input with 500-character limit
- Intent understanding across 8 question types: errors, latency, traffic, security, comparison, breakdown, complaint/crash, business-specific
- DQL query generation and execution via Dynatrace Grail REST API
- Yes/No headline with 20-word maximum
- Contextual paragraph with severity judgment and escalation recommendation
- Time-series line chart and bar chart for comparisons
- Uncertainty flag shown when data looks implausible
- Ambiguity clarification: agent asks one clarifying question for vague inputs
- Out-of-scope refusal: agent politely declines non-observability questions
- Destructive request refusal: agent refuses write/delete requests immediately
- Query failure notification: agent reports plainly rather than guessing

### Interface features
- Two-screen flow: connect screen (demo or own account) then question interface
- Three example question chips that auto-fill the input
- Dynamic follow-up chips generated from the actual data returned
- Loading spinner during agent processing
- Error banner for rate limits, network errors, and empty input
- Mobile-responsive layout (tested at 375px, no horizontal scroll)
- No login required for demo mode

### Safety and security
- Rate limiter: 20 requests per minute per IP, returns HTTP 429
- Runaway guard: agent aborts if more than 5 tool calls are made for one question
- `InMemorySessionService` created per request (no cross-user state leakage)
- All output rendered via `textContent` (never `innerHTML`) — XSS prevented by design
- Content Security Policy meta tag restricts script sources to self + Chart.js CDN only
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- Dynatrace token stored in GCP Secret Manager, never in environment variables
- Error responses never expose stack traces, class names, DQL queries, or internal paths

---

## Development Journey

### Phase 1 — Repo Foundation (Day 1)
Set up `.gitignore`, folder structure, requirements.txt, Dockerfile with non-root user, MIT license, and `.env.example` template. All secrets excluded from git from the first commit.

### Phase 2 — Dynatrace Connectivity (Day 2)
Discovered that the Dynatrace MCP gateway (`platform-reserved/mcpgateway`) returns 404 on trial tenants. Pivoted to direct Dynatrace Grail REST API calls using `httpx`. Verified `fetch logs | limit 3` returned `state: SUCCEEDED`. This pivot turned out to be simpler and faster than MCP transport.

### Phase 3 — Backend Skeleton on Cloud Run (Day 3)
Wrote minimal FastAPI app with `/health` endpoint, CORS middleware, Cloud Logging setup, and static file mount. Enabled required GCP APIs. Created Secret Manager secret. First Cloud Run deploy returned `{"ok": true}` from live URL.

**Cloud Run URL:** `https://observability-agent-601086227447.us-central1.run.app`

### Phase 4 — Agent + Tools Wired (Days 4–5)
Wrote `system_prompt.txt` with the 5-step loop and 8 hard rules. Wrote `agent.py` using `LlmAgent` with two `FunctionTool`s (`run_dql`, `get_problems`). Wrote `answer_parser.py` to parse agent text output into typed JSON. Added `/ask` endpoint to FastAPI with Pydantic validation, rate limiter, runaway guard, and security headers. First end-to-end local test returned a real Dynatrace-backed answer. Deployed to Cloud Run with exact frozen requirements.

### Phase 5 — Prompt Refinement (Days 6–7)
Tuned the system prompt to correctly handle:
- Vague questions: agent asks exactly one clarifying question
- Out-of-scope questions: clean refusal with redirect
- Destructive requests: immediate read-only refusal
- Missing time window: agent states the assumption explicitly ("Looking at the last hour…")

### Phase 6 — Eval Framework (Day 8)
Wrote `eval_questions.json` (10 fixed questions with expected behaviours) and `eval.py` (interactive 0/1/2 scoring runner). Ran first baseline eval. Identified which questions were failing and which prompt rules needed tightening.

### Phase 7 — Safety Hardening and Eval ≥ 12/20 (Days 9–10)
Fixed failing questions by tuning the system prompt:
- Q4 (slowest page): added latency ranking guidance
- Q5 (security alerts): explicit routing to `get_problems` instead of `generate_dql`
- Q6 (comparison): two separate DQL calls for two time windows
- Q7 (escalation): clear "call your engineer" vs "no action needed" phrasing

Verified runaway guard by temporarily lowering limit to 1 — confirmed friendly error, no stack trace.

**Eval result: ≥ 12/20.**

### Phase 8 — Chart + Uncertainty + Eval ≥ 16/20 (Day 11)
Tested chart output end-to-end. Strengthened the chart format example in the system prompt. Verified uncertainty flag correctly propagates from `UNCERTAIN:` tag in agent output. Polished escalation phrasing.

**Eval result: ≥ 16/20.**

### Phase 9 — Frontend Built and Wired (Days 12–13)
Built the complete frontend from scratch:
- `index.html`: semantic structure, CSP meta tag, Chart.js at pinned version 4.4.2
- `style.css`: two-color palette, spinner animation, mobile breakpoint at 500px
- `app.js`: state machine (IDLE → LOADING → ANSWERED), chip handlers, fetch, chart rendering

Deployed with `min-instances=1` to keep the container warm. Tested all error states: rate limit (429 banner), network error, empty input, XSS input (renders as literal text). Mobile tested at 375px — no horizontal scroll.

### Phase 12 — Agent Quality and UX Polish (added after frontend was live)
This phase was not in the original plan. Added after observing real usage patterns.

**Follow-up chips:** Added `FOLLOWUP:` output section to the system prompt. Agent generates 2-3 self-contained questions specific to the data returned (not generic templates). Parser extracts the JSON array. Frontend renders chips with a fade-in animation. Clicking a chip sends the previous question as silent context.

**Question type accuracy fixes:**
- Added a time window extraction table (e.g. "last night" → `now()-16h`, "this morning" → `now()-10h`)
- Added `COMPLAINT` question type: trigger words like "weird", "broken", "crashed" run a full 3-query breakdown without asking for clarification
- Added `DID IT CRASH?` question type: 0 problems + low errors → headline starts with "No."
- Added `BUSINESS-SPECIFIC` question type: for login/checkout/payment questions, agent acknowledges honestly that the data is Windows system logs, not application data
- Added `TIMING` question type: "when did these errors happen?" runs a time-series without content filtering (content filtering on time-series queries returns empty and causes a wrong "No." answer)

**Headline and chart improvements:**
- Headline capped at 20 words; error type details banned from headline (paragraph only)
- Bar chart type added for comparison answers (blue = current, grey = previous)
- `answer_parser.py` validates chart type is "line" or "bar" before passing to frontend

### Phase 10 — Repo Is Judge-Ready (Day 15)
Wrote comprehensive README with demo link, architecture diagrams, full setup instructions, "What I Built and Learned" section, and known limitations. Verified repo is public, MIT license visible in GitHub About panel, no secrets in git history.

### Phase 11 — Final Eval and Submission (Days 17–18)
Ran final eval against live Cloud Run URL.

**Final eval result: 18/20.**

---

## Key Technical Decisions

**REST API instead of MCP transport.** The original plan used the Dynatrace MCP gateway. Trial tenants return 404 on that endpoint. Direct REST API calls with `httpx` and two `FunctionTool`s turned out to be simpler, more debuggable, and faster. No MCP dependency means one fewer moving part in production.

**Stateless sessions per request.** `InMemorySessionService` is created inside the `/ask` handler, not at module level. This means no state leaks between users. The trade-off is no multi-turn conversation memory, which is acceptable for the use case (one question, one answer, with follow-up chips providing the next step).

**Structured output parsing instead of function calling.** The agent outputs a fixed text format (HEADLINE, PARAGRAPH, CHART JSON, FOLLOWUP JSON). `answer_parser.py` parses this with regex rather than using structured output or function calling. This is more fragile but gives more control over what the agent produces and how errors are handled.

**Hard rules in the system prompt for guardrails.** The agent needed explicit hard rules (never use em dashes, never put breakdown details in the headline, never claim to see data that is not there, never say "Mostly yes" to a crash question) because the model would produce plausible-sounding but wrong answers without them. Rules evolve through the eval cycle — each failing question reveals a missing or underspecified rule.

**Never `innerHTML`, always `textContent`.** All agent output is rendered via `textContent` in JavaScript. This is enforced by design, not by sanitization. An `eval()` or `innerHTML` slip would open an XSS path from agent output to the browser. This rule is hardcoded in the project's non-negotiables and verified on every frontend deploy.

---

## What the Data Actually Shows

The demo connects to a Dynatrace Playground account (`wgt98056.apps.dynatrace.com`) — a free trial tenant monitoring a Windows machine via Dynatrace OneAgent. It captures:

- Windows service events, application restarts, background process errors
- SSL handshake events and system health metrics
- Davis AI-detected active problems

It does **not** capture web traffic, user logins, checkout events, or customer counts — because there is no application-level instrumentation connected. The agent is honest about this in every answer involving those topics.

In a real deployment, a business would install Dynatrace OneAgent on their actual server and connect this agent to their own tenant URL and token. The same questions would return answers based on real production traffic.

---

## Eval Results History

| Run | Score | Against |
|---|---|---|
| Baseline (Day 8) | ~8/20 | Local |
| After Phase 7 | ≥ 12/20 | Local |
| After Phase 8 | ≥ 16/20 | Local |
| Phase 11 first attempt | 12/20 | Live Cloud Run (token stale — fixed) |
| Phase 11 final | **18/20** | Live Cloud Run |

---

## Project Structure

```
Plain-English-Observability-Agent/
|
+-- backend/
|   +-- main.py              FastAPI app: /ask, /health, rate limiter, CORS, security headers
|   +-- agent.py             LlmAgent with run_dql() and get_problems() tools
|   +-- system_prompt.txt    5-step loop, question type patterns, 11 hard rules
|   +-- answer_parser.py     Converts raw agent text output into typed JSON
|   +-- eval.py              10-question automated scoring runner
|   +-- eval_questions.json  Fixed test question set with expected behaviours
|   +-- requirements.txt     Pinned Python dependencies
|   +-- Dockerfile           python:3.11-slim, non-root user, port 8080
|   +-- .dockerignore        Excludes .env, .venv, __pycache__, eval results
|
+-- frontend/
|   +-- index.html           Connect screen + app screen, CSP meta tag
|   +-- app.js               State machine, chip handlers, fetch, chart rendering
|   +-- style.css            Design system, spinner, mobile breakpoint at 500px
|
+-- docs/                    Gitignored — private implementation docs and videos
|   +-- architecture_overview.png   (tracked — referenced in README)
|   +-- architecture.png            (tracked — referenced in README)
|   +-- demo.gif                    (tracked — referenced in README)
|
+-- .env.example             Template for local environment variables (no real values)
+-- LICENSE                  MIT
+-- README.md                Public project README with live demo link and setup guide
+-- PROJECT_OVERVIEW.md      This document
```

---

## Running It Yourself

**Prerequisites:** Python 3.11+, a GCP project with Vertex AI enabled, a Dynatrace tenant with a Platform Token.

```bash
git clone <repo-url>
cd Plain-English-Observability-Agent
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r backend/requirements.txt
cp .env.example .env
# Fill in DT_TENANT_URL, DT_PLATFORM_TOKEN, GOOGLE_CLOUD_PROJECT in .env
cd backend
uvicorn main:app --reload --port 8080
```

Your Dynatrace Platform Token needs scopes: `storage:logs:read`, `storage:metrics:read`, `storage:events:read`, `storage:entities:read`.

---

## License

MIT. See [LICENSE](LICENSE).

---

*Built for the Google Cloud x Dynatrace AI Challenge.*
