# Ask Analytics: DHIS2 app + self-hosted backend

**Status: working build / demo deployment.** It has been tested against the public DHIS2
demo database. It is not in production use by any organisation. Check every figure
against your own DHIS2 data before you rely on it.

Ask Analytics lets a DHIS2 user ask questions about aggregate data in plain language
("Compare ANC 1 coverage across districts for last year") and get an answer with
charts, a table, a map, a short report or a data export. It has two parts:

| Part | Where it runs | What it does |
|---|---|---|
| `dhis2-app/` (the App Hub app) | Inside DHIS2, in the user's browser | Chat UI with the DHIS2 header bar. Uses the user's existing DHIS2 session. Calls the backend **only** through a DHIS2 Route. |
| `backend/` (FastAPI) | Your server (Docker) | Understands the question, reads DHIS2 analytics/metadata with a server-side token, calls the AI model, renders charts/reports. |

```
Browser (DHIS2 session cookie)
   │  POST /api/routes/ask-analytics/run/api/chat
   ▼
DHIS2 server ── adds X-Route-Key (stored encrypted in the Route) + X-Forwarded-User
   │
   ▼
Backend (DEPLOYMENT_MODE=route) ── checks the key ── reads DHIS2 with DHIS2_PAT ── calls the AI model
```

No backend URL, API key or credential is in the app bundle, the DataStore or the
browser. The only setting the app stores is the Route **code** (not secret).

---

## 1. DHIS2 version support

- **DHIS2 2.40 or later** (Routes API). Recommended: **2.40.10+, 2.41.6+, 2.42+**, where a
  Route's response timeout can be raised to 60 seconds. Earlier patch releases have a fixed
  10 s (or 30 s) timeout, which long answers (reports) can exceed.
- Tested: the app UI against the 2.41.11 play database (with the Route behaviour emulated
  locally, see "Known gaps"); unit tests for the backend's route auth.

## 2. Run the backend (Docker)

The backend needs: a DHIS2 account it can read with, an AI model, and a shared Route key.

1. Create a **read-only DHIS2 user** for the assistant (data read + analytics; the org units
   it can see are the org units the assistant can answer about). Log in as that user →
   *Profile → Personal access tokens* → create a token. That is `DHIS2_PAT`.
2. Generate the shared key: `openssl rand -hex 32` → `ROUTE_SHARED_KEY`.
3. Create a `.env` (never commit it) from `.env.example`:

```env
DEPLOYMENT_MODE=route
ROUTE_SHARED_KEY=<64 hex chars from step 2>
DHIS2_BASE_URL=https://dhis2.example.org        # your DHIS2, reachable from the backend
DHIS2_PAT=<token from step 1>
DHIS2_SNAPSHOT_MODE=off

# AI model: pick ONE
# a) Hosted model (data leaves your network, see section 6)
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-flash-latest
LLM_API_KEY=<your key>
# b) Self-hosted, nothing leaves your network
# LLM_PROVIDER=ollama
# LLM_MODEL=llama3.1
# LLM_BASE_URL=http://ollama:11434
# c) Any OpenAI-compatible server (vLLM, LM Studio, ...)
# LLM_PROVIDER=openai
# LLM_MODEL=openai/<model-id>
# LLM_BASE_URL=http://vllm:8000/v1
# LLM_API_KEY=any

LLM_TIMEOUT_SECONDS=50
DATABASE_URL=sqlite+aiosqlite:////app/data/assistant.db
```

4. Build and run:

```bash
docker build -t ask-analytics-backend .
docker run -d --name ask-analytics --env-file .env -p 8000:8000 \
  -v ask-analytics-data:/app/data ask-analytics-backend
curl http://localhost:8000/health        # {"status":"ok","deployment_mode":"route",...}
```

Or with Postgres/Redis: `docker compose up -d` (uses the same `.env`).

5. Put it behind HTTPS (nginx/Caddy/Traefik) at a URL **your DHIS2 server** can reach,
   e.g. `https://assistant.example.org`. It does not need to be reachable from users'
   browsers; only DHIS2 calls it. Restricting it to your DHIS2 server's IP is a good idea.

### Environment variables (route mode)

| Variable | Required | Meaning |
|---|---|---|
| `DEPLOYMENT_MODE` | yes | `route` (accept only Route calls). `combined` also keeps the standalone login. |
| `ROUTE_SHARED_KEY` | yes | ≥ 32 chars. Same value as the Route's `api-headers` auth. The backend refuses to start without it. |
| `ROUTE_KEY_HEADER` | no | Header name for the key. Default `X-Route-Key`. |
| `ROUTE_USER_HEADER` | no | Header DHIS2 adds with the username. Default `X-Forwarded-User`. |
| `DHIS2_BASE_URL` | yes | Your DHIS2 server. No default instance. |
| `DHIS2_PAT` | yes* | Personal access token of the read-only account. (*or `DHIS2_SERVICE_ACCOUNT_USER`/`_PASS`.) |
| `LLM_PROVIDER`, `LLM_MODEL` | yes | Model to use (LiteLLM model string). `mock` runs without a model (canned text). |
| `LLM_API_KEY` | hosted models | API key for a hosted model. |
| `LLM_BASE_URL` | self-hosted | Ollama / OpenAI-compatible endpoint. |
| `LLM_TIMEOUT_SECONDS` | no | Per model call. One answer makes 2–3 calls, so a fast model matters more than this value: the whole answer must finish inside the Route timeout (max 60 s). |
| `TAVILY_API_KEY` | no | Optional web search for context. Leave empty to keep everything inside DHIS2 + your model. |
| `DATABASE_URL` | no | Conversation history store. SQLite by default; Postgres supported. |
| `DHIS2_SNAPSHOT_MODE` | no | Keep `off` (default). The bundled snapshot is public demo data. |
| `DEMO_QUESTIONS_PATH` | no | JSON file with the suggested-question chips. |
| `RATE_LIMIT_RPM` | no | Requests per minute per DHIS2 user (default 60). |
| `DISABLE_AIOHTTP_TRANSPORT` | behind a proxy | Set `True` if the backend reaches the internet through an HTTP proxy. |

