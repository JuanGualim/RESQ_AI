"""Setup scripts stay consistent with the data contract (offline: no Postgres, no Zetaris)."""
import importlib.util
from pathlib import Path

import pytest

from resq.tools import zetaris

ROOT_DIR = Path(__file__).resolve().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT_DIR / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scripts():
    pytest.importorskip("psycopg")
    return load_script("load_postgres"), load_script("register_zetaris"), load_script("generate_data")


def test_postgres_schema_matches_generator_columns(scripts):
    load_postgres, _, generate_data = scripts
    for name, columns in load_postgres.SCHEMA.items():
        assert [column for column, _ in columns] == generate_data.COLUMNS[name], name


def test_every_agent_table_is_loaded_and_registered(scripts):
    load_postgres, register_zetaris, _ = scripts
    assert set(load_postgres.SCHEMA) == set(zetaris.TABLES)
    assert set(register_zetaris.TABLES) == set(zetaris.TABLES)


def test_dry_run_masks_the_password(scripts, monkeypatch):
    _, register_zetaris, _ = scripts
    from resq import config
    monkeypatch.setenv("RESQ_PG_PASSWORD", "super-secret-value")
    config.get_settings.cache_clear()
    shown = "\n".join(register_zetaris.statements(mask=True))
    assert "super-secret-value" not in shown and "******" in shown
    assert 'jdbcurl "jdbc:postgresql://resq-postgres:5432/resq"' in shown
    assert "REGISTER DATASOURCE TABLES FROM resq_pg" in shown


def test_datasource_description_is_valid_for_zetaris(scripts):
    _, register_zetaris, _ = scripts
    description = register_zetaris.statements(mask=True)[0].split('DESCRIBE BY "')[1].split('"')[0]
    assert all(ch.isalnum() or ch in "_.-," for ch in description)  # Zetaris rejects spaces and parentheses
