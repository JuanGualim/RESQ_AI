"""Run RESQ AI from the command line, or call `execute()` from the UI.

    python -m resq.run --question "How should we distribute aid right now?"
    python -m resq.run --event block:T6          # coordinator blocks segment T6, then re-plans
    python -m resq.run --question "Why did the plan change?"
    python -m resq.run --reset                   # wipe the World Model state
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone

from resq import scenario, world
from resq.graph import build_graph
from resq.schemas import Event, Plan, ResqState

DEFAULT_QUESTION = "How should we distribute aid right now?"
EVENT_ALIASES = {"block": "segment_blocked", "reopen": "segment_reopened"}


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]


def execute(question: str = DEFAULT_QUESTION, event: dict | None = None) -> dict:
    """One graph run: {"plan": Plan | None, "report": str, "trace": list[dict], "escalated": bool, "run_id": str}."""
    scenario.bootstrap()
    latest = world.latest_plan()
    if event is not None and latest is None:
        execute(DEFAULT_QUESTION)  # a re-plan needs a baseline plan to compare against
        latest = world.latest_plan()
    initial = ResqState(
        run_id=new_run_id(),
        question=question if event is None else (question or f"{event['type']} {event['id']}"),
        event=Event(**event) if event else None,
        previous_plan=Plan(**latest) if latest else None,
    )
    final = build_graph().invoke(initial, config={"recursion_limit": 40})
    plan = final.get("plan")
    plan = plan if isinstance(plan, Plan) or plan is None else Plan(**plan)
    return {
        "run_id": initial.run_id,
        "request_type": final.get("request_type"),
        "plan": plan,
        "report": final.get("report", ""),
        "trace": final.get("trace", []),
        "escalated": bool(final.get("escalated")) or bool(plan and plan.escalated),
        "reviews": final.get("reviews", []),
    }


def parse_event(text: str) -> dict:
    """'block:T6' -> {"type": "segment_blocked", "id": "T6", "source": "coordinator"}"""
    action, _, segment_id = text.partition(":")
    if action not in EVENT_ALIASES or not segment_id:
        raise argparse.ArgumentTypeError(f"use block:<segment> or reopen:<segment>, got {text!r}")
    return {"type": EVENT_ALIASES[action], "id": segment_id.strip().upper(), "source": "coordinator"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RESQ AI: multi-agent flood aid planner")
    parser.add_argument("--question", default=None, help="question from the coordinator")
    parser.add_argument("--event", type=parse_event, default=None, help="coordinator event: block:T6 or reopen:T6")
    parser.add_argument("--reset", action="store_true", help="wipe the World Model state first")
    args = parser.parse_args(argv)

    if args.reset:
        world.reset()
        print("World Model state reset.")
        if args.question is None and args.event is None:
            return 0
    result = execute(args.question or ("" if args.event else DEFAULT_QUESTION), args.event)
    print(result["report"])
    print("\n---")
    for step in result["trace"]:
        print(f"[{step['agent']:12}] iter={step['iteration']} {step['duration_ms']:>6} ms  {step['output_summary'][:140]}")
    print(f"run_id={result['run_id']}  escalated={result['escalated']}  trace=logs/trace_{result['run_id']}.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
