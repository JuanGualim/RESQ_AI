"""Heavy test battery: every scenario repeated N times, measured and checked.

    python scripts/heavy_test.py                 # 4 scenarios x 5 runs (phase 2 gate)
    python scripts/heavy_test.py --runs 10       # phase 3 battery
    python scripts/heavy_test.py --scenario block_T6
    python scripts/heavy_test.py --report docs/test_results/heavy_test_2026-10-25.md

Uses whatever .env says (Zetaris or SAMPLE_MODE, Nightshift or direct NVIDIA).
Each run starts from a clean World Model, so it never inherits the previous plan.

Besides latency it checks the quality of every turn (the plan passes the hard
rules, no route uses the blocked segment, a re-plan explains itself, the "why"
answer names the segment, the report invents no community) and classifies every
failure by kind, so a red run says what to fix and where.
"""
from __future__ import annotations

import argparse
import json
import re
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
from resq.protocol import CRITICAL_ESSENTIALS, MAX_CRITIC_ROUNDS  # noqa: E402
from resq.run import DEFAULT_QUESTION, execute  # noqa: E402
from resq.tools.validators import critical_minimum_gaps, validate_plan  # noqa: E402

WHY_QUESTION = "Why did the plan change?"
COMMUNITY_ID = re.compile(r"\bC\d{2}\b")
# A re-plan may lower a tier, but halving someone's water or food once the road is open
# again is a step backwards, not a trade-off.
ESSENTIAL_FLOOR = 0.5


def blocking(segment: str) -> list[dict]:
    """Baseline plan, then the coordinator blocks one segment, then "why did it change?"."""
    return [
        {"name": "plan", "question": DEFAULT_QUESTION},
        {"name": "block", "event": {"type": "segment_blocked", "id": segment, "source": "coordinator"},
         "blocked": segment, "expect_changes": True},
        {"name": "why", "question": WHY_QUESTION, "expect_mentions": segment},
    ]


def block_and_reopen(segment: str) -> list[dict]:
    """Block a segment and then reopen it: v3 should look like v1 again."""
    return [
        {"name": "plan", "question": DEFAULT_QUESTION},
        {"name": "block", "event": {"type": "segment_blocked", "id": segment, "source": "coordinator"},
         "blocked": segment, "expect_changes": True},
        {"name": "reopen", "event": {"type": "segment_reopened", "id": segment, "source": "coordinator"},
         "expect_changes": True, "compare_with": "plan"},
    ]


# A scenario is a sequence of coordinator turns. The agents keep the World Model
# state between the turns of one run, which is what makes a re-plan a re-plan.
SCENARIOS: dict[str, list[dict]] = {
    "block_T6": blocking("T6"),
    "block_T3": blocking("T3"),
    "block_T20": blocking("T20"),
    "reopen_T6": block_and_reopen("T6"),
}

FAILURE_KINDS = ("timeout", "invalid_json", "empty_reply", "service_unavailable",
                 "rounds_exhausted", "no_plan", "quality", "other")


def classify_failure(error: str) -> str:
    """Bucket an error so a red battery says which file to look at (point 9)."""
    text = error.lower()
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "json" in text:
        return "invalid_json"
    if "empty" in text or "no content" in text:
        return "empty_reply"
    if "unreachable" in text or "connection" in text or "refused" in text:
        return "service_unavailable"
    return "other"


def unreachable_service(trace: list[dict]) -> str:
    """execute() reports an unreachable service as one trace line from "run" (see resq/run.py)."""
    for step in trace:
        if step.get("agent") == "run":
            return str(step.get("output_summary", ""))[:200]
    return ""


def critic_rounds(trace: list[dict]) -> int:
    """How many times the Critic ran in this turn (one round = one plan review)."""
    return sum(1 for step in trace if step.get("agent") == "critic")


def false_blocks(reviews: list) -> int:
    """Rejections where the hard rules passed and only the model objected (point 13)."""
    return sum(1 for review in reviews if not review.approved and not review.violations and review.feedback)


