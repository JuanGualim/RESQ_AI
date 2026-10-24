"""End-to-end graph runs with a scripted model: baseline plan, then a coordinator event and a re-plan."""
import pytest

from resq import llm, run, world


def scripted_chat_json(messages, lane="fast", max_tokens=None):
    system, user = messages[0]["content"], messages[-1]["content"]
    reply = {"model": "scripted", "lane": lane, "duration_ms": 1, "usage": {}}
    if "You are the Reconciler" in system:
        return {"decisions": []}, reply
    if "You are the Risk Analyst" in system:
        return {"summary": ["C07 critical"]}, reply
    if "You are the Planner" in system:
        import json
        context = json.loads(user)
        tiers = {"critical": "minimum", "high": "minimum", "medium": "none"}
        return {"priorities": [{"community_id": c["id"], "rank": i + 1, "tier": tiers.get(c["risk_level"], "none"),
                                "reason": f"{c['risk_level']} risk {c['risk_score']} (P5.1)", "evidence": ["P5.2"]}
                               for i, c in enumerate(context["communities"])], "confidence": 0.8}, reply
    if "You are the Critic" in system:
        return {"issues": [], "summary": "ok"}, reply
    raise AssertionError(f"unexpected prompt: {system[:60]}")


def scripted_chat(messages, lane="fast", tools=None, max_tokens=None):
    return {"content": "## Situation\n- scripted report", "model": "scripted", "lane": lane, "duration_ms": 1, "usage": {}}


@pytest.fixture(autouse=True)
def scripted_model(monkeypatch):
    monkeypatch.setattr(llm, "chat_json", scripted_chat_json)
    monkeypatch.setattr(llm, "chat", scripted_chat)


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
