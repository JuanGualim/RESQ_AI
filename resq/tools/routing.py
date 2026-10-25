"""Deterministic routing over the road network (protocol P2, P6.3).

`state` is the dict returned by `resq.world.get_state()`: road segments carry
their verified `status` (falling back to `official_status`), and vehicles carry
`can_ford`. Agents never invent routes; they always ask `best_route`.
"""
from __future__ import annotations

import networkx as nx

from resq.protocol import IMPASSABLE, PASSABLE_ALL, PASSABLE_FORD_ONLY
from resq.schemas import Route

PLACE_TABLES = ("warehouses", "communities", "shelters")


def as_bool(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "t"}


def segment_status(segment: dict) -> str:
    return str(segment.get("status") or segment.get("official_status") or "open")


def can_pass(segment: dict, can_ford: bool) -> bool:
    status = segment_status(segment)
    if status in IMPASSABLE:
        return False
    if status in PASSABLE_ALL:
        return True
    if status in PASSABLE_FORD_ONLY:
        return can_ford
    return False  # unknown status: be safe


def road_node(place_id: str, state: dict) -> str:
    """Road node of a place id (W1, C04, S2) or the id itself if it is already a node."""
    for table in PLACE_TABLES:
        place = state.get(table, {}).get(place_id)
        if place:
            return place["road_node"]
    return place_id


def build_graph(state: dict, can_ford: bool) -> nx.Graph:
    graph = nx.Graph()
    for segment_id, segment in state.get("road_segments", {}).items():
        if can_pass(segment, can_ford):
            origin, destination = segment["origin"], segment["destination"]
            weight = float(segment["distance_km"])
            current = graph.get_edge_data(origin, destination)
            # A simple graph keeps the route contract compact. When the road
            # data contains parallel segments, retain the shortest passable one
            # instead of whichever row happened to be read last.
            if current is None or weight < current["weight"]:
                graph.add_edge(origin, destination, segment_id=segment_id, weight=weight)
    return graph


def _known_road_nodes(state: dict) -> set[str]:
    nodes = set(state.get("road_nodes", {}))
    for segment in state.get("road_segments", {}).values():
        nodes.update((segment["origin"], segment["destination"]))
    for table in PLACE_TABLES:
        nodes.update(place["road_node"] for place in state.get(table, {}).values())
    return nodes


def best_route(origin: str, destination: str, state: dict, vehicle_id: str) -> Route | None:
    """Shortest passable route for that vehicle, or None if there is none."""
    vehicle = state.get("vehicles", {}).get(vehicle_id)
    if vehicle is None:
        raise KeyError(f"unknown vehicle: {vehicle_id}")
    start, end = road_node(origin, state), road_node(destination, state)
    known_nodes = _known_road_nodes(state)
    if start not in known_nodes or end not in known_nodes:
        return None
    if start == end:
        return Route(origin=start, destination=end, nodes=[start], segments=[], distance_km=0.0)
    graph = build_graph(state, as_bool(vehicle.get("can_ford")))
    if start not in graph or end not in graph:
        return None
    try:
        nodes = nx.shortest_path(graph, start, end, weight="weight")
    except nx.NetworkXNoPath:
        return None
    edges = [graph.edges[a, b] for a, b in zip(nodes, nodes[1:])]
    return Route(
        origin=start, destination=end, nodes=nodes,
        segments=[edge["segment_id"] for edge in edges],
        distance_km=round(sum(edge["weight"] for edge in edges), 2),
    )


def reachability(community_id: str, state: dict) -> str:
    """'all' if a non-fording vehicle can reach it, 'ford_only' if only fording ones can, else 'none'."""
    best = "none"
    for vehicle_id, vehicle in state.get("vehicles", {}).items():
        if best_route(vehicle["warehouse_id"], community_id, state, vehicle_id) is None:
            continue
        if not as_bool(vehicle.get("can_ford")):
            return "all"
        best = "ford_only"
    return best
