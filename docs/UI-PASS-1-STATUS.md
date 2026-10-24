# UI pass 1 — state at pause (OpenAI/Codex usage limit)

Paused deliberately: the Codex seat hit its usage limit (429, ~5 h). Nothing is lost; the UI work is
committed, pushed and open as a PR. This file exists so the retry starts from facts, not memory.

## Routes tried, and what actually works

| Attempt | Route | Outcome |
|---|---|---|
| 1 | `-m astra` (alias → `provider: custom`, ExperientialLabs) | **Dead** — ran 27 min, 0 bytes output, touched 3 files, killed. `Unknown provider 'astra'` when passed as `--provider` |
| 2 | `-m gpt-6-sol --provider openai-codex --reasoning medium` | **Works** (`SOL_OK`) but was killed to retry with astra |
| 3 | `-m gpt-6-astra --provider openai-codex --reasoning medium` | **Works** (`ASTRA_CODEX_OK`). Did the real work, then the parent hit the 429 before integration |

`gpt-6-astra` is in the `openai-codex` catalog alongside `gpt-6-astra-900k` (long-context). The
alias `astra` in `config.yaml` points at ExperientialLabs, which is not the same model seat and did
not respond.

## What landed

- Branch **`ui/pass-1`**, commit **`2444418`**, pushed to `origin`, **PR #1** open against `main`.
- 19 files, **+500 / −1,155** lines. UI only: `src/**`, `tests/e2e/**`, docs. No `public/data`, no
  `pipeline`, no gate scripts.
- Key changes: map-first layout with collapsible right and bottom rails; depth colours from one
  exported `DEPTH_PRESENTATION` consumed by `MapCanvas` via `depthPresentationColor()`; `NOT A
  FORECAST` rendered once from `HONESTY_CHIP`; onset empty state (`Onset — no accumulated change
  yet.`); typography scale with tabular numerals; amber reserved for the warning.

## Verified locally (all green)

`npm run build:sandbox` ✓ 5.99 s · `check-data` **38/38** · `check-budget` PASS · `check-honesty` PASS
+ `--self-test` PASS · unit **14/14** · pipeline pytest **29 passed**

## Not yet verified

1. **Playwright E2E** — CI on PR #1 is the authority (local Chromium cannot fork: `spawn EPERM`).
2. **Visual review** — Chrome holds the real profile lock, so no local screenshot was possible.
   `npx vite preview --port 4192` serves the new build at `http://localhost:4192/assam-flood-dynamics/`
   for a screenshot pass once the browser is free.

## Acceptance tests from the brief — delivered vs missing

| # | Requirement | State |
|---|---|---|
| 2 | District rows visible, ≥5 in view | **Delivered** — 33-row assertion plus `toBeInViewport` |
| 4 | Formula not clipped | **Delivered** — `scrollWidth <= clientWidth + 2` |
| 6 | Onset empty-state copy | **Implemented**; assertion not added |
| 3 | Legend hex equals map constant | **Satisfied by construction** (shared function); no explicit test |
| 1 | Map ≥ 60 vh with rails open, ≥ 75 vh collapsed | **Missing** — needs an explicit assertion |
| 5 | Exactly one `NOT A FORECAST` in the DOM | **Missing** — tests assert `.first()` visible, not cardinality |

## Resume plan (when the limit refreshes)

1. Confirm `gpt-6-astra --provider openai-codex --reasoning medium` responds again.
2. Add the three missing assertions (map height at both rail states, DOM cardinality of the warning,
   legend/map hex equality).
3. Get PR #1 CI green, then a screenshot pass and a merge decision.
4. Still parked from earlier phases: **N-01** (`risk_class_area_share_denominator`), **N-02**
   (attribution clipping), **N-03** (AOI-relative scores stated only on flagged rows) — all `open` in
   `docs/NITS.md`.
