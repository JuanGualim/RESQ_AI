"""Planner agent (deep lane): decides how scarce aid is split between communities.

The model makes the judgment call: the order of communities and the delivery tier of
each one (P4.1), and why, following protocol P5. Code supplies every number
(needs, stock, fleet capacity, reachability), packs the allocations into vehicles
and routes (tools/packing.py, P6), and adds the risks it can compute itself.
On a retry the model receives the Critic's feedback.
"""
from __future__ import annotations

import json
import math
import time

from resq import llm, trace, world
from resq.protocol import MAX_TRIPS_PER_VEHICLE, RESOURCE_PRIORITY, SHELTER_FULL_AT, TIERS
from resq.schemas import Plan, ResqState
from resq.tools.packing import pack
from resq.tools.validators import critical_minimum_gaps
from resq.tools.routing import as_bool, best_route

SYSTEM_PROMPT = """You are the Planner of RESQ AI. You decide how to split scarce flood aid between communities
for the next 24 hours, for a municipal emergency coordinator. For each community you choose a TIER (and a rank,
used only to break ties); code turns tiers into quantities, vehicles and routes, serving communities in
descending risk (P5.1) until stock or vehicle capacity runs out.
Tiers (share of each need delivered): full = 100% of everything; essential = 100% water_20l, food_kit,
medical_kit and 50% hygiene_kit, blanket; minimum = 50% water_20l and food_kit, 100% medical_kit; none = nothing.
Protocol:
- P5.1 rank by risk. P5.2 every reachable CRITICAL community gets at least "minimum", and no MEDIUM community
  gets anything unless every critical one is at least "minimum".
- Check "scarcity": sum the needs your tiers imply and keep them within "stock" for each resource, otherwise the
  last communities in your ranking get cut. If stock is short, give "minimum" or "essential" instead of "full".
- P5.4 communities in "unreachable" go to "unserved". Communities with tier none go to "unserved".
- If "feasibility" lists gaps, P5.2 cannot be met for every critical community: give "minimum" to as many
  critical communities as possible in rank order (best effort); the rest is escalated to a human.
Reason: at most 20 words citing evidence (risk level/score, report ids R0.., rules P#).
If critic_feedback is present, fix every point (raise the tier of communities that were short, lower others).
If previous_plan is present, keep what still works.
Reply with ONLY JSON:
{"priorities": [{"community_id": "C..", "rank": 1, "tier": "full|essential|minimum|none", "reason": "...",
  "evidence": ["..."]}], "unserved": ["C.."], "risks": ["max 5 short strings"], "confidence": 0.0}"""


def build_context(current: dict, state: ResqState) -> dict:
    communities = sorted(
        (c | {"id": cid} for cid, c in current["communities"].items() if c.get("risk_level") not in (None, "low")),
        key=lambda c: c.get("risk_score", 0), reverse=True)
    fleet = {"all_vehicles_kg": 0.0, "fording_vehicles_kg": 0.0}
    for vehicle in current["vehicles"].values():
        load = MAX_TRIPS_PER_VEHICLE * float(vehicle["capacity_kg"])
        fleet["all_vehicles_kg"] += load
        if as_bool(vehicle["can_ford"]):
            fleet["fording_vehicles_kg"] += load
    stock: dict[str, dict] = {}
    for items in current["inventory"].values():
        for resource, item in items.items():
            entry = stock.setdefault(resource, {"quantity": 0, "unit_weight_kg": float(item["unit_weight_kg"])})
            entry["quantity"] += int(item["quantity"])
    context = {
        "as_of": state.as_of,
        "communities": [{
            "id": c["id"], "name": c["name"], "risk_level": c["risk_level"], "risk_score": c["risk_score"],
            "needs": c.get("needs", {}), "reachability": c.get("reachability"),
            "reported_status": c.get("reported_status"), "status_evidence": c.get("reported_status_evidence", []),
        } for c in communities],
        "unreachable": [c["id"] for c in communities if c.get("reachability") == "none"],
        "total_stock": stock,
        "scarcity": scarcity(communities, stock),
        "feasibility": critical_minimum_gaps(current),
        "fleet": fleet,
    }
    if state.previous_plan is not None:
        totals: dict[str, int] = {}
        for a in state.previous_plan.assignments:
            totals[f"{a.community_id} {a.resource}"] = totals.get(f"{a.community_id} {a.resource}", 0) + a.quantity
        context["previous_plan"] = totals
        context["new_events"] = [{k: e.get(k) for k in ("type", "id", "status", "ts")}
                                 for e in world.history() if e.get("source") == "coordinator"][-5:]
    if state.reviews and not state.reviews[-1].approved:
        last = state.reviews[-1]
        context["critic_feedback"] = last.violations + last.feedback
    return context


