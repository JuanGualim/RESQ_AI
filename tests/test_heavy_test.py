import importlib.util
from pathlib import Path

from resq.schemas import Assignment, CriticReview, Plan

ROOT_DIR = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("heavy_test", ROOT_DIR / "scripts" / "heavy_test.py")
heavy_test = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(heavy_test)


def turn(name="plan", ok=True, total_ms=1000, **extra):
    base = {"turn": name, "ok": ok, "error": "", "failure_kind": "", "problems": [], "total_ms": total_ms}
    if ok:
        base |= {"request_type": "plan", "critic_rounds": 1, "escalated": False, "agent_ms": {}, "false_blocks": 0}
    base |= extra
    return base


def plan_with(*lines, version=1, changes=()):
    """lines are (community, resource, quantity, route)."""
    return Plan(version=version, changes_vs_previous=list(changes), assignments=[
        Assignment(community_id=c, origin_id="W1", resource=r, quantity=q, vehicle_id="V1",
                   route=list(route), priority=i + 1, reason="x", evidence=[])
        for i, (c, r, q, route) in enumerate(lines)])


def test_scenarios_start_with_a_plan_turn():
    # A re-plan needs a baseline to compare against, so every scenario plans first.
    for steps in heavy_test.SCENARIOS.values():
        assert steps[0].get("question")
        assert "event" not in steps[0]


def test_every_blocking_scenario_blocks_its_own_segment():
    assert set(heavy_test.SCENARIOS) == {"block_T3", "block_T6", "block_T20", "reopen_T6"}
    for segment in ("T3", "T6", "T20"):
        steps = heavy_test.SCENARIOS[f"block_{segment}"]
        assert [step["name"] for step in steps] == ["plan", "block", "why"]
        assert steps[1]["event"] == {"type": "segment_blocked", "id": segment, "source": "coordinator"}
        assert steps[1]["blocked"] == segment
        assert steps[2]["expect_mentions"] == segment


def test_the_reopen_scenario_compares_v3_against_v1():
    steps = heavy_test.SCENARIOS["reopen_T6"]
    assert [step["name"] for step in steps] == ["plan", "block", "reopen"]
    assert steps[2]["event"]["type"] == "segment_reopened"
    assert steps[2]["compare_with"] == "plan"


def test_critic_rounds_counts_one_per_review():
    trace = [{"agent": "planner"}, {"agent": "critic"}, {"agent": "planner"}, {"agent": "critic"}]
    assert heavy_test.critic_rounds(trace) == 2
    assert heavy_test.critic_rounds([{"agent": "explainer"}]) == 0


def test_agent_latency_sums_the_iterations_of_each_agent():
    trace = [
        {"agent": "planner", "duration_ms": 100},
        {"agent": "planner", "duration_ms": 250},
        {"agent": "critic", "duration_ms": 30},
        {"agent": "intake"},  # a step with no duration counts as 0
    ]
    assert heavy_test.agent_latency(trace) == {"planner": 350, "critic": 30, "intake": 0}


def test_false_blocks_counts_only_model_only_rejections():
    # A rejection backed by a hard rule is the Critic doing its job, not a false positive.
    reviews = [
        CriticReview(round=1, approved=False, violations=["P5.2: ..."], feedback=["P5.2: ..."]),
        CriticReview(round=2, approved=False, violations=[], feedback=["C04: priority inversion"]),
        CriticReview(round=3, approved=True, violations=[], feedback=[]),
    ]
    assert heavy_test.false_blocks(reviews) == 1
    assert heavy_test.false_blocks([]) == 0


def test_similarity_measures_untouched_delivery_lines():
    first = plan_with(("C07", "water_20l", 100, ["T1"]), ("C12", "food_kit", 50, ["T2"]))
    same = plan_with(("C07", "water_20l", 100, ["T9"]), ("C12", "food_kit", 50, ["T8"]))
    assert heavy_test.similarity(first, same) == 1.0, "a different route is not a different delivery"
    half = plan_with(("C07", "water_20l", 100, ["T1"]), ("C12", "food_kit", 10, ["T2"]))
    assert heavy_test.similarity(first, half) == 0.5
    assert heavy_test.similarity(Plan(), Plan()) == 1.0


def test_classify_failure_buckets_each_kind():
    assert heavy_test.classify_failure("APITimeoutError: request timed out") == "timeout"
    assert heavy_test.classify_failure("LLMError: invalid JSON in model reply") == "invalid_json"
    assert heavy_test.classify_failure("LLMError: empty content from the model") == "empty_reply"
    assert heavy_test.classify_failure("ZetarisError: connection refused") == "service_unavailable"
    assert heavy_test.classify_failure("TypeError: a genuine bug") == "other"


