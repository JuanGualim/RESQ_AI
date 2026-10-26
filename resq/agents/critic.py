"""Critic agent: hard rules in code first, then a model review of reasons and evidence (P8).

Rejected plans go back to the Planner with concrete feedback, at most 3 rounds.
The plan is escalated to a human when it still fails after the last round,
when a critical community cannot be reached, or when confidence is too low.
"""
from __future__ import annotations

import json
import time

from resq import llm, trace, world
from resq.protocol import ESCALATE_BELOW_CONFIDENCE, MAX_CRITIC_ROUNDS
from resq.schemas import CriticReview, ResqState
from resq.agents.common import plan_by_community
from resq.tools.validators import critical_minimum_gaps, validate_plan

SYSTEM_PROMPT = """You are the Critic of RESQ AI. Hard rules (capacity, stock, routes, critical minimums) were already
checked in code and passed. You review the plan's REASONING, per community: risk level and score, need, what the
plan delivers (coverage = delivered / need) and the Planner's reason and evidence.
Flag as "blocking" ONLY a wrong DECISION:
- priority inversion: a community with clearly higher risk (score at least 0.05 higher, or a higher risk level)
  gets clearly lower coverage of water_20l or food_kit than a lower-risk community;
- a reason built on a wrong fact (wrong risk level or wrong reported status for that community).
Never block for wording, style, or because coverage is below 100%: stock is limited and tiers are partial
on purpose. Splitting deliveries across vehicles, trips or warehouses is normal and never an issue.
"stock_cuts" lists what ran out while delivering in protocol order. A community whose coverage is lower
because its resource appears there was cut by scarcity, not by the Planner's ranking: that is NOT a priority
inversion and is not an issue at all. Before flagging an inversion, check both communities against
"stock_cuts", and only flag it when the lower-risk one was served ahead of the higher-risk one with stock
still available.
"reachability" is the other reason coverage can be low without anyone making a mistake: "ford_only" means
only the fording vehicles can get there, and they are a small part of the fleet, so such a community often
gets less than a lower-risk one that every vehicle can reach. That is the road network, not the ranking.
Never flag an inversion when the higher-risk community is harder to reach ("ford_only" or "none") than the
one you are comparing it with.
Risk scores and levels are computed by code (P3: critical >= 0.60, high >= 0.45, medium >= 0.30) and are
correct by definition: never question them. Put any other remark as "minor".
Reply with ONLY JSON: {"issues": [{"community_id": "C..", "severity": "blocking|minor", "problem": "..."}], "summary": "..."}"""


def stock_cuts(plan) -> list[str]:
    """What the packing ran out of (P6.2): lower coverage here is scarcity, not a ranking mistake."""
    return [risk for risk in plan.risks if risk.startswith("P6.2")]


def _review_reasons(plan, current: dict) -> tuple[list[str], list[str], dict | None]:
    cuts = stock_cuts(plan)
    payload = {"communities": plan_by_community(plan, current), "stock_cuts": cuts[:12],
               "risks": [r for r in plan.risks if not r.startswith("P6.2")][:10],
               "confidence": plan.confidence}
    data, reply = llm.chat_json([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ], lane="deep")
    issues = [i for i in (data.get("issues", []) if isinstance(data, dict) else []) if isinstance(i, dict)]
    blocking = [f"{i.get('community_id')}: {i.get('problem')}" for i in issues if i.get("severity") == "blocking"]
    minor = [f"{i.get('community_id')}: {i.get('problem')}" for i in issues if i.get("severity") != "blocking"]
    return blocking, minor, reply


def node_critic(state: ResqState) -> dict:
    started = time.monotonic()
    round_number = state.critic_round + 1
    current = world.get_state()
    plan = state.plan
    reply, minor = None, []

    gaps = critical_minimum_gaps(current)
    if plan is None:
        review = CriticReview(round=round_number, approved=False, violations=["Planner produced no plan (model unavailable)"])
    else:
        violations = validate_plan(plan, current)
        if gaps:  # P8.2.1: P5.2 cannot be met at all; do not loop on it, escalate with the gap
            violations = [v for v in violations if not v.startswith("P5.2")]
        blocking: list[str] = []
        if not violations:
            try:
                blocking, minor, reply = _review_reasons(plan, current)
            except llm.LLMError as exc:
                minor = [f"reason review skipped: {str(exc)[:120]}"]
            if round_number > 1:  # P8.2: the reasoning review can send a plan back only once
                minor, blocking = minor + blocking, []
        approved = not violations and not blocking
        feedback = blocking + ([f"packing shortfall: {s}" for s in state.pack_shortfalls] if not approved else [])
        review = CriticReview(round=round_number, approved=approved, violations=violations, feedback=feedback)

    unreachable_critical = [cid for cid, c in current["communities"].items()
                            if c.get("risk_level") == "critical" and c.get("reachability") == "none"]
    out_of_rounds = not review.approved and (round_number >= MAX_CRITIC_ROUNDS or plan is None)
    low_confidence = plan is not None and plan.confidence < ESCALATE_BELOW_CONFIDENCE
    escalated = out_of_rounds or bool(unreachable_critical) or bool(gaps) or (review.approved and low_confidence)
    if plan is not None:
        reasons = [f"P8.3: {g}" for g in gaps]
        if out_of_rounds:
            reasons.append(f"P8.3: the Critic still rejects the plan after {round_number} rounds")
        if review.approved and low_confidence:
            reasons.append(f"P8.3: plan confidence {plan.confidence} is below {ESCALATE_BELOW_CONFIDENCE}")
        plan = plan.model_copy(update={"escalated": escalated, "risks": list(dict.fromkeys(plan.risks + reasons))})

    entry = trace.record(
        state.run_id, "critic",
        {"round": round_number, "assignments": len(plan.assignments) if plan else 0},
        {"approved": review.approved, "violations": review.violations, "blocking": review.feedback, "minor": minor,
         "escalated": escalated, "unreachable_critical": unreachable_critical, "infeasible": gaps},
        lane="code+deep", model=reply["model"] if reply else "", duration_ms=int((time.monotonic() - started) * 1000),
        iteration=round_number,
    )
    return {"reviews": [review], "critic_round": round_number, "approved": review.approved,
            "escalated": escalated, "plan": plan, "trace": [entry]}


def route_after_critic(state: ResqState) -> str:
    """'explainer' when approved, out of rounds or without a plan; otherwise 'planner' for another round."""
    if state.approved or state.plan is None or state.critic_round >= MAX_CRITIC_ROUNDS:
        return "explainer"
    return "planner"