def agent_latency(trace: list[dict]) -> dict[str, int]:
    """Milliseconds spent per agent in this turn (summed over its iterations)."""
    totals: dict[str, int] = {}
    for step in trace:
        agent = step.get("agent", "?")
        totals[agent] = totals.get(agent, 0) + int(step.get("duration_ms") or 0)
    return totals


def delivered(plan) -> dict[tuple[str, str], int]:
    totals: dict[tuple[str, str], int] = {}
    for a in plan.assignments:
        key = (a.community_id, a.resource)
        totals[key] = totals.get(key, 0) + a.quantity
    return totals


def similarity(first, second) -> float:
    """Share of (community, resource) lines delivered in the same quantity in both plans.

    Reported as information, not as a pass/fail: a re-plan is allowed to change tiers.
    After reopening T6 the Planner moved four communities from "full" to "essential"
    and used what it saved to reach three that the baseline left unserved. That is a
    better plan under P5.2 and it scores under 50% here, so `regressions` below is
    what decides, not this number.
    """
    before, after = delivered(first), delivered(second)
    keys = set(before) | set(after)
    if not keys:
        return 1.0
    same = sum(1 for key in keys if before.get(key) == after.get(key))
    return round(same / len(keys), 3)


def regressions(baseline, current) -> list[str]:
    """What a re-plan is never allowed to do once the restriction is lifted.

    Dropping a community that was served, or cutting its water or food, means the plan
    went backwards. Moving everyone from "full" to "essential" to reach more people does not.
    """
    before, after = delivered(baseline), delivered(current)
    served_before = {community for community, _ in before}
    served_after = {community for community, _ in after}
    problems = [f"{community} was served in the baseline and is unserved now"
                for community in sorted(served_before - served_after)]
    for community, resource in sorted(before):
        if resource not in CRITICAL_ESSENTIALS:
            continue
        was, now = before[(community, resource)], after.get((community, resource), 0)
        if now < was * ESSENTIAL_FLOOR:
            problems.append(f"{community} {resource}: {was} -> {now}, below {ESSENTIAL_FLOOR:.0%} of the baseline")
    return problems


def quality_problems(step: dict, result: dict, state: dict, plans: dict) -> list[str]:
    """The automatic quality checks of point 8. An empty list means the turn is clean."""
    problems: list[str] = []
    plan = result["plan"]
    report = result["report"]

    if plan is not None:
        violations = validate_plan(plan, state)
        if critical_minimum_gaps(state):  # P5.2 cannot be met at all: expected, already escalated
            violations = [v for v in violations if not v.startswith("P5.2")]
        problems += [f"hard rule: {v}" for v in violations[:5]]

        blocked = step.get("blocked")
        if blocked:
            using = sorted({a.community_id for a in plan.assignments if blocked in a.route})
            if using:
                problems.append(f"route still uses blocked {blocked} for {', '.join(using)}")

        if step.get("expect_changes") and not plan.changes_vs_previous:
            problems.append("changes_vs_previous is empty after a coordinator event")

        known = set(state.get("communities", {}))
        invented = sorted(set(COMMUNITY_ID.findall(report)) - known)
        if invented:
            problems.append(f"report mentions unknown communities: {', '.join(invented)}")

    mentions = step.get("expect_mentions")
    if mentions and mentions not in report:
        problems.append(f"the answer never mentions {mentions}")

    compare_with = step.get("compare_with")
    if compare_with and plan is not None and plans.get(compare_with) is not None:
        problems += [f"after reopening, {p}" for p in regressions(plans[compare_with], plan)]
    return problems


