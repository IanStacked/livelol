"""Tests for the heartbeat liveness classification (scripts/heartbeat_check.py)."""

from scripts.heartbeat_check import DOWN_MAX, GREEN_MAX, classify_liveness


def test_fresh_and_connected_is_green():
    liveness, _ = classify_liveness(age_seconds=30, connected=True)
    assert liveness == "green"


def test_fresh_but_disconnected_is_degraded():
    liveness, detail = classify_liveness(age_seconds=30, connected=False)
    assert liveness == "degraded"
    assert "not connected" in detail


def test_stale_but_connected_is_degraded():
    # Between GREEN_MAX and DOWN_MAX -> degraded (beating, but stale).
    age = (GREEN_MAX + DOWN_MAX) / 2
    liveness, detail = classify_liveness(age_seconds=age, connected=True)
    assert liveness == "degraded"
    assert "stale" in detail


def test_very_stale_is_down_even_if_flagged_connected():
    liveness, _ = classify_liveness(age_seconds=DOWN_MAX + 1, connected=True)
    assert liveness == "down"


def test_green_max_boundary_is_still_green():
    # The staleness check is strictly greater-than, so exactly GREEN_MAX is green.
    liveness, _ = classify_liveness(age_seconds=GREEN_MAX, connected=True)
    assert liveness == "green"
