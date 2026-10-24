import pytest

from resq.tools.routing import best_route, can_pass, reachability, road_node


def set_status(state, segment_id, status):
    state["road_segments"][segment_id]["status"] = status


def test_route_on_official_network(state):
    route = best_route("W1", "C04", state, "V1")
    assert route.segments == ["T3", "T7"]
    assert route.nodes == ["N01", "N04", "N08"]
    assert route.distance_km == pytest.approx(8.2)


def test_place_ids_resolve_to_road_nodes(state):
    assert road_node("C07", state) == "N11"
    assert road_node("W2", state) == "N02"
    assert road_node("N05", state) == "N05"


def test_flooded_segment_only_for_fording_vehicles(state):
    set_status(state, "T7", "flooded")
    assert best_route("W1", "C04", state, "V2").segments == ["T3", "T7"]  # V2 can ford
    assert best_route("W1", "C04", state, "V1").segments == ["T3", "T6", "T8"]  # V1 detours


def test_blocked_segment_is_avoided_by_everyone(state):
    set_status(state, "T7", "blocked")
    assert "T7" not in best_route("W1", "C04", state, "V2").segments


def test_no_route_returns_none(state):
    for segment_id in ("T6", "T7"):
        set_status(state, segment_id, "closed")
    assert best_route("W1", "C04", state, "V1") is None


def test_officially_flooded_t11_stops_normal_vehicles(state):
    assert "T11" not in best_route("W1", "C07", state, "V1").segments
    state["road_segments"]["T12"]["status"] = "closed"
    assert best_route("W1", "C07", state, "V2").segments[-1] == "T11"  # V2 can ford T11
    state["road_segments"]["T12"]["status"] = "open"
    state["road_segments"]["T9"]["status"] = "passable_4x4"
    assert best_route("W1", "C07", state, "V1").segments[-2:] == ["T20", "T21"]


def test_same_node_is_an_empty_route(state):
    assert best_route("W1", "N01", state, "V1").segments == []


def test_unknown_vehicle_raises(state):
    with pytest.raises(KeyError):
        best_route("W1", "C04", state, "V99")


def test_reachability_levels(state):
    assert reachability("C04", state) == "all"
    for segment_id in ("T6", "T8", "T9", "T10", "T12"):
        set_status(state, segment_id, "flooded")
    set_status(state, "T7", "flooded")
    assert reachability("C04", state) == "ford_only"
    for segment_id in ("T6", "T7"):
        set_status(state, segment_id, "closed")
    assert reachability("C04", state) == "none"


@pytest.mark.parametrize("status, can_ford, expected", [
    ("open", False, True), ("damaged", False, True), ("flooded", False, False), ("flooded", True, True),
    ("passable_4x4", True, True), ("uncertain", False, False), ("closed", True, False), ("blocked", True, False),
    ("mystery", True, False),
])
def test_can_pass(status, can_ford, expected):
    assert can_pass({"status": status}, can_ford) is expected
