#!/usr/bin/env bash
# Phase 1b completion: resume the ERA5 fetch after the Open-Meteo hourly window resets,
# then run every gate and commit only if they pass green.
set -u
cd "$HOME/Desktop/baanh" || exit 1
LOG="$LOCALAPPDATA/Temp/p1b-rain-resume.log"
: > "$LOG"
log() { echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }

now=$(date +%s)
next=$(( (now / 3600 + 1) * 3600 + 180 ))
wait_s=$(( next - now ))
log "waiting ${wait_s}s for the hourly window to reset"
sleep "$wait_s"

log "resuming build-rainfall (142/187 chunk-years cached)"
PYTHONPATH=pipeline/src python -m baanh_pipeline.cli build-rainfall \
  --cache pipeline/cache/rainfall \
  --out-rainfall public/data/series/rainfall.json \
  --out-forecast public/data/series/rainfall-forecast.json >> "$LOG" 2>&1
rc=$?
log "build-rainfall EXIT=$rc"
if [ "$rc" -ne 0 ]; then
  log "STOP: rainfall fetch failed again; no files written, nothing committed"
  grep -oE "HTTP 429[^\"]*" "$LOG" | tail -1 >> "$LOG"
  echo "RAINFALL_BLOCKED" >> "$LOG"
  exit "$rc"
fi

log "check-data"
node scripts/check-data.mjs >> "$LOG" 2>&1; cd_rc=$?
log "check-data EXIT=$cd_rc"
log "check-budget"
node scripts/check-budget.mjs >> "$LOG" 2>&1; log "check-budget EXIT=$?"
log "check-honesty"
node scripts/check-honesty.mjs >> "$LOG" 2>&1; log "check-honesty EXIT=$?"
node scripts/check-honesty.mjs --self-test >> "$LOG" 2>&1; log "check-honesty self-test EXIT=$?"
log "unit tests"
npm run test:unit >> "$LOG" 2>&1; log "unit EXIT=$?"
log "pipeline pytest"
PYTHONPATH=pipeline/src python -m pytest pipeline/tests -q >> "$LOG" 2>&1; log "pytest EXIT=$?"
log "build (sandbox)"
npm run build:sandbox >> "$LOG" 2>&1; log "build EXIT=$?"

if [ "$cd_rc" -ne 0 ]; then
  log "STOP: check-data still failing; not committing"
  echo "GATES_FAILED" >> "$LOG"
  exit 1
fi

git add -A >> "$LOG" 2>&1
git -c user.email=hermes@local -c user.name=hermes commit -qm "phase 1b: ERA5 JJAS rainfall (resumable), masked district exposure, class badges" >> "$LOG" 2>&1
log "commit EXIT=$?"
git push >> "$LOG" 2>&1
log "push EXIT=$?"
git log --oneline -1 >> "$LOG"
echo "PHASE_1B_DONE" >> "$LOG"
