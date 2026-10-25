"""Register the scenario Postgres in Zetaris as a datasource and import its tables.

    python scripts/register_zetaris.py --dry-run   # show the statements (password masked)
    python scripts/register_zetaris.py             # CREATE DATASOURCE + REGISTER DATASOURCE TABLES
    python scripts/register_zetaris.py --verify    # only check that every table answers through Zetaris

Needs a Zetaris administrator API key (CREATE DATASOURCE is administrators only).
Zetaris runs in Docker, so the JDBC URL uses the container name (RESQ_PG_HOST_FOR_ZETARIS).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from resq.config import get_settings  # noqa: E402
from resq.tools import zetaris  # noqa: E402

TABLES = [name for name in zetaris.TABLES]


def statements(mask: bool) -> list[str]:
    s = get_settings()
    password = "******" if mask else s.pg_password
    return [
        f'CREATE DATASOURCE {s.zetaris_datasource} DESCRIBE BY "RESQ_AI_flood_scenario_PostgreSQL" OPTIONS ('
        f'jdbcdriver "org.postgresql.Driver", jdbcurl "jdbc:postgresql://{s.pg_host_for_zetaris}/{s.pg_db}", '
        f'username "{s.pg_user}", password "{password}", fetchsize "1000")',
        f"REGISTER DATASOURCE TABLES FROM {s.zetaris_datasource}",
    ]


def verify() -> bool:
    ok = True
    for name in TABLES:
        qualified = f"{get_settings().zetaris_datasource}.{name}"
        try:
            count = zetaris._run_zetaris(f"SELECT COUNT(*) AS n FROM {qualified}", 1)[0]["n"]
            print(f"OK   {qualified:28} {count} rows")
        except zetaris.ZetarisError as error:
            ok = False
            print(f"FAIL {qualified:28} {str(error)[:150]}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the statements, send nothing")
    parser.add_argument("--verify", action="store_true", help="only query every table through Zetaris")
    parser.add_argument("--skip-exists", action="store_true", help="continue when the datasource already exists")
    args = parser.parse_args()

    if args.dry_run:
        print("\n".join(statements(mask=True)))
        return 0
    if not args.verify:
        if not get_settings().pg_password:
            raise SystemExit("RESQ_PG_PASSWORD is not set in .env")
        # Uses the Zetaris backend directly, whatever SAMPLE_MODE says: this is setup, not agent data access.
        for statement, shown in zip(statements(mask=False), statements(mask=True)):
            print(f"-> {shown[:110]}…" if len(shown) > 110 else f"-> {shown}")
            try:
                rows = zetaris._run_zetaris(statement, 100)
                print(f"   ok {rows[:3]}")
            except zetaris.ZetarisError as error:
                message = str(error).replace(get_settings().pg_password, "******")
                if args.skip_exists and "exist" in message.lower():
                    print("   already exists, skipped")
                    continue
                print(f"   FAILED: {message[:300]}")
                return 1
    return 0 if verify() else 1


if __name__ == "__main__":
    sys.exit(main())
