# Task Plan: Restore Dev Crawls And Runbook

## Goal
Restore the local and staging-backed development flows so crawl history and monitoring are available again, then document reliable startup steps that prevent avoidable downtime.

## Success Criteria
- [ ] Local API and local frontend are running and verified
- [ ] A staging-backed frontend is running and verified
- [ ] Historical crawls are visible in the correct frontend
- [ ] Startup/runbook documentation exists and is accurate
- [ ] Result is verified with fresh checks before handoff

## Constraints
- Scope constraints: Fix developer startup/runtime issues without changing production infrastructure.
- Technical constraints: Preserve the separate local and staging-backed frontend modes.
- Non-goals: Re-architect auth, backend tenancy, or crawl execution.

## Current Phase
Phase 1 — Requirements & Discovery

## Phases

### Phase 1: Requirements & Discovery
- [x] Capture user intent
- [x] Identify constraints and assumptions
- [x] Record requirements in findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [ ] Choose an approach
- [ ] Identify files/systems to inspect or change
- [ ] Record key decisions and tradeoffs
- **Status:** in_progress

### Phase 3: Implementation / Research
- [ ] Restore local API/frontend
- [ ] Restore staging-backed frontend
- [ ] Add stable startup commands and documentation
- **Status:** pending

### Phase 4: Verification
- [ ] Verify local API/frontend
- [ ] Verify staging-backed frontend and historical crawl visibility
- [ ] Verify documentation against actual commands
- **Status:** pending

### Phase 5: Delivery & Handoff
- [ ] Summarize root causes and fixes
- [ ] List follow-ups or open questions
- [ ] Deliver the result to the user
- **Status:** pending

## Key Questions
1. Which frontend should show historical staging crawls?
2. Why are the dev servers dropping or becoming unavailable?
3. What exact commands/env vars should be documented for reliable startup?

## Decisions Made
| Decision | Rationale | Impact |
|----------|-----------|--------|
| Keep separate local and staging-backed frontends | Local DB only has one crawl; staging has the broader history | Need side-by-side startup flow |

## Errors Encountered
| Error | Attempt | Resolution | Status |
|-------|---------|------------|--------|
| `3003` staging-backed UI showed `Could not load crawls` then died | Started ad hoc `next dev` with staging API env | Investigating server/runtime failure before retrying | open |

## Files / Areas to Touch
- Read: `web/package.json`, `web/next.config.ts`, `web/.env.local`, `.env`, relevant docs
- Modify: likely `web/package.json`, docs
- Create: runbook docs and helper scripts if needed

## Notes
- Re-read this file before major decisions.
- Update phase statuses as work advances.
- Never repeat the same failed action without changing the approach.
