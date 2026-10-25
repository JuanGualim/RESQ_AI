"""Heavy test battery: every scenario repeated N times, measured per agent.

    python scripts/heavy_test.py                # 3 scenarios x 5 runs
    python scripts/heavy_test.py --runs 10      # phase 3 battery
    python scripts/heavy_test.py --scenario block_T6

Uses whatever .env says (Zetaris or SAMPLE_MODE, Nightshift or direct NVIDIA).
Each scenario starts from a clean World Model, so a run never inherits the
previous one's plan. Writes logs/heavy_test_<stamp>.json with every run and
prints a summary of latency, critic rounds, escalations and failures.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from resq import world  # noqa: E402
from resq.config import get_settings  # noqa: E402
from resq.run import DEFAULT_QUESTION, execute  # noqa: E402

WHY_QUESTION = "Why did the plan change?"

# A scenario is a sequence of coordinator turns. The agents keep the World Model
# state between the turns of one run, which is what makes a re-plan a re-plan.
SCENARIOS: dict[str, list[dict]] = {
    "baseline": [
        {"name": "plan", "question": DEFAULT_QUESTION},
    ],
    "block_T6": [
        {"name": "plan", "question": DEFAULT_QUESTION},
        {"name": "block", "event": {"type": "segment_blocked", "id": "T6", "source": "coordinator"}},
        {"name": "why", "question": WHY_QUESTION},
    ],
    "block_T3": [
        {"name": "plan", "question": DEFAULT_QUESTION},
        {"name": "block", "event": {"type": "segment_blocked", "id": "T3", "source": "coordinator"}},
        {"name": "why", "question": WHY_QUESTION},
    ],
}


def critic_rounds(trace: list[dict]) -> int:
    """How many times the Critic ran in this turn (one round = one plan review)."""
    return sum(1 for step in trace if step.get("agent") == "critic")


def agent_latency(trace: list[dict]) -> dict[str, int]:
    """Milliseconds spent per agent in this turn (summed over its iterations)."""
    totals: dict[str, int] = {}
    for step in trace:
        agent = step.get("agent", "?")
        totals[agent] = totals.get(agent, 0) + int(step.get("duration_ms") or 0)
    return totals


def run_turn(step: dict) -> dict:
    """One graph run. Failures are recorded instead of stopping the battery."""
    started = time.monotonic()
    record = {"turn": step["name"], "ok": True, "error": ""}
    try:
        result = execute(step.get("question", ""), step.get("event"))
    except Exception as error:  # noqa: BLE001 - a failed run is a result, not a crash
        record.update(ok=False, error=f"{type(error).__name__}: {error}"[:300])
        traceback.print_exc(limit=2)
    else:
        plan = result["plan"]
        record.update(
            run_id=result["run_id"],
            request_type=result["request_type"],
            plan_version=plan.version if plan else None,
            assignments=len(plan.assignments) if plan else 0,
            unserved=len(plan.unserved) if plan else 0,
            confidence=plan.confidence if plan else None,
            escalated=result["escalated"],
            critic_rounds=critic_rounds(result["trace"]),
            agent_ms=agent_latency(result["trace"]),
            report_chars=len(result["report"]),
            changes=len(plan.changes_vs_previous) if plan else 0,
        )
    record["total_ms"] = int((time.monotonic() - started) * 1000)
    return record


def summarize(scenario: str, runs: list[list[dict]]) -> dict:
    """Aggregate the repeated runs of one scenario."""
    turns = [turn for run in runs for turn in run]
    ok = [turn for turn in turns if turn["ok"]]
    durations = [turn["total_ms"] for turn in ok]
    rounds = [turn["critic_rounds"] for turn in ok if turn.get("request_type") == "plan"]
    per_agent: dict[str, list[int]] = {}
    for turn in ok:
        for agent, value in turn.get("agent_ms", {}).items():
            per_agent.setdefault(agent, []).append(value)
    return {
        "scenario": scenario,
        "runs": len(runs),
        "turns": len(turns),
        "failures": [turn for turn in turns if not turn["ok"]],
        "escalated_turns": sum(1 for turn in ok if turn.get("escalated")),
        "total_ms_mean": round(statistics.fmean(durations)) if durations else 0,
        "total_ms_median": round(statistics.median(durations)) if durations else 0,
        "total_ms_max": max(durations) if durations else 0,
        "critic_rounds_mean": round(statistics.fmean(rounds), 2) if rounds else 0,
        "critic_rounds_max": max(rounds) if rounds else 0,
        "agent_ms_mean": {a: round(statistics.fmean(v)) for a, v in sorted(per_agent.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5, help="repetitions per scenario (default 5)")
    parser.add_argument("--scenario", action="append", choices=sorted(SCENARIOS),
                        help="run only this scenario (repeatable; default: all)")
    args = parser.parse_args()
    chosen = args.scenario or sorted(SCENARIOS)

    settings = get_settings()
    header = {
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": "SAMPLE_MODE" if settings.sample_mode else "Zetaris",
        "world": world.backend().name,
        "fast_model": settings.lane_model("fast"),
        "deep_model": settings.lane_model("deep"),
        "endpoint": settings.model_base_url,
        "runs_per_scenario": args.runs,
    }
    print(json.dumps(header, indent=2))

    results = {}
    for scenario in chosen:
        runs = []
        for index in range(1, args.runs + 1):
            world.reset()  # each run starts from the untouched scenario
            turns = []
            for step in SCENARIOS[scenario]:
                turn = run_turn(step)
                turns.append(turn)
                mark = "ok  " if turn["ok"] else "FAIL"
                print(f"{mark} {scenario} run {index}/{args.runs} {turn['turn']:<6} "
                      f"{turn['total_ms']:>6} ms  rounds={turn.get('critic_rounds', '-')} "
                      f"escalated={turn.get('escalated', '-')} {turn['error']}")
            runs.append(turns)
        results[scenario] = {"runs": runs, "summary": summarize(scenario, runs)}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_file = settings.logs_dir / f"heavy_test_{stamp}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps({"header": header, "scenarios": results}, indent=2, default=str) + "\n",
                        encoding="utf-8")

    print("\n=== summary ===")
    failures = 0
    for scenario in chosen:
        summary = results[scenario]["summary"]
        failures += len(summary["failures"])
        print(f"\n{scenario}: {summary['runs']} runs, {summary['turns']} turns, "
              f"{len(summary['failures'])} failures, {summary['escalated_turns']} escalated turns")
        print(f"  total per turn: mean {summary['total_ms_mean']} ms · median {summary['total_ms_median']} ms "
              f"· max {summary['total_ms_max']} ms")
        print(f"  critic rounds on plan turns: mean {summary['critic_rounds_mean']} · max {summary['critic_rounds_max']}")
        print("  mean per agent: " + " · ".join(f"{a} {v} ms" for a, v in summary["agent_ms_mean"].items()))
        for failure in summary["failures"]:
            print(f"  FAILURE on turn {failure['turn']}: {failure['error']}")
    print(f"\nfull results: {out_file}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
