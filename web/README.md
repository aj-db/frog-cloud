# Web Frontend

Next.js App Router frontend for Frog in the Cloud.

## Development

Use the shared runbook:

- `../docs/development/dev-startup.md`

Common commands from `web/`:

```bash
npm run dev
npm run dev:staging
npm test
npm run lint
npx tsc --noEmit
```

## Deployment

For the current frontend release path, required environment variables, and manual smoke-test checklist, see:

- `../docs/development/web-deploy.md`

The repository currently automates API deployment only. Frontend deploys are still documented/manual until a hosting target and CI workflow are chosen.