def computed_risks(current: dict) -> list[str]:
    """Risks the code can state without the model (P1.1, P1.2, P7, P8.3)."""
    risks = []
    for segment_id, segment in sorted(current["road_segments"].items()):
        if segment.get("status") == "uncertain":
            risks.append(f"P1.1: {segment_id} status uncertain (evidence {', '.join(segment.get('status_evidence', []))}); only fording vehicles may use it until verified")
        if segment.get("status") == "blocked":
            risks.append(f"P1.2: {segment_id} blocked by the coordinator")
    free_shelters = []
    for shelter_id, shelter in sorted(current["shelters"].items()):
        status = shelter.get("status", "operational")
        if status in ("flooded", "uncertain", "full") or int(shelter["current_occupancy"]) >= SHELTER_FULL_AT * int(shelter["capacity"]):
            risks.append(f"P7.1: shelter {shelter_id} {shelter['name']} cannot receive people ({status})")
        else:
            free_shelters.append((shelter_id, shelter))
    for community_id, community in sorted(current["communities"].items()):
        if community.get("risk_level") == "critical" and community.get("reported_status") in ("isolated", "evacuating") and free_shelters:
            nearest = _nearest_shelter(community_id, free_shelters, current)
            if nearest:
                risks.append(f"P7.2: {community_id} {community['name']} is {community['reported_status']}; nearest shelter with room: {nearest}")
        if community.get("risk_level") == "critical" and community.get("reachability") == "none":
            risks.append(f"P8.3: critical {community_id} {community['name']} cannot be reached by any vehicle")
    return risks


def _nearest_shelter(community_id: str, shelters: list[tuple[str, dict]], current: dict) -> str | None:
    best = None
    for shelter_id, shelter in shelters:
        for vehicle_id in current["vehicles"]:
            route = best_route(community_id, shelter["road_node"], current, vehicle_id)
            if route and (best is None or route.distance_km < best[0]):
                best = (route.distance_km, f"{shelter_id} {shelter['name']} ({route.distance_km} km)")
    return best[1] if best else None


def scarcity(communities: list[dict], stock: dict) -> dict:
    """Per resource: total stock vs need by risk level, so the model sees what is short."""
    table: dict[str, dict] = {}
    for resource in RESOURCE_PRIORITY:
        row = {"stock": stock.get(resource, {}).get("quantity", 0)}
        for level in ("critical", "high", "medium"):
            row[f"need_{level}"] = sum(int(c.get("needs", {}).get(resource, 0)) for c in communities if c["risk_level"] == level)
        table[resource] = row
    return table


