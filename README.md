# Signal AI: Plain-English Observability Agent

> Ask questions about your system in plain English. Get clear, jargon-free answers backed by live Dynatrace monitoring data. No query languages, no dashboards, no engineering background needed.

**Live demo:** https://observability-agent-601086227447.us-central1.run.app

---

## The Problem It Solves

Non-technical founders and business owners cannot read Dynatrace dashboards or write DQL queries. When something feels wrong with their site, they either ignore it or call an engineer.

Signal AI closes that gap. Instead of opening a monitoring tool, they just ask a question:

> *"Were there any errors last night?"*
> *"Is my site running normally right now?"*
> *"Compare today's errors to yesterday."*
> *"Tell me the summary of my system."*

The agent queries Dynatrace in real time, interprets the data, and responds in one clear sentence with supporting context, a chart if the data warrants it, and suggested follow-up questions to continue the investigation.

---

## Architecture

### Overview

A quick mental model of how the five layers connect:

![Architecture overview](docs/architecture_overview.png)

### Detailed Breakdown

Full component view with data flows, internal modules, and security notes:

![Detailed architecture](docs/architecture.png)

### Layer-by-Layer Summary

| Layer | Technology | What it does |
|---|---|---|
| Frontend | HTML + CSS + JS + Chart.js | Two-screen SPA: connect screen, then the question/answer interface |
| Backend | FastAPI on Cloud Run | Receives questions, enforces rate limits, returns structured JSON |
| Agent | Google ADK + LlmAgent | Runs the 5-step reasoning loop that turns a question into queries |
| AI Model | Gemini 2.5 Flash on Vertex AI | Understands intent, picks the right query pattern, writes the answer |
| Data | Dynatrace Grail REST API | Executes DQL queries against real log and event data |

---

## How It Works: The 5-Step Loop

Every question the user asks goes through the same fixed reasoning loop defined in `system_prompt.txt`:

**Step 1: Understand**
The agent reads the question and identifies two things: the metric type (errors, activity, health, comparison, breakdown) and the time window ("last night", "today", "last hour", etc.). It maps natural language time phrases to exact DQL timestamps.

**Step 2: Write the query**
Based on the question type, the agent selects the right DQL pattern. A summary question runs three queries (problems + error count + total events). A comparison question runs two queries for two separate time windows. A breakdown question also fetches sample error content to name what kind of errors appeared.

**Step 3: Execute**
The agent calls one of two tools:
- `run_dql(query)`: executes a DQL statement against the Dynatrace Grail storage endpoint
- `get_problems()`: fetches active Davis AI problems

**Step 4: Validate**
The agent checks whether the results make sense (positive numbers, non-empty records). If values look wrong, it retries once with a corrected query and flags the answer as uncertain if it still cannot verify.

**Step 5: Translate**
The agent produces a structured output:
- **HEADLINE**: one or two short sentences, starts with YES/NO or a specific number, 20-word maximum
- **PARAGRAPH**: 2-3 sentences of context in plain English, names error types if a breakdown was run
- **FOLLOWUP**: 2-3 specific follow-up questions based on what the data actually showed
- **CHART** (optional): JSON block for a line chart (time-series) or bar chart (comparisons)

The `answer_parser.py` module then strips all labels and converts this text output into a typed JSON response the frontend can render directly.

---

## Features

**Plain-English answers**
Every answer starts with YES/NO or a specific number. No jargon, no raw query output, no field names.

**Real-time Dynatrace data**
Every question triggers live queries. The data is never cached.

**Smart follow-up chips**
After every answer, 2-3 follow-up questions appear as clickable chips. They are specific to the actual data returned, not generic templates. Clicking one sends it as a follow-up question with the previous question as silent context.

**Line and bar charts**
Error trends over time render as line charts. Comparison answers (today vs yesterday) render as bar charts. Charts only appear when there is multi-point data worth visualising.

**Two connection modes**
Users can connect their own Dynatrace account by entering a tenant URL and Platform API Token. Alternatively, they can use the built-in demo mode which connects to a live Dynatrace Playground environment.

**Secure credential handling**
Credentials entered on the connect screen are stored in `sessionStorage` only. They are never persisted to disk, never sent to any third party, and are cleared when the browser tab closes. The Dynatrace token only needs read-only scopes.

**Mobile responsive**
The interface is fully usable at 375px viewport width with no horizontal scrolling.

**Rate limiting**
The backend enforces 20 requests per IP per 60 seconds to prevent runaway usage.

---

## Tech Stack

