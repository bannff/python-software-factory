# Frontends

Non-Python frontend consumers of the Python Software Factory API base.

These are standalone applications that connect to the API base's HTTP endpoints
(`POST /api/tools/{tool_name}`, `GET /api/tools`, `POST /ag-ui/run`, `GET /api/health`).
They are NOT Polylith bricks — no BRICK.yaml, no MCP server, no `interface.py`.

## Available Frontends

- `next-dashboard/` — Next.js 15 + shadcn/ui + Magic UI dashboard
- `shared-renderer/` — TypeScript package (`@companion-x/shared-renderer`) the
  dashboard links with `file:../shared-renderer`; no app entrypoint of its own

## Building

`shared-renderer/` compiles its sources in `src/` to `lib/`, which is not
committed. Install it first: `npm ci` runs the package's `prepare` build, so the
renderer is ready before the dashboard resolves it.

```sh
cd frontends/shared-renderer && npm ci          # installs, then `tsc -b`
cd ../next-dashboard && npm ci && npm run build
```

Rebuild the renderer with `npm run build` after editing its sources, and run
`npm test` in each package for the frontend suites. The `frontend-tests` job in
`.github/workflows/ci.yml` runs exactly this sequence, and
`frontends/next-dashboard/Dockerfile` builds the renderer the same way.
