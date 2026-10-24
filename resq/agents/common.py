"""Helpers shared by agents."""
from __future__ import annotations

from resq.schemas import Plan


def plan_by_community(plan: Plan, current: dict) -> dict:
    """Aggregate assignments per community: delivered vs need, so the review is about decisions, not trips."""
    summary: dict[str, dict] = {}
    for a in plan.assignments:
        entry = summary.setdefault(a.community_id, {"delivered": {}, "reason": a.reason, "evidence": a.evidence})
        entry["delivered"][a.resource] = entry["delivered"].get(a.resource, 0) + a.quantity
    for community_id, community in current["communities"].items():
        if community.get("risk_level") in (None, "low") and community_id not in summary:
            continue
        entry = summary.setdefault(community_id, {"delivered": {}, "reason": "", "evidence": []})
        needs = community.get("needs", {})
        entry.update(name=community.get("name"), risk_level=community.get("risk_level"), risk_score=community.get("risk_score"),
                     reported_status=community.get("reported_status"), need=needs,
                     coverage={r: round(entry["delivered"].get(r, 0) / n, 2) for r, n in needs.items() if n},
                     unserved=community_id in plan.unserved)
    return summary
