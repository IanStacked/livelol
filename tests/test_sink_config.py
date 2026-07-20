"""Tests for the sink logging handler and setup (utils/sink_config.py)."""

import logging
import sys

from utils.sink_client import SinkClient
from utils.sink_config import SinkLoggingHandler, setup_sink


def _record(msg, exc_info=None):
    return logging.LogRecord(
        name="cogs.background",
        level=logging.ERROR,
        pathname="background.py",
        lineno=42,
        msg=msg,
        args=(),
        exc_info=exc_info,
        func="update_loop",
    )


def _collecting_client(tmp_path, collected):
    client = SinkClient("http://x", "t", "livelol", buffer_path=str(tmp_path / "b"))
    client.capture = collected.append
    return client


def test_plain_error_log_is_handled(tmp_path):
    collected = []
    handler = SinkLoggingHandler(_collecting_client(tmp_path, collected))
    handler.emit(_record("something failed"))
    ev = collected[0]
    assert ev["handled"] is True
    assert ev["type"] == "ERROR"
    assert ev["fingerprint"] == "background:update_loop:ERROR"
    assert ev["project"] == "livelol"


def test_exception_log_is_unhandled_with_exc_type(tmp_path):
    collected = []
    handler = SinkLoggingHandler(_collecting_client(tmp_path, collected))
    try:
        raise ValueError("boom")
    except ValueError:
        handler.emit(_record("caught it", exc_info=sys.exc_info()))
    ev = collected[0]
    assert ev["handled"] is False
    assert ev["type"] == "ValueError"
    assert ev["fingerprint"] == "background:update_loop:ValueError"


def test_setup_sink_is_noop_without_env(monkeypatch):
    monkeypatch.delenv("SINK_URL", raising=False)
    monkeypatch.delenv("SINK_TOKEN", raising=False)
    assert setup_sink() is None
