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
- The standardized split now in use is:
  - `localhost:3001` = local frontend
  - `localhost:3002` = staging-backed frontend
  - `localhost:8000` = local API
- The failed `3003` attempt was caused by staging API CORS not allowing that origin.
- Next.js dev servers bound on `localhost` can look down if probed only via `127.0.0.1`.
- Current crawl metric inventory:
  - job-level persisted metrics: status, progress percent, started/completed timestamps, last heartbeat, URLs crawled, error state
  - page-level persisted metrics: status code, title, meta description, H1, word count, indexability, crawl depth, response time, canonical data, content type, redirect URL, size bytes, inlinks/outlinks, robots fields, pagination status, HTTP version, link score, plus extra metadata
  - issue-level persisted metrics: issue type, severity, details, page linkage
  - link-level persisted metrics: source URL, target URL, link type, anchor text, status code
- The frontend currently exposes only a subset of page metrics directly in the main pages table: status code, title, word count, response time, indexability, and crawl depth.
- The frontend type also reserves `issues_count` and `avg_response_time_ms`, but the backend does not currently populate those aggregates on `CrawlJob`.

## Technical Decisions
| Decision | Rationale | Impact |
|----------|-----------|--------|
| Use separate ports for local and staging-backed UIs | Avoid env collisions and make data source obvious | More reliable development workflow |
| Add documented startup commands/scripts | Prevent downtime from one-off terminal commands | Easier recovery and onboarding |
| Keep staging-backed UI on `3002` | Matches staging API CORS and previous verified flow | Removes need for backend config changes during local dev |

## Risks / Unknowns
- Clerk/localhost behavior may still require strict hostname consistency.
- If staging API CORS changes in the future, the runbook must stay in sync with the allowed localhost ports.

## Resources
- `docs/architecture/cloud-crawl-architecture.md`
- `web/.env.local`
- `.env`
- `api/crawler/worker.py`

## Visual / Browser Findings
- `localhost:3001/crawls` now shows local crawl history, including local `example.com` jobs and one `fox.com` row.
- `localhost:3002/crawls` now shows the historical staging `fox.com` crawl list with many completed rows.

## Open Questions
- What exact startup command set keeps the staging-backed frontend stable?
- Should helper scripts live in a new `scripts/` directory or only as npm scripts?
