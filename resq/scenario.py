"""Loads the scenario from Zetaris (or SAMPLE_MODE) into the World Model, and keeps the scenario clock."""
from __future__ import annotations

from datetime import datetime, timedelta

from resq import world
from resq.tools.zetaris import run_sql, table

SEED_TABLES = ("communities", "shelters", "warehouses", "inventory", "road_nodes", "road_segments", "vehicles")
COORDINATOR_STEP_MIN = 5


def normalize_ts(value: str) -> str:
    """'2020-11-05T10:00' or '2020-11-05 10:00:00' -> '2020-11-05T10:00:00'."""
    return datetime.fromisoformat(str(value).replace(" ", "T")).strftime("%Y-%m-%dT%H:%M:%S")


def load_tables() -> dict[str, list[dict]]:
    return {name: run_sql(f"SELECT * FROM {table(name)}", limit=5000) for name in SEED_TABLES}


def data_time() -> str:
    """Decision time = latest observation in the data (rainfall or field report)."""
    rain = run_sql(f"SELECT MAX(datetime) AS latest FROM {table('rainfall')}", limit=1)
    reports = run_sql(f"SELECT MAX(timestamp) AS latest FROM {table('field_reports')}", limit=1)
    candidates = [row["latest"] for row in rain + reports if row.get("latest")]
    return max(normalize_ts(value) for value in candidates)


def now() -> str:
    """Scenario 'now': the data time, moved forward by every coordinator event already applied."""
    latest = data_time()
    for event in world.history():
        if event.get("source") == "coordinator" and event.get("ts", "") > latest:
            latest = event["ts"]
    return latest


def next_coordinator_ts() -> str:
    """Coordinator actions happen a few scenario minutes after the latest known moment."""
    moment = datetime.fromisoformat(now()) + timedelta(minutes=COORDINATOR_STEP_MIN)
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def bootstrap() -> dict:
    """Seed the World Model with the scenario rows (idempotent) and return the current state."""
    world.seed(load_tables(), at=data_time())
    return world.get_state()
