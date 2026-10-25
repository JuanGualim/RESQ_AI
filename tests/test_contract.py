"""The contract of run.execute(): the keys and types the Streamlit UI reads.

AGENTS.md section 6 fixes this shape. A change here breaks Chema's UI, so it has
to be agreed with the group first, not discovered when the demo is recorded.
"""
import pytest

from resq import run
from resq.schemas import Assignment, CriticReview, Plan

RESULT_KEYS = {"run_id", "request_type", "plan", "report", "trace", "escalated", "reviews"}
TRACE_KEYS = {"ts", "run_id", "agent", "input_summary", "output_summary", "lane", "model", "duration_ms", "iteration"}
REQUEST_TYPES = {"plan", "event", "why", "situation"}


@pytest.fixture(autouse=True)
def _scripted(scripted_model):
    """Every test in this file runs on the scripted model from conftest."""


def check_result(result: dict) -> None:
    assert set(result) == RESULT_KEYS, "execute() returned a different set of keys"
    assert isinstance(result["run_id"], str) and result["run_id"]
    assert result["request_type"] in REQUEST_TYPES
    assert isinstance(result["report"], str)
    assert isinstance(result["escalated"], bool)
    assert isinstance(result["trace"], list) and result["trace"]
    assert isinstance(result["reviews"], list)
    assert result["plan"] is None or isinstance(result["plan"], Plan)
    for step in result["trace"]:
        assert TRACE_KEYS <= set(step), f"trace line is missing keys: {TRACE_KEYS - set(step)}"
        assert isinstance(step["agent"], str) and isinstance(step["duration_ms"], int)
        assert isinstance(step["iteration"], int)
    for review in result["reviews"]:
        assert isinstance(review, CriticReview)
        assert isinstance(review.round, int) and isinstance(review.approved, bool)
        assert isinstance(review.violations, list) and isinstance(review.feedback, list)


def check_plan(plan: Plan) -> None:
    assert isinstance(plan.version, int) and plan.version >= 1
    assert isinstance(plan.unserved, list) and all(isinstance(c, str) for c in plan.unserved)
    assert isinstance(plan.risks, list) and all(isinstance(r, str) for r in plan.risks)
    assert isinstance(plan.confidence, float) and 0.0 <= plan.confidence <= 1.0
    assert isinstance(plan.escalated, bool)
    assert isinstance(plan.changes_vs_previous, list)
    for assignment in plan.assignments:
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.community_id, str) and assignment.community_id
        assert isinstance(assignment.origin_id, str) and assignment.origin_id
        assert isinstance(assignment.resource, str) and assignment.resource
        assert isinstance(assignment.quantity, int) and assignment.quantity > 0
        assert isinstance(assignment.vehicle_id, str) and assignment.vehicle_id
        assert isinstance(assignment.route, list) and all(isinstance(s, str) for s in assignment.route)
        assert isinstance(assignment.priority, int) and assignment.priority >= 1
        assert isinstance(assignment.reason, str)
        assert isinstance(assignment.evidence, list)


def test_plan_request_matches_the_contract():
    result = run.execute("How should we distribute aid right now?")
    check_result(result)
    assert result["request_type"] == "plan"
    assert result["plan"] is not None
    check_plan(result["plan"])
    assert result["report"].strip().startswith("#"), "the report must be Markdown the UI can render"


def test_event_request_matches_the_contract():
    run.execute()
    result = run.execute("", {"type": "segment_blocked", "id": "T6", "source": "coordinator"})
    check_result(result)
    assert result["request_type"] == "event"
    check_plan(result["plan"])


def test_why_request_matches_the_contract():
    run.execute()
    result = run.execute("Why did the plan change?")
    check_result(result)
    assert result["request_type"] == "why"


def test_situation_request_matches_the_contract():
    result = run.execute("What is the current situation?")
    check_result(result)
    assert result["request_type"] == "situation"


def test_the_plan_is_json_serializable_for_the_ui():
    # The UI stores plans as JSON (output_examples/*.json), so model_dump must round-trip.
    import json
    plan = run.execute()["plan"]
    restored = Plan(**json.loads(json.dumps(plan.model_dump(), default=str)))
    assert restored.version == plan.version
    assert len(restored.assignments) == len(plan.assignments)
