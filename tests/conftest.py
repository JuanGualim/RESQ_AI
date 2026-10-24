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
