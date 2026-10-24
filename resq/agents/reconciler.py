"""Reconciler agent: turns contradictory field reports into verified facts (protocol P1).

Code scores every reported status (source weight x recency). Objects whose
reports agree are accepted as scored. Contested objects go to the model, which
reads the report details and picks a candidate status (or `uncertain`) with a
reason. Every conclusion becomes a World Model event with its evidence.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime

from resq import llm, trace, world
from resq.protocol import (
    FULL_SUPPORT_SCORE, RECENCY_HALF_LIFE_H, SOURCE_WEIGHTS, UNCERTAIN_BELOW,
)
from resq.scenario import normalize_ts
from resq.schemas import ResqState
from resq.tools.zetaris import run_sql, table

EVENT_TYPES = {
    "road_segment": "segment_status_verified",
    "shelter": "shelter_status_verified",
    "community": "community_status_verified",
}

SYSTEM_PROMPT = """You are the Reconciler of RESQ AI, a flood response decision system.
Field reports about road segments, shelters and communities contradict each other.
For each contested object you get its reports and a reliability score per reported status
(protocol P1: brigade 0.9, official 0.7, social_media 0.3, halved every 2 hours of age).
Decide the most likely CURRENT status. Read the report details: a stale bulletin repeated later
does not beat a direct observation that explains why something changed. Choose only among the
candidate statuses, or "uncertain" when the evidence is too weak or balanced.
Reply with ONLY JSON: {"decisions": [{"object_id": "...", "status": "...", "confidence": 0.0-1.0,
"reason": "one sentence citing report ids", "evidence": ["R0.."]}]}"""


def load_reports() -> list[dict]:
    rows = run_sql(f"SELECT * FROM {table('field_reports')} ORDER BY timestamp, id", limit=5000)
    for row in rows:
        row["timestamp"] = normalize_ts(row["timestamp"])
    return rows


def score_reports(reports: list[dict]) -> list[dict]:
    """Group reports per object and score each reported status (P1)."""
    if not reports:
        return []
    latest = max(datetime.fromisoformat(r["timestamp"]) for r in reports)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for report in reports:
        grouped[(report["object_type"], report["object_id"])].append(report)

    objects = []
    for (object_type, object_id), items in sorted(grouped.items()):
        scores: dict[str, float] = defaultdict(float)
        support: dict[str, list[str]] = defaultdict(list)
        for report in items:
            age_h = (latest - datetime.fromisoformat(report["timestamp"])).total_seconds() / 3600
            weight = SOURCE_WEIGHTS.get(report["source"], 0.1) * 0.5 ** (age_h / RECENCY_HALF_LIFE_H)
            scores[report["reported_status"]] += weight
            support[report["reported_status"]].append(report["id"])
        winner = max(scores, key=lambda status: (scores[status], max(support[status])))
        total = sum(scores.values())
        confidence = (scores[winner] / total) * min(1.0, scores[winner] / FULL_SUPPORT_SCORE)
        objects.append({
            "object_type": object_type,
            "object_id": object_id,
            "reports": [{k: r[k] for k in ("id", "timestamp", "source", "reported_status", "detail")} for r in items],
            "scores": {status: round(value, 3) for status, value in sorted(scores.items())},
            "computed_status": winner if len(scores) == 1 or confidence >= UNCERTAIN_BELOW else "uncertain",
            "computed_confidence": round(confidence, 2),
            "evidence": support[winner],
            "latest_ts": max(r["timestamp"] for r in items),
            "contested": len(scores) > 1,
        })
    return objects


def _ask_model(contested: list[dict]) -> tuple[dict[str, dict], dict]:
    payload = [{k: o[k] for k in ("object_type", "object_id", "reports", "scores", "computed_status", "computed_confidence")}
               for o in contested]
    data, reply = llm.chat_json([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ], lane="fast")
    decisions = data.get("decisions", []) if isinstance(data, dict) else data
    return {str(d.get("object_id")): d for d in decisions if isinstance(d, dict)}, reply


def _accept(obj: dict, decision: dict | None) -> dict:
    """Use the model's decision only when it is a candidate status; otherwise keep the computed one."""
    allowed = set(obj["scores"]) | {"uncertain"}
    if decision and decision.get("status") in allowed:
        evidence = [e for e in decision.get("evidence", []) if any(r["id"] == e for r in obj["reports"])]
        confidence = float(decision.get("confidence", obj["computed_confidence"]))
        return {"status": decision["status"], "confidence": round(min(max(confidence, 0.0), 1.0), 2),
                "evidence": evidence or obj["evidence"], "reason": str(decision.get("reason", ""))[:300],
                "decided_by": "model"}
    reason = (f"Scored {obj['scores']} with protocol P1; " + ("contested, model unavailable or invalid" if obj["contested"] else "reports agree"))
    return {"status": obj["computed_status"], "confidence": obj["computed_confidence"],
            "evidence": obj["evidence"], "reason": reason, "decided_by": "code"}


def node_reconciler(state: ResqState) -> dict:
    started = time.monotonic()
    objects = score_reports(load_reports())
    contested = [o for o in objects if o["contested"]]
    decisions, reply, error = {}, None, ""
    if contested:
        try:
            decisions, reply = _ask_model(contested)
        except llm.LLMError as exc:
            error = str(exc)[:200]

    conclusions = []
    for obj in objects:
        verdict = _accept(obj, decisions.get(obj["object_id"]) if obj["contested"] else None)
        world.apply_event({
            "type": EVENT_TYPES[obj["object_type"]], "id": obj["object_id"], "source": "agent", "by": "reconciler",
            "ts": obj["latest_ts"], "run_id": state.run_id, "computed_status": obj["computed_status"],
            "computed_confidence": obj["computed_confidence"], **verdict,
        })
        conclusions.append({"id": obj["object_id"], "status": verdict["status"], "confidence": verdict["confidence"],
                            "by": verdict["decided_by"]})

    entry = trace.record(
        state.run_id, "reconciler",
        {"objects": len(objects), "contested": [o["object_id"] for o in contested]},
        {"conclusions": conclusions, "model_error": error},
        lane="fast", model=reply["model"] if reply else "", duration_ms=int((time.monotonic() - started) * 1000),
    )
    return {"trace": [entry]}
