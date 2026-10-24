"""Risk Analyst agent: risk index and needs per community (protocol P3, P4).

The index and the needs are computed in code from Zetaris data and the
verified World Model state, so they are reproducible. The model writes a short
situation summary on top of them for the coordinator.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta

from resq import llm, trace, world
from resq.protocol import (
    COVERED_SHARE, DEPENDENTS_FULL_AT_PCT, ELEVATION_DEFAULT, ELEVATION_STEPS, FAMILY_SIZE,
    ISOLATION_FORD_ONLY, ISOLATION_FULL, ISOLATION_NONE, MEDICAL_ELDERLY_PCT,
    MEDICAL_PEOPLE_PER_KIT_HIGH, MEDICAL_PEOPLE_PER_KIT_LOW, RAIN_24H_STEPS, RAIN_DEFAULT,
    REPORTED_NEED, RISK_LEVEL_DEFAULT, RISK_LEVELS, RISK_WEIGHTS, STABLE_NEED_FACTOR, UNCERTAIN_BELOW,
)
from resq.schemas import ResqState
from resq.tools.routing import reachability
from resq.tools.zetaris import run_sql, table

SYSTEM_PROMPT = """You are the Risk Analyst of RESQ AI, a flood response decision system.
You get the risk index per community (computed with protocol P3) and the rainfall of the last 24 hours.
Write the situation summary for the municipal emergency coordinator: 3 to 5 short bullet points,
most urgent first, citing community ids, risk levels and the factor that drives each one.
Do not change any number. Reply with ONLY JSON: {"summary": ["...", "..."]}"""


def rain_last_24h(as_of: str) -> float:
    since = (datetime.fromisoformat(as_of) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
    rows = run_sql(
        f"SELECT SUM(precipitation_mm) AS mm FROM {table('rainfall')} "
        f"WHERE datetime > '{since}' AND datetime <= '{as_of[:16]}'", limit=1)
    return float(rows[0]["mm"] or 0.0) if rows else 0.0


def _step(value: float, steps: list[tuple[float, float]], default: float, above: bool) -> float:
    for threshold, factor in steps:
        if (value >= threshold) if above else (value <= threshold):
            return factor
    return default


def risk_level(score: float) -> str:
    for threshold, level in RISK_LEVELS:
        if score >= threshold:
            return level
    return RISK_LEVEL_DEFAULT


def assess(community: dict, rain_mm: float, reach: str) -> dict:
    """P3 factors, score and level for one community."""
    status = community.get("reported_status")
    status_ok = status and (community.get("reported_status_confidence") or 0) >= UNCERTAIN_BELOW
    factors = {
        "exposure": round(_step(float(community["elevation_m"]), ELEVATION_STEPS, ELEVATION_DEFAULT, above=False)
                          * _step(rain_mm, RAIN_24H_STEPS, RAIN_DEFAULT, above=True), 3),
        "vulnerability": round((int(community["vulnerability"]) - 1) / 4, 3),
        "dependents": round(min(1.0, (float(community["pct_children"]) + float(community["pct_elderly"])) / DEPENDENTS_FULL_AT_PCT), 3),
        "isolation": {"all": ISOLATION_NONE, "ford_only": ISOLATION_FORD_ONLY}.get(reach, ISOLATION_FULL),
        "reported_need": REPORTED_NEED.get(status, 0.0) if status_ok else 0.0,
    }
    score = round(sum(RISK_WEIGHTS[name] * value for name, value in factors.items()), 3)
    return {"risk_score": score, "risk_level": risk_level(score), "factors": factors}


def needs(community: dict, level: str) -> dict:
    """P4: one 24-hour delivery round."""
    covered = int(community["population"]) * COVERED_SHARE[level]
    if covered <= 0:
        return {}
    families = math.ceil(covered / FAMILY_SIZE)
    isolated = community.get("reported_status") == "isolated"
    per_kit = MEDICAL_PEOPLE_PER_KIT_HIGH if float(community["pct_elderly"]) >= MEDICAL_ELDERLY_PCT or isolated else MEDICAL_PEOPLE_PER_KIT_LOW
    result = {
        "water_20l": families,
        "food_kit": families,
        "hygiene_kit": math.ceil(families / 2),
        "medical_kit": math.ceil(covered / per_kit),
    }
    if level == "critical":
        result["blanket"] = families
    if community.get("reported_status") == "stable":
        result = {resource: math.ceil(quantity * STABLE_NEED_FACTOR) for resource, quantity in result.items()}
    return result


def _summarize(ranked: list[dict], rain_mm: float) -> tuple[list[str], dict | None]:
    payload = {"rain_last_24h_mm": round(rain_mm, 1), "communities": [
        {k: c[k] for k in ("id", "name", "risk_level", "risk_score", "factors", "reachability", "reported_status")}
        for c in ranked if c["risk_level"] != "low"]}
    try:
        data, reply = llm.chat_json([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ], lane="fast")
        summary = data.get("summary", []) if isinstance(data, dict) else []
        return [str(line) for line in summary][:6], reply
    except llm.LLMError:
        top = [c for c in ranked if c["risk_level"] in {"critical", "high"}][:5]
        return [f"{c['id']} {c['name']}: {c['risk_level']} risk ({c['risk_score']})" for c in top], None


def node_risk_analyst(state: ResqState) -> dict:
    started = time.monotonic()
    current = world.get_state()
    rain_mm = rain_last_24h(state.as_of)
    ranked = []
    for community_id, community in current["communities"].items():
        reach = reachability(community_id, current)
        result = assess(community, rain_mm, reach)
        result["needs"] = needs(community, result["risk_level"])
        result["reachability"] = reach
        world.apply_event({"type": "community_risk_assessed", "id": community_id, "source": "agent", "by": "risk_analyst",
                           "ts": state.as_of, "run_id": state.run_id, "rain_last_24h_mm": round(rain_mm, 1),
                           "confidence": 1.0, **result})
        ranked.append({"id": community_id, "name": community["name"], "reported_status": community.get("reported_status"), **result})
    ranked.sort(key=lambda c: c["risk_score"], reverse=True)
    summary, reply = _summarize(ranked, rain_mm)

    entry = trace.record(
        state.run_id, "risk_analyst",
        {"rain_last_24h_mm": round(rain_mm, 1), "communities": len(ranked)},
        {"ranking": [(c["id"], c["risk_level"], c["risk_score"], c["reachability"]) for c in ranked], "summary": summary},
        lane="fast", model=reply["model"] if reply else "", duration_ms=int((time.monotonic() - started) * 1000),
    )
    return {"situation": summary, "trace": [entry]}
