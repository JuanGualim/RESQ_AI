"""Honest errors: a service that is down ends escalated, never with a traceback.

Chema's UI calls execute() directly, so an unreachable Zetaris, World Model or
model must come back as a normal escalated result it can render.
"""
import pytest

from resq import llm, run, scenario, world
from resq.tools import zetaris
from resq.world import WorldError

REQUIRED_KEYS = {"run_id", "request_type", "plan", "report", "trace", "escalated", "reviews"}


def boom(message):
    def fail(*args, **kwargs):
        raise message
    return fail


def check_escalated_result(result: dict, expected_in_report: str) -> None:
    assert set(result) == REQUIRED_KEYS
    assert result["escalated"] is True
    assert result["plan"] is None
    assert expected_in_report in result["report"]
    assert "P8.3" in result["report"], "the report must cite the escalation rule"
    assert result["trace"], "even a failed run leaves a trace line"


def test_zetaris_down_escalates_instead_of_raising(monkeypatch):
    monkeypatch.setattr(zetaris, "run_sql", boom(zetaris.ZetarisError("connection refused")))
    monkeypatch.setattr(scenario, "run_sql", boom(zetaris.ZetarisError("connection refused")))
    result = run.execute("How should we distribute aid right now?")
    check_escalated_result(result, "Zetaris")
    assert result["request_type"] == "plan"


def test_world_model_down_escalates_instead_of_raising(monkeypatch):
    monkeypatch.setattr(world, "seed", boom(WorldError("world model service timed out")))
    result = run.execute("How should we distribute aid right now?")
    check_escalated_result(result, "World Model")


def test_world_model_down_on_an_event_still_reports_the_event_type(monkeypatch):
    monkeypatch.setattr(world, "latest_plan", boom(WorldError("world model service timed out")))
    result = run.execute("", {"type": "segment_blocked", "id": "T6", "source": "coordinator"})
    check_escalated_result(result, "World Model")
    assert result["request_type"] == "event"


def test_model_down_still_produces_an_escalated_plan_run(no_model):
    # The model is the one service the graph can work around: the Planner returns no
    # plan, the Critic escalates and the Explainer writes the report without the model.
    result = run.execute("How should we distribute aid right now?")
    assert set(result) == REQUIRED_KEYS
    assert result["escalated"] is True
    assert result["plan"] is None
    assert result["report"].strip(), "the coordinator still gets a readable report"
    assert [step["agent"] for step in result["trace"]] == [
        "intake", "reconciler", "risk_analyst", "planner", "critic", "explainer"]
    assert any("no plan" in v.lower() or "model" in v.lower()
               for review in result["reviews"] for v in review.violations)


def test_a_real_bug_is_not_swallowed(monkeypatch):
    # Only service errors become escalations; anything else must still surface.
    monkeypatch.setattr(world, "seed", boom(TypeError("a genuine bug")))
    with pytest.raises(TypeError):
        run.execute("How should we distribute aid right now?")


def test_service_name_falls_back(monkeypatch):
    assert run.service_name(zetaris.ZetarisError("x")) == "Zetaris"
    assert run.service_name(WorldError("x")) == "the World Model service"
    assert run.service_name(RuntimeError("x")) == "a required service"


@pytest.fixture
def no_model(monkeypatch):
    monkeypatch.setattr(llm, "chat", boom(llm.LLMError("model unreachable")))
    monkeypatch.setattr(llm, "chat_json", boom(llm.LLMError("model unreachable")))
