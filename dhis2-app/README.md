# Ask Analytics (DHIS2 app)

Ask questions about aggregate DHIS2 data in plain language and get answers with charts,
maps, tables, reports and data exports, inside DHIS2.

**Status:** working build / demo deployment, tested against the public DHIS2 demo
database. Not in production use by any organisation.

This folder is the DHIS2 web app (App Platform, React, `@dhis2/ui`, `@dhis2/app-runtime`).
It needs the self-hosted backend in this repository, reached **only through a DHIS2
Route**. Full setup (backend Docker, env vars, Route Manager, install, external
services): **[../docs/APPHUB.md](../docs/APPHUB.md)**.

## How it works

- Runs inside DHIS2 with the standard header bar and the user's existing session
  (no separate login).
- Every backend call goes to `/api/routes/<routeCode>/run/...` on the user's own DHIS2
  server. DHIS2 adds the shared key (stored encrypted in the Route) and the username,
  then forwards to the backend.
- The Route code (default `ask-analytics`) is read from UserDataStore
  `ask-analytics/settings`, then DataStore `ask-analytics/settings` (reserved namespace,
  declared in `d2.config.js`). No URLs, keys or credentials are stored in the app or the
  DataStore.
- Custom authority `ASK_ANALYTICS_RUN_ROUTE`: add it to the Route's `authorities` and to
  the user roles that should use the assistant.

## Requirements

- DHIS2 2.40+ (Routes). 2.40.10+ / 2.41.6+ recommended for a 60 s Route timeout.
- The backend running somewhere your DHIS2 server can reach (see docs).
- An AI model: a hosted API (data leaves your network) or a self-hosted
  OpenAI-compatible model such as Ollama (it does not).

## Develop

```bash
npm install
npm start                 # d2-app-scripts start; log in to a DHIS2 server (e.g. --proxy)
npm test                  # unit tests (route URLs, SSE parsing)
npm run build             # -> build/bundle/ask-analytics-<version>.zip
```

The icon source is `assets/icon.svg` (512×512 PNG in `assets/icon-512.png`; menu icons in
`public/`). It is original artwork and does not use the DHIS2 logo.

## Licence

BSD-3-Clause, see [../LICENSE](../LICENSE).
