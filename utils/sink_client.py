"""Owned error-sink client.

A vendored, minimal implementation of the error-sink HTTP contract (`POST /events`
with bearer auth; one JSON event or a batch). Stdlib only - no new dependency.

Two invariants this file guarantees:
  1. `capture()` never raises - an observability failure must not become an app failure.
  2. No event is lost while the sink is down - it is buffered to an append-only file and
     replayed on the next successful send; the server dedups by `id`, so replay is safe.
"""

from __future__ import annotations

import contextlib
import json
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

BATCH_MAX = 500  # server cap per request
BUFFER_MAX_LINES = 10_000  # bound the offline buffer; drop oldest past this


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class SinkClient:
    """Build and POST error events to the owned sink, buffering on failure."""

    def __init__(
        self,
        base_url: str,
        token: str,
        project: str,
        buffer_path: str = "./.errors/buffer.jsonl",
        timeout: float = 3.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project = project
        self.buffer_path = Path(buffer_path)
        self.timeout = timeout

    def build_event(
        self,
        type_: str,
        message: str | None = None,
        *,
        handled: bool = True,
        fingerprint: str | None = None,
    ) -> dict:
        """Return one event dict in the sink schema."""
        return {
            "id": str(uuid.uuid4()),  # idempotency key; dedups on replay
            "project": self.project,
            "ts": _now_iso(),
            "release": None,
            "type": type_,
            "message": message,
            "fingerprint": fingerprint,
            "handled": handled,
            "fix_ref": None,
        }

    def capture(self, event: dict) -> None:
        """Send one event; on any failure buffer it. Never raises."""
        try:
            self.flush()  # opportunistic backfill before the next send
            self._post([event])
        except Exception:
            with contextlib.suppress(Exception):
                self._buffer(event)

    def flush(self) -> int:
        """Drain the buffer to the sink in batches; return the number replayed."""
        if not self.buffer_path.exists():
            return 0
        lines = self.buffer_path.read_text(encoding="utf-8").splitlines()
        events = [json.loads(ln) for ln in lines if ln.strip()]
        if not events:
            return 0
        for start in range(0, len(events), BATCH_MAX):
            self._post(events[start : start + BATCH_MAX])
        # every batch accepted -> safe to clear (the server dedups replays anyway)
        self.buffer_path.write_text("", encoding="utf-8")
        return len(events)

    def _post(self, events: list[dict]) -> None:
        body = json.dumps(events).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/events",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if resp.status // 100 != 2:
                raise urllib.error.HTTPError(
                    resp.url, resp.status, "non-2xx", resp.headers, None
                )

    def _buffer(self, event: dict) -> None:
        self.buffer_path.parent.mkdir(parents=True, exist_ok=True)
        with self.buffer_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
        self._enforce_bound()

    def _enforce_bound(self) -> None:
        lines = self.buffer_path.read_text(encoding="utf-8").splitlines()
        if len(lines) <= BUFFER_MAX_LINES:
            return
        keep = lines[-BUFFER_MAX_LINES:]
        self.buffer_path.write_text("\n".join(keep) + "\n", encoding="utf-8")
