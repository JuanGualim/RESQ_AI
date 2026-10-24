"""Intake agent: classifies the request and applies coordinator events (rule-based, no model)."""
from __future__ import annotations

import re
import time

from resq import scenario, trace, world
from resq.schemas import ResqState

WHY = re.compile(r"\b(why|explain|what changed|reason|por ?qu[eé]|qu[eé] cambi[oó])\b", re.IGNORECASE)
SITUATION = re.compile(r"\b(situation|status|what is happening|overview|risk|situaci[oó]n|estado)\b", re.IGNORECASE)


def classify(question: str, has_event: bool) -> str:
    """situation | plan | event | why"""
    if has_event:
        return "event"
    if WHY.search(question or ""):
        return "why"
    if SITUATION.search(question or "") and not re.search(r"\b(plan|distribut|send|deliver|allocate)\w*", question or "", re.IGNORECASE):
        return "situation"
    return "plan"


def node_intake(state: ResqState) -> dict:
    started = time.monotonic()
    request_type = classify(state.question, state.event is not None)
    applied = None
    if state.event is not None:
        event = state.event.model_dump()
        event["ts"] = event.get("ts") or scenario.next_coordinator_ts()
        event["run_id"] = state.run_id
        world.apply_event(event)
        applied = event
    as_of = scenario.now()
    entry = trace.record(
        state.run_id, "intake",
        {"question": state.question, "event": applied},
        {"request_type": request_type, "as_of": as_of},
        lane="rules", duration_ms=int((time.monotonic() - started) * 1000),
    )
    return {"request_type": request_type, "as_of": as_of, "trace": [entry]}
