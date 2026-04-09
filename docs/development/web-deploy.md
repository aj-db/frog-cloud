# Web Frontend Deploy Runbook

This repository currently automates the API deploy path only.

- `.github/workflows/deploy.yml` deploys the FastAPI service
- the same workflow runs `web` lint and tests
- there is still no committed CI deploy job for the Next.js frontend

The currently documented manual hosting target for the frontend is Replit.

## Current State

The frontend is a Next.js App Router app in `web/`.

It expects:

- Clerk auth environment variables
- `NEXT_PUBLIC_API_URL` pointing at the target API

The repo already supports:

- local frontend on `http://localhost:3001`
- staging-backed frontend on `http://localhost:3002`
- production-style builds via `cd web && npm run build`
- Replit-safe host binding via `npm run dev:replit` and `npm run start:replit`

`dev:replit` and `start:replit` bind the app to `0.0.0.0`, which is required for Replit previews and deployments.

## Replit Commands

Use the repo root in Replit, but run the web app from `web/`.

Recommended commands:

```bash
# Workspace preview
cd web && npm run dev:replit

# Deployment build
cd web && npm ci && npm run test && npm run lint && npx tsc --noEmit && npm run build

# Deployment run
cd web && npm run start:replit
```

`next dev` and `next start` will respect a `PORT` value supplied by Replit. If no port is provided, Next.js falls back to `3000`.

## Required Environment Variables

At minimum, set the following for the deployed frontend runtime:

```bash
NEXT_PUBLIC_API_URL=https://<target-api-host>
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<clerk-publishable-key>
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
CLERK_SECRET_KEY=<clerk-secret-key>
CLERK_AUTHORIZED_PARTIES=https://<frontend-host>
```

Reference values and local defaults live in `.env.example`.

The app now hardens Clerk middleware with `authorizedParties`.

- local development auto-allows `http://localhost:3001` and `http://localhost:3002`
- Replit workspace previews auto-allow `https://$REPLIT_DEV_DOMAIN` when Replit sets that env var
- deployed frontend domains still need to be listed explicitly in `CLERK_AUTHORIZED_PARTIES`

## External Configuration Required

In addition to the frontend runtime vars, Replit deploys need two external systems configured correctly:

1. Clerk
   - Add the deployed Replit URL or custom domain to the Clerk app configuration.
   - For public production deploys, use a Clerk production instance with live keys.
2. Backend CORS
   - Add the deployed frontend origin to the API's `CORS_ORIGINS` environment variable.
   - A Replit-hosted frontend will not be able to call the API until that origin is allowed.

Also note that Replit workspace secrets do not automatically become deployment secrets. Copy the required env vars into the deployment environment as well.

## Root Replit Config

The repo now includes a root `.replit` file for the frontend workflow:

- workspace Run button: boots the Next.js frontend from `web/`
- deployment build: installs dependencies, runs tests/lint/type-check, then builds
- deployment run: starts the production frontend with the Replit-safe host binding

## Manual Release Checklist

From `web/`:

```bash
npm ci
npm test
npm run lint
npx tsc --noEmit
NEXT_PUBLIC_API_URL=https://<target-api-host> npm run build
```

Then start the built app in hosted mode for a smoke test:

```bash
NEXT_PUBLIC_API_URL=https://<target-api-host> npm run start:replit
```

## Smoke Test

Before shipping a frontend build, verify:

1. `/sign-in` loads without Clerk configuration errors.
2. Auth redirects into `/crawls`.
3. `/crawls` loads against the intended API environment.
4. Opening a crawl detail page still loads summary, pages, filters, retry, duplicate, delete, and CSV export.
5. Browser network requests succeed from the deployed frontend origin instead of failing on CORS.

## What Is Not Automated Yet

The repo does not currently define:

- frontend preview deployments for pull requests
- a production frontend deploy job in GitHub Actions
- environment promotion for web builds

If we want the next step after this runbook, the natural follow-up is to add a dedicated frontend deploy workflow for the chosen host.
