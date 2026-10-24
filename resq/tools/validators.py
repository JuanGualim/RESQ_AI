"""Hard rules the Critic enforces in code (protocol P2, P5, P6, P8).

`validate_plan(plan, state)` returns one message per violation, each starting
with the protocol rule and citing the IDs involved. An empty list = valid.
"""
from __future__ import annotations

from collections import defaultdict

from resq.protocol import CRITICAL_ESSENTIALS, CRITICAL_MIN_SHARE, MAX_TRIPS_PER_VEHICLE
from resq.schemas import Assignment, Plan
from resq.tools.routing import as_bool, can_pass, road_node


def validate_plan(plan: Plan, state: dict) -> list[str]:
    violations: list[str] = []
    for index, assignment in enumerate(plan.assignments, start=1):
        violations += _check_assignment(index, assignment, state)
    violations += _check_vehicle_loads(plan, state)
    violations += _check_inventory(plan, state)
    violations += _check_unserved(plan)
    violations += _check_critical_first(plan, state)
    return violations


def _label(index: int, a: Assignment) -> str:
    return f"assignment {index} ({a.community_id} {a.resource} x{a.quantity} by {a.vehicle_id})"


def _weight(a: Assignment, state: dict) -> float:
    stock = state.get("inventory", {}).get(a.origin_id, {}).get(a.resource)
    return a.quantity * float(stock["unit_weight_kg"]) if stock else 0.0


def _check_assignment(index: int, a: Assignment, state: dict) -> list[str]:
    label = _label(index, a)
    problems = []
    if a.community_id not in state.get("communities", {}):
        problems.append(f"P8.1: {label} references unknown community {a.community_id}")
    if a.origin_id not in state.get("warehouses", {}):
        problems.append(f"P8.1: {label} references unknown warehouse {a.origin_id}")
    vehicle = state.get("vehicles", {}).get(a.vehicle_id)
    if vehicle is None:
        problems.append(f"P8.1: {label} references unknown vehicle {a.vehicle_id}")
    if a.resource not in state.get("inventory", {}).get(a.origin_id, {}):
        problems.append(f"P6.4: {label}: warehouse {a.origin_id} has no {a.resource}")
    if problems:
        return problems

    if vehicle["warehouse_id"] != a.origin_id:
        problems.append(f"P6.1: {label}: {a.vehicle_id} belongs to {vehicle['warehouse_id']}, not {a.origin_id}")
    weight = _weight(a, state)
    if weight > float(vehicle["capacity_kg"]):
        problems.append(f"P6.2: {label}: load {weight:.0f} kg exceeds {a.vehicle_id} capacity {vehicle['capacity_kg']} kg")
    problems += _check_route(label, a, vehicle, state)
    return problems


def _check_route(label: str, a: Assignment, vehicle: dict, state: dict) -> list[str]:
    start, end = road_node(a.origin_id, state), road_node(a.community_id, state)
    if not a.route:
        return [] if start == end else [f"P6.3: {label} has no route from {start} to {end}"]
    segments = state.get("road_segments", {})
    problems, node = [], start
    for segment_id in a.route:
        segment = segments.get(segment_id)
        if segment is None:
            return [f"P8.1: {label}: route uses unknown segment {segment_id}"]
        if node not in (segment["origin"], segment["destination"]):
            return [f"P6.3: {label}: route is not connected at {segment_id} (expected a segment from {node})"]
        if not can_pass(segment, as_bool(vehicle.get("can_ford"))):
            status = segment.get("status") or segment.get("official_status")
            problems.append(f"P2: {label}: {a.vehicle_id} cannot use {segment_id} ({status})")
        node = segment["destination"] if node == segment["origin"] else segment["origin"]
    if node != end:
        problems.append(f"P6.3: {label}: route ends at {node}, not at {a.community_id} ({end})")
    return problems


def _check_vehicle_loads(plan: Plan, state: dict) -> list[str]:
    loads: dict[str, float] = defaultdict(float)
    for a in plan.assignments:
        loads[a.vehicle_id] += _weight(a, state)
    problems = []
    for vehicle_id, load in sorted(loads.items()):
        vehicle = state.get("vehicles", {}).get(vehicle_id)
        if vehicle and load > MAX_TRIPS_PER_VEHICLE * float(vehicle["capacity_kg"]):
            limit = MAX_TRIPS_PER_VEHICLE * float(vehicle["capacity_kg"])
            problems.append(f"P6.2: {vehicle_id} total load {load:.0f} kg exceeds {MAX_TRIPS_PER_VEHICLE} trips x {vehicle['capacity_kg']} kg = {limit:.0f} kg")
    return problems


def _check_inventory(plan: Plan, state: dict) -> list[str]:
    used: dict[tuple[str, str], int] = defaultdict(int)
    for a in plan.assignments:
        used[(a.origin_id, a.resource)] += a.quantity
    problems = []
    for (warehouse_id, resource), quantity in sorted(used.items()):
        stock = state.get("inventory", {}).get(warehouse_id, {}).get(resource)
        if stock and quantity > int(stock["quantity"]):
            problems.append(f"P6.4: {warehouse_id} {resource}: plan uses {quantity}, stock is {stock['quantity']}")
    return problems


def _check_unserved(plan: Plan) -> list[str]:
    served = {a.community_id for a in plan.assignments}
    return [f"P5.4: {c} is listed as unserved but has assignments" for c in sorted(served & set(plan.unserved))]


def _delivered(plan: Plan) -> dict[tuple[str, str], int]:
    delivered: dict[tuple[str, str], int] = defaultdict(int)
    for a in plan.assignments:
        delivered[(a.community_id, a.resource)] += a.quantity
    return delivered


def _check_critical_first(plan: Plan, state: dict) -> list[str]:
    """P5.2: reachable critical communities get >= 50% of water and food before any medium one gets anything."""
    communities = state.get("communities", {})
    delivered = _delivered(plan)
    short = []
    for community_id, community in sorted(communities.items()):
        if community.get("risk_level") != "critical" or community_id in plan.unserved:
            continue
        needs = community.get("needs") or {}
        for resource in CRITICAL_ESSENTIALS:
            need = int(needs.get(resource, 0))
            got = delivered.get((community_id, resource), 0)
            if need and got < CRITICAL_MIN_SHARE * need:
                short.append(f"P5.2: critical {community_id} gets {got} {resource}, below {CRITICAL_MIN_SHARE:.0%} of its need {need}")
    if not short:
        return []
    medium_served = sorted({a.community_id for a in plan.assignments
                            if communities.get(a.community_id, {}).get("risk_level") in {"medium", "low"}})
    if medium_served:
        short.append(f"P5.2: medium/low communities {', '.join(medium_served)} are served while critical ones are short")
    return short
