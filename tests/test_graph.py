"""End-to-end graph runs with a scripted model: baseline plan, then a coordinator event and a re-plan."""
import pytest

from resq import run, world


@pytest.fixture(autouse=True)
def _scripted(scripted_model):
    """Every test in this file runs on the scripted model from conftest."""


def test_baseline_plan():
    result = run.execute("How should we distribute aid right now?")
    assert result["request_type"] == "plan"
    assert result["plan"].version == 1 and result["plan"].assignments
    assert not result["escalated"]
    assert [step["agent"] for step in result["trace"]] == ["intake", "reconciler", "risk_analyst", "planner", "critic", "explainer"]
    assert world.latest_plan()["version"] == 1
    assert "Assignments (plan v1)" in result["report"]


def test_event_replans_and_escalates_when_infeasible():
    run.execute()
    result = run.execute("", {"type": "segment_blocked", "id": "T6", "source": "coordinator"})
    plan = result["plan"]
    assert result["request_type"] == "event"
    assert plan.version == 2 and plan.changes_vs_previous
    assert all("T6" not in a.route for a in plan.assignments)
    assert result["escalated"] and any(r.startswith("P8.3") for r in plan.risks)
    blocked = [e for e in world.history() if e.get("type") == "segment_blocked"]
    assert blocked and blocked[0]["ts"] == "2020-11-05T10:05:00"


def test_event_without_baseline_builds_one_first():
    result = run.execute("", {"type": "segment_blocked", "id": "T6", "source": "coordinator"})
    assert result["plan"].version == 2


def test_why_question_explains_latest_plan():
    run.execute()
    result = run.execute("Why did the plan change?")
    assert result["request_type"] == "why"
    assert [step["agent"] for step in result["trace"]] == ["intake", "explainer"]
    assert result["plan"].version == 1


def test_parse_event():
    assert run.parse_event("block:t6") == {"type": "segment_blocked", "id": "T6", "source": "coordinator"}
    with pytest.raises(Exception):
        run.parse_event("explode:T6")
