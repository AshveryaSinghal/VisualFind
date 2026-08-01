# VisualFind — Frontend

A premium, dark-mode-first React frontend for the VisualFind FastAPI backend.
Upload a product photo, get live prices from trusted e-commerce platforms,
compare listings side by side, browse history as cards, and view analytics —
all backed by the real API, no mock data.

## Tech stack

React 18 · TypeScript · Vite · React Router · Tailwind CSS · Framer Motion ·
TanStack Query · Axios · React Hook Form · Zod · Recharts · Lucide Icons ·
Vitest · React Testing Library

UI primitives (`src/components/ui/*`) are hand-built in the shadcn/ui style
(same design tokens, same component API shape) but without Radix, to keep
the dependency tree small and guaranteed to install without a network-gated
CLI step.

## Prerequisites

- Node.js 18+ and npm
- The VisualFind FastAPI backend running and reachable (see `visualfind/README.md`
  in this project for backend setup — you need `serpapi_key`, `cloudinary_*`
  env vars configured there, then `uvicorn app.main:app --reload`)

## Setup

```bash
cd frontend
npm install
cp .env.example .env
```

Edit `.env` if your backend isn't at the default address:

```
VITE_API_BASE_URL=http://localhost:8000
```

## Run (development)

```bash
npm run dev
```

Visit the URL Vite prints (default `http://localhost:5173`). Make sure the
backend is already running at `VITE_API_BASE_URL` (default
`http://localhost:8000`) — the navbar shows a live green/red dot indicating
whether the backend is reachable.

## Build (production)

```bash
npm run build
npm run preview   # serve the production build locally to sanity-check it
```

`npm run build` type-checks the whole project (`tsc -b`) before bundling, so
a broken build will fail loudly rather than shipping silently. Routes other
than the landing page are code-split with `React.lazy`, and vendor libraries
(React, TanStack Query, Framer Motion, Recharts) are split into their own
chunks via `build.rollupOptions.output.manualChunks` in `vite.config.ts`, so
no single bundle balloons past a few hundred KB.

## Testing

```bash
npm run test          # run once
npm run test:watch    # watch mode
npm run test:coverage # with coverage
```

Vitest + React Testing Library, configured in `vite.config.ts` (`test` block)
with `src/setupTests.ts` wiring up `@testing-library/jest-dom`. Coverage
focuses on logic that's easy to get subtly wrong and cheap to regression-test:
formatting helpers (`utils/format.test.ts`), the debounce hook used by search
filters, the product-comparison selection context, and a couple of component
smoke tests (`EmptyState`, `ProductCard`) that assert real data renders
correctly and that a missing price shows "Price unavailable" rather than a
fabricated number.

## Product comparison

Any `ProductCard` can be added to a comparison set (up to 4 at once) via the
"Compare" toggle on its thumbnail. A floating bar tracks the current
selection from anywhere in the app; "Compare" opens a side-by-side dialog
built entirely from fields the search API already returns per listing —
price, savings, rating, review count, availability (derived from whether a
live price was actually extracted), seller/platform, official-store status,
and price-extraction confidence. The "AI recommended" highlight reuses the
same `is_best_deal` flag the backend already computes; it isn't a second,
separate AI call. See `src/context/CompareContext.tsx`,
`src/components/compare/`.

## Search pipeline timeline

`src/components/search/SearchTimeline.tsx` visualizes the eight-stage
pipeline (upload → brand detection → Google Lens → official store →
trusted retailers → matching → pricing → recommendation) in two modes:

- **Live**, while a search is in flight. The backend returns one upload
  progress signal and then a single response — there's no real per-stage
  event stream — so, consistent with the pre-existing `SearchProgress`
  component, the remaining stages cycle on a timer purely to keep the wait
  feeling active rather than frozen.
- **Summary**, collapsed under a finished result ("How VisualFind found
  this"). Every checkmark here reflects a real field on the response
  (`detected_brand`, `official_product_found`, `priced_count`, etc.) — none
  of it is simulated.

## Project structure

```
src/
  api/            Axios client + centralized error normalization
  services/       Typed functions, one per real FastAPI endpoint
  types/          TypeScript types mirroring app/models.py exactly
  hooks/          TanStack Query hooks wrapping the service layer
  context/        Theme, toast notifications, cross-page search handoff,
                  product-comparison selection
  components/
    ui/           shadcn-style primitives (button, card, dialog, table, ...)
    layouts/      Navbar, footer, page shell
    upload/       Drag-and-drop image upload
    search/       Product cards, filters, results grid, progress/timeline
    compare/      Floating compare bar + side-by-side comparison dialog
    history/      Search history — modern card grid (default) + table view
    analytics/    Stat cards, top-list bar charts
    common/       Page header, empty/error states, error boundary
  pages/          One file per route
  utils/          Formatting helpers (currency, dates, numbers), cn()
```

## Routes

| Path            | Page                                    |
|-----------------|------------------------------------------|
| `/`             | Landing page                             |
| `/search`       | Upload a photo and view live results     |
| `/results/:id`  | View a past search's full results        |
| `/history`      | Search history (filter, paginate, delete)|
| `/analytics`    | Analytics dashboard                      |
| `/about`        | How the pipeline works                   |
| `*`             | 404                                      |

## Backend endpoints used

Every network call in this app maps to a real route already in
`visualfind/app/routers/search.py`:

- `POST /api/search/image` — upload + search
- `GET /api/search/history` — list search history
- `GET /api/search/history/{id}` — one search's full results
- `DELETE /api/search/history/{id}` — delete one history row **(new)**
- `DELETE /api/search/history` — clear all history **(new)**
- `GET /api/search/analytics/summary` — analytics dashboard data
- `GET /api/search/platforms` — trusted platform allowlist

**Note on the two `DELETE` routes:** the History page's Delete/Clear History
actions are only possible because these two endpoints were added to
`app/routers/search.py` (thin HTTP-layer additions only — no existing
business logic, service, or model was touched). Everything else in the
backend is untouched.
