# Progress Log: Restore Dev Crawls And Runbook

## Session: 2026-04-07

### Current Snapshot
- **Phase:** Phase 5 — Delivery & Handoff
- **Started:** 2026-04-07T21:17:00-04:00
- **Last Updated:** 2026-04-08T10:00:00-04:00
- **Status:** complete

### Actions Taken
- Confirmed all local dev ports were down at session start.
- Confirmed earlier local UI behavior was showing only one crawl because the local DB only contains one crawl row.
- Started persistent planning files to capture recovery work and avoid repeating transient debugging.
- Added stable dev commands for local and staging-backed frontends in `web/package.json`.
- Verified `web/next.config.ts` supports isolated `NEXT_DIST_DIR`, `NEXT_TS_CONFIG_PATH`, and fixed `turbopack.root`.
- Updated `Makefile` with stable `dev-local`, `dev-side-by-side`, `dev-stop`, and `dev-reset` workflow targets.
- Fixed `make dev-status` so it correctly detects `localhost`-bound Next.js servers.
- Verified `localhost:3001/crawls` loads local crawl history.
- Verified `localhost:3002/crawls` loads historical staging crawl history.
- Verified `http://127.0.0.1:8000/health` returns `{"status":"ok"}`.
- Added a root `README.md` that points directly to `docs/development/dev-startup.md`.
- Inventoried which crawl metrics are persisted in the backend versus currently shown in the frontend UI.

### Files Created / Modified
- `task_plan.md`
- `findings.md`
- `progress.md`
- `web/package.json`
- `web/next.config.ts`
- `Makefile`
- `docs/development/dev-startup.md`
- `README.md`

### Tests / Checks
| Check | Command / Method | Result | Status |
|-------|------------------|--------|--------|
| Port scan | Python socket check for `3001/3002/3003/8000` | All closed at session start | complete |
| Service status | `make dev-status` | API/local/staging all up | complete |
| API health | `curl http://127.0.0.1:8000/health` | `{"status":"ok"}` | complete |
| Browser verification | `localhost:3001/crawls` snapshot | Local crawl history visible | complete |
| Browser verification | `localhost:3002/crawls` snapshot | Historical staging crawls visible | complete |

### Errors / Blockers
| Timestamp | Error / Blocker | Attempt | Resolution / Next Step |
|-----------|------------------|---------|------------------------|
| 2026-04-07T21:17:00-04:00 | Staging-backed UI previously died after first render | Ad hoc `next dev` with staging API env | Root cause: wrong origin/port path during ad hoc startup; standardized on `localhost:3002` |
| 2026-04-07T21:46:00-04:00 | `make dev-status` falsely reported down web servers | First implementation probed `127.0.0.1` only | Fixed to probe `localhost` via `socket.create_connection()` |

### Next Up
- Share the crawl metric inventory and recommend the next aggregation/UI additions

### Handoff Notes
- Local and staging data sources must remain clearly separated in docs and commands.
- Use `3001` for local data and `3002` for staging history. Do not improvise staging port changes without updating backend CORS.

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 2 — Planning & Structure |
| Where am I going? | Restore both frontend modes, then document them |
| What's the goal? | Restore dev crawl visibility and prevent downtime with a runbook |
| What have I learned? | See findings.md |
| What have I done? | See Actions Taken above |
