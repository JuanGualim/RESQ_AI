"""World Model integration: the agents' shared, event-sourced domain state.

Contract (AGENTS.md section 6):
    get_state(as_of=None) -> dict   scenario state with every verified fact applied; with as_of, only
                                    what had been observed by then ("what did we believe at 09:00?")
    apply_event(event) -> None      record a domain event (coordinator action or agent conclusion)
    history() -> list[dict]         every domain event, in order
    timeline(object_id) -> list     how the belief about one object evolved, with evidence
    audit() -> list[dict]           the engine's own audit log (every mutation, in order)

Scenario rows are stored as World Model entities; agent conclusions and
coordinator actions are facts about them, each with provenance (source kind,
agent, observation time). For a predicate, the most recent observation wins
(ties: the later write), which is the engine's "most-recent-wins" policy.
"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache

from resq.config import get_settings
from resq.world.backends import HttpWorld, MemoryWorld, WorldBackend, WorldError

__all__ = [
    "WorldError", "apply_event", "audit", "backend", "get_state", "history", "latest_plan",
    "reset", "save_plan", "seed", "timeline",
]

log = logging.getLogger(__name__)

TABLE_TYPES = {
    "communities": "community", "shelters": "shelter", "warehouses": "warehouse",
    "road_nodes": "road_node", "road_segments": "road_segment", "vehicles": "vehicle", "inventory": "stock",
}
TYPE_TABLES = {v: k for k, v in TABLE_TYPES.items()}

# Domain event type -> (entity type, predicate) stored as a World Model fact.
EVENT_FACTS = {
    "segment_blocked": ("road_segment", "status"),
    "segment_reopened": ("road_segment", "status"),
    "segment_status_verified": ("road_segment", "status"),
    "shelter_status_verified": ("shelter", "status"),
    "community_status_verified": ("community", "reported_status"),
    "community_risk_assessed": ("community", "risk"),
    "plan_published": ("plan", "plan"),
}
COORDINATOR_STATUS = {"segment_blocked": "blocked", "segment_reopened": "open"}


@lru_cache(maxsize=1)
def backend() -> WorldBackend:
    url = get_settings().world_model_url
    if url:
        return HttpWorld(url)
    log.warning("WORLD_MODEL_URL is empty: using the in-memory World Model fallback (development only)")
    return MemoryWorld()


def reset() -> None:
    backend().reset()


def seed(tables: dict[str, list[dict]], at: str) -> dict:
    """Store scenario rows as entities. Unchanged rows are skipped, so seeding every run is cheap."""
    entities = []
    for table, rows in tables.items():
        entity_type = TABLE_TYPES[table]
        for row in rows:
            entity_id = f"{row['warehouse_id']}.{row['resource']}" if table == "inventory" else row["id"]
            entities.append({"type": entity_type, "id": entity_id, "attrs": row, "at": at, "by": "loader"})
    return backend().upsert_entities(entities)


def apply_event(event: dict) -> None:
    """Record a domain event, e.g. {"type": "segment_blocked", "id": "T7", "source": "coordinator", "ts": "..."}."""
    if event.get("type") not in EVENT_FACTS:
        raise ValueError(f"unknown event type: {event.get('type')!r}")
    if not event.get("ts"):
        raise ValueError("every event needs a 'ts' (scenario time of the observation)")
    entity_type, predicate = EVENT_FACTS[event["type"]]
    value = dict(event)
    if event["type"] in COORDINATOR_STATUS:
        value.setdefault("status", COORDINATOR_STATUS[event["type"]])
        value.setdefault("confidence", 1.0)
    backend().assert_fact({
        "about_type": entity_type,
        "about_id": str(event["id"]),
        "predicate": predicate,
        "value": value,
        "confidence": float(value.get("confidence", 0.5)),
        "source": {"kind": str(event.get("source", "agent")), "by": str(event.get("by", event.get("source", "agent"))),
                   "at": event["ts"], "runId": event.get("run_id")},
    })


def history() -> list[dict]:
    """Every domain event in write order, with its World Model sequence number."""
    return [{**fact["value"], "seq": fact["seq"]} for fact in backend().facts()]


def _current_facts(as_of: str | None = None) -> dict[tuple[str, str], dict[str, dict]]:
    current: dict[tuple[str, str], dict[str, dict]] = {}
    for fact in backend().facts():
        if as_of is not None and fact["at"] > as_of:
            continue  # not observed yet at that moment
        slot = current.setdefault((fact["type"], fact["id"]), {})
        previous = slot.get(fact["predicate"])
        if previous is None or (fact["at"], fact["seq"]) >= (previous["at"], previous["seq"]):
            slot[fact["predicate"]] = fact
    return current


def get_state(as_of: str | None = None) -> dict:
    """Scenario state with verified facts applied (the input of routing, validators and agents).

    With `as_of` (ISO scenario time), only facts observed up to that moment are applied, so the
    state is what the system believed then. Scenario rows themselves are not versioned.
    """
    if as_of is not None:
        as_of = datetime.fromisoformat(as_of.replace(" ", "T")).strftime("%Y-%m-%dT%H:%M:%S")
    state: dict = {table: {} for table in TABLE_TYPES}
    for entity in backend().entities():
        table = TYPE_TABLES.get(entity["type"])
        if table:
            state[table][entity["id"]] = dict(entity["attrs"])
    inventory: dict[str, dict] = {}
    for row in state.pop("inventory").values():
        inventory.setdefault(row["warehouse_id"], {})[row["resource"]] = {
            "quantity": row["quantity"], "unit_weight_kg": row["unit_weight_kg"]}
    state["inventory"] = inventory

    for (entity_type, entity_id), predicates in _current_facts(as_of).items():
        table = TYPE_TABLES.get(entity_type)
        record = state.get(table, {}).get(entity_id) if table else None
        if record is None:
            continue
        for predicate, fact in predicates.items():
            value = fact["value"]
            if predicate == "risk":
                record.update(risk_score=value.get("risk_score"), risk_level=value.get("risk_level"),
                              risk_factors=value.get("factors", {}), needs=value.get("needs", {}),
                              reachability=value.get("reachability"))
            else:
                record[predicate] = value.get("status")
                record[f"{predicate}_confidence"] = value.get("confidence")
                record[f"{predicate}_evidence"] = value.get("evidence", [])
                record[f"{predicate}_source"] = value.get("source")
    return state


def save_plan(plan: dict, ts: str, run_id: str | None = None) -> None:
    apply_event({"type": "plan_published", "id": f"v{plan['version']}", "source": "agent", "by": "explainer",
                 "ts": ts, "run_id": run_id, "plan": plan, "confidence": plan.get("confidence", 0.5)})


def latest_plan() -> dict | None:
    plans = [e for e in history() if e.get("type") == "plan_published"]
    return max(plans, key=lambda e: e["plan"]["version"])["plan"] if plans else None


def timeline(object_id: str) -> list[dict]:
    """Every fact recorded about one object (segment, shelter, community, plan), in observation order."""
    facts = [f for f in backend().facts() if f["id"] == object_id]
    facts.sort(key=lambda f: (f["at"], f["seq"]))
    keep = ("type", "status", "risk_level", "risk_score", "confidence", "evidence", "reason", "by", "decided_by")
    return [{"seq": f["seq"], "at": f["at"], "predicate": f["predicate"], "source": f["source"].get("kind"),
             **{k: f["value"][k] for k in keep if isinstance(f["value"], dict) and k in f["value"]}}
            for f in facts]


def audit() -> list[dict]:
    """The World Model's audit log: one entry per mutation (seq, at, kind, actor, summary)."""
    return backend().audit()
