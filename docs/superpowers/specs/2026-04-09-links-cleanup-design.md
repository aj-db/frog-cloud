# Links Cleanup Design

## Goal
Remove dead frontend links code so the app surface matches the current product, without deleting the backend links data path that may be useful later.

## Context
- The backend still exposes `GET /api/crawls/{job_id}/links` and stores real crawl link rows.
- The frontend does not render a links view and never calls `getCrawlLinks()`.
- The frontend helper is also drifted from the backend contract: it sends `cursor` while the backend endpoint accepts `offset`.
- This creates maintenance noise without providing any user-facing value.

## Options Considered

### Option 1: Frontend-only cleanup
Remove unused frontend links types, OpenAPI path metadata, and API helper, while leaving the backend endpoint untouched.

Pros:
- Smallest safe change
- No user-facing behavior change
- Removes current drift and dead code
- Keeps backend data path available for future work

Cons:
- Backend links endpoint remains unused for now

### Option 2: Full-stack removal
Delete the frontend dead code and also remove the backend `/links` endpoint and related response schema.

Pros:
- Fully removes unused code
- Reduces backend surface area

Cons:
- Harder to restore later if links analysis becomes a feature
- Higher regression risk than needed for this cleanup

### Option 3: Keep but fix
Keep the unused frontend helper but change it to match backend `offset` pagination.

Pros:
- Minimal behavior change

Cons:
- Preserves dead code
- Still leaves an unused client surface that suggests a feature that does not exist

## Decision
Use Option 1.

This keeps the product surface honest and removes the current API/client mismatch without deleting backend capabilities that may be reused later.

## Design

### Files to change
- `web/lib/api-types.ts`
- `web/lib/api-client.ts`

### Planned changes
- Remove `CrawlLinkRow` and `PaginatedLinks` from frontend API types.
- Remove the `/api/crawls/{job_id}/links` entry from the frontend `paths` map.
- Remove `getCrawlLinks()` from `createCrawlApi()`.
- Leave backend endpoint and schemas unchanged.

### User-facing impact
- No visible UI changes
- No behavior changes for crawl detail or crawl list pages
- Reduced maintenance and less misleading API surface in the frontend code

### Error handling
- No new runtime paths are introduced.
- TypeScript and linting should catch any stale references during cleanup.

## Verification
- Run `npm run lint` in `web/`
- Search for remaining `getCrawlLinks`, `CrawlLinkRow`, and `PaginatedLinks` references

## Out of Scope
- Building a links table or graph view
- Removing the backend `/links` endpoint
- Changing crawl deletion behavior or copy that references stored links
