"""Hard rules the Critic enforces in code (protocol P2, P5, P6, P8).

`validate_plan(plan, state)` returns one message per violation, each starting
with the protocol rule and citing the IDs involved. An empty list = valid.
"""
from __future__ import annotations

import math
from collections import defaultdict

from resq.protocol import CRITICAL_ESSENTIALS, CRITICAL_MIN_SHARE, MAX_TRIPS_PER_VEHICLE, PRIORITY_GAP, TIERS
from resq.schemas import Assignment, Plan
from resq.tools.routing import as_bool, best_route, can_pass, road_node


def validate_plan(plan: Plan, state: dict) -> list[str]:
    violations: list[str] = []
    for index, assignment in enumerate(plan.assignments, start=1):
        violations += _check_assignment(index, assignment, state)
    violations += _check_vehicle_loads(plan, state)
    violations += _check_inventory(plan, state)
    violations += _check_unserved(plan)
    violations += _check_critical_first(plan, state)
    violations += _check_priority_order(plan, state)
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
    if not problems:
        expected = best_route(a.origin_id, a.community_id, state, a.vehicle_id)
        if expected is None:
            problems.append(f"P6.3: {label}: no passable route exists from {start} to {end}")
        elif a.route != expected.segments:
            expected_text = ", ".join(expected.segments) or "an empty route"
            problems.append(f"P6.3: {label}: route is not the shortest passable route (expected {expected_text})")
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
        if community.get("risk_level") != "critical" or community.get("reachability") == "none":
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


def _coverage(plan: Plan, community_id: str, resource: str, state: dict) -> float | None:
    need = int(state["communities"][community_id].get("needs", {}).get(resource, 0))
    if not need:
        return None
    return sum(a.quantity for a in plan.assignments if a.community_id == community_id and a.resource == resource) / need


REACH_ORDER = {"all": 0, "ford_only": 1, "none": 2}


def _check_priority_order(plan: Plan, state: dict) -> list[str]:
    """P5.1: a clearly higher-risk community never gets clearly less water or food than a lower-risk one.

    Pairs where the higher-risk community is harder to reach (ford_only vs all) are exempt: a
    different, smaller part of the fleet limits it.
    """
    ranked = sorted(((cid, c) for cid, c in state.get("communities", {}).items() if c.get("needs")),
                    key=lambda item: item[1].get("risk_score", 0), reverse=True)
    problems = []
    for i, (high_id, high) in enumerate(ranked):
        if high.get("reachability") == "none":
            continue
        for low_id, low in ranked[i + 1:]:
            if high.get("risk_score", 0) - low.get("risk_score", 0) < PRIORITY_GAP:
                continue
            if REACH_ORDER.get(high.get("reachability"), 0) > REACH_ORDER.get(low.get("reachability"), 0):
                continue
            for resource in CRITICAL_ESSENTIALS:
                high_cov, low_cov = _coverage(plan, high_id, resource, state), _coverage(plan, low_id, resource, state)
                if high_cov is not None and low_cov is not None and high_cov + 0.1 < low_cov:
                    problems.append(f"P5.1: {high_id} (risk {high['risk_score']}) gets {high_cov:.0%} of its {resource} need "
                                    f"while lower-risk {low_id} (risk {low['risk_score']}) gets {low_cov:.0%}")
                    break
    return problems


def critical_minimum_gaps(state: dict) -> list[str]:
    """Can P5.2 be met at all for water and food at their minimum shares?"""
    minimum = {resource: TIERS["minimum"][resource] for resource in CRITICAL_ESSENTIALS}
    critical = {cid: c for cid, c in state.get("communities", {}).items()
                if c.get("risk_level") == "critical" and c.get("reachability") in ("all", "ford_only")}
    weights: dict[str, float] = {}
    for items in state.get("inventory", {}).values():
        for resource, item in items.items():
            weights[resource] = float(item["unit_weight_kg"])
    gaps = []
    stock = defaultdict(int)
    for items in state.get("inventory", {}).values():
        for resource, item in items.items():
            stock[resource] += int(item["quantity"])
    for resource in CRITICAL_ESSENTIALS:
        required = sum(math.ceil(int(c.get("needs", {}).get(resource, 0)) * minimum[resource]) for c in critical.values())
        if required > stock[resource]:
            gaps.append(f"P5.2 infeasible: critical communities need at least {required} {resource}, stock is {stock[resource]}")
    def minimum_kg(communities) -> float:
        return sum(math.ceil(int(c.get("needs", {}).get(r, 0)) * share) * weights.get(r, 0)
                   for c in communities for r, share in minimum.items())
    vehicles = state.get("vehicles", {}).values()
    fording_kg = sum(MAX_TRIPS_PER_VEHICLE * float(v["capacity_kg"]) for v in vehicles if as_bool(v.get("can_ford")))
    fleet_kg = sum(MAX_TRIPS_PER_VEHICLE * float(v["capacity_kg"]) for v in vehicles)
    ford_only = [c for c in critical.values() if c.get("reachability") == "ford_only"]
    if ford_only and minimum_kg(ford_only) > fording_kg:
        gaps.append(f"P5.2 infeasible: critical communities reachable only by fording vehicles "
                    f"({', '.join(sorted(cid for cid, c in critical.items() if c.get('reachability') == 'ford_only'))}) "
                    f"need at least {minimum_kg(ford_only):,.0f} kg; fording vehicles carry {fording_kg:,.0f} kg")
    if minimum_kg(critical.values()) > fleet_kg:
        gaps.append(f"P5.2 infeasible: critical minimum is {minimum_kg(critical.values()):,.0f} kg; the fleet carries {fleet_kg:,.0f} kg")
    return gaps