def test_quality_check_catches_a_route_through_the_blocked_segment():
    state = {"communities": {"C07": {}}, "road_segments": {}, "vehicles": {}, "warehouses": {}, "inventory": {}}
    plan = plan_with(("C07", "water_20l", 10, ["T6"]), changes=["C07 water_20l: new"])
    result = {"plan": plan, "report": "ok", "trace": []}
    problems = heavy_test.quality_problems({"name": "block", "blocked": "T6"}, result, state, {})
    assert any("blocked T6" in p and "C07" in p for p in problems)


def test_quality_check_catches_an_empty_diff_and_an_invented_community():
    state = {"communities": {"C07": {}}, "road_segments": {}, "vehicles": {}, "warehouses": {}, "inventory": {}}
    result = {"plan": Plan(), "report": "we also served C99 and C07", "trace": []}
    problems = heavy_test.quality_problems({"name": "block", "expect_changes": True}, result, state, {})
    assert any("changes_vs_previous is empty" in p for p in problems)
    assert any("C99" in p for p in problems)
    assert not any("C07" in p for p in problems)


def test_a_down_service_is_reported_as_such_not_as_a_missing_plan(monkeypatch):
    # Zetaris went down mid-battery once; the turns were blamed on the agents.
    monkeypatch.setattr(heavy_test, "execute", lambda *a, **k: {
        "plan": None, "report": "Zetaris did not answer", "escalated": True, "reviews": [],
        "run_id": "r", "request_type": "plan",
        "trace": [{"agent": "run", "output_summary": '{"unavailable": "Zetaris"}', "duration_ms": 1,
                   "iteration": 0}]})
    monkeypatch.setattr(heavy_test.world, "get_state", lambda: {"communities": {}})
    record = heavy_test.run_turn({"name": "plan", "question": "q"}, {})
    assert record["ok"] is False
    assert record["failure_kind"] == "service_unavailable"
    assert "Zetaris" in record["error"]


def test_unreachable_service_reads_the_run_trace_line():
    assert heavy_test.unreachable_service([{"agent": "run", "output_summary": "Zetaris"}]) == "Zetaris"
    assert heavy_test.unreachable_service([{"agent": "planner"}, {"agent": "critic"}]) == ""


def test_a_planning_turn_without_a_plan_is_a_failure(monkeypatch):
    # Whatever the cause, a turn that should plan and comes back empty is not "clean".
    monkeypatch.setattr(heavy_test, "execute", lambda *a, **k: {
        "plan": None, "report": "", "trace": [], "escalated": True, "reviews": [],
        "run_id": "r", "request_type": "plan"})
    monkeypatch.setattr(heavy_test.world, "get_state", lambda: {"communities": {}})
    record = heavy_test.run_turn({"name": "plan", "question": "q"}, {})
    assert record["ok"] is False
    assert record["failure_kind"] == "no_plan"
    assert record["error"] == "the turn produced no plan"


def test_a_why_turn_without_a_plan_is_not_a_failure(monkeypatch):
    monkeypatch.setattr(heavy_test, "execute", lambda *a, **k: {
        "plan": None, "report": "T6 was blocked", "trace": [], "escalated": False, "reviews": [],
        "run_id": "r", "request_type": "why"})
    monkeypatch.setattr(heavy_test.world, "get_state", lambda: {"communities": {}})
    record = heavy_test.run_turn({"name": "why", "question": "why?", "expect_mentions": "T6"}, {})
    assert record["ok"] is True and record["failure_kind"] == ""


def test_quality_check_catches_a_why_answer_that_never_names_the_segment():
    state = {"communities": {}, "road_segments": {}, "vehicles": {}, "warehouses": {}, "inventory": {}}
    result = {"plan": None, "report": "The plan changed because of the weather.", "trace": []}
    step = {"name": "why", "expect_mentions": "T6"}
    assert heavy_test.quality_problems(step, result, state, {}) == ["the answer never mentions T6"]
    result["report"] = "T6 was blocked by the coordinator."
    assert heavy_test.quality_problems(step, result, state, {}) == []


def test_a_reopen_may_change_tiers_without_going_backwards():
    # Measured on the real scenario: after reopening T6 the Planner moved four
    # communities from "full" to "essential" and reached three the baseline had left
    # unserved. That is a better plan under P5.2 and must not be reported as a failure.
    state = {"communities": {"C07": {}, "C01": {}}, "road_segments": {}, "vehicles": {},
             "warehouses": {}, "inventory": {}}
    baseline = plan_with(("C07", "water_20l", 100, []), ("C07", "blanket", 100, []))
    reopened = plan_with(("C07", "water_20l", 100, []), ("C07", "blanket", 50, []),
                         ("C01", "medical_kit", 7, []), version=3, changes=["C07 blanket: 100 -> 50"])
    step = {"name": "reopen", "expect_changes": True, "compare_with": "plan"}
    result = {"plan": reopened, "report": "ok", "trace": []}
    problems = heavy_test.quality_problems(step, result, state, {"plan": baseline})
    assert [p for p in problems if p.startswith("after reopening")] == []


