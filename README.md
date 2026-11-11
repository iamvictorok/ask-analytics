# Ask Analytics

Ask questions about your DHIS2 aggregate data in plain language and get an answer with
charts, a district map, a data table, a short report or a data export, inside DHIS2.

> "Compare ANC 1 coverage across districts for last year"
> → a bar chart, a map, the table behind it, and one line saying exactly which indicator,
> organisation units and period were used.

**Status:** working build / demo deployment, tested against the public DHIS2 demo
database through a real DHIS2 Route. It is not in production use by any organisation.
AI answers can be wrong: check figures against your own DHIS2 data before relying on them.

Licence: BSD-3-Clause ([LICENSE](LICENSE)).

## What is in this repository

| Folder | What it is |
|---|---|
| `dhis2-app/` | The DHIS2 web app (App Platform, React, `@dhis2/ui`). Runs inside DHIS2 with the header bar and the user's existing session. This is what goes on App Hub. |
| `backend/` | The self-hosted backend (Python, FastAPI). Finds the matching indicators and org units in your metadata, reads figures from the DHIS2 Analytics API, calls the AI model, and renders charts, maps, reports and exports. |
| `docs/APPHUB.md` | Full setup guide: backend, environment variables, Route Manager, install, external services, security notes, known gaps. |

## Architecture

The app never talks to the backend directly. Every call goes through a **DHIS2 Route**
on the user's own DHIS2 server:

```
Browser (DHIS2 session cookie)
   │  POST <DHIS2>/api/routes/ask-analytics/run/api/chat
   ▼
DHIS2 server ── checks the user may run the Route (ASK_ANALYTICS_RUN_ROUTE)
   │            adds X-Route-Key (stored encrypted in the Route) + X-Forwarded-User
   ▼
Backend (DEPLOYMENT_MODE=route) ── checks the key ── reads DHIS2 with its own token ── calls the AI model
```

- No backend URL, API key or credential is in the app bundle, the DataStore or the browser.
  The only setting the app stores is the Route code (not secret).
- The backend accepts a request only when the Route key matches. Conversations are kept
  per DHIS2 username.
- DHIS2 Routes buffer the response, so the answer appears when it is complete. Each answer
  must finish inside the Route timeout (max 60 s); the backend keeps its own time budget
  below that.

## Self-host quickstart

You need: a DHIS2 2.40+ server (2.40.10+ / 2.41.6+ recommended), Docker, and an AI model
(a hosted API key, or a self-hosted OpenAI-compatible model such as Ollama).

1. **Read-only DHIS2 account.** Create a DHIS2 user for the assistant with data read and
   analytics access, then create a personal access token for it (`DHIS2_PAT`).
2. **Configure.** `cp .env.example .env`, then set at least:

   ```env
   DEPLOYMENT_MODE=route
   ROUTE_SHARED_KEY=<openssl rand -hex 32>
   DHIS2_BASE_URL=https://dhis2.example.org
   DHIS2_PAT=<token>
   LLM_PROVIDER=gemini                  # or ollama / openai (any OpenAI-compatible server)
   LLM_MODEL=gemini/gemini-flash-latest
   LLM_API_KEY=<key>                    # not needed for a self-hosted model
   ```

3. **Run the backend.**

   ```bash
   docker build -t ask-analytics-backend .
   docker run -d --name ask-analytics --env-file .env -p 8000:8000 \
     -v ask-analytics-data:/app/data ask-analytics-backend
   curl http://localhost:8000/health    # {"status":"ok","deployment_mode":"route",...}
   ```

   Put it behind HTTPS at a URL your DHIS2 server can reach. Users' browsers never call it.
   (`render.yaml` is an optional one-service Render Blueprint for the same thing.)

4. **Create the Route** in Route Manager (or `POST /api/routes`):

   | Field | Value |
   |---|---|
   | Code | `ask-analytics` |
   | URL | `https://assistant.example.org/**` |
   | Authentication | API headers: `X-Route-Key` = your `ROUTE_SHARED_KEY` |
   | Response timeout | `60` seconds |
   | Authorities | `ASK_ANALYTICS_RUN_ROUTE` |

   If your server restricts outbound Routes, allow the host in `dhis.conf`:
   `route.remote_servers_allowed = https://assistant.example.org/`

5. **Install the app.** App Management → install from App Hub, or upload the zip built with
   `cd dhis2-app && npm install && npm run build` (→ `build/bundle/ask-analytics-<version>.zip`).
   Add the app and the `ASK_ANALYTICS_RUN_ROUTE` authority to the user roles that should use it.
   *Settings → Test connection* in the app checks the Route.

Details, every environment variable and troubleshooting: [docs/APPHUB.md](docs/APPHUB.md).

## Outside services (declared)

| Connection | When | What is sent |
|---|---|---|
| Your backend, via the DHIS2 Route | Always | The question, recent conversation history, the DHIS2 username. |
| DHIS2 Web API (from the backend) | Always | Analytics and metadata reads with the backend's own token. |
| The AI model provider you configure | Always | The question, short history and the aggregated figures needed for the answer. With a hosted model (e.g. Google Gemini, OpenAI) this leaves your network; with a self-hosted model it does not. |
| Tavily web search | Only if `TAVILY_API_KEY` is set on the backend | Search terms derived from the question. The DHIS2 app asks for answers without web search. |

The app itself loads no external scripts, fonts or map tiles; the browser only talks to
your DHIS2 server.

**Data scope:** all DHIS2 reads use the backend's token, so every user with the Route
authority can ask about whatever that account can see. Give it only the org units and data
you are happy to share with those users.

## Development

```bash
# backend
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
pytest backend/tests
uvicorn backend.main:app --reload --port 8000

# DHIS2 app
cd dhis2-app
npm install
npm test
npm start          # d2-app-scripts start, against a DHIS2 server
npm run build
```

`LLM_PROVIDER=mock` runs the backend without any AI model (canned text), which is handy for
UI work and tests.
