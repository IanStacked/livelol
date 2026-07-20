"""Wire the owned error sink in beside Sentry (utils/sentry_config.py).

A logging handler mirrors ERROR-level records to the sink, so the sink and Sentry
capture the same events (dual-run; Sentry is cut last). Emission runs on a background
thread via QueueListener - the POST must never block the Discord event loop.

Fault semantics for the incident pipeline: a record carrying exception info is emitted
as UNHANDLED (a real fault the incident poller should surface as a TODO finding); a
plain error log with no exception is emitted as handled. The poller only escalates
unhandled groups, so this is what decides which logs become auto-fix candidates.
"""

from __future__ import annotations

import logging
import os
import queue
from logging.handlers import QueueHandler, QueueListener

from utils.sink_client import SinkClient

# The sink identity MUST match what the incident poller queries: the fleet directory
# name, which is `livelol` (not the legacy `leaguehelper` that scripts/health.sh still
# uses). Emit under the wrong name and the poller sees nothing.
SINK_PROJECT = "livelol"

logger = logging.getLogger(__name__)

_listener: QueueListener | None = None


class SinkLoggingHandler(logging.Handler):
    """Forward each emitted log record to the sink as one event."""

    def __init__(self, client: SinkClient) -> None:
        super().__init__(level=logging.ERROR)
        self._client = client

    def emit(self, record: logging.LogRecord) -> None:
        """Build a sink event from the record and capture it."""
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
            self._client.capture(event)
        except Exception:
            self.handleError(record)


def setup_sink() -> SinkClient | None:
    """Attach the sink handler to the root logger if configured; return the client.

    No-op when SINK_URL / SINK_TOKEN are absent, mirroring the Sentry DSN-absent path.
    """
    global _listener
    url = os.getenv("SINK_URL")
    token = os.getenv("SINK_TOKEN")
    if not url or not token:
        logger.warning("⚠️ SINK_URL/SINK_TOKEN not set. Error sink is DISABLED.")
        return None
    if _listener is not None:
        return None  # already initialized

    client = SinkClient(base_url=url, token=token, project=SINK_PROJECT)

    # QueueHandler enqueues ERROR+ records cheaply on the calling (event-loop) thread;
    # the QueueListener drains them on a background thread where the blocking POST is
    # safe. This is what keeps a sink round-trip off the Discord event loop.
    log_queue: queue.SimpleQueue = queue.SimpleQueue()
    q_handler = QueueHandler(log_queue)
    q_handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(q_handler)

    _listener = QueueListener(
        log_queue, SinkLoggingHandler(client), respect_handler_level=True
    )
    _listener.start()
    logger.info("✅ Error sink emission initialized.")
    return client
