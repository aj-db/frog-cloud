# Development Startup Runbook

This project has two different frontend modes during development:

- `localhost:3001`: local frontend backed by the local API/database
- `localhost:3002`: staging-backed frontend for historical/shared crawl data

Use the fixed port split below. Do not improvise ports unless you also update the matching backend/CORS settings.

## Port Map

| Service | URL | Data source | Command |
| --- | --- | --- | --- |
| Local API | `http://localhost:8000` | Local Postgres from `.env` | `make api-dev` |
| Local frontend | `http://localhost:3001` | Local API on `8000` | `make web-dev-local` |
| Staging-backed frontend | `http://localhost:3002` | Staging Cloud Run API | `make web-dev-staging` |

## Recommended Startup Flows

### Local-only development

From the project root:

```bash
make dev-local
```

That starts:

- local API on `8000`
- local frontend on `3001`

### Side-by-side local + staging UI

From the project root:

```bash
make dev-side-by-side
```

That starts:

- local API on `8000`
- local frontend on `3001`
- staging-backed frontend on `3002`

## Health Checks

Check whether the expected services are up:

```bash
make dev-status
```

Expected output shape:

```text
api: http://localhost:8000 (up)
web-local: http://localhost:3001 (up)
web-staging: http://localhost:3002 (up)
```

Stop everything on the standard dev ports:

```bash
make dev-stop
```

## Which UI Should Show Historical Crawls?

Use `http://localhost:3002` for historical staging crawls.

Use `http://localhost:3001` for local development against the local database.

If `3001` only shows one crawl, that is expected when the local database only contains one crawl row.

## Important Rules

### 1. Use `localhost` for frontend hosts

Start the web apps on `localhost`, not `127.0.0.1`.

Clerk's local auth flow can fail or mis-proxy when the app is launched on `127.0.0.1` but redirects/proxy requests target `localhost`.

### 2. Keep staging on `3002`

The staging API currently allows `http://localhost:3002`.

Do not move the staging-backed UI to `3003` unless you also update staging API CORS.

Symptoms of using the wrong port:

- crawl list shows `Could not load crawls`
- retrying does not recover
- the staging API is healthy, but browser requests still fail

### 3. Keep the two frontend build directories separate

The startup commands use separate `NEXT_DIST_DIR` values so local and staging-backed Next.js dev servers do not fight over the same `.next` lock files.

## Recovery Checklist

If the UIs or API disappear during development:

1. Check status:

```bash
make dev-status
```

2. If a service is down, stop the standard dev ports:

```bash
make dev-stop
```

3. Restart with the intended mode:

```bash
make dev-local
```

or

```bash
make dev-side-by-side
```

4. Verify API health:

```bash
curl http://127.0.0.1:8000/health
```

5. Open the correct frontend:

- local data: `http://localhost:3001/crawls`
- staging history: `http://localhost:3002/crawls`

## Troubleshooting

### Local UI is up but history is missing

You are probably on `3001`, which uses the local DB.

Switch to `3002` if you want staging crawl history.

### Staging UI says `Could not load crawls`

Check these first:

1. Are you using `http://localhost:3002`?
2. Are you signed in to the correct Clerk org?
3. Is the staging API healthy?

```bash
curl -I https://staging-frog-api-i6yiz2xm6a-uc.a.run.app/health
```

4. If you changed the staging UI port, restore it to `3002` or update backend CORS.

### Next.js warns about multiple lockfiles

`web/next.config.ts` explicitly sets `turbopack.root` to the `web` app directory so Turbopack does not infer the wrong workspace root from parent lockfiles.
