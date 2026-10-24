"""Explainer agent: the coordinator-facing report and "what changed and why".

Code computes the exact differences between plan versions and finds the World
Model events in between; the model turns them into a short report. The final
plan is published to the World Model, so the next run can compare against it.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict

from resq import llm, trace, world
from resq.agents.common import plan_by_community
from resq.schemas import Plan, ResqState

SYSTEM_PROMPT = """You are the Explainer of RESQ AI, writing for a municipal emergency coordinator during a flood.
Write a short report in English Markdown with these sections:
## Situation: 2-4 bullets.
## Plan: who gets what first and why, citing community ids, tiers or coverage, and evidence.
## Why the plan changed: ONLY if "events_since_previous_plan" is not empty: 2-3 sentences linking those events
   (e.g. a blocked segment) to the changes (the exact list is appended by code, do not repeat it).
## Risks and decisions for you: facts to verify; if "escalated" is true, say clearly that a human decision is
   needed and why, using "escalation_reasons".
Use only the facts provided; never invent numbers, routes or ids. Under 250 words. No word count."""


def _key(assignment: dict) -> tuple[str, str]:
    return assignment["community_id"], assignment["resource"]


def diff_plans(previous: Plan | None, plan: Plan) -> list[str]:
    """Exact, code-generated differences between two plan versions."""
    if previous is None:
        return []
    before: dict[tuple, list[dict]] = defaultdict(list)
    after: dict[tuple, list[dict]] = defaultdict(list)
    for a in previous.model_dump()["assignments"]:
        before[_key(a)].append(a)
    for a in plan.model_dump()["assignments"]:
        after[_key(a)].append(a)
    changes = []
    for key in sorted(set(before) | set(after)):
        community, resource = key
        old, new = before.get(key, []), after.get(key, [])
        old_qty, new_qty = sum(a["quantity"] for a in old), sum(a["quantity"] for a in new)
        old_desc = ", ".join(f"{a['vehicle_id']} via {'-'.join(a['route']) or 'local'}" for a in old)
        new_desc = ", ".join(f"{a['vehicle_id']} via {'-'.join(a['route']) or 'local'}" for a in new)
        if not old:
            changes.append(f"{community} {resource}: new, {new_qty} units ({new_desc})")
        elif not new:
            changes.append(f"{community} {resource}: removed (was {old_qty} units, {old_desc})")
        elif old_qty != new_qty or old_desc != new_desc:
            changes.append(f"{community} {resource}: {old_qty} -> {new_qty} units; {old_desc} -> {new_desc}")
    for community in sorted(set(plan.unserved) - set(previous.unserved)):
        changes.append(f"{community}: now unserved")
    for community in sorted(set(previous.unserved) - set(plan.unserved)):
        changes.append(f"{community}: served again")
    return changes


STATUS_EVENTS = ("segment_blocked", "segment_reopened", "segment_status_verified", "shelter_status_verified")


def _effective(events: list[dict]) -> dict[str, dict]:
    """Current status per object: the most recent observation wins, ties go to the later write."""
    winners: dict[str, dict] = {}
    for event in events:
        current = winners.get(event["id"])
        if current is None or (event.get("ts", ""), event["seq"]) >= (current.get("ts", ""), current["seq"]):
            winners[event["id"]] = event
    return winners


def events_since_previous_plan(previous: Plan | None) -> list[dict]:
    """Status changes that took effect after the previous plan was published: what caused the re-plan."""
    history = world.history()
    published = [e["seq"] for e in history if e.get("type") == "plan_published"
                 and previous is not None and e["plan"]["version"] == previous.version]
    since = published[-1] if published else 0
    status_events = [e for e in history if e.get("type") in STATUS_EVENTS]
    before = _effective([e for e in status_events if e["seq"] <= since])
    after = _effective(status_events)
    keep = ("seq", "type", "id", "status", "confidence", "source", "by", "ts", "evidence", "reason")
    changes = [{k: event[k] for k in keep if k in event} for object_id, event in sorted(after.items())
               if since and before.get(object_id, {}).get("status") != event.get("status")]
    if not since:
        changes = [{k: e[k] for k in keep if k in e} for e in status_events if e.get("source") == "coordinator"]
    return changes[-15:]


def render_table(plan: Plan) -> str:
    lines = ["| # | Community | Resource | Qty | Vehicle | From | Route |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for a in sorted(plan.assignments, key=lambda a: a.priority):
        lines.append(f"| {a.priority} | {a.community_id} | {a.resource} | {a.quantity} | {a.vehicle_id} | {a.origin_id} | {'-'.join(a.route) or 'local'} |")
    return "\n".join(lines)


def _write_report(facts: dict) -> tuple[str, dict | None]:
    try:
        reply = llm.chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(facts, ensure_ascii=False, default=str)},
        ], lane="fast")
        return reply["content"], reply
    except llm.LLMError as exc:
        lines = ["## Situation", *[f"- {s}" for s in facts.get("situation", [])],
                 "## Changes", *[f"- {c}" for c in facts.get("changes_vs_previous", [])],
                 "## Risks", *[f"- {r}" for r in facts.get("risks", [])],
                 f"\n_(report written without the model: {str(exc)[:80]})_"]
        return "\n".join(lines), None


def node_explainer(state: ResqState) -> dict:
    started = time.monotonic()
    plan, previous = state.plan, state.previous_plan
    update: dict = {}

    if state.request_type in ("plan", "event") and plan is None:
        facts = {"question": state.question, "situation": state.situation, "escalated": True,
                 "problem": "The Planner could not produce a plan; a human decision is needed.",
                 "critic_rounds": [r.model_dump() for r in state.reviews]}
    elif state.request_type == "why":
        latest = world.latest_plan()
        plan = Plan(**latest) if latest else None
        facts = {"question": state.question, "latest_plan": plan.model_dump() if plan else None,
                 "changes_vs_previous": plan.changes_vs_previous if plan else [],
                 "events": events_since_previous_plan(None)[-10:]}
    elif state.request_type == "situation":
        current = world.get_state()
        facts = {"question": state.question, "situation": state.situation,
                 "uncertain_or_blocked": {sid: s.get("status") for sid, s in current["road_segments"].items()
                                          if s.get("status") in ("uncertain", "blocked", "closed", "flooded", "passable_4x4")}}
    else:
        changes = diff_plans(previous, plan)
        plan = plan.model_copy(update={"changes_vs_previous": changes, "escalated": state.escalated or plan.escalated})
        reviews = [{"round": r.round, "approved": r.approved, "violations": r.violations[:3], "feedback": r.feedback[:3]}
                   for r in state.reviews]
        facts = {"question": state.question, "plan_version": plan.version,
                 "previous_version": previous.version if previous else None, "situation": state.situation,
                 "communities": plan_by_community(plan, world.get_state()), "unserved": plan.unserved,
                 "events_since_previous_plan": events_since_previous_plan(previous) if previous else [],
                 "number_of_changes": len(changes), "critic_rounds": reviews, "escalated": plan.escalated,
                 "escalation_reasons": [r for r in plan.risks if r.startswith("P8.3")],
                 "risks": [r for r in plan.risks if not r.startswith("P8.3")][:8]}
        world.save_plan(plan.model_dump(), ts=state.as_of, run_id=state.run_id)
        update["plan"] = plan

    report, reply = _write_report(facts)
    if plan is not None and state.request_type in ("plan", "event"):
        if plan.changes_vs_previous:
            report = report.rstrip() + f"\n\n### Exact changes vs plan v{plan.version - 1}\n\n" + "\n".join(f"- {c}" for c in plan.changes_vs_previous)
        report = report.rstrip() + "\n\n### Assignments (plan v%d)\n\n%s\n" % (plan.version, render_table(plan))
    entry = trace.record(
        state.run_id, "explainer", {"request_type": state.request_type, "plan_version": plan.version if plan else None},
        {"changes": plan.changes_vs_previous if plan else [], "report_chars": len(report)},
        lane="fast", model=reply["model"] if reply else "", duration_ms=int((time.monotonic() - started) * 1000),
    )
    return {**update, "report": report, "trace": [entry]}
