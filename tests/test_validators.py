import pytest

from resq.schemas import Assignment, Plan
from resq.tools.validators import critical_minimum_gaps, validate_plan


def assignment(**overrides):
    base = dict(community_id="C04", origin_id="W1", resource="water_20l", quantity=50, vehicle_id="V1",
                route=["T3", "T7"], priority=1, reason="test", evidence=["R012"])
    return Assignment(**{**base, **overrides})


def plan(*assignments, unserved=()):
    return Plan(version=1, assignments=list(assignments), unserved=list(unserved), confidence=0.8)


def rules(violations):
    return [v.split(":")[0] for v in violations]


def test_valid_plan_has_no_violations(state):
    assert validate_plan(plan(assignment()), state) == []


def test_unknown_ids(state):
    assert rules(validate_plan(plan(assignment(community_id="C99")), state)) == ["P8.1"]
    assert "P8.1" in rules(validate_plan(plan(assignment(vehicle_id="V99")), state))


def test_vehicle_must_start_at_home_warehouse(state):
    violations = validate_plan(plan(assignment(vehicle_id="V5", route=["T3", "T7"])), state)
    assert any(v.startswith("P6.1") and "V5" in v for v in violations)


def test_single_load_over_capacity(state):
    violations = validate_plan(plan(assignment(vehicle_id="V3", quantity=100)), state)  # 2000 kg > 1200 kg
    assert any(v.startswith("P6.2") and "V3" in v for v in violations)


def test_total_load_over_two_trips(state):
    trips = [assignment(vehicle_id="V3", quantity=50) for _ in range(3)]  # 3 x 1000 kg > 2 x 1200 kg
    assert any("total load" in v for v in validate_plan(plan(*trips), state))


def test_inventory_exceeded(state):
    stock = state["inventory"]["W1"]["medical_kit"]["quantity"]
    violations = validate_plan(plan(assignment(resource="medical_kit", quantity=stock + 1)), state)
    assert any(v.startswith("P6.4") for v in violations)


def test_route_through_flooded_segment_for_non_fording_vehicle(state):
    state["road_segments"]["T7"]["status"] = "flooded"
    violations = validate_plan(plan(assignment()), state)
    assert any(v.startswith("P2") and "T7" in v for v in violations)
    assert validate_plan(plan(assignment(vehicle_id="V2")), state) == []


def test_disconnected_or_wrong_route(state):
    assert any(v.startswith("P6.3") for v in validate_plan(plan(assignment(route=["T7", "T3"])), state))
    assert any(v.startswith("P6.3") for v in validate_plan(plan(assignment(route=["T3"])), state))
    assert any(v.startswith("P6.3") for v in validate_plan(plan(assignment(route=[])), state))


def test_connected_but_non_shortest_route_is_rejected(state):
    violations = validate_plan(plan(assignment(route=["T3", "T6", "T8"])), state)
    assert any(v.startswith("P6.3") and "shortest" in v for v in violations)


def test_unserved_community_with_assignments(state):
    assert rules(validate_plan(plan(assignment(), unserved=["C04"]), state)) == ["P5.4"]


def test_critical_community_short_of_essentials(state):
    state["communities"]["C04"].update(risk_level="critical", needs={"water_20l": 100, "food_kit": 100})
    state["communities"]["C14"].update(risk_level="medium", needs={"water_20l": 10})
    medium = assignment(community_id="C14", route=["T3"], quantity=5)
    violations = validate_plan(plan(assignment(quantity=60), medium), state)
    assert any("critical C04 gets 0 food_kit" in v for v in violations)
    assert any("C14" in v and "served while critical" in v for v in violations)


def test_reachable_critical_community_cannot_bypass_minimum_as_unserved(state):
    state["communities"]["C04"].update(
        risk_level="critical", reachability="all", needs={"water_20l": 100, "food_kit": 100}
    )
    violations = validate_plan(plan(unserved=["C04"]), state)
    assert any("critical C04 gets 0 water_20l" in v for v in violations)


def test_critical_community_with_enough_essentials(state):
    state["communities"]["C04"].update(risk_level="critical", needs={"water_20l": 100, "food_kit": 100})
    plan_ok = plan(assignment(quantity=50), assignment(resource="food_kit", quantity=50, vehicle_id="V2"))
    assert validate_plan(plan_ok, state) == []


def test_quantity_must_be_positive():
    with pytest.raises(ValueError):
        assignment(quantity=0)


def test_critical_minimum_capacity_only_counts_p5_2_essentials(state):
    for community in state["communities"].values():
        community.update(risk_level="low", reachability="all", needs={})
    state["communities"]["C04"].update(
        risk_level="critical",
        needs={"water_20l": 1, "food_kit": 1, "medical_kit": 100_000},
    )
    assert critical_minimum_gaps(state) == []
