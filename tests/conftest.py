"""Every test runs offline: SAMPLE_MODE, in-memory World Model and logs in a temp folder."""
import pytest

from resq import config, llm, world
from resq.tools import zetaris


def _clear_caches():
    for cached in (config.get_settings, zetaris._sample_db, world.backend, llm._client):
        getattr(cached, "cache_clear", lambda: None)()  # tests may monkeypatch some of them


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("WORLD_MODEL_URL", "")
    monkeypatch.setenv("RESQ_LOGS_DIR", str(tmp_path / "logs"))
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture
def state():
    """Scenario state with no verified facts yet (official statuses only)."""
    from resq import scenario
    return scenario.bootstrap()


def scripted_chat_json(messages, lane="fast", max_tokens=None):
    """Deterministic stand-in for the model: every agent gets a valid, minimal answer."""
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


@pytest.fixture
def scripted_model(monkeypatch):
    """Run the whole graph without a network: every llm call answers from the script above."""
    monkeypatch.setattr(llm, "chat_json", scripted_chat_json)
    monkeypatch.setattr(llm, "chat", scripted_chat)
