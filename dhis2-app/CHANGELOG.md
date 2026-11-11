# Changelog

## 0.1.1

Tested end to end through a real DHIS2 Route (play.im.dhis2.org, 2.41.11).

- Backend: per-answer time budget in route mode (default 45 s), so answers finish inside
  the 60 s Route timeout even when the AI provider is slow; falls back to a figures-only
  answer instead of a 504.
- App: the waiting message says answers can take up to a minute (DHIS2 Routes deliver the
  answer in one piece, not streamed).

## 0.1.0

First App Hub candidate.

- Chat inside DHIS2 with the header bar and the user's session; no separate login.
- Backend reached only through a DHIS2 Route (`/api/routes/<code>/run/...`); Route code
  configurable (UserDataStore, then DataStore `ask-analytics`, default `ask-analytics`).
- Answers with charts, district maps (no third-party tiles), data tables (XLSX/CSV),
  reports (DOCX/PDF) and slides (PPTX); "Data used" line and sources.
- Conversation history per DHIS2 user; settings dialog with a Route connection test.
