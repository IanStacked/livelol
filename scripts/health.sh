#!/usr/bin/env bash
# health.sh for leaguehelper (LiveLOL) - SPEC-project-manifest §4 health contract.
#
# Emits ONE JSON object on stdout: {liveness, services, errors, checked_at}.
# The daily-report skill + chief-of-staff digest read `liveness` and the `errors` block.
#
# Config: PROJECT.yaml error_sink (kind: none here, so no sink query) + SINK_TOKEN env.
# Liveness comes from the bot's Firestore heartbeat (cogs/background.py writes
# bot_health/heartbeat every 60s; scripts/heartbeat_check.py reads it). If the check
# can't run (no uv/creds/network) liveness degrades to `unknown` - never a faked green.
set -euo pipefail

PROJECT="${PROJECT:-leaguehelper}"
WINDOW="${WINDOW:-24h}"
SINK_REF="${SINK_REF:-}"           # PROJECT.yaml error_sink.ref; empty == kind: none
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- errors block (null-safe; kind: none -> nulls) ----------------------------
if [[ -n "$SINK_REF" ]]; then
  ERRORS="$(python3 "$HERE/errors_block.py" --project "$PROJECT" --window "$WINDOW" \
             --ref "$SINK_REF" --token-env SINK_TOKEN)"
else
  ERRORS="$(python3 "$HERE/errors_block.py" --project "$PROJECT" --window "$WINDOW")"
fi

# --- liveness: from the bot's Firestore heartbeat -----------------------------
# Needs the project venv (firebase-admin), so run via `uv run` from the repo root.
# Any failure -> empty output -> liveness falls back to `unknown` below.
HB_JSON="$( (cd "$HERE/.." && uv run --quiet python3 scripts/heartbeat_check.py) 2>/dev/null || true )"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 - "$CHECKED_AT" "$ERRORS" "$HB_JSON" <<'PY'
import json, sys

checked_at, errors_raw, hb_raw = sys.argv[1], sys.argv[2], sys.argv[3]
errors = json.loads(errors_raw)
try:
    hb = json.loads(hb_raw) if hb_raw.strip() else {}
except json.JSONDecodeError:
    hb = {}

liveness = hb.get("liveness", "unknown")
services = []
if hb:
    services.append({
        "name": "discord-bot",
        "status": liveness,
        "detail": hb.get("detail"),
    })

print(json.dumps({
    "liveness": liveness,
    "services": services,
    "errors": errors,
    "checked_at": checked_at,
}))
PY
