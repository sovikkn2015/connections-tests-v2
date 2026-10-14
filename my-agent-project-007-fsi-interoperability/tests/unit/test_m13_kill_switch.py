"""Unit tests for ``m13_fix_bridge.client.kill_switch`` — Spec §R7."""

from __future__ import annotations

import json
import os

import pytest

from m13_fix_bridge.client.kill_switch import KillSwitch


def test_initial_state_neither_blocked(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    assert ks.is_blocked("brokerx") is False
    snap = ks.snapshot()
    assert snap["global"]["on"] is False
    assert snap["venues"] == {}


def test_global_kill_blocks_all_venues(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    ks.set_global(True, reason="global-halt-001", actor_aid="aid-sup-01")
    assert ks.is_blocked("brokerx") is True
    assert ks.is_blocked("broker_y") is True


def test_venue_kill_blocks_only_that_venue(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    ks.set_venue("brokerx", True, reason="venue-degraded-001", actor_aid="aid-sup-01")
    assert ks.is_blocked("brokerx") is True
    assert ks.is_blocked("broker_y") is False


def test_state_persists_across_instances(tmp_path) -> None:
    """R7.1 — survives restart."""
    p = str(tmp_path / "ks.json")
    ks1 = KillSwitch(p)
    ks1.set_global(True, reason="global-halt-001", actor_aid="aid-sup-01")
    ks2 = KillSwitch(p)
    assert ks2.is_blocked("brokerx") is True
    assert ks2.global_state()["on"] is True


def test_state_file_is_json(tmp_path) -> None:
    p = str(tmp_path / "ks.json")
    ks = KillSwitch(p)
    ks.set_venue("brokerx", True, reason="test-reason-0001", actor_aid="aid-sup")
    with open(p) as fh:
        data = json.load(fh)
    assert data["venues"]["brokerx"]["on"] is True


def test_toggle_off_clears_block(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    ks.set_global(True, reason="incident-001", actor_aid="aid-sup")
    ks.set_global(False, reason="incident-resolved-001", actor_aid="aid-sup")
    assert ks.is_blocked("brokerx") is False


def test_venue_kill_overridden_by_global(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    ks.set_venue("brokerx", False, reason="no-issue-here", actor_aid="aid-sup")
    ks.set_global(True, reason="global-emergency-001", actor_aid="aid-sup")
    assert ks.is_blocked("brokerx") is True


def test_snapshot_round_trip(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    ks.set_global(True, reason="x" * 10, actor_aid="aid-a")
    ks.set_venue("brokerx", True, reason="y" * 10, actor_aid="aid-b")
    snap = ks.snapshot()
    assert snap["global"]["reason"] == "x" * 10
    assert snap["venues"]["brokerx"]["reason"] == "y" * 10


def test_no_temp_file_lingers_after_write(tmp_path) -> None:
    p = str(tmp_path / "ks.json")
    ks = KillSwitch(p)
    ks.set_global(True, reason="halt-ref-0001", actor_aid="aid-sup")
    assert os.path.exists(p)
    assert not os.path.exists(p + ".tmp")


def test_corrupt_file_reads_as_empty(tmp_path) -> None:
    p = str(tmp_path / "ks.json")
    # Write garbage first, then wrap with KillSwitch.
    with open(p, "w") as fh:
        fh.write("not json{}{")
    ks = KillSwitch(p)
    # Recovers cleanly — returns no blocks until explicitly set.
    assert ks.is_blocked("brokerx") is False
