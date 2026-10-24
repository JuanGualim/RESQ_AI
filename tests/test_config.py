import pytest

from resq.config import load_settings

ENV_VARS = [
    "ZETARIS_REST_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY",
    "MODEL_BASE_URL", "MODEL_API_KEY", "NEMOTRON_MODEL",
    "LANE_FAST_MODEL", "LANE_DEEP_MODEL", "WORLD_MODEL_URL", "SAMPLE_MODE",
]


@pytest.fixture
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.mark.parametrize("raw, expected", [
    ("true", True), ("TRUE", True), ("1", True), ("yes", True),
    ("false", False), ("0", False), ("", False),
])
def test_sample_mode_parsing(clean_env, raw, expected):
    clean_env.setenv("SAMPLE_MODE", raw)
    assert load_settings().sample_mode is expected


def test_sample_mode_defaults_to_false(clean_env):
    assert load_settings().sample_mode is False


def test_lanes_fall_back_to_nemotron_model(clean_env):
    clean_env.setenv("NEMOTRON_MODEL", "nvidia/nemotron-test")
    settings = load_settings()
    assert settings.lane_model("fast") == "nvidia/nemotron-test"
    assert settings.lane_model("deep") == "nvidia/nemotron-test"


def test_explicit_lanes_win(clean_env):
    clean_env.setenv("NEMOTRON_MODEL", "base")
    clean_env.setenv("LANE_FAST_MODEL", "fast-model")
    clean_env.setenv("LANE_DEEP_MODEL", "deep-model")
    settings = load_settings()
    assert settings.lane_model("fast") == "fast-model"
    assert settings.lane_model("deep") == "deep-model"


def test_unknown_lane_raises(clean_env):
    with pytest.raises(ValueError):
        load_settings().lane_model("medium")


def test_secrets_are_not_in_repr(clean_env):
    clean_env.setenv("ZETARIS_API_KEY", "zetaris-secret-value")
    clean_env.setenv("MODEL_API_KEY", "nvapi-secret-value")
    text = repr(load_settings())
    assert "zetaris-secret-value" not in text
    assert "nvapi-secret-value" not in text


def test_urls_lose_trailing_slash(clean_env):
    clean_env.setenv("ZETARIS_REST_URL", "http://localhost:8888/api/v1.0/")
    clean_env.setenv("MODEL_BASE_URL", "http://127.0.0.1:8088/v1/")
    settings = load_settings()
    assert settings.zetaris_rest_url == "http://localhost:8888/api/v1.0"
    assert settings.model_base_url == "http://127.0.0.1:8088/v1"
