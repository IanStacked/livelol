"""Tests for the sink logging handler and setup (utils/sink_config.py).

These drive events through a real Logger (not handler.emit in isolation), so they
exercise the wired path: logger.error -> logging framework -> SinkLoggingHandler.emit,
with the record's exc_info intact. That is the path bot.py actually uses.
"""

import logging
import queue

from utils.sink_client import SinkClient
from utils.sink_config import SinkLoggingHandler, setup_sink


def _wired_logger(tmp_path):
    q = queue.SimpleQueue()
    client = SinkClient("http://x", "t", "livelol", buffer_path=str(tmp_path / "b"))
    log = logging.getLogger(f"sink_test_{id(q)}")
    log.handlers.clear()
    log.addHandler(SinkLoggingHandler(q, client))
    log.setLevel(logging.ERROR)
    log.propagate = False
    return log, q


def test_plain_error_log_is_handled(tmp_path):
    log, q = _wired_logger(tmp_path)
    log.error("something failed")
    ev = q.get_nowait()
    assert ev["handled"] is True
    assert ev["type"] == "ERROR"
    assert ev["fingerprint"].endswith(":ERROR")
    assert ev["project"] == "livelol"


def test_exception_log_through_logger_is_unhandled_with_exc_type(tmp_path):
    log, q = _wired_logger(tmp_path)
    try:
        raise ValueError("boom")
    except ValueError:
        log.error("caught it", exc_info=True)
    ev = q.get_nowait()
    assert ev["handled"] is False
    assert ev["type"] == "ValueError"
    assert ev["fingerprint"].endswith(":ValueError")


def test_setup_sink_is_noop_without_env(monkeypatch):
    monkeypatch.delenv("SINK_URL", raising=False)
    monkeypatch.delenv("SINK_TOKEN", raising=False)
    assert setup_sink() is None
