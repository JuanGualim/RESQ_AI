"""Central configuration for RESQ AI.

Reads `.env` once (real environment variables win) and exposes typed settings.
Every other module reads configuration from here instead of `os.environ`.
Secret fields are excluded from `repr()` so settings can be logged safely.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DATA_DIR = ROOT_DIR / "data" / "sample"
LOGS_DIR = ROOT_DIR / "logs"

load_dotenv(ROOT_DIR / ".env", override=False)

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class Settings:
    # Data: Zetaris
    zetaris_rest_url: str
    zetaris_org_id: str
    zetaris_api_key: str = field(repr=False)
    zetaris_datasource: str = "resq_pg"  # Postgres datasource registered in Zetaris
    zetaris_rainfall_table: str = ""  # Open-Meteo REST table; empty = <datasource>.rainfall
    # Power: model provider (Nightshift by default, direct NVIDIA only in development)
    model_base_url: str = ""
    model_api_key: str = field(default="", repr=False)
    model_name: str = ""
    lane_fast_model: str = ""
    lane_deep_model: str = ""
    # World Model service (TODO(verify): confirmed once R1 is closed)
    world_model_url: str = ""
    # No-services mode: read data/sample/ instead of Zetaris
    sample_mode: bool = False
    sample_data_dir: Path = SAMPLE_DATA_DIR
    logs_dir: Path = LOGS_DIR
    # Limits from AGENTS.md section 7
    zetaris_timeout_s: int = 60
    model_timeout_s: int = 90
    max_retries: int = 2
    max_critic_rounds: int = 3

    def lane_model(self, lane: str) -> str:
        """Model name for a lane ("fast" | "deep")."""
        if lane == "fast":
            return self.lane_fast_model
        if lane == "deep":
            return self.lane_deep_model
        raise ValueError(f"unknown lane: {lane!r} (expected 'fast' or 'deep')")


def load_settings() -> Settings:
    """Build settings from the current environment (no caching)."""
    model_name = _env("NEMOTRON_MODEL")
    fast_model = _env("LANE_FAST_MODEL") or model_name
    return Settings(
        zetaris_rest_url=_env("ZETARIS_REST_URL").rstrip("/"),
        zetaris_org_id=_env("ZETARIS_ORG_ID"),
        zetaris_api_key=_env("ZETARIS_API_KEY"),
        zetaris_datasource=_env("ZETARIS_DATASOURCE", "resq_pg"),
        zetaris_rainfall_table=_env("ZETARIS_RAINFALL_TABLE"),
        model_base_url=_env("MODEL_BASE_URL").rstrip("/"),
        model_api_key=_env("MODEL_API_KEY"),
        model_name=model_name,
        lane_fast_model=fast_model,
        lane_deep_model=_env("LANE_DEEP_MODEL") or fast_model,
        world_model_url=_env("WORLD_MODEL_URL").rstrip("/"),
        sample_mode=_env_bool("SAMPLE_MODE"),
        logs_dir=Path(_env("RESQ_LOGS_DIR") or LOGS_DIR),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, loaded once."""
    return load_settings()
