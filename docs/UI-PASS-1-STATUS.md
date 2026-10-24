# UI pass 1 — state at pause (OpenAI/Codex usage limit)

> Historical handoff, superseded by `docs/UI-PASS-1.md` for 1C acceptance and
> runtime evidence. The “no per-test regression” conclusion below was not a
> controlled measurement. The current suite consolidates the six UI checks into
> one isolated page with named steps; browser results and timing belong to CI.

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

## CI result (PR #1, run `40108839515`)

**All green:** `pipeline pytest` **pass** 23 s · `verify:m0` (Playwright, 12+ tests) **pass**
**18 m 24 s** · GitGuardian **pass**. PR is `MERGEABLE` / `CLEAN`.

Two notes for the retry:

- `data-district-id` lives in the new `src/panels/RiskRow.tsx`, not `RiskPanel.tsx` — that is why the
  33-row assertion still passes after the panel was restructured.

## Not yet verified

1. ~~**Playwright E2E**~~ — **passed in CI** (18 m 24 s). Local Chromium still cannot fork (`spawn EPERM`).
2. **Visual review** — Chrome holds the real profile lock, so no local screenshot was possible.
   `npx vite preview --port 4192` serves the new build at `http://localhost:4192/assam-flood-dynamics/`
   for a screenshot pass once the browser is free.

## Acceptance tests from the brief — all six delivered

They live in **`tests/e2e/ui-pass-1.ts`** (a new spec, not `m0.spec.ts`), and CI ran them green.
An earlier reviewer note claiming three were missing was wrong: it grepped only `m0.spec.ts`.

| # | Requirement | Where | How it is actually asserted |
|---|---|---|---|
| 1 | Map owns the screen | `ui-pass-1.ts:6` | 1440×900: map ≥ 540 px (60 vh) with rails open, ≥ 675 px (75 vh) after collapsing analytics; rail widths 380 → 520 → 44; toggled by keyboard Enter/Space |
| 2 | Five district rows visible | `:25` | rows 1–5 must contain `#1…` and their `data-score`, and each row's box must sit inside the panel box |
| 3 | Legend equals map palette | `:40` | DOM `getComputedStyle` colours converted to hex and compared with **`DEPTH_PRESENTATION` imported from source** |
| 4 | Formula not clipped | `:51` | `scrollWidth <= clientWidth + 2` |
| 5 | Exactly one warning | `:58` | across all five tabs: `toHaveCount(1)` **plus** a text-node count of 1 (ancestors excluded) |
| 6 | Onset empty state | `:71` | timeline-analytics region contains `Onset — no accumulated change yet.` |

## E2E runtime — corrected reading

Suite result: **20 tests passed in 10.4 min**. The 18 m 24 s job figure includes install, build and
artifact upload. Per-test cost is 17–47 s, which is normal for a WebGL map that loads and settles per
test; the longest are the S00/S04/S07 paint comparison (47.5 s) and the S07 scrub (40.0 s).

So there is **no hang and no per-test regression** — the earlier "2.5× slowdown" note compared a
12-test run with a 20-test run. The real lever, if CI time matters later, is fewer page loads
(shared fixture) or more workers, not a bug hunt.

## Keyboard-path failure: environment, not code (reviewer investigation)

`m0.spec.ts:79` ("Space plays, arrows step") failed twice on `6e5515b`, then **passed on a rerun of the
same commit** (`verify:m0` pass, 10 m 5 s). Evidence gathered before concluding:

- Reproduced locally **4/4 at HEAD and 3/3 at `2444418`** — every commit fails on this Windows host, so
  the UI change cannot be the cause.
- The failure snapshot shows the app already at **S07, 8/12**: playback ran, then `playing` went false
  before the poll observed it.
- Mechanism: `usePlayback` pauses when `document.hidden` is true — deliberate product behaviour. On this
  host the headless window is treated as occluded; CI headless is not.

**No product change made.** Two follow-ups:

- **N-04** — the keyboard test should `page.bringToFront()` or wait for `visibilityState === 'visible'`
  before asserting transport behaviour, so it cannot depend on window occlusion.
- **N-05** — pausing playback in a hidden tab is intentional; "keep playing in the background" would be
  an explicit product decision, not a regression fix.

A fixed-slice timer clock was prototyped against this failure and **reverted unverified**: local runs on
this host cannot validate transport timing, so it must not be resurrected without a failing CI case.

## Resume plan (complete)

1. ~~Confirm `gpt-6-astra --provider openai-codex --reasoning medium` responds~~ — confirmed
   (`ASTRA_READY`); it executed 1C.
2. ~~Add the three assertions~~ — they already existed; 1C tightened them (see the table above).
3. ~~Get PR #1 CI green~~ — green at `6e5515b`, mergeable.
4. Screenshot pass and merge decision remain open, plus parked nits **N-01** … **N-05** in `docs/NITS.md`.
