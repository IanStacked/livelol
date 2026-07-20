#!/usr/bin/env python3
"""Derive LiveLOL bot liveness from its Firestore heartbeat.

The bot writes a `bot_health/heartbeat` doc every 60s (see `cogs/background.py`
`heartbeat_task`). This reads that doc and maps its freshness to the
everythingdev liveness word (MANAGED-PROJECTS.md), then prints a small JSON object:

    {"liveness": "green|degraded|down|unknown", "detail": "...", "age_seconds": N}

Degrade, don't fail: any error (missing creds, Firestore unreachable, no doc)
prints `liveness: unknown` and exits 0, so `health.sh` never breaks. Run from the
project root via `uv run python3 scripts/heartbeat_check.py` (needs firebase-admin
and the same Firebase creds the bot uses).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime

# Make the repo root importable (this file lives in scripts/), so `import database`
# resolves whether run from the root or via `uv run python3 scripts/heartbeat_check.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Thresholds (seconds) - tunable via env. Beat interval is 60s in the bot.
GREEN_MAX = int(os.getenv("HEARTBEAT_GREEN_MAX", "180"))  # <= 3 missed beats
DOWN_MAX = int(os.getenv("HEARTBEAT_DOWN_MAX", "900"))  # 15 min -> down

APP_NAME = "heartbeat-check"


def _emit(liveness: str, detail: str, age: float | None = None) -> None:
    out = {"liveness": liveness, "detail": detail}
    if age is not None:
        out["age_seconds"] = round(age)
    print(json.dumps(out))


def classify_liveness(age_seconds: float, connected: bool) -> tuple[str, str]:
    """Map heartbeat freshness + connection state to a liveness word + detail.

    Pure and side-effect-free so it can be unit-tested without Firestore.
    Assumes a heartbeat doc with a valid `last_beat` exists (missing docs are
    handled as `down` by the caller).
    """
    if age_seconds > DOWN_MAX:
        return "down", f"last beat {round(age_seconds)}s ago (> {DOWN_MAX}s)"
    if not connected:
        return "degraded", "beating but not connected to Discord"
    if age_seconds > GREEN_MAX:
        return "degraded", f"stale: last beat {round(age_seconds)}s ago"
    return "green", f"beating, connected ({round(age_seconds)}s ago)"


def _load_client():
    """Init a throwaway firebase-admin app the same way the bot does."""
    import base64

    import firebase_admin
    from dotenv import load_dotenv
    from firebase_admin import credentials, firestore

    load_dotenv()

    b64_creds = os.getenv("FIREBASE_CREDENTIALS_BASE64")
    if b64_creds:
        b64_creds = b64_creds.strip()
        pad = len(b64_creds) % 4
        if pad:
            b64_creds += "=" * (4 - pad)
        cred_info = json.loads(base64.b64decode(b64_creds).decode("utf-8"))
        cred = credentials.Certificate(cred_info)
    elif os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
    else:
        cred = credentials.ApplicationDefault()

    app = firebase_admin.initialize_app(cred, name=APP_NAME)
    return firestore.client(app)


def main() -> int:
    try:
        from database import BOT_HEALTH_COLLECTION, HEARTBEAT_DOC

        db = _load_client()
        snap = db.collection(BOT_HEALTH_COLLECTION).document(HEARTBEAT_DOC).get()
        if not snap.exists:
            _emit("down", "no heartbeat doc - bot has never reported in")
            return 0

        data = snap.to_dict() or {}
        last_beat = data.get("last_beat")
        if last_beat is None:
            _emit("down", "heartbeat doc missing last_beat")
            return 0

        age = (datetime.now(UTC) - last_beat).total_seconds()
        connected = bool(data.get("connected", False))
        liveness, detail = classify_liveness(age, connected)
        _emit(liveness, detail, age)
        return 0
    except Exception as exc:  # noqa: BLE001 - fail-safe: never break health.sh
        _emit("unknown", f"heartbeat check failed: {type(exc).__name__}: {exc}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