def test_a_reopen_that_drops_a_community_or_its_water_is_a_failure():
    state = {"communities": {"C07": {}, "C12": {}}, "road_segments": {}, "vehicles": {},
             "warehouses": {}, "inventory": {}}
    baseline = plan_with(("C07", "water_20l", 100, []), ("C12", "food_kit", 40, []))
    reopened = plan_with(("C07", "water_20l", 20, []), version=3, changes=["C07 water_20l: 100 -> 20"])
    step = {"name": "reopen", "expect_changes": True, "compare_with": "plan"}
    result = {"plan": reopened, "report": "ok", "trace": []}
    problems = heavy_test.quality_problems(step, result, state, {"plan": baseline})
    assert any("C12 was served in the baseline and is unserved now" in p for p in problems)
    assert any("C07 water_20l: 100 -> 20" in p for p in problems)


def test_regressions_ignores_a_tier_change_that_keeps_the_essentials():
    baseline = plan_with(("C07", "water_20l", 100, []), ("C07", "hygiene_kit", 50, []))
    gentler = plan_with(("C07", "water_20l", 100, []), ("C07", "hygiene_kit", 25, []))
    assert heavy_test.regressions(baseline, gentler) == []
    assert heavy_test.similarity(baseline, gentler) == 0.5, "similarity still reports the change"


def test_summary_aggregates_latency_rounds_and_escalations():
    runs = [
        [turn(total_ms=1000, critic_rounds=1, agent_ms={"planner": 400})],
        [turn(total_ms=3000, critic_rounds=3, agent_ms={"planner": 600}, escalated=True)],
    ]
    summary = heavy_test.summarize("block_T6", runs)
    assert summary["runs"] == 2 and summary["turns"] == 2 and summary["clean_turns"] == 2
    assert summary["total_ms_mean"] == 2000
    assert summary["total_ms_median"] == 2000
    assert summary["total_ms_max"] == 3000
    assert summary["critic_rounds_mean"] == 2.0
    assert summary["critic_rounds_max"] == 3
    assert summary["escalated_turns"] == 1
    assert summary["agent_ms_mean"] == {"planner": 500}
    assert summary["failures"] == []


def test_summary_keeps_crashed_turns_out_of_the_latency_numbers():
    runs = [[turn(total_ms=1000, agent_ms={"planner": 400}),
             turn(name="block", ok=False, total_ms=90000, error="timed out", failure_kind="timeout")]]
    summary = heavy_test.summarize("block_T6", runs)
    assert summary["turns"] == 2 and summary["clean_turns"] == 1
    assert [f["kind"] for f in summary["failures"]] == ["timeout"]
    assert summary["failure_kinds"] == {"timeout": 1}
    assert summary["total_ms_mean"] == 1000 and summary["total_ms_max"] == 1000


def test_summary_keeps_a_turn_that_ran_but_failed_a_check_in_the_latency_numbers():
    # The turn produced a plan, so its latency is real data even though a check failed.
    runs = [[turn(total_ms=2000, agent_ms={"planner": 500}, critic_rounds=2, ok=False, failure_kind="quality",
                  error="route still uses blocked T6", problems=["route still uses blocked T6"])]]
    summary = heavy_test.summarize("block_T6", runs)
    assert summary["clean_turns"] == 0
    assert summary["total_ms_mean"] == 2000
    assert summary["critic_rounds_mean"] == 2.0
    assert summary["failure_kinds"] == {"quality": 1}


def test_critic_rounds_are_measured_on_plan_turns_only():
    # A "why" turn never reaches the Critic; counting it would dilute the average.
    runs = [[turn(critic_rounds=3), turn(name="why", critic_rounds=0, agent_ms={})]]
    summary = heavy_test.summarize("block_T6", runs)
    assert summary["critic_rounds_mean"] == 3.0


def test_replan_stability_is_averaged_across_runs():
    runs = [[turn(name="reopen", replan_similarity=0.8)], [turn(name="reopen", replan_similarity=1.0)]]
    assert heavy_test.summarize("reopen_T6", runs)["replan_stability"] == 0.9
    assert heavy_test.summarize("block_T6", [[turn()]])["replan_stability"] is None


def test_markdown_report_lists_every_scenario_and_its_failures():
    header = {"started_at": "2026-10-25T08:00:00+00:00", "data": "SAMPLE_MODE", "world": "memory",
              "endpoint": "http://127.0.0.1:8088/v1", "fast_model": "fast", "deep_model": "deep",
              "runs_per_scenario": 5}
    runs = [[turn(total_ms=1000, agent_ms={"planner": 400}),
             turn(name="block", ok=False, total_ms=2000, error="route still uses blocked T6",
                  failure_kind="quality", agent_ms={"planner": 500})]]
    results = {"block_T6": {"runs": runs, "summary": heavy_test.summarize("block_T6", runs)}}
    text = heavy_test.markdown_report(header, results, ["block_T6"])
    assert "# Heavy test" in text
    assert "SAMPLE_MODE" in text
    assert "block_T6" in text
    assert "route still uses blocked T6" in text
    assert "`quality`" in text
