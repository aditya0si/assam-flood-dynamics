# Review 10 — publish plan (approved): public repo `aditya0si/assam-flood-dynamics`

User decision (2026-10-21): **public repo under `aditya0si`, name `assam-flood-dynamics`, GitHub
Pages enabled.** Execute only after B4 is green.

## Blocker to fix first: the base path

`vite.config.ts` builds with `base: '/baanh/'`. A GitHub Pages *project* site is served at
`https://<user>.github.io/<repo>/`, so every asset and every `data/` fetch would 404 into the SPA
fallback and the app would boot to a blank shell. Change:

- `base` for `build` and `preview` → **`/assam-flood-dynamics/`** (keep `/` for dev);
- any test or preview URL that hard-codes `/baanh/`;
- `README.md` links (live URL + clone path).

Keep it overridable (`process.env.BAANH_BASE ?? '/assam-flood-dynamics/'`) so a different repo name
does not require a code edit.

## Publish sequence

1. `npm ci && npm run build` (plain vite) → `dist/` contains `index.html`, hashed assets, `data/`,
   `.nojekyll`.
2. `gh repo create aditya0si/assam-flood-dynamics --public --source . --remote origin --push`
   (git identity already configured; default branch `main`).
3. Pages: `gh api -X POST repos/aditya0si/assam-flood-dynamics/pages -f build_type=workflow`
   (the committed `pages.yml` uses `actions/configure-pages` + `upload-pages-artifact`, so the
   workflow token builds and deploys; no `gh-pages` branch needed).
4. Watch the run: `gh run watch` / `gh run list --workflow=pages.yml`.
5. Only then announce the URL.

## Live verification (reviewer, after deploy)

- `https://aditya0si.github.io/assam-flood-dynamics/` returns 200 and is HTML.
- Direct asset probes return **content-type javascript/css**, not HTML: a 200 that is the SPA index
  is a 404 in disguise (already caught once in this project).
- `data/flood/frames/step-07.png` and `data/manifest.json` return 200 with correct content types.
- In a browser: `data-ready=true`, `__baanh.step=0`, `frameFile=frames/step-00.png`,
  `NOT A FORECAST` visible, playback advances, zero console errors.
- `data-tile-health` behaves: `live` with network, `offline` when tile hosts are blocked, app still
  plays.

## Definition of done for the whole project

- `npm run verify:m0` → **10/10** Playwright tests on the published base path, all static gates green.
- Clean clone → `npm ci` → `npm run build` → exit 0.
- Live Pages URL verified by the checks above.
- `docs/M0-REPORT.md` records the deployed URL, the commit SHA it was built from, and the results.

## Do not

Force-push, rewrite history, add the sandbox scripts to CI, or publish before `verify:m0` is 10/10
on the new base path.
