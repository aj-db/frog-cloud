# Web Frontend Deploy Runbook

This repository currently automates the API deploy path only.

- `.github/workflows/deploy.yml` deploys the FastAPI service
- the same workflow now runs `web` lint and tests
- there is still no committed host-specific build/deploy job for the Next.js frontend

Use this runbook for manual frontend releases until a hosting target and automated pipeline are chosen.

## Current State

The frontend is a Next.js App Router app in `web/`.

It expects:

- Clerk auth environment variables
- `NEXT_PUBLIC_API_URL` pointing at the target API

The repo already supports:

- local frontend on `http://localhost:3001`
- staging-backed frontend on `http://localhost:3002`
- production-style builds via `cd web && npm run build`

## Required Environment Variables

At minimum, set the following for the deployed frontend runtime:

```bash
NEXT_PUBLIC_API_URL=https://<target-api-host>
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<clerk-publishable-key>
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
CLERK_SECRET_KEY=<clerk-secret-key>
```

Reference values and local defaults live in `.env.example`.

## Manual Release Checklist

From `web/`:

```bash
npm ci
npm test
npm run lint
npx tsc --noEmit
NEXT_PUBLIC_API_URL=https://<target-api-host> npm run build
```

Then start the built app locally for a smoke test:

```bash
NEXT_PUBLIC_API_URL=https://<target-api-host> npm start
```

## Smoke Test

Before shipping a frontend build, verify:

1. Auth loads without Clerk configuration errors.
2. `/crawls` loads against the intended API environment.
3. Opening a crawl detail page still loads summary, pages, filters, retry, duplicate, delete, and CSV export.
4. The frontend points at the correct API host for the target environment.

## What Is Not Automated Yet

The repo does not currently define:

- a frontend hosting platform in code
- preview deployments for pull requests
- a production frontend deploy job in GitHub Actions
- environment promotion for web builds

If we want the next step after this runbook, the natural follow-up is to choose a hosting target and add a dedicated frontend deploy workflow around it.
