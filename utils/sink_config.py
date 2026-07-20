"""Wire the owned error sink in beside Sentry (utils/sentry_config.py).

A logging handler mirrors ERROR-level records to the sink, so the sink and Sentry
capture the same events (dual-run; Sentry is cut last).

Threading: the event is BUILT on the logging thread (inside `emit`), where the
record's `exc_info` is still intact, and only the finished event is handed to a
background sender thread that does the blocking POST. The blocking I/O must never run
on the Discord event loop. (Note: a stdlib QueueHandler cannot be used in front of the
sink handler - QueueHandler.prepare() clears `record.exc_info`, which would erase the
exception type and the handled flag before this handler ever sees them.)

Fault semantics for the incident pipeline: a record carrying exception info is emitted
as UNHANDLED (a real fault the incident poller should surface as a TODO finding); a
plain error log with no exception is emitted as handled. The poller only escalates
unhandled groups, so this is what decides which logs become auto-fix candidates.
"""

from __future__ import annotations

import logging
import os
import queue
import threading

from utils.sink_client import SinkClient

# The sink identity MUST match what the incident poller queries: the fleet directory
# name, which is `livelol` (not the legacy `leaguehelper` that scripts/health.sh still
# uses). Emit under the wrong name and the poller sees nothing.
SINK_PROJECT = "livelol"

logger = logging.getLogger(__name__)

_worker: threading.Thread | None = None


class SinkLoggingHandler(logging.Handler):
    """Build a sink event from each ERROR record and enqueue it for the sender."""

    def __init__(self, event_queue: queue.SimpleQueue, client: SinkClient) -> None:
        super().__init__(level=logging.ERROR)
        self._queue = event_queue
        self._client = client

    def emit(self, record: logging.LogRecord) -> None:
        """Build the event here (exc_info is valid on this thread) and enqueue it.

        Cheap and non-blocking - the blocking POST happens on the sender thread.
        """
        try:
            exc_type = None
            if record.exc_info and record.exc_info[0] is not None:
                exc_type = record.exc_info[0].__name__
            type_ = exc_type or record.levelname
            # Call-site fingerprint so distinct faults stay distinct even when their
            # messages differ only in ids/paths (which the server would otherwise fold).
            fingerprint = f"{record.module}:{record.funcName}:{type_}"
            event = self._client.build_event(
                type_,
                record.getMessage(),
                handled=record.exc_info is None,
                fingerprint=fingerprint,
            )
            self._queue.put(event)
        except Exception:
            self.handleError(record)


def _sender_loop(event_queue: queue.SimpleQueue, client: SinkClient) -> None:
    """Drain built events and POST them off the event loop; capture never raises."""
    while True:
        event = event_queue.get()
        client.capture(event)


def setup_sink() -> SinkClient | None:
    """Attach the sink handler to the root logger if configured; return the client.

    No-op when SINK_URL / SINK_TOKEN are absent, mirroring the Sentry DSN-absent path.
    """
    global _worker
    url = os.getenv("SINK_URL")
    token = os.getenv("SINK_TOKEN")
    if not url or not token:
        logger.warning("⚠️ SINK_URL/SINK_TOKEN not set. Error sink is DISABLED.")
        return None
    if _worker is not None:
        return None  # already initialized

    client = SinkClient(base_url=url, token=token, project=SINK_PROJECT)
    event_queue: queue.SimpleQueue = queue.SimpleQueue()

    _worker = threading.Thread(
        target=_sender_loop,
        args=(event_queue, client),
        name="sink-sender",
        daemon=True,
    )
    _worker.start()

    logging.getLogger().addHandler(SinkLoggingHandler(event_queue, client))
    logger.info("✅ Error sink emission initialized.")
    return client
