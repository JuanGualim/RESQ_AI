"""Deterministic vehicle packing (protocol P6): turns allocations into vehicle assignments.

The Planner (model) decides *how much of each resource each community gets*.
This module decides *which vehicle carries it and by which route*: it respects
the vehicle's home warehouse, per-trip capacity, the trip limit, warehouse stock
and passability, and reports whatever it could not fit as a shortfall.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from resq.protocol import MAX_TRIPS_PER_VEHICLE
from resq.schemas import Assignment
from resq.tools.routing import best_route


@dataclass
class PackResult:
    assignments: list[Assignment] = field(default_factory=list)
    shortfalls: list[str] = field(default_factory=list)  # "C07 water_20l: 40 of 244 units could not be carried"


def pack(allocations: list[dict], state: dict) -> PackResult:
    """allocations: [{"community_id", "resource", "quantity", "priority", "reason", "evidence"}], highest priority first."""
    load_left = {vid: MAX_TRIPS_PER_VEHICLE * float(v["capacity_kg"]) for vid, v in state["vehicles"].items()}
    stock_left = {(wid, res): int(item["quantity"]) for wid, items in state["inventory"].items() for res, item in items.items()}
    routes: dict[tuple[str, str], object] = {}
    result = PackResult()

    for allocation in sorted(allocations, key=lambda a: a.get("priority", 99)):
        community, resource = allocation["community_id"], allocation["resource"]
        remaining = int(allocation["quantity"])
        candidates = []
        for vehicle_id, vehicle in state["vehicles"].items():
            key = (vehicle_id, community)
            if key not in routes:
                routes[key] = best_route(vehicle["warehouse_id"], community, state, vehicle_id)
            if routes[key] is not None:
                candidates.append((routes[key].distance_km, -float(vehicle["capacity_kg"]), vehicle_id))
        for _, _, vehicle_id in sorted(candidates):
            if remaining <= 0:
                break
            vehicle = state["vehicles"][vehicle_id]
            warehouse = vehicle["warehouse_id"]
            item = state["inventory"].get(warehouse, {}).get(resource)
            if not item:
                continue
            weight = float(item["unit_weight_kg"])
            while remaining > 0:
                per_trip = int(min(float(vehicle["capacity_kg"]), load_left[vehicle_id]) // weight)
                quantity = min(remaining, per_trip, stock_left[(warehouse, resource)])
                if quantity <= 0:
                    break
                result.assignments.append(Assignment(
                    community_id=community, origin_id=warehouse, resource=resource, quantity=quantity,
                    vehicle_id=vehicle_id, route=routes[(vehicle_id, community)].segments,
                    priority=int(allocation.get("priority", 99)), reason=str(allocation.get("reason", "")),
                    evidence=list(allocation.get("evidence", [])),
                ))
                remaining -= quantity
                load_left[vehicle_id] -= quantity * weight
                stock_left[(warehouse, resource)] -= quantity
        if remaining > 0:
            reason = "no vehicle can reach it" if not candidates else "not enough stock or vehicle capacity left"
            result.shortfalls.append(f"{community} {resource}: {remaining} of {allocation['quantity']} units could not be carried ({reason})")
    return result
