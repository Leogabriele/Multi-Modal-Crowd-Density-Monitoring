"""
Tests for server.py logic that don't require a camera, MQTT broker, or
real hardware. Run: python3 tests/test_server_logic.py

For the MQTT round-trip test (requires a local Mosquitto broker running),
see docs/RESULTS_LOG.md for how that was verified manually.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import tier_from_pct, SharedState


def test_tier_boundaries():
    assert tier_from_pct(0) == "normal"
    assert tier_from_pct(59.9) == "normal"
    assert tier_from_pct(60) == "busy"
    assert tier_from_pct(89.9) == "busy"
    assert tier_from_pct(90) == "critical"
    assert tier_from_pct(150) == "critical"  # over capacity


def test_shared_state():
    s = SharedState()
    s.update(10.0, 10.0, "normal")
    snap = s.snapshot()
    assert snap["count"] == 10.0
    assert snap["tier"] == "normal"

    s.update(95.0, 95.0, "critical")
    snap2 = s.snapshot()
    assert snap2["tier"] == "critical"
    assert snap2["last_updated"] > snap["last_updated"]


if __name__ == "__main__":
    test_tier_boundaries()
    test_shared_state()
    print("All server logic tests passed.")
