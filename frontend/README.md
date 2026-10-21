# Hisaab Web App

Next.js 16 frontend for the personal finance workspace. See the
[root README](../README.md) for full setup, features and screenshots-free walkthrough.

## Run

```bash
npm install
npm run dev
```

Open <http://localhost:3000>. The backend must be running on
`http://127.0.0.1:8000` (override with `API_BASE_URL`).

The Next.js server proxies browser requests from `/api/proxy/*` to the FastAPI
backend and attaches `API_AUTH_TOKEN` server-side, so the token is never shipped
to the browser.

## Validate

```bash
npm run lint
npm run build
```

## Structure

- `src/app/` — dashboard, transactions, transfers, reports, budgets, goals,
  recurring, import/export and settings pages
- `src/components/` — layout, forms, charts and shadcn/ui primitives
- `src/lib/` — API client, hooks, formatting helpers and shared types
- `src/app/api/proxy/[...path]/route.ts` — server-side API proxy

All pages are client components that fetch through the proxy. Money values from
the API are decimal strings and are formatted with `formatMoney`/`toNumber`.
The app opens on the baseline month when the baseline date is in the future.
