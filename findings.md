# Findings: Restore Dev Crawls And Runbook

## Requirements Captured
- Required: Bring local and staging-backed dev environments back up, ensure historical crawls are visible in the right UI, and document the reliable startup procedure.
- Nice to have: Add stable helper scripts/commands to reduce manual env mistakes.
- Out of scope: Production rollout changes or crawl engine architecture changes.

## Research / Discoveries
- The local frontend at `localhost:3002` was intentionally pointed at `http://localhost:8000`.
- The local database currently contains exactly one crawl row for the `FOX One` tenant.
- Historical crawl history is therefore not missing because of table rendering; it is absent from the local DB.
- A separate staging-backed frontend is required to show the broader historical crawl dataset.
- Prior failures were caused by fragile ad hoc startup commands, host mismatches (`127.0.0.1` vs `localhost` with Clerk), and transient dev server processes.

## Technical Decisions
| Decision | Rationale | Impact |
|----------|-----------|--------|
| Use separate ports for local and staging-backed UIs | Avoid env collisions and make data source obvious | More reliable development workflow |
| Add documented startup commands/scripts | Prevent downtime from one-off terminal commands | Easier recovery and onboarding |

## Risks / Unknowns
- The staging-backed frontend failure needs a concrete root cause from its server log or reproducible startup path.
- Clerk/localhost behavior may still require strict hostname consistency.

## Resources
- `docs/architecture/cloud-crawl-architecture.md`
- `web/.env.local`
- `.env`
- `api/crawler/worker.py`

## Visual / Browser Findings
- `localhost:3002/crawls` previously rendered one completed `fox.com` crawl from the local DB.
- `localhost:3003/crawls` initially loaded, then showed `Could not load crawls` before the dev server disappeared.

## Open Questions
- What exact startup command set keeps the staging-backed frontend stable?
- Should helper scripts live in a new `scripts/` directory or only as npm scripts?