def clean_allocations(data: dict, current: dict) -> tuple[list[dict], list[str]]:
    """Model tiers (P4.1) -> allocations (need x tier share), cut where total stock runs out.

    Delivery order follows the protocol, not the model: P5.2 first gives every critical community its
    "minimum" share (in descending risk, P5.1), then the rest of each chosen tier, again by risk.
    """
    stock_left: dict[str, int] = {}
    for items in current["inventory"].values():
        for resource, item in items.items():
            stock_left[resource] = stock_left.get(resource, 0) + int(item["quantity"])

    def order(entry: dict) -> tuple:
        community = current["communities"].get(str(entry.get("community_id")), {})
        rank = entry.get("rank") if isinstance(entry.get("rank"), (int, float)) else 99
        return (-float(community.get("risk_score") or 0), rank)

    ranked = sorted((p for p in data.get("priorities", []) if isinstance(p, dict)
                     and str(p.get("community_id")) in current["communities"]), key=order)
    wanted: dict[tuple[str, str], int] = {}
    passes: list[list[tuple[dict, str, int]]] = [[], []]
    for entry in ranked:
        community_id = str(entry["community_id"])
        community = current["communities"][community_id]
        shares = TIERS.get(str(entry.get("tier", "none")).lower(), TIERS["none"])
        for resource in RESOURCE_PRIORITY:
            need = int(community.get("needs", {}).get(resource, 0))
            total = math.ceil(need * shares.get(resource, 0.0))
            if total <= 0:
                continue
            wanted[(community_id, resource)] = total
            first = min(total, math.ceil(need * TIERS["minimum"][resource])) if community.get("risk_level") == "critical" else 0
            if first:
                passes[0].append((entry, resource, first))
            if total - first:
                passes[1].append((entry, resource, total - first))

    allocations, given = [], {}
    for entry, resource, quantity in passes[0] + passes[1]:
        quantity_ok = min(quantity, stock_left.get(resource, 0))
        if quantity_ok <= 0:
            continue
        community_id = str(entry["community_id"])
        stock_left[resource] -= quantity_ok
        given[(community_id, resource)] = given.get((community_id, resource), 0) + quantity_ok
        allocations.append({
            "community_id": community_id, "resource": resource, "quantity": quantity_ok,
            "priority": len(allocations) + 1, "reason": str(entry.get("reason", ""))[:300],
            "evidence": [str(e) for e in entry.get("evidence", [])][:8],
        })
    cuts = [f"{c} {r}: stock ran out, {given.get((c, r), 0)} of {total} units"
            for (c, r), total in wanted.items() if given.get((c, r), 0) < total]
    return allocations, cuts


def to_plan(data: dict, current: dict, version: int) -> tuple[Plan, list[str]]:
    allocations, cuts = clean_allocations(data, current)
    packed = pack(allocations, current)
    packed.shortfalls = cuts + packed.shortfalls
    unreachable = {cid for cid, c in current["communities"].items()
                   if c.get("reachability") == "none" and c.get("risk_level") not in (None, "low")}
    served = {a.community_id for a in packed.assignments}
    unserved = sorted((set(str(c) for c in data.get("unserved", [])) - served) | unreachable)
    risks = list(dict.fromkeys(computed_risks(current) + [f"P6.2: {s}" for s in packed.shortfalls]
                               + [str(r) for r in data.get("risks", [])][:5]))
    confidence = data.get("confidence", 0.6)
    plan = Plan(version=version, assignments=packed.assignments, unserved=unserved, risks=risks,
                confidence=min(max(float(confidence) if isinstance(confidence, (int, float)) else 0.6, 0.0), 1.0))
    return plan, packed.shortfalls


def node_planner(state: ResqState) -> dict:
    started = time.monotonic()
    current = world.get_state()
    context = build_context(current, state)
    version = (state.previous_plan.version + 1) if state.previous_plan else 1
    iteration = state.critic_round + 1
    plan, shortfalls, reply, error, decision = None, [], None, "", []
    try:
        data, reply = llm.chat_json([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ], lane="deep")
        data = data if isinstance(data, dict) else {}
        decision = [(p.get("rank"), p.get("community_id"), p.get("tier")) for p in data.get("priorities", []) if isinstance(p, dict)]
        plan, shortfalls = to_plan(data, current, version)
    except llm.LLMError as exc:
        error = str(exc)[:200]

    entry = trace.record(
        state.run_id, "planner",
        {"version": version, "targets": [c["id"] for c in context["communities"]], "critic_feedback": context.get("critic_feedback", [])},
        {"decision": decision, "assignments": len(plan.assignments) if plan else 0, "unserved": plan.unserved if plan else [],
         "shortfalls": shortfalls, "error": error},
        lane="deep", model=reply["model"] if reply else "", duration_ms=int((time.monotonic() - started) * 1000),
        iteration=iteration,
    )
    return {"plan": plan, "pack_shortfalls": shortfalls, "trace": [entry]}