| Technology | Version | Role |
|---|---|---|
| Gemini 2.5 Flash | Latest | Large language model via Vertex AI |
| Google ADK | 1.10.0 | Agent framework: LlmAgent, Runner, InMemorySessionService |
| FastAPI | 0.136.3 | Backend API server |
| Google Cloud Run | n/a | Serverless container hosting |
| Dynatrace REST API | Grail v1 | Log, metric, and event queries via DQL |
| httpx | 0.28.1 | Async HTTP client for Dynatrace API calls |
| Chart.js | 4.4.2 | Frontend chart rendering (line + bar) |
| python-dotenv | 1.2.2 | Local environment variable loading |

---

## Project Structure

```
Plain-English-Observability-Agent/
|
+-- backend/
|   +-- main.py              FastAPI app with /ask, /health, rate limiter, CORS, security headers
|   +-- agent.py             LlmAgent definition, run_dql() and get_problems() tools
|   +-- system_prompt.txt    5-step reasoning loop, question type patterns, 8 hard rules
|   +-- answer_parser.py     Parses raw agent text into typed JSON (headline, paragraph, chart, followups)
|   +-- eval.py              10-question automated scoring runner (target: 16/20)
|   +-- eval_questions.json  Fixed test question set with expected behaviours
|   +-- requirements.txt     Pinned Python dependencies
|   +-- Dockerfile           python:3.11-slim base, non-root appuser, port 8080
|
+-- frontend/
|   +-- index.html           Two-screen SPA with CSP meta tag and all 11 element IDs
|   +-- app.js               State machine (IDLE, LOADING, ANSWERED), chip handlers, chart rendering
|   +-- style.css            Design system, spinner animation, mobile breakpoint at 640px
|
+-- docs/
|   +-- architecture_overview.png   Simple 5-box overview diagram
|   +-- architecture.png            Detailed component diagram with data flows
|
+-- .env.example             Template for local environment variables
+-- LICENSE                  MIT
```

---

## Local Setup

**Prerequisites**
- Python 3.11 or higher
- A Google Cloud project with Vertex AI API enabled
- A Dynatrace tenant with a Platform Token (Bearer JWT format)

**Step 1: Clone the repository**

```bash
git clone <your-repo-url>
cd Plain-English-Observability-Agent
```

**Step 2: Create and activate a virtual environment**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**Step 3: Install dependencies**

```bash
pip install -r backend/requirements.txt
```

**Step 4: Configure environment variables**

```bash
cp .env.example .env
```

Open `.env` and fill in the three values:

```
DT_TENANT_URL=https://your-tenant.apps.dynatrace.com
DT_PLATFORM_TOKEN=dt0...
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```

**Step 5: Start the server**

```bash
cd backend
uvicorn main:app --reload --port 8080
```

Open `http://localhost:8080` in your browser.

### Dynatrace Platform Token Scopes

Create a Platform Token in your Dynatrace account (Account Management > My Platform Tokens) with these four scopes:

- `storage:logs:read`
- `storage:metrics:read`
- `storage:events:read`
- `storage:entities:read`

The token format starts with `dt0`.

---

## API Reference

### POST /ask

Accepts a plain-English question and returns a structured answer.

**Request body:**
```json
{
  "question": "Were there any errors in the last hour?",
  "prev_question": "optional — the previous question for follow-up context"
}
```

**Response:**
```json
{
  "headline": "Yes. 28 errors were recorded in the last hour.",
  "paragraph": "Most errors relate to application restarts and SSL handshake failures. These typically resolve on their own.",
  "chart_data": {
    "type": "line",
    "labels": ["6:00 PM", "6:05 PM", "6:10 PM"],
    "values": [4, 11, 3],
    "unit": "errors"
  },
  "uncertainty": false,
  "needs_clarification": false,
  "followup_questions": [
    "When did most of these errors happen?",
    "How does this compare to yesterday?"
  ]
}
```

**Custom credentials (optional headers):**

To use a specific Dynatrace account instead of the demo environment, pass these headers:
```
X-DT-Tenant-URL: https://your-tenant.apps.dynatrace.com
X-DT-Token: dt0...
```

### GET /health

Returns `{"ok": true}` when the service is running.

---

## Security Notes

- The `DT_PLATFORM_TOKEN` is stored in GCP Secret Manager and injected at runtime using `--set-secrets`. It is never set as a plain environment variable in Cloud Run.
- The API token only has read-only scopes. The agent cannot write, delete, or modify any data in Dynatrace.
- User-supplied credentials are stored in `sessionStorage` and cleared on tab close.
- All responses use `textContent` assignment in JavaScript. `innerHTML` is never used.
- Content Security Policy is enforced via a meta tag in `index.html`.

---

## License

MIT. See [LICENSE](LICENSE) for details.

---

*Built for the Google Cloud x Dynatrace AI Challenge.*
