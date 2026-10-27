"""python -m resq.llm --check: Meterless provider settings and checks, with a fake Runtime."""
from types import SimpleNamespace

import httpx
import openai
import pytest

from resq import config, llm


def fake_completion(content):
    message = SimpleNamespace(content=content, tool_calls=None, model_extra={})
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], model="nvidia/fake", usage=None)


class FakeRuntime:
    def __init__(self, models=("nvidia/fast", "nvidia/deep"), list_error=None, reply="ready"):
        self._models, self._error, self._reply = models, list_error, reply
        self.models = SimpleNamespace(list=self.list)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_: fake_completion(self._reply)))

    def list(self):
        if self._error:
            raise self._error
        return [SimpleNamespace(id=m) for m in self._models]


@pytest.fixture
def meterless_env(monkeypatch):
    for name in ("MODEL_BASE_URL", "MODEL_API_KEY", "NEMOTRON_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("METERLESS_BASE_URL", "http://100.0.0.1:8088/v1")
    monkeypatch.setenv("METERLESS_RUNTIME_TOKEN", "runtime-secret-token")
    monkeypatch.setenv("METERLESS_MODEL", "meterless/auto")
    monkeypatch.setenv("LANE_FAST_MODEL", "nvidia/fast")
    monkeypatch.setenv("LANE_DEEP_MODEL", "nvidia/deep")
    config.get_settings.cache_clear()
    return monkeypatch


def install(monkeypatch, runtime):
    monkeypatch.setattr(llm, "_client", lambda: runtime)


def test_meterless_settings_are_the_default_provider(meterless_env):
    settings = config.get_settings()
    assert settings.model_base_url == "http://100.0.0.1:8088/v1"
    assert settings.model_api_key == "runtime-secret-token"
    assert settings.model_name == "meterless/auto"
    assert settings.model_provider == "Meterless Nightshift"


def test_model_settings_override_for_development(meterless_env):
    meterless_env.setenv("MODEL_BASE_URL", "https://integrate.api.nvidia.com/v1")
    meterless_env.setenv("MODEL_API_KEY", "nvapi-dev")
    config.get_settings.cache_clear()
    assert config.get_settings().model_provider == "NVIDIA direct (development only)"


def test_all_checks_pass(meterless_env, capsys):
    install(meterless_env, FakeRuntime())
    assert llm.main(["--check"]) == 0
    out = capsys.readouterr().out
    assert "PASS  provider" in out and "Meterless Nightshift" in out
    assert "PASS  meterless primary provider" in out
    assert "PASS  model discovery" in out and "PASS  deep lane request" in out
    assert "runtime-secret-token" not in out


def test_rejected_token_is_explained(meterless_env, capsys):
    response = httpx.Response(401, request=httpx.Request("GET", "http://x/v1/models"))
    install(meterless_env, FakeRuntime(list_error=openai.AuthenticationError("unauthorized", response=response, body=None)))
    assert llm.main(["--check"]) == 1
    assert "Nightshift Console" in capsys.readouterr().out


def test_unlisted_lane_model_and_empty_reply_fail(meterless_env):
    install(meterless_env, FakeRuntime(models=("nvidia/other",), reply=""))
    rows = {name: ok for name, ok, _ in llm.check(("fast",))}
    assert rows["fast lane model"] is False
    assert rows["fast lane request"] is False


def test_missing_configuration(monkeypatch):
    for name in ("MODEL_BASE_URL", "MODEL_API_KEY", "METERLESS_BASE_URL", "METERLESS_RUNTIME_TOKEN"):
        monkeypatch.setenv(name, "")
    config.get_settings.cache_clear()
    rows = llm.check()
    assert rows[0][1] is False and "Nightshift Console" in rows[-1][2]


def test_direct_nvidia_warns_but_does_not_fail(meterless_env, capsys):
    meterless_env.setenv("MODEL_BASE_URL", "https://integrate.api.nvidia.com/v1")
    meterless_env.setenv("MODEL_API_KEY", "nvapi-dev")
    config.get_settings.cache_clear()
    install(meterless_env, FakeRuntime())
    assert llm.main(["--check"]) == 0
    assert "WARN  meterless primary provider" in capsys.readouterr().out
