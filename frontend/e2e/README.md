# E2E tests

Playwright tests that exercise the two core user journeys through the real
built UI (not mocked components — an actual browser, an actual click, an
actual rendered DOM):

- `image-search.spec.ts` — upload a photo → ranked results grid → best-deal
  badge, plus the failure path (backend 502 → retryable error state).
- `ai-assistant.spec.ts` — describe a need in the chat → recommendation
  card with a real purchase link, plus the failure path (Gemini not
  configured → clear 503 message).

## Why mocked network calls

These tests mock `/api/search/*` and `/api/ai/*` at the browser level with
`page.route()` rather than hitting a real backend. That means:

- Zero API keys needed to run the suite (SerpApi, Cloudinary, Gemini).
- Deterministic assertions — a real product search result changes every
  time SerpApi is queried, which would make the test flaky by definition.
- No SerpApi/Gemini quota burned by CI runs.

They still catch real regressions: a broken request shape, a renamed
response field the frontend no longer reads correctly, a component that
silently fails to render a value it used to display. What they don't catch
is the backend integration itself — that's what `tests/` (pytest) is for.

## Running locally

```bash
cd frontend
npm run build              # one-time, or after any change
npx playwright install --with-deps chromium   # one-time
npm run test:e2e
```

Add `--ui` for the interactive runner (`npm run test:e2e:ui`), or `--debug`
to step through a single test.

## Running against a real, deployed backend instead of mocks

Set `E2E_BASE_URL` to the deployed frontend's URL and remove/relax the
`page.route()` intercepts you want to bypass — useful for a one-off smoke
test against a live environment, but not how these run in CI (see above).
