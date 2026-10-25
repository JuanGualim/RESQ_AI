import pytest

from resq.tools.zetaris import ZetarisError, coerce, run_sql, table


def test_sample_mode_reads_every_table():
    for name in ("communities", "shelters", "warehouses", "inventory", "road_nodes", "road_segments", "vehicles", "field_reports", "rainfall"):
        assert run_sql(f"SELECT COUNT(*) AS n FROM {table(name)}")[0]["n"] > 0


def test_numbers_are_parsed():
    row = run_sql(f"SELECT population, lat FROM {table('communities')} WHERE id = 'C07'")[0]
    assert isinstance(row["population"], int)
    assert isinstance(row["lat"], float)


def test_limit_is_applied():
    assert len(run_sql(f"SELECT * FROM {table('field_reports')}", limit=5)) == 5


def test_joins_work():
    rows = run_sql(
        f"SELECT v.id, w.road_node FROM {table('vehicles')} v JOIN {table('warehouses')} w ON v.warehouse_id = w.id ORDER BY v.id"
    )
    assert rows[0] == {"id": "V1", "road_node": "N01"}


def test_one_statement_per_call():
    with pytest.raises(ZetarisError):
        run_sql("SELECT 1; SELECT 2")


def test_bad_sql_raises_zetaris_error():
    with pytest.raises(ZetarisError):
        run_sql("SELECT * FROM no_such_table")


def test_unknown_table_name():
    with pytest.raises(ValueError):
        table("people")


def test_zetaris_mode_qualifies_names(monkeypatch):
    from resq import config
    monkeypatch.setenv("SAMPLE_MODE", "false")
    monkeypatch.setenv("ZETARIS_DATASOURCE", "resq_pg")
    config.get_settings.cache_clear()
    assert table("communities") == "resq_pg.communities"


@pytest.mark.parametrize("raw, expected", [("1", 1), ("-3", -3), ("2.5", 2.5), ("C01", "C01"), ("2020-11-05T10:00", "2020-11-05T10:00"), (None, None)])
def test_coerce(raw, expected):
    assert coerce(raw) == expected
