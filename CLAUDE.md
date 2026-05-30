# CLAUDE.md — Plain-English Observability Agent

## What This Project Is

A hackathon agent that lets non-technical users ask plain-English questions about their website's health ("Was checkout slow today?") and get real, jargon-free answers backed by live Dynatrace monitoring data.

**Hackathon:** Google Cloud Rapid Agent Hackathon — Dynatrace track
**Submission deadline:** June 12, 2026 at 2:30 AM IST (non-negotiable)
**Tech stack:** Gemini 2.5 Flash (Vertex AI) · Google ADK · Dynatrace MCP Server · FastAPI · Cloud Run

---

## FIRST THING: Read the Implementation Plan

**Before doing any work in any session, read `docs/IP.md` in full.**

It contains:
- The current phase and the step you are on (check for `[x]` marks to find where work left off)
- The abbreviation legend for all cross-references
- The Operational Rules that apply to every line of code
- Commit message conventions

Do not write code, make plans, or suggest changes until you have read `docs/IP.md`.

---

## Documentation Map

| File | What it contains |
|---|---|
| `docs/IP.md` | **Implementation Plan** — ordered steps, cross-references, commit messages, phase gates. The source of truth for what to do next. |
| `docs/BP.md` | **Backend Plan** — exact code for `agent.py`, `main.py`, `answer_parser.py`, `eval.py`, Dockerfile, requirements.txt, Cloud Run deploy command |
| `docs/FP.md` | **Frontend Plan** — all 11 element IDs, state machine, full `index.html`/`app.js`/`style.css` code, API contract |
| `docs/SOD.md` | **Security & Operations** — security rules per phase and step, token rotation, secret scanning, HTTP headers, session isolation |
| `docs/TPD.md` | **Testing Plan** — `[AUTO]`/`[MANUAL]`/`[CLAUDE]`/`[EDGE]`/`[SECURITY]` tests for every step. A step is not done until all its tests pass. |
| `docs/PSD.md` | **Phase Strategy** — rationale for build order, prerequisites, key decisions per phase |
| `docs/PRD.md` | **Product Requirements** — feature list (F-01–F-20), user stories, edge cases, eval targets |
| `docs/TOOLS.md` | **Tools & Technologies** — exact versions, ADK patterns, Dynatrace MCP tool names |

---

## Non-Negotiable Rules

These apply to every session, every step, every line of code.

### Security
- `DT_PLATFORM_TOKEN` lives ONLY in `.env` (local) or Secret Manager (Cloud Run). Never in code, never in logs, never in commits.
- Run `grep -ri "dt0" .` before every `git push`. Must return empty.
- Use `--set-secrets` (not `--set-env-vars`) for the Dynatrace token in Cloud Run.
- Use `textContent` everywhere in `app.js` — never `innerHTML`. No `eval()`, no `new Function()`.
- Error responses must never expose stack traces, exception class names, DQL, or internal paths.

### Code Patterns
- `MCPToolset` MUST be used as `async with MCPToolset(...) as toolset:` — direct instantiation leaks the connection.
- `InMemorySessionService()` MUST be created inside the `async def ask()` handler, not at module level.
- Use `os.environ["KEY"]` (raises `KeyError` if missing), not `os.environ.get("KEY")` (returns `None` silently).
- `destroyChart()` must be called before every `renderChart()` call in `app.js`.
- `const API_URL = "/ask"` — relative URL only, no hardcoded domain.

### Process
- Complete and verify every step BEFORE moving to the next. No batching. No skipping.
- A step is done only when every test in `docs/TPD.md` for that step has passed.
- Mark steps done with `[x]` in `docs/IP.md` as you complete them.
- One system prompt change at a time — never change multiple things simultaneously.
- Never commit `eval.py` with `TARGET_URL` set to the Cloud Run URL.

### Commits
- Format: `<type>: <description>` — types: `add`, `fix`, `tune`, `deploy`, `freeze`, `eval`
- Under 72 characters. No AI attribution. No "co-authored by Claude" in any commit.

---

## Architecture (5 Boxes)

```
Browser → FastAPI (Cloud Run) → ADK Runner → Gemini (Vertex AI) → Dynatrace MCP → Dynatrace Playground
```

- Browser: `frontend/index.html` + `app.js` + `style.css`
- FastAPI: `backend/main.py` — `/health`, `/ask`, `/static/`
- ADK Runner: `backend/agent.py` — `LlmAgent` + `MCPToolset` context manager
- Gemini: `gemini-2.5-flash` via Vertex AI — verify exact model ID in console before use
- Dynatrace MCP: 4 tools — `generate_dql`, `explain_dql`, `run_dql`, `investigate_problems`

---

## Where Things Live

```
backend/
  main.py            FastAPI app, /ask endpoint, rate limiter, CORS, logging
  agent.py           LlmAgent + MCPToolset — async context manager pattern
  system_prompt.txt  5-step loop + 8 hard rules — the agent's brain
  answer_parser.py   Converts agent text output to {headline, paragraph, chart_data, ...}
  eval.py            10-question scoring runner — target ≥ 16/20 before submission
  eval_questions.json Fixed 10-question test set — never change after baseline
  requirements.txt   Pinned dependencies — freeze after first successful run
  Dockerfile         python:3.11-slim, non-root appuser, port 8080

frontend/
  index.html         All 11 element IDs, CSP meta tag, Chart.js @4.4.2 CDN
  app.js             State machine: IDLE → LOADING → ANSWERED, chip handlers, chart render
  style.css          Two-color palette, spinner, mobile @media (max-width: 500px)
```

---

## Current Phase

Check `docs/IP.md` for `[ ]` vs `[x]` to determine current position. The most recently completed step is the last `[x]`. The next `[ ]` is where work resumes.

**Eval targets to reach before submission:**
- After Day 7: Q1, Q2, Q3 each score 2 manually
- After Day 10: eval.py total ≥ 12/20
- After Day 11: eval.py total ≥ 16/20
- After Day 17: ≥ 16/20 against live Cloud Run URL