def run_turn(step: dict, plans: dict) -> dict:
    """One graph run plus its quality checks. Failures are recorded, never raised."""
    started = time.monotonic()
    record = {"turn": step["name"], "ok": True, "error": "", "failure_kind": "", "problems": []}
    try:
        result = execute(step.get("question", ""), step.get("event"))
    except Exception as error:  # noqa: BLE001 - a failed run is a result, not a crash
        detail = f"{type(error).__name__}: {error}"
        record.update(ok=False, error=detail[:300], failure_kind=classify_failure(detail))
        traceback.print_exc(limit=2)
    else:
        plan = result["plan"]
        state = world.get_state()
        problems = quality_problems(step, result, state, plans)
        plans[step["name"]] = plan
        record.update(
            run_id=result["run_id"],
            request_type=result["request_type"],
            plan_version=plan.version if plan else None,
            assignments=len(plan.assignments) if plan else 0,
            unserved=len(plan.unserved) if plan else 0,
            confidence=plan.confidence if plan else None,
            escalated=result["escalated"],
            critic_rounds=critic_rounds(result["trace"]),
            false_blocks=false_blocks(result["reviews"]),
            agent_ms=agent_latency(result["trace"]),
            report_chars=len(result["report"]),
            changes=len(plan.changes_vs_previous) if plan else 0,
            problems=problems,
        )
        down = unreachable_service(result["trace"])
        if down:
            # Zetaris or the World Model is down: the battery says so instead of
            # blaming the agents for the empty plan that follows.
            record.update(ok=False, failure_kind="service_unavailable", error=down)
        elif plan is None and step["name"] != "why":
            # A planning turn that ends without a plan is a failure, however it got there.
            kind = "rounds_exhausted" if record["critic_rounds"] >= MAX_CRITIC_ROUNDS else "no_plan"
            record.update(ok=False, failure_kind=kind, error="the turn produced no plan")
        elif problems:
            record.update(ok=False, failure_kind="quality", error="; ".join(problems)[:300])
    record["total_ms"] = int((time.monotonic() - started) * 1000)
    return record


def stability(runs: list[list[dict]]) -> float | None:
    """Mean share of delivery lines a re-plan leaves untouched (point 12)."""
    scores = [turn["replan_similarity"] for run in runs for turn in run if turn.get("replan_similarity") is not None]
    return round(statistics.fmean(scores), 3) if scores else None


def summarize(scenario: str, runs: list[list[dict]]) -> dict:
    """Aggregate the repeated runs of one scenario."""
    turns = [turn for run in runs for turn in run]
    ok = [turn for turn in turns if turn["ok"]]
    measured = [turn for turn in turns if "agent_ms" in turn]  # ran, even if a check failed
    durations = [turn["total_ms"] for turn in measured]
    rounds = [turn["critic_rounds"] for turn in measured
              if turn.get("turn") == "plan" and turn.get("critic_rounds") is not None]
    per_agent: dict[str, list[int]] = {}
    for turn in measured:
        for agent, value in turn.get("agent_ms", {}).items():
            per_agent.setdefault(agent, []).append(value)
    kinds = {kind: sum(1 for t in turns if t.get("failure_kind") == kind) for kind in FAILURE_KINDS}
    return {
        "scenario": scenario,
        "runs": len(runs),
        "turns": len(turns),
        "clean_turns": len(ok),
        "failures": [{"turn": t["turn"], "kind": t["failure_kind"], "error": t["error"]} for t in turns if not t["ok"]],
        "failure_kinds": {k: v for k, v in kinds.items() if v},
        "escalated_turns": sum(1 for turn in measured if turn.get("escalated")),
        "total_ms_mean": round(statistics.fmean(durations)) if durations else 0,
        "total_ms_median": round(statistics.median(durations)) if durations else 0,
        "total_ms_max": max(durations) if durations else 0,
        "critic_rounds_mean": round(statistics.fmean(rounds), 2) if rounds else 0,
        "critic_rounds_max": max(rounds) if rounds else 0,
        "false_blocks": sum(turn.get("false_blocks", 0) for turn in measured),
        "replan_stability": stability(runs),
        "agent_ms_mean": {a: round(statistics.fmean(v)) for a, v in sorted(per_agent.items())},
    }


