#!/usr/bin/env bash
# Retry the ERA5 JJAS fetch with backoff until the Open-Meteo quota allows it.
set -u
cd "$HOME/Desktop/baanh" || exit 1
LOG="$LOCALAPPDATA/Temp/p1b-rain-retry.log"
: > "$LOG"
log() { echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }
for attempt in 1 2 3 4 5 6 7 8; do
  log "attempt $attempt: build-rainfall"
  PYTHONPATH=pipeline/src python -m baanh_pipeline.cli build-rainfall \
    --cache pipeline/cache/rainfall \
    --out-rainfall public/data/series/rainfall.json \
    --out-forecast public/data/series/rainfall-forecast.json >> "$LOG" 2>&1
  rc=$?
  log "attempt $attempt EXIT=$rc"
  if [ "$rc" -eq 0 ]; then
    ls -la public/data/series/rainfall*.json >> "$LOG" 2>&1
    echo "RAINFALL_OK" >> "$LOG"
    exit 0
  fi
  cached=$(ls pipeline/cache/rainfall/archive-2*.json 2>/dev/null | wc -l)
  log "cached pairs now: $cached ; sleeping 1500s"
  sleep 1500
done
log "exhausted retries"
echo "RAINFALL_BLOCKED" >> "$LOG"
exit 1
