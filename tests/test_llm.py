from types import SimpleNamespace

import pytest

from resq import llm


def fake_completion(content, model="fake-model"):
    message = SimpleNamespace(content=content, tool_calls=None, model_extra={"reasoning_content": "thinking"})
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], model=model, usage=None)


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.requests.append(request)
        return fake_completion(self.replies.pop(0))


@pytest.fixture
def client(monkeypatch):
    def install(*replies):
        fake = FakeClient(replies)
        monkeypatch.setattr(llm, "_client", lambda: fake)
        return fake
    return install


@pytest.fixture(autouse=True)
def model_env(monkeypatch):
    # The fast lane falls back to NEMOTRON_MODEL only when LANE_FAST_MODEL is unset,
    # so drop it: a developer's .env must not change what these tests see.
    monkeypatch.delenv("LANE_FAST_MODEL", raising=False)
    monkeypatch.setenv("NEMOTRON_MODEL", "nvidia/nemotron-test")
    monkeypatch.setenv("LANE_DEEP_MODEL", "nvidia/nemotron-deep-test")
    monkeypatch.setenv("LANE_DEEP_THINKING", "true")
    from resq import config
    config.get_settings.cache_clear()


def test_fast_lane_turns_thinking_off(client):
    fake = client("hello")
    reply = llm.chat([{"role": "user", "content": "hi"}], lane="fast")
    assert reply["content"] == "hello"
    assert reply["reasoning"] == "thinking"
    assert fake.requests[0]["model"] == "nvidia/nemotron-test"
    assert fake.requests[0]["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False


def test_both_lanes_are_deterministic(client):
    # The demo has to be rehearsable: the same scenario must give the same plan.
    # Both lanes decide (which report to believe, which tier), they do not write prose.
    fake = client("one", "two")
    llm.chat([{"role": "user", "content": "hi"}], lane="fast")
    llm.chat([{"role": "user", "content": "hi"}], lane="deep")
    assert fake.requests[0]["temperature"] == 0.0
    assert fake.requests[1]["temperature"] == 0.0


def test_deep_lane_uses_its_model_and_thinks(client):
    fake = client("ok")
    llm.chat([{"role": "user", "content": "hi"}], lane="deep")
    assert fake.requests[0]["model"] == "nvidia/nemotron-deep-test"
    assert fake.requests[0]["extra_body"]["chat_template_kwargs"]["enable_thinking"] is True


def test_unknown_lane():
    with pytest.raises(ValueError):
        llm.chat([], lane="medium")


@pytest.mark.parametrize("text, expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Sure! Here it is: {"a": [1, 2]} hope it helps', {"a": [1, 2]}),
    ("[1, 2]", [1, 2]),
])
def test_parse_json(text, expected):
    assert llm.parse_json(text) == expected


def test_parse_json_without_json():
    with pytest.raises(llm.LLMError):
        llm.parse_json("no json here")


def test_chat_json_repairs_once(client):
    fake = client("not json", '{"fixed": true}')
    data, _ = llm.chat_json([{"role": "user", "content": "give json"}])
    assert data == {"fixed": True}
    assert len(fake.requests) == 2
