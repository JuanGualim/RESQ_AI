"""Load data/sample/ into the scenario Postgres (docker-compose.yml) that Zetaris reads as resq_pg.

Recreates every table with explicit types and loads the CSVs with COPY, so a
re-run always leaves Postgres identical to data/sample/.

    docker compose up -d
    python scripts/load_postgres.py            # load
    python scripts/load_postgres.py --check    # only compare row counts with the CSVs
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import psycopg
from psycopg import sql

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from resq.config import get_settings  # noqa: E402

# Column types per table, in CSV column order. Timestamps stay as ISO text so the same
# string comparisons work in Zetaris, Postgres and SAMPLE_MODE (SQLite).
SCHEMA = {
    "communities": [("id", "text primary key"), ("name", "text"), ("population", "integer"),
                    ("pct_children", "double precision"), ("pct_elderly", "double precision"),
                    ("vulnerability", "integer"), ("elevation_m", "integer"), ("lat", "double precision"),
                    ("lon", "double precision"), ("road_node", "text")],
    "shelters": [("id", "text primary key"), ("name", "text"), ("capacity", "integer"),
                 ("current_occupancy", "integer"), ("road_node", "text")],
    "warehouses": [("id", "text primary key"), ("name", "text"), ("road_node", "text")],
    "inventory": [("warehouse_id", "text"), ("resource", "text"), ("quantity", "integer"),
                  ("unit_weight_kg", "double precision")],
    "road_nodes": [("id", "text primary key"), ("lat", "double precision"), ("lon", "double precision")],
    "road_segments": [("id", "text primary key"), ("origin", "text"), ("destination", "text"),
                      ("distance_km", "double precision"), ("surface", "text"), ("official_status", "text")],
    "vehicles": [("id", "text primary key"), ("type", "text"), ("capacity_kg", "integer"),
                 ("can_ford", "boolean"), ("warehouse_id", "text")],
    "field_reports": [("id", "text primary key"), ("timestamp", "text"), ("source", "text"),
                      ("object_type", "text"), ("object_id", "text"), ("reported_status", "text"), ("detail", "text")],
    "rainfall": [("datetime", "text primary key"), ("precipitation_mm", "double precision")],
}
EXTRA = {"inventory": "primary key (warehouse_id, resource)"}


def connect() -> psycopg.Connection:
    s = get_settings()
    if not s.pg_password:
        raise SystemExit("RESQ_PG_PASSWORD is not set in .env")
    return psycopg.connect(host=s.pg_host, port=s.pg_port, dbname=s.pg_db, user=s.pg_user,
                           password=s.pg_password, connect_timeout=10)


def csv_rows(name: str) -> int:
    with (get_settings().sample_data_dir / f"{name}.csv").open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.reader(handle)) - 1


def load(conn: psycopg.Connection) -> None:
    sample_dir = get_settings().sample_data_dir
    with conn.cursor() as cur:
        for name, columns in SCHEMA.items():
            with (sample_dir / f"{name}.csv").open(encoding="utf-8", newline="") as handle:
                header = next(csv.reader(handle))
            expected = [column for column, _ in columns]
            if header != expected:
                raise SystemExit(f"{name}.csv columns {header} do not match the schema {expected}")
            definitions = [sql.SQL("{} {}").format(sql.Identifier(c), sql.SQL(t)) for c, t in columns]
            if name in EXTRA:
                definitions.append(sql.SQL(EXTRA[name]))
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(name)))
            cur.execute(sql.SQL("CREATE TABLE {} ({})").format(sql.Identifier(name), sql.SQL(", ").join(definitions)))
            copy = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
                sql.Identifier(name), sql.SQL(", ").join(map(sql.Identifier, expected)))
            with cur.copy(copy) as writer, (sample_dir / f"{name}.csv").open("rb") as handle:
                while chunk := handle.read(65536):
                    writer.write(chunk)
    conn.commit()


def check(conn: psycopg.Connection) -> bool:
    ok = True
    with conn.cursor() as cur:
        for name in SCHEMA:
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(name)))
            count, expected = cur.fetchone()[0], csv_rows(name)
            ok &= count == expected
            print(f"{'OK  ' if count == expected else 'DIFF'} {name:15} postgres={count:4} csv={expected:4}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only compare row counts with data/sample/")
    args = parser.parse_args()
    with connect() as conn:
        if not args.check:
            load(conn)
        return 0 if check(conn) else 1


if __name__ == "__main__":
    sys.exit(main())
