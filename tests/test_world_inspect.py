"""Point-in-time state, per-object timelines, audit and the inspection CLI."""
from resq import scenario, world
from resq.world.__main__ import main


def block_t6():
    world.apply_event({"type": "segment_status_verified", "id": "T6", "status": "open", "confidence": 1.0,
                       "evidence": ["R029"], "source": "agent", "by": "reconciler", "ts": "2020-11-05T09:45:00"})
    world.apply_event({"type": "segment_blocked", "id": "T6", "source": "coordinator", "ts": "2020-11-05T10:05:00"})


def test_state_as_of_ignores_later_observations(state):
    block_t6()
    assert world.get_state()["road_segments"]["T6"]["status"] == "blocked"
    assert world.get_state(as_of="2020-11-05T10:00")["road_segments"]["T6"]["status"] == "open"
    assert "status" not in world.get_state(as_of="2020-11-05T09:00")["road_segments"]["T6"]


def test_as_of_includes_an_observation_at_that_exact_minute(state):
    block_t6()
    assert world.get_state(as_of="2020-11-05T10:05")["road_segments"]["T6"]["status"] == "blocked"


def test_timeline_is_in_observation_order(state):
    # written in the opposite order of observation time
    world.apply_event({"type": "segment_blocked", "id": "T6", "source": "coordinator", "ts": "2020-11-05T10:05:00"})
    world.apply_event({"type": "segment_status_verified", "id": "T6", "status": "open", "source": "agent",
                       "by": "reconciler", "ts": "2020-11-05T09:45:00", "evidence": ["R029"]})
    rows = world.timeline("T6")
    assert [(r["at"], r["status"], r["source"]) for r in rows] == [
        ("2020-11-05T09:45:00", "open", "agent"), ("2020-11-05T10:05:00", "blocked", "coordinator")]
    assert rows[0]["evidence"] == ["R029"]
    assert world.timeline("T99") == []


def test_audit_records_every_mutation(state):
    before = len(world.audit())
    block_t6()
    entries = world.audit()
    assert len(entries) == before + 2
    assert [e["seq"] for e in entries] == sorted(e["seq"] for e in entries)
    assert entries[-1]["kind"] == "assertFact" and "road_segment:resq:T6.status" in entries[-1]["summary"]


def test_cli_commands(state, capsys):
    block_t6()
    world.save_plan({"version": 1, "assignments": [], "escalated": False}, ts=scenario.now())
    assert main(["summary"]) == 0
    assert main(["timeline", "T6"]) == 0
    assert main(["state", "--at", "2020-11-05T10:00"]) == 0
    assert main(["audit", "--last", "3"]) == 0
    out = capsys.readouterr().out
    assert "latest plan: v1" in out
    assert "blocked" in out and "coordinator" in out
    assert "T6    open" in out