## 3. Create the Route (Route Manager)

Install **Route Manager** from App Hub, then *Create route*:

| Field | Value |
|---|---|
| Name | `Ask Analytics backend` |
| Code | `ask-analytics` (the app's default; any code works if you set it in the app) |
| URL | `https://assistant.example.org/**` (must end with `/**`: wildcard route) |
| Authentication | **API headers**: header `X-Route-Key`, value = your `ROUTE_SHARED_KEY` |
| Response timeout | `60` seconds (2.40.10+/2.41.6+) |
| Authorities | `ASK_ANALYTICS_RUN_ROUTE` (declared by the app; add it to the user roles that should use the assistant) |

Equivalent API call (as a superuser):

```bash
curl -u admin -X POST https://dhis2.example.org/api/routes -H 'Content-Type: application/json' -d '{
  "name": "Ask Analytics backend",
  "code": "ask-analytics",
  "url": "https://assistant.example.org/**",
  "auth": { "type": "api-headers", "headers": { "X-Route-Key": "<ROUTE_SHARED_KEY>" } },
  "authorities": ["ASK_ANALYTICS_RUN_ROUTE"],
  "responseTimeoutSeconds": 60
}'
```

DHIS2 stores the header value encrypted; it is never returned by the API or sent to browsers.
Also allow the backend host in `dhis.conf`:

```
route.remote_servers_allowed = https://assistant.example.org/
```

Test: `GET https://dhis2.example.org/api/routes/ask-analytics/run/health` while logged in
→ `{"status":"ok","deployment_mode":"route",...}`. In the app, *Settings → Test connection*
does the same.

## 4. Install the app

- From App Hub (once listed): *App Management → App Hub → Ask Analytics → Install*.
- Or upload the zip: *App Management → Manual install →* `ask-analytics-<version>.zip`
  (built with `cd dhis2-app && npm install && npm run build` → `build/bundle/`).

Then give users access: add the app (`Ask Analytics`) **and** `ASK_ANALYTICS_RUN_ROUTE`
to their user role. If you used a Route code other than `ask-analytics`, open the app →
*Settings* → enter the code → *Save for everyone* (superusers) or *Save for me*.

The app reserves the DataStore namespace `ask-analytics` (declared in its manifest), which
holds only `{ "routeCode": "..." }`. To stop non-admins from changing the instance default,
restrict write sharing on `ask-analytics/settings` in the Datastore Management app.

## 5. What users see

The DHIS2 header bar, a conversation list, and a chat box. Each answer can include charts,
a map (boundaries from your DHIS2, no third-party map tiles), a data table with XLSX/CSV
download, a report with DOCX/PDF download, slides (PPTX), and the sources used
("Data used: indicator, org unit, period"). Conversations are stored per DHIS2 username on
the backend.

## 6. External services (declare these)

| Connection | When | What is sent |
|---|---|---|
| Your backend (via the DHIS2 Route) | Always | The question, conversation history, DHIS2 username. |
| DHIS2 Web API (from the backend) | Always | Analytics/metadata reads with `DHIS2_PAT`. |
| AI model provider | Always | The question, short history, and the aggregated figures needed to answer. **Hosted model** (e.g. Google Gemini, OpenAI): this leaves your network. **Self-hosted** (Ollama/vLLM): it does not. |
| Tavily web search | Only if `TAVILY_API_KEY` is set | Search terms derived from the question. The DHIS2 app requests answers without web search. |

The browser only talks to your DHIS2 server. The app loads no external scripts, fonts or
map tiles.

## 7. Security notes

- The backend trusts a request only when the Route key matches (constant-time compare).
  `X-Forwarded-User` is used for history and rate limiting, never on its own.
- In route mode the standalone `/auth/login` is disabled.
- **Data scope:** all DHIS2 reads use the backend's token, so every app user can ask about
  whatever that account can see. Give the assistant's DHIS2 account only the org units and
  data you are comfortable sharing with everyone who has the Route authority. Per-user
  data scoping is not implemented (see Known gaps).
- Answers are produced by an AI model and can be wrong. The "Data used" line names the exact
  indicator, org unit and period so users can check them.

## 8. Known gaps

- Not yet tested end to end against a real DHIS2 Route proxy. Streaming may be buffered by
  DHIS2 (the app then shows the full answer when it finishes), and answers longer than the
  Route timeout (max 60 s) fail with a 504. Screenshots were taken with the Route contract
  emulated locally (same headers) against the public 2.41.11 demo database.
- Per-user DHIS2 permissions are not applied (single server-side token).
- The in-app report is read-only (the standalone UI has an editor).
- UI strings are English only (no i18n yet).
- The Plotly chart library is ~1.5 MB gzipped; it loads only when the first chart appears.
