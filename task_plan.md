# Task Plan: Restore Dev Crawls And Runbook

## Goal
Restore the local and staging-backed development flows so crawl history and monitoring are available again, then document reliable startup steps that prevent avoidable downtime.

## Success Criteria
- [x] Local API and local frontend are running and verified
- [x] A staging-backed frontend is running and verified
- [x] Historical crawls are visible in the correct frontend
- [x] Startup/runbook documentation exists and is accurate
- [x] Result is verified with fresh checks before handoff

## Constraints
- Scope constraints: Fix developer startup/runtime issues without changing production infrastructure.
- Technical constraints: Preserve the separate local and staging-backed frontend modes.
- Non-goals: Re-architect auth, backend tenancy, or crawl execution.

## Current Phase
Phase 5 — Delivery & Handoff

## Phases

### Phase 1: Requirements & Discovery
- [x] Capture user intent
- [x] Identify constraints and assumptions
- [x] Record requirements in findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [x] Choose an approach
- [x] Identify files/systems to inspect or change
- [x] Record key decisions and tradeoffs
- **Status:** complete

### Phase 3: Implementation / Research
- [x] Restore local API/frontend
- [x] Restore staging-backed frontend
- [x] Add stable startup commands and documentation
- **Status:** complete

### Phase 4: Verification
- [x] Verify local API/frontend
- [x] Verify staging-backed frontend and historical crawl visibility
- [x] Verify documentation against actual commands
- **Status:** complete

### Phase 5: Delivery & Handoff
- [x] Summarize root causes and fixes
- [x] List follow-ups or open questions
- [x] Deliver the result to the user
- **Status:** complete

## Key Questions
1. Which frontend should show historical staging crawls?
2. Why are the dev servers dropping or becoming unavailable?
3. What exact commands/env vars should be documented for reliable startup?

## Decisions Made
| Decision | Rationale | Impact |
|----------|-----------|--------|
| Keep separate local and staging-backed frontends | Local DB only has one crawl; staging has the broader history | Need side-by-side startup flow |
| Standardize staging-backed dev UI on `localhost:3002` | Staging API CORS already allows `3002`; ad hoc `3003` caused load failures | Avoid repeated downtime from arbitrary ports |
| Add named `make` and npm startup commands | Ad hoc env-heavy commands were fragile and easy to forget | Repeatable local recovery path |

## Errors Encountered
| Error | Attempt | Resolution | Status |
|-------|---------|------------|--------|
| `3003` staging-backed UI showed `Could not load crawls` | Started ad hoc `next dev` with staging API env | Root cause was staging API CORS only allowing `localhost:3002`; standardized staging UI back to `3002` | resolved |
| `make dev-status` reported web services as down while pages were live | First version probed `127.0.0.1` even though Next bound to `localhost`/IPv6 | Switched status probe to `socket.create_connection(('localhost', port), ...)` | resolved |

## Files / Areas to Touch
- Read: `web/package.json`, `web/next.config.ts`, `web/.env.local`, `.env`, relevant docs
- Modify: likely `web/package.json`, docs
- Create: runbook docs and helper scripts if needed

## Notes
- Re-read this file before major decisions.
- Update phase statuses as work advances.
- Never repeat the same failed action without changing the approach.
