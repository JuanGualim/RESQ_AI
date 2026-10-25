import csv
import importlib.util
from pathlib import Path

import networkx as nx

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT_DIR / "data" / "sample"

_spec = importlib.util.spec_from_file_location("generate_data", ROOT_DIR / "scripts" / "generate_data.py")
generate_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_data)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def ids(rows: list[dict]) -> set[str]:
    return {row["id"] for row in rows}


def test_same_seed_gives_same_scenario():
    assert generate_data.build_scenario() == generate_data.build_scenario()


def test_different_seed_changes_random_fields():
    assert generate_data.build_scenario(1)["communities"] != generate_data.build_scenario(2)["communities"]


def test_committed_sample_is_up_to_date(tmp_path):
    generate_data.write_scenario(generate_data.build_scenario(), tmp_path)
    for generated in tmp_path.glob("*.csv"):
        committed = SAMPLE_DIR / generated.name
        assert committed.read_text(encoding="utf-8") == generated.read_text(encoding="utf-8"), (
            f"{committed.name} is stale: run python scripts/generate_data.py"
        )


def test_sizes_match_agents_md():
    tables = generate_data.build_scenario()
    assert 12 <= len(tables["communities"]) <= 15
    assert 3 <= len(tables["shelters"]) <= 4
    assert len(tables["warehouses"]) == 2
    assert 18 <= len(tables["road_segments"]) <= 22
    assert 5 <= len(tables["vehicles"]) <= 8
    assert 25 <= len(tables["field_reports"]) <= 35


def test_columns_match_declared_order():
    for table, rows in generate_data.build_scenario().items():
        assert list(rows[0]) == generate_data.COLUMNS[table], table


def test_ids_are_unique():
    for table, rows in generate_data.build_scenario().items():
        if "id" in generate_data.COLUMNS[table]:
            assert len(ids(rows)) == len(rows), table


def test_road_network_is_connected_and_every_place_is_on_it():
    tables = generate_data.build_scenario()
    graph = nx.Graph()
    graph.add_edges_from((s["origin"], s["destination"]) for s in tables["road_segments"])
    assert set(graph.nodes) == set(generate_data.NODES)
    assert nx.is_connected(graph)
    for table in ("communities", "shelters", "warehouses"):
        for row in tables[table]:
            assert row["road_node"] in graph, (table, row["id"])


def test_foreign_keys_exist():
    tables = generate_data.build_scenario()
    warehouse_ids = ids(tables["warehouses"])
    assert {row["warehouse_id"] for row in tables["inventory"]} <= warehouse_ids
    assert {row["warehouse_id"] for row in tables["vehicles"]} <= warehouse_ids
    known = {
        "road_segment": ids(tables["road_segments"]),
        "shelter": ids(tables["shelters"]),
        "community": ids(tables["communities"]),
    }
    for report in tables["field_reports"]:
        assert report["object_id"] in known[report["object_type"]], report["id"]


def test_value_ranges():
    tables = generate_data.build_scenario()
    for community in tables["communities"]:
        assert 1 <= community["vulnerability"] <= 5
        assert community["population"] > 0
        assert 0 < community["pct_children"] + community["pct_elderly"] < 100
    for shelter in tables["shelters"]:
        assert 0 <= shelter["current_occupancy"] <= shelter["capacity"]
    assert any(v["can_ford"] == "true" for v in tables["vehicles"])
    assert any(v["can_ford"] == "false" for v in tables["vehicles"])


def test_reports_are_chronological_and_before_decision_time():
    reports = generate_data.build_scenario()["field_reports"]
    timestamps = [r["timestamp"] for r in reports]
    assert timestamps == sorted(timestamps)
    assert timestamps[-1] <= generate_data.SCENARIO_TIME + ":00"


def test_seeded_contradiction_on_t7():
    reports = [r for r in generate_data.build_scenario()["field_reports"] if r["object_id"] == "T7"]
    statuses = {(r["source"], r["reported_status"]) for r in reports}
    assert ("official", "open") in statuses
    assert ("brigade", "flooded") in statuses


def test_rainfall_snapshot_is_valid():
    rows = read_csv(SAMPLE_DIR / "rainfall.csv")
    assert rows, "run python scripts/generate_data.py --fetch-rainfall"
    assert rows[-1]["datetime"] <= generate_data.SCENARIO_TIME
    assert all(float(row["precipitation_mm"]) >= 0 for row in rows)
    assert sum(float(row["precipitation_mm"]) for row in rows) > 100  # Eta was a heavy rain event


def test_every_road_node_has_coordinates():
    tables = generate_data.build_scenario()
    nodes = {row["id"]: row for row in tables["road_nodes"]}
    used = {s["origin"] for s in tables["road_segments"]} | {s["destination"] for s in tables["road_segments"]}
    assert used == set(nodes)
    for row in nodes.values():
        assert 15.0 < row["lat"] < 16.0 and -89.5 < row["lon"] < -88.0
