# Changelog

## 0.1.0 (unreleased)

First App Hub candidate.

- Chat inside DHIS2 with the header bar and the user's session; no separate login.
- Backend reached only through a DHIS2 Route (`/api/routes/<code>/run/...`); Route code
  configurable (UserDataStore, then DataStore `ask-analytics`, default `ask-analytics`).
- Answers with charts, district maps (no third-party tiles), data tables (XLSX/CSV),
  reports (DOCX/PDF) and slides (PPTX); "Data used" line and sources.
- Conversation history per DHIS2 user; settings dialog with a Route connection test.
