#!/usr/bin/env bash
# Centralised heavy-job queue. Every Blender render/bake/export, Godot import/export and
# browser capture MUST go through this wrapper so that parallel agents never saturate the
# host (4 vCPU, no GPU). Jobs run one at a time, FIFO-ish via flock, at reduced priority.
#   build/heavy.sh <label> <command...>
set -euo pipefail
LABEL="$1"; shift
LOCK="${THREE_BEDROOM_HEAVY_LOCK:-/tmp/three-bedroom-heavy.lock}"
LOG_DIR="${THREE_BEDROOM_HEAVY_LOG:-/tmp/three-bedroom-heavy-logs}"
mkdir -p "$LOG_DIR"
echo "[heavy] queued: $LABEL ($(date +%T))" >&2
exec 9>"$LOCK"
flock 9
echo "[heavy] running: $LABEL ($(date +%T))" >&2
start=$(date +%s)
set +e
nice -n 5 "$@"
rc=$?
set -e
echo "[heavy] done: $LABEL rc=$rc in $(( $(date +%s) - start ))s" | tee -a "$LOG_DIR/history.log" >&2
exit $rc
