import importlib.util
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("heavy_test", ROOT_DIR / "scripts" / "heavy_test.py")
heavy_test = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(heavy_test)


def turn(name="plan", ok=True, total_ms=1000, **extra):
    base = {"turn": name, "ok": ok, "error": "", "total_ms": total_ms}
    if ok:
        base |= {"request_type": "plan", "critic_rounds": 1, "escalated": False, "agent_ms": {}}
    base |= extra
    return base


def test_scenarios_start_with_a_plan_turn():
    # A re-plan needs a baseline to compare against, so every scenario plans first.
    for steps in heavy_test.SCENARIOS.values():
        assert steps[0].get("question")
        assert "event" not in steps[0]


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


def test_summary_aggregates_latency_rounds_and_escalations():
    runs = [
        [turn(total_ms=1000, critic_rounds=1, agent_ms={"planner": 400})],
        [turn(total_ms=3000, critic_rounds=3, agent_ms={"planner": 600}, escalated=True)],
    ]
    summary = heavy_test.summarize("baseline", runs)
    assert summary["runs"] == 2
    assert summary["turns"] == 2
    assert summary["total_ms_mean"] == 2000
    assert summary["total_ms_median"] == 2000
    assert summary["total_ms_max"] == 3000
    assert summary["critic_rounds_mean"] == 2.0
    assert summary["critic_rounds_max"] == 3
    assert summary["escalated_turns"] == 1
    assert summary["agent_ms_mean"] == {"planner": 500}
    assert summary["failures"] == []


def test_summary_keeps_failures_out_of_the_latency_numbers():
    runs = [[turn(total_ms=1000, agent_ms={"planner": 400}),
             turn(name="block", ok=False, total_ms=90000, error="LLMError: timeout")]]
    summary = heavy_test.summarize("block_T6", runs)
    assert summary["turns"] == 2
    assert [failure["turn"] for failure in summary["failures"]] == ["block"]
    assert summary["total_ms_mean"] == 1000
    assert summary["total_ms_max"] == 1000


def test_critic_rounds_are_measured_on_plan_turns_only():
    # A "why" turn never reaches the Critic; counting it would dilute the average.
    runs = [[turn(critic_rounds=3), turn(name="why", request_type="why", critic_rounds=0)]]
    summary = heavy_test.summarize("block_T6", runs)
    assert summary["critic_rounds_mean"] == 3.0
