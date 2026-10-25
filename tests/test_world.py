import pytest

from resq import scenario, world


def test_seed_is_idempotent(state):
    again = world.seed(scenario.load_tables(), at=scenario.data_time())
    assert again["written"] == 0


def test_state_has_every_table(state):
    assert len(state["communities"]) == 14
    assert len(state["road_segments"]) == 21
    assert len(state["road_nodes"]) == 16
    assert state["road_nodes"]["N01"] == {"id": "N01", "lat": 15.47, "lon": -88.84}
    assert state["inventory"]["W1"]["water_20l"]["unit_weight_kg"] == 20.0
    assert state["road_segments"]["T7"]["official_status"] == "open"
    assert "status" not in state["road_segments"]["T7"]


def test_verified_fact_overlays_state(state):
    world.apply_event({"type": "segment_status_verified", "id": "T7", "status": "flooded", "confidence": 0.85,
                       "evidence": ["R008", "R013"], "source": "agent", "by": "reconciler", "ts": "2020-11-05T08:15:00"})
    segment = world.get_state()["road_segments"]["T7"]
    assert segment["status"] == "flooded"
    assert segment["status_confidence"] == 0.85
    assert segment["status_evidence"] == ["R008", "R013"]


def test_most_recent_observation_wins(state):
    world.apply_event({"type": "segment_blocked", "id": "T6", "source": "coordinator", "ts": "2020-11-05T10:05:00"})
    # an older report-based conclusion written later must not undo the coordinator block
    world.apply_event({"type": "segment_status_verified", "id": "T6", "status": "open", "confidence": 0.7,
                       "source": "agent", "by": "reconciler", "ts": "2020-11-05T09:45:00"})
    assert world.get_state()["road_segments"]["T6"]["status"] == "blocked"
    world.apply_event({"type": "segment_reopened", "id": "T6", "source": "coordinator", "ts": "2020-11-05T10:10:00"})
    assert world.get_state()["road_segments"]["T6"]["status"] == "open"


def test_same_event_twice_is_a_no_op(state):
    event = {"type": "segment_blocked", "id": "T6", "source": "coordinator", "ts": "2020-11-05T10:05:00"}
    world.apply_event(event)
    world.apply_event(event)
    assert len(world.history()) == 1


def test_history_is_ordered(state):
    world.apply_event({"type": "segment_blocked", "id": "T6", "source": "coordinator", "ts": "2020-11-05T10:05:00"})
    world.apply_event({"type": "segment_blocked", "id": "T3", "source": "coordinator", "ts": "2020-11-05T10:10:00"})
    seqs = [event["seq"] for event in world.history()]
    assert seqs == sorted(seqs)
    assert [event["id"] for event in world.history()] == ["T6", "T3"]


def test_events_need_type_and_ts():
    with pytest.raises(ValueError):
        world.apply_event({"type": "nonsense", "id": "T1", "ts": "2020-11-05T10:00:00"})
    with pytest.raises(ValueError):
        world.apply_event({"type": "segment_blocked", "id": "T1"})


def test_plans_are_versioned(state):
    world.save_plan({"version": 1, "assignments": [], "confidence": 0.7}, ts="2020-11-05T10:00:00")
    world.save_plan({"version": 2, "assignments": [], "confidence": 0.6}, ts="2020-11-05T10:05:00")
    assert world.latest_plan()["version"] == 2


def test_scenario_clock_moves_with_coordinator_events(state):
    assert scenario.now() == "2020-11-05T10:00:00"
    assert scenario.next_coordinator_ts() == "2020-11-05T10:05:00"
    world.apply_event({"type": "segment_blocked", "id": "T6", "source": "coordinator", "ts": scenario.next_coordinator_ts()})
    assert scenario.now() == "2020-11-05T10:05:00"
