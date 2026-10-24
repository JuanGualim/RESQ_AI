"""The agents' only data access: one SQL statement per call (AGENTS.md rule 1).

Normal mode sends the SQL to Zetaris' REST API. In SAMPLE_MODE the same SQL runs
on an in-memory SQLite copy of data/sample/, so judges and developers without
Zetaris get identical rows. Keep queries to portable SQL (SELECT, JOIN, WHERE,
GROUP BY, ORDER BY) so they work on both, and build table names with `table()`.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import time
import uuid
from functools import lru_cache

import requests

from resq.config import get_settings

TABLES = (
    "communities", "shelters", "warehouses", "inventory",
    "road_segments", "vehicles", "field_reports", "rainfall",
)
_INT = re.compile(r"-?\d+")
_FLOAT = re.compile(r"-?\d+\.\d*([eE]-?\d+)?")


class ZetarisError(RuntimeError):
    """A query failed: bad SQL, bad credentials or the service is unreachable."""


def table(name: str) -> str:
    """Qualified table name for the active backend."""
    if name not in TABLES:
        raise ValueError(f"unknown table: {name!r}")
    settings = get_settings()
    if settings.sample_mode:
        return name
    if name == "rainfall" and settings.zetaris_rainfall_table:
        return settings.zetaris_rainfall_table
    return f"{settings.zetaris_datasource}.{name}"


def run_sql(sql: str, limit: int = 500) -> list[dict]:
    """Run ONE statement and return its rows as dicts with numbers already parsed."""
    statement = sql.strip().rstrip(";").strip()
    if not statement:
        raise ZetarisError("empty SQL")
    if ";" in statement:
        raise ZetarisError("one statement per call: remove the ';'")
    if get_settings().sample_mode:
        return _run_sample(statement, limit)
    return _run_zetaris(statement, limit)


def coerce(value):
    """Zetaris returns every value as text; parse integers and decimals."""
    if not isinstance(value, str):
        return value
    if _INT.fullmatch(value):
        return int(value)
    if _FLOAT.fullmatch(value):
        return float(value)
    return value


def _run_zetaris(sql: str, limit: int) -> list[dict]:
    settings = get_settings()
    if not (settings.zetaris_rest_url and settings.zetaris_api_key and settings.zetaris_org_id):
        raise ZetarisError("Zetaris is not configured: set ZETARIS_REST_URL, ZETARIS_ORG_ID and ZETARIS_API_KEY, or SAMPLE_MODE=true")
    url = settings.zetaris_rest_url + "/sql-editor/sqls/run"
    last_error = ""
    for attempt in range(settings.max_retries + 1):
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": "Bearer " + settings.zetaris_api_key,
                    "X-Org-ID": settings.zetaris_org_id,
                    "X-Request-ID": str(uuid.uuid4()),
                },
                json={"queryId": str(uuid.uuid4()), "sql": sql, "source": "SqlEditor", "limit": limit},
                timeout=settings.zetaris_timeout_s,
            )
        except requests.RequestException as error:
            last_error = f"Zetaris unreachable: {type(error).__name__}"
        else:
            if response.status_code < 500:
                return _parse_response(response, sql)
            last_error = f"Zetaris HTTP {response.status_code}"
        if attempt < settings.max_retries:
            time.sleep(1.5 * (attempt + 1))
    raise ZetarisError(f"{last_error} after {settings.max_retries + 1} attempts")


def _parse_response(response: requests.Response, sql: str) -> list[dict]:
    if response.status_code != 200:
        raise ZetarisError(f"Zetaris HTTP {response.status_code}: {response.text[:200]} | SQL: {sql[:120]}")
    body = response.json()
    if not isinstance(body, dict) or "data" not in body:
        raise ZetarisError(f"unexpected Zetaris response: {str(body)[:200]}")
    headers = body.get("headers") or []
    return [dict(zip(headers, (coerce(v) for v in row))) for row in body["data"]]


@lru_cache(maxsize=1)
def _sample_db() -> sqlite3.Connection:
    """In-memory SQLite with every CSV in data/sample/ loaded as a table."""
    sample_dir = get_settings().sample_data_dir
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    for name in TABLES:
        path = sample_dir / f"{name}.csv"
        if not path.exists():
            raise ZetarisError(f"{path} not found: run python scripts/generate_data.py")
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [[coerce(v) for v in row.values()] for row in reader]
            columns = reader.fieldnames or []
        connection.execute(f'CREATE TABLE {name} ({", ".join(f"{c!r}" for c in columns)})')
        connection.executemany(f'INSERT INTO {name} VALUES ({", ".join("?" for _ in columns)})', rows)
    return connection


def _run_sample(sql: str, limit: int) -> list[dict]:
    try:
        cursor = _sample_db().execute(sql)
    except sqlite3.Error as error:
        raise ZetarisError(f"SAMPLE_MODE query failed: {error} | SQL: {sql[:120]}") from error
    return [dict(row) for row in cursor.fetchmany(limit)]
