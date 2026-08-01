# PR: Analyse, retrieval comparison and latency views

Branch `rebuild/v2`. Adds `apps/web`, a React 19 + Vite + Tailwind v4 application with
three views, running fully on a mock adapter and one line from live.

## What is in it

| Path | Purpose |
|---|---|
| `apps/web/src/api/contracts.ts` | zod schemas for every payload, plus `parseOrThrow`. The only place a runtime shape is asserted. |
| `apps/web/src/api/{adapter,mock-adapter,http-adapter,index}.ts` | One interface, two implementations, one-line swap in `getAdapter`. |
| `apps/web/src/api/mock/` | Glossary expansion and a real in-browser reimplementation of both retrieval configurations. |
| `apps/web/src/api/queries.ts` | Every server interaction, through TanStack Query v5. |
| `apps/web/src/features/analyse/` | View 1: document-forward split, citation chips, marks in the text. |
| `apps/web/src/features/compare/` | View 2: two arms, shared and unique chunks, the Recall@6 delta. |
| `apps/web/src/features/latency/` | View 3: badge in the masthead plus the breakdown panel. |
| `apps/web/src/styles/tokens.css` | OKLCH token layer. Dark mode is a variable swap; there are no `dark:` utilities. |
| `scripts/build_web_fixtures.py` | Generates fixtures from the real corpus using the API's own chunkers. |
| `scripts/contrast.py`, `scripts/check_glossary_parity.py` | Committed checks for the numbers this PR claims. |

## Verification

```
cd apps/web && npm install
npm run verify        # tsc -b --noEmit, then the smoke test, then the production build
```

- `tsc --noEmit` clean under `strict` plus `noUncheckedIndexedAccess`.
- Smoke test: 29 fixtures, 257 clause chunks, every mark proven to slice back to its own
  text and lie inside its citation span; the two arms diverge on 18 of 24 query and
  contract pairs.
- Build: initial critical path about 118 kB gzipped. The comparison view (3.7 kB), the
  latency view (3.1 kB) and Motion (26.8 kB) are all lazy.
- `python scripts/contrast.py` passes every pair in both themes.
- Static discipline greps: zero `dark:` utilities, zero raw hex outside the token file,
  zero stock palette classes, zero manual `useMemo` or `useCallback` for memoisation, zero
  `rounded-2xl` or `shadow-lg`, and the string "No data" appears nowhere as UI copy.

## Contract shapes I had to change, and why

The brief specified three endpoint shapes. Two are unchanged. Four things were added, and
each is additive, so a backend implementing the brief's shape verbatim still validates.

**1. `source: "mock" | "http"` on every response.** Not in the brief. Added because an
interface that cannot tell a demo from live data will eventually present one as the other.
The footer renders it.

**2. `answerStatus` and `answerDetail` on `/analyse`.** The brief has `{ answer, citations,
timing }`. The deployed API has no generation provider configured, so "no answer, but here
are the citations" is a normal outcome rather than an error, and the interface needs to say
which of the two it is. `answerStatus: "ok" | "unavailable" | "error"`.

**3. `evidence` on each arm of `/compare`, and `overlapChunkIds` on the response.** The
brief has `arms: [{ config, chunks, recallAt6 }]`. `recallAt6` alone is not enough to render
honestly: a bare number invites the reader to think it was computed from their query. The
`evidence` object carries `runId`, `questions`, `datasetSha256` and `embeddingProvider`
alongside the metric, which is what lets the view label it as a corpus aggregate over 110
questions. `overlapChunkIds` is computed once server-side so both columns agree on what is
shared.

**4. `page`, `clauseId` and `clauseTitle` on each citation.** The brief has `{ chunkId,
text, span, score }`. Without the clause label a chip can only say "Citation 3", which is
not something an analyst can act on. These come free from the existing `chunks` table.

**One shape I kept despite a reservation.** `span: { start, end }` is a single flat range.
The backend stores `page_spans[]` as well, because a chunk crossing a page boundary needs
per-page local offsets. For the document-forward render here the flat span is sufficient
and it is what the brief asked for. If the reader pane ever becomes paginated, `span` has
to become `spans: PageSpan[]`, and that is a component change as well as a contract change.
Flagged now rather than discovered later.

## Going live

```
VITE_ADAPTER=http VITE_API_BASE=http://localhost:8000 npm run build
```
or append `?adapter=http` to the URL. No component changes. The HTTP adapter expects
`GET /documents`, `GET /documents/:id/text`, `POST /analyse`, `POST /compare` and
`GET /metrics/latency`; the first two exist on the API today, the last three do not and are
the backend work this PR implies.

## Known gaps

- **Nobody has looked at it.** No browser was available, so there are no screenshots and
  the keyboard walk, reduced-motion behaviour and screen reader output are unverified. They
  are listed as NOT VERIFIED in `docs/accessibility-audit-web.md` rather than claimed.
- **One accessibility defect, open:** the answer record has no live region, so a screen
  reader user is not told when retrieval finishes. WCAG 4.1.3, recorded as FAIL.
- **The extractive answer is a template.** It demonstrates the citation mechanism honestly
  but is not a sample of what the product would say with a generation provider attached.
- Three further build critiques, including the cramped right-hand column and the repeated
  extractive note, are written up at the end of `docs/taste-pass-analyse.md`.
