"""Tests for the owned error-sink client (utils/sink_client.py)."""

import json

from utils.sink_client import SinkClient


def _raise_down(*_):
    raise OSError("sink down")


def _client(tmp_path):
    return SinkClient(
        base_url="http://127.0.0.1:9",
        token="t",
        project="livelol",
        buffer_path=str(tmp_path / "buffer.jsonl"),
    )


def test_build_event_schema(tmp_path):
    c = _client(tmp_path)
    ev = c.build_event(
        "ValueError", "boom", handled=False, fingerprint="m:f:ValueError"
    )
    assert ev["project"] == "livelol"
    assert ev["type"] == "ValueError"
    assert ev["message"] == "boom"
    assert ev["handled"] is False
    assert ev["fingerprint"] == "m:f:ValueError"
    assert ev["id"]
    assert set(ev) == {
        "id",
        "project",
        "ts",
        "release",
        "type",
        "message",
        "fingerprint",
        "handled",
        "fix_ref",
    }


def test_capture_never_raises_and_buffers_when_sink_down(tmp_path):
    c = _client(tmp_path)
    c._post = _raise_down
    c.capture(c.build_event("ValueError", "x"))  # must not raise
    lines = (tmp_path / "buffer.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["type"] == "ValueError"


def test_flush_replays_and_clears(tmp_path):
    c = _client(tmp_path)
    c._post = _raise_down
    c.capture(c.build_event("A", "1"))
    c.capture(c.build_event("B", "2"))
    assert len((tmp_path / "buffer.jsonl").read_text().splitlines()) == 2

    sent = []

    def _collect(events):
        sent.extend(events)

    c._post = _collect
    replayed = c.flush()
    assert replayed == 2
    assert [e["type"] for e in sent] == ["A", "B"]
    assert (tmp_path / "buffer.jsonl").read_text().strip() == ""


def test_flush_quarantines_corrupt_line_and_replays_rest(tmp_path):
    c = _client(tmp_path)
    c._post = _raise_down
    c.capture(c.build_event("A", "1"))
    buf = tmp_path / "buffer.jsonl"
    with buf.open("a") as fh:
        fh.write("{not json\n")
    c.capture(c.build_event("B", "2"))

    sent = []
    c._post = lambda events: sent.extend(events)
    replayed = c.flush()
    assert replayed == 2
    assert [e["type"] for e in sent] == ["A", "B"]
    assert buf.read_text().strip() == ""
    quarantined = (tmp_path / "buffer.quarantine.jsonl").read_text().splitlines()
    assert quarantined == ["{not json"]


def test_flush_quarantines_non_dict_json_line(tmp_path):
    c = _client(tmp_path)
    c._post = _raise_down
    c.capture(c.build_event("A", "1"))
    buf = tmp_path / "buffer.jsonl"
    with buf.open("a") as fh:
        fh.write("42\n")  # valid JSON, not an event object
        fh.write('["list"]\n')

    sent = []
    c._post = lambda events: sent.extend(events)
    assert c.flush() == 1
    assert [e["type"] for e in sent] == ["A"]
    assert buf.read_text().strip() == ""
    quarantined = (tmp_path / "buffer.quarantine.jsonl").read_text().splitlines()
    assert quarantined == ["42", '["list"]']


def test_flush_clears_buffer_of_only_corrupt_lines(tmp_path):
    c = _client(tmp_path)
    buf = tmp_path / "buffer.jsonl"
    buf.write_text("garbage one\ngarbage two\n")

    def _fail(_):
        raise AssertionError("nothing valid to post")

    c._post = _fail
    assert c.flush() == 0
    assert buf.read_text().strip() == ""
    quarantined = (tmp_path / "buffer.quarantine.jsonl").read_text().splitlines()
    assert quarantined == ["garbage one", "garbage two"]


def test_flush_keeps_buffer_and_quarantine_untouched_while_sink_down(tmp_path):
    c = _client(tmp_path)
    c._post = _raise_down
    c.capture(c.build_event("A", "1"))
    buf = tmp_path / "buffer.jsonl"
    with buf.open("a") as fh:
        fh.write("{not json\n")
    before = buf.read_text()

    c.capture(c.build_event("B", "2"))  # flush inside fails; must not lose lines
    after = buf.read_text().splitlines()
    assert before.splitlines() == after[:2]  # original lines intact, in order
    assert len(after) == 3  # plus the newly buffered event
    # quarantine only happens on a successful drain - no file while the sink is down
    assert not (tmp_path / "buffer.quarantine.jsonl").exists()


def test_buffer_bound_drops_oldest(tmp_path, monkeypatch):
    monkeypatch.setattr("utils.sink_client.BUFFER_MAX_LINES", 5)
    c = _client(tmp_path)
    c._post = _raise_down
    for i in range(8):
        c.capture(c.build_event("E", str(i)))
    lines = (tmp_path / "buffer.jsonl").read_text().splitlines()
    assert len(lines) <= 5
    # oldest dropped: the last event survives, the first does not
    messages = [json.loads(ln)["message"] for ln in lines]
    assert "7" in messages
    assert "0" not in messages
