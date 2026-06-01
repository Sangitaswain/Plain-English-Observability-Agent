# Signal AI — Plain-English Observability

Ask questions about your system in plain English. Get clear, jargon-free answers backed by live Dynatrace monitoring data — no query languages, no dashboards, no engineering background needed.

**Live demo:** https://observability-agent-601086227447.us-central1.run.app

---

## What it does

Instead of learning DQL, opening dashboards, or calling an engineer, a founder or business owner can just ask:

> *"Were there any errors last night?"*
> *"Tell me the summary of my system."*
> *"Compare today's errors to yesterday."*

Signal AI queries your Dynatrace tenant in real time, interprets the data, and responds in plain English — with a chart when the data warrants one, and suggested follow-up questions to keep the investigation going.

---

## Architecture

![Architecture overview](docs/architecture_overview.png)

<details>
<summary>Detailed architecture diagram (click to expand)</summary>

![Detailed architecture](docs/architecture.png)

</details>

| Layer | Component | Role |
|---|---|---|
| Frontend | `index.html` + `app.js` + `style.css` | Two-screen SPA: connect → ask |
| Backend | `FastAPI` on Cloud Run | `/ask` endpoint, rate limiting, security headers |
| Agent | `Google ADK` + `LlmAgent` | Drives the 5-step reasoning loop |
| AI | `Gemini 2.5 Flash` on Vertex AI | Interprets questions, decides which tools to call |
| Data | `Dynatrace REST API` (Grail DQL) | Returns real logs, errors, events |

**Request flow:**
1. User types a question → browser sends `POST /ask`
2. FastAPI validates and rate-limits the request
3. ADK Runner creates an isolated session and invokes `LlmAgent`
4. Gemini reads the system prompt, decides to call `run_dql()` or `get_problems()`
5. Tools hit the Dynatrace Grail REST API with a Bearer token
6. Results come back → `answer_parser.py` converts text output to structured JSON
7. Browser renders: headline, paragraph, optional chart, follow-up chips

---

## Features

- **Plain-English answers** — YES/NO headlines, context in plain sentences
- **Live Dynatrace data** — queries run in real time on every question
- **Smart follow-ups** — 2–3 suggested next questions after every answer, specific to what the data showed
- **Charts** — line charts for time-series trends, bar charts for comparisons
- **Two connection modes** — connect your own Dynatrace account, or use the built-in demo (Dynatrace Playground)
- **Secure by design** — credentials stored in `sessionStorage` only, never persisted or logged; read-only token scopes
- **Mobile responsive** — works at 375px with no horizontal scroll

---

## Tech stack

| Technology | Version | Purpose |
|---|---|---|
| Gemini 2.5 Flash | — | Large language model |
| Google ADK | 1.10.0 | Agent framework (LlmAgent + Runner) |
| FastAPI | 0.136.3 | Backend API server |
| Cloud Run | — | Serverless hosting |
| Dynatrace REST API | v1 Grail | Log and event queries |
| Chart.js | 4.4.2 | Frontend charts |
| httpx | 0.28.1 | Async HTTP client for Dynatrace |

---

## Local setup

**Prerequisites:** Python 3.11+, a GCP project with Vertex AI enabled, a Dynatrace tenant with a Platform Token.

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd Plain-English-Observability-Agent

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env — fill in DT_TENANT_URL, DT_PLATFORM_TOKEN, GOOGLE_CLOUD_PROJECT

# 5. Start the server
cd backend
uvicorn main:app --reload --port 8080
```

Open `http://localhost:8080` in your browser.

### Required Dynatrace token scopes

Create a Platform Token (Bearer JWT) with these scopes:
- `storage:logs:read`
- `storage:metrics:read`
- `storage:events:read`
- `storage:entities:read`

### Environment variables

| Variable | Description |
|---|---|
| `DT_TENANT_URL` | Your Dynatrace tenant, e.g. `https://abc12345.apps.dynatrace.com` |
| `DT_PLATFORM_TOKEN` | Platform Token starting with `dt0` |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID with Vertex AI enabled |

---

## How the agent thinks

Every question goes through a fixed 5-step loop baked into `system_prompt.txt`:

1. **Understand** — identify metric type (errors / activity / health / comparison / breakdown) and time window
2. **Write query** — choose the right DQL pattern for the question type
3. **Execute** — call `run_dql()` or `get_problems()` against the Dynatrace REST API
4. **Validate** — check that results look sensible; flag uncertainty if not
5. **Translate** — produce a HEADLINE (≤ 20 words, starts with YES/NO or a number), PARAGRAPH (plain English context), optional CHART JSON, and FOLLOWUP questions

The agent never shows raw DQL, field names, or query errors to the user.

---

## Project structure

```
backend/
  main.py              FastAPI app — /ask, /health, rate limiter, CORS
  agent.py             LlmAgent + run_dql / get_problems tools
  system_prompt.txt    5-step reasoning loop + 8 hard rules
  answer_parser.py     Converts raw agent text → structured JSON
  eval.py              10-question scoring runner
  eval_questions.json  Fixed test set (never modified after baseline)
  requirements.txt     Pinned dependencies
  Dockerfile           python:3.11-slim, non-root user, port 8080

frontend/
  index.html           Connect screen + app screen, CSP meta tag
  app.js               State machine, chip handlers, fetch, chart render
  style.css            Two-font palette, spinner, mobile @media 640px
```

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built for the Google Cloud × Dynatrace AI Challenge.*