def markdown_report(header: dict, results: dict, chosen: list[str]) -> str:
    """The summary that goes to docs/test_results/, because logs/ is not in git."""
    lines = [f"# Heavy test · {header['started_at']}", "",
             f"- Data: **{header['data']}** · World Model: `{header['world']}`",
             f"- Endpoint: `{header['endpoint']}`",
             f"- Fast lane: `{header['fast_model']}` · deep lane: `{header['deep_model']}`",
             f"- Runs per scenario: {header['runs_per_scenario']}", "",
             "| Scenario | Turns | Clean | Failures | Escalated | Mean ms | Max ms | Critic rounds | False blocks | Re-plan stability |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for scenario in chosen:
        s = results[scenario]["summary"]
        stable = f"{s['replan_stability']:.0%}" if s["replan_stability"] is not None else "-"
        lines.append(f"| {scenario} | {s['turns']} | {s['clean_turns']} | {len(s['failures'])} | "
                     f"{s['escalated_turns']} | {s['total_ms_mean']} | {s['total_ms_max']} | "
                     f"{s['critic_rounds_mean']} (max {s['critic_rounds_max']}) | {s['false_blocks']} | {stable} |")
    lines += ["", "## Latency per agent (mean ms)", "",
              "| Scenario | " + " | ".join(sorted({a for scenario in chosen
                                                   for a in results[scenario]["summary"]["agent_ms_mean"]})) + " |"]
    agents = sorted({a for scenario in chosen for a in results[scenario]["summary"]["agent_ms_mean"]})
    lines.append("| --- |" + " --- |" * len(agents))
    for scenario in chosen:
        per_agent = results[scenario]["summary"]["agent_ms_mean"]
        lines.append(f"| {scenario} | " + " | ".join(str(per_agent.get(a, "-")) for a in agents) + " |")
    failures = [(scenario, failure) for scenario in chosen for failure in results[scenario]["summary"]["failures"]]
    lines += ["", "## Failures", ""]
    lines += [f"- **{scenario}** · {f['turn']} · `{f['kind']}` — {f['error']}" for scenario, f in failures] or ["None."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=5, help="repetitions per scenario (default 5)")
    parser.add_argument("--scenario", action="append", choices=sorted(SCENARIOS),
                        help="run only this scenario (repeatable; default: all)")
    parser.add_argument("--report", help="also write a Markdown summary here (e.g. docs/test_results/...md)")
    args = parser.parse_args()
    chosen = args.scenario or sorted(SCENARIOS)
    # A battery runs for tens of minutes, often with its output redirected to a file;
    # without this, progress sits in the buffer until the very end.
    sys.stdout.reconfigure(line_buffering=True)

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
            turns, plans = [], {}
            for step in SCENARIOS[scenario]:
                turn = run_turn(step, plans)
                compare_with = step.get("compare_with")
                if compare_with and plans.get(compare_with) is not None and plans.get(step["name"]) is not None:
                    turn["replan_similarity"] = similarity(plans[compare_with], plans[step["name"]])
                turns.append(turn)
                mark = "ok  " if turn["ok"] else "FAIL"
                print(f"{mark} {scenario} run {index}/{args.runs} {turn['turn']:<6} "
                      f"{turn['total_ms']:>6} ms  rounds={turn.get('critic_rounds', '-')} "
                      f"escalated={turn.get('escalated', '-')} {turn['failure_kind']} {turn['error']}")
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
        stable = f"{summary['replan_stability']:.0%}" if summary["replan_stability"] is not None else "-"
        print(f"\n{scenario}: {summary['turns']} turns, {summary['clean_turns']} clean, "
              f"{len(summary['failures'])} failures, {summary['escalated_turns']} escalated")
        print(f"  total per turn: mean {summary['total_ms_mean']} ms · median {summary['total_ms_median']} ms "
              f"· max {summary['total_ms_max']} ms")
        print(f"  critic rounds on plan turns: mean {summary['critic_rounds_mean']} · max {summary['critic_rounds_max']}"
              f" · false blocks {summary['false_blocks']} · re-plan stability {stable}")
        print("  mean per agent: " + " · ".join(f"{a} {v} ms" for a, v in summary["agent_ms_mean"].items()))
        if summary["failure_kinds"]:
            print("  failure kinds: " + ", ".join(f"{k}={v}" for k, v in summary["failure_kinds"].items()))
        for failure in summary["failures"]:
            print(f"  FAILURE {failure['turn']} [{failure['kind']}]: {failure['error']}")
    print(f"\nfull results: {out_file}")

    if args.report:
        report_file = Path(args.report)
        if not report_file.is_absolute():
            report_file = ROOT_DIR / report_file
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(markdown_report(header, results, chosen), encoding="utf-8")
        print(f"markdown summary: {report_file}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
