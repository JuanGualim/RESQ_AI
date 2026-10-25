"""Generate the synthetic RESQ AI flood scenario into data/sample/.

The municipality, communities, roads and field reports are fictional and built
from a fixed seed, so every run produces identical CSVs. Rainfall is a real
public snapshot from the Open-Meteo archive (Hurricane Eta, November 2020) at
the reference coordinates, cut at the scenario's decision time.

The road layout and the field reports below are scenario *data*: they include
deliberate contradictions (e.g. the official bulletin says T7 is open while two
brigades report it flooded) that the agents must discover on their own.

Usage:
    python scripts/generate_data.py                   # rebuild the scenario CSVs
    python scripts/generate_data.py --fetch-rainfall  # also refresh rainfall.csv
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

SEED = 20201105
ROOT_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT_DIR / "data" / "sample"

# Decision time of the scenario (local time, America/Guatemala, UTC-6).
SCENARIO_DATE = "2020-11-05"
SCENARIO_TIME = f"{SCENARIO_DATE}T10:00"
REFERENCE_LAT, REFERENCE_LON = 15.47, -88.84
RAINFALL_START = "2020-11-01"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

# Road nodes: id -> (lat, lon, (min_elevation_m, max_elevation_m)).
# The east of the municipality is the low river valley.
NODES = {
    "N01": (15.470, -88.840, (52, 58)),    # town center
    "N02": (15.520, -88.850, (125, 140)),  # north hill
    "N03": (15.465, -88.880, (60, 80)),
    "N04": (15.455, -88.800, (35, 45)),
    "N05": (15.565, -88.875, (180, 220)),
    "N06": (15.440, -88.905, (70, 90)),
    "N07": (15.430, -88.775, (18, 25)),
    "N08": (15.450, -88.770, (10, 16)),
    "N09": (15.455, -88.745, (8, 12)),
    "N10": (15.400, -88.760, (15, 22)),
    "N11": (15.410, -88.730, (6, 10)),
    "N12": (15.570, -88.815, (150, 190)),
    "N13": (15.545, -88.905, (90, 120)),
    "N14": (15.480, -88.925, (50, 65)),
    "N15": (15.445, -88.955, (70, 85)),
    "N16": (15.385, -88.740, (9, 14)),
}
LOWLAND_NODES = {"N07", "N08", "N09", "N10", "N11", "N16"}

# Undirected road segments: (id, origin, destination, distance_km, surface, official_status).
ROAD_SEGMENTS = [
    ("T1", "N01", "N02", 6.5, "paved", "open"),
    ("T2", "N01", "N03", 4.0, "paved", "open"),
    ("T3", "N01", "N04", 5.2, "paved", "open"),
    ("T4", "N02", "N05", 7.8, "gravel", "open"),
    ("T5", "N03", "N06", 3.5, "gravel", "open"),
    ("T6", "N04", "N07", 4.1, "paved", "open"),
    ("T7", "N04", "N08", 3.0, "paved", "open"),
    ("T8", "N07", "N08", 2.6, "dirt", "open"),
    ("T9", "N08", "N09", 2.2, "dirt", "open"),
    ("T10", "N07", "N10", 5.5, "gravel", "open"),
    ("T11", "N10", "N11", 3.3, "dirt", "flooded"),
    ("T12", "N09", "N11", 4.0, "dirt", "open"),
    ("T13", "N05", "N12", 6.0, "gravel", "open"),
    ("T14", "N12", "N13", 3.1, "dirt", "open"),
    ("T15", "N06", "N13", 4.7, "gravel", "open"),
    ("T16", "N03", "N14", 5.9, "paved", "open"),
    ("T17", "N14", "N15", 3.8, "gravel", "open"),
    ("T18", "N06", "N15", 6.4, "dirt", "closed"),
    ("T19", "N02", "N12", 9.0, "paved", "open"),
    ("T20", "N10", "N16", 2.9, "dirt", "open"),
    ("T21", "N11", "N16", 3.6, "dirt", "open"),
]

# Communities: (id, name, road_node).
COMMUNITIES = [
    ("C01", "Cerro Verde", "N05"),
    ("C02", "Buena Vista", "N06"),
    ("C03", "Los Amates", "N07"),
    ("C04", "Las Pozas", "N08"),
    ("C05", "Playitas", "N09"),
    ("C06", "Rio Blanco", "N10"),
    ("C07", "El Zapotal", "N11"),
    ("C08", "El Mirador", "N12"),
    ("C09", "La Ceibita", "N13"),
    ("C10", "San Marcos Abajo", "N14"),
    ("C11", "Nuevo Esfuerzo", "N15"),
    ("C12", "El Paraiso", "N16"),
    ("C13", "Las Flores", "N03"),
    ("C14", "Santa Rosa", "N04"),
]

# Shelters: (id, name, capacity, (min_occupancy, max_occupancy), road_node).
SHELTERS = [
    ("S1", "Escuela Central", 400, (180, 260), "N01"),
    ("S2", "Salon Comunal Loma Alta", 250, (200, 225), "N02"),
    ("S3", "Iglesia San Marcos", 150, (40, 80), "N14"),
    ("S4", "Centro Deportivo Los Amates", 300, (90, 140), "N07"),
]

WAREHOUSES = [
    ("W1", "Bodega Municipal Central", "N01"),
    ("W2", "Bodega Loma Alta", "N02"),
]

# Resources: name -> unit weight in kg.
RESOURCES = {
    "water_20l": 20.0,
    "food_kit": 12.0,
    "hygiene_kit": 3.0,
    "medical_kit": 5.0,
    "blanket": 1.5,
}
# Stock ranges per warehouse: (warehouse_id, resource) -> (min, max).
STOCK_RANGES = {
    "W1": {"water_20l": (500, 700), "food_kit": (600, 800), "hygiene_kit": (300, 400),
           "medical_kit": (60, 90), "blanket": (400, 600)},
    "W2": {"water_20l": (200, 300), "food_kit": (250, 350), "hygiene_kit": (120, 180),
           "medical_kit": (20, 35), "blanket": (150, 250)},
}

# Vehicles: (id, type, capacity_kg, can_ford, warehouse_id).
VEHICLES = [
    ("V1", "truck", 8000, False, "W1"),
    ("V2", "all_terrain_truck", 5000, True, "W1"),
    ("V3", "pickup", 1200, False, "W1"),
    ("V4", "pickup_4x4", 1000, True, "W2"),
    ("V5", "truck", 6000, False, "W2"),
    ("V6", "pickup_4x4", 900, True, "W2"),
]

# Field reports: (local time HH:MM, source, object_type, object_id, reported_status, detail).
FIELD_REPORTS = [
    ("05:30", "official", "road_segment", "T7", "open", "Road bulletin: T7 open to all traffic."),
    ("05:30", "official", "road_segment", "T11", "flooded", "Road bulletin: T11 under water near the river crossing."),
    ("05:30", "official", "road_segment", "T18", "closed", "Road bulletin: landslide on T18, road closed."),
    ("05:45", "official", "shelter", "S4", "operational", "Shelter S4 operating normally."),
    ("06:20", "brigade", "road_segment", "T3", "open", "Brigade 2 crossed T3 without problems."),
    ("06:40", "social_media", "community", "C07", "isolated", "Post: families on rooftops in El Zapotal, water rising."),
    ("06:55", "social_media", "road_segment", "T14", "closed", "Post: the bridge on T14 collapsed."),
    ("07:10", "brigade", "road_segment", "T7", "flooded", "Brigade 1: water 60 cm deep over T7 at km 2; only high-clearance vehicles can pass."),
    ("07:25", "social_media", "road_segment", "T7", "closed", "Post: road to Las Pozas closed, cars stuck."),
    ("07:40", "brigade", "shelter", "S4", "flooded", "Brigade 3: ground floor of S4 flooded, people moved upstairs; cannot receive more people."),
    ("07:50", "brigade", "road_segment", "T9", "passable_4x4", "Brigade 1: deep mud on T9, 4x4 vehicles only."),
    ("08:05", "brigade", "community", "C04", "needs_aid", "Brigade 1: Las Pozas needs drinking water and food for about 120 families."),
    ("08:15", "brigade", "road_segment", "T7", "flooded", "Brigade 4: confirms T7 flooded, water level still rising."),
    ("08:20", "brigade", "road_segment", "T11", "open", "Brigade 5: water receded on T11, passable with care."),
    ("08:30", "social_media", "road_segment", "T11", "flooded", "Post: T11 still flooded, do not cross."),
    ("08:35", "brigade", "road_segment", "T14", "damaged", "Brigade 6: T14 bridge has minor damage, open to traffic."),
    ("08:40", "brigade", "shelter", "S2", "full", "Brigade 2: S2 at about 95% of its capacity."),
    ("08:50", "official", "road_segment", "T1", "open", "Road bulletin update: T1 open."),
    ("08:55", "brigade", "community", "C07", "isolated", "Brigade 5: El Zapotal isolated, about 40 families need water and medical care; 3 elderly people with chronic illness."),
    ("09:00", "social_media", "community", "C05", "evacuating", "Post: Playitas is evacuating to the hill."),
    ("09:05", "brigade", "road_segment", "T18", "closed", "Brigade 6: T18 still blocked by the landslide."),
    ("09:10", "official", "shelter", "S4", "operational", "Bulletin update: shelter S4 remains available."),
    ("09:15", "brigade", "road_segment", "T20", "open", "Brigade 5: T20 open."),
    ("09:20", "social_media", "road_segment", "T20", "flooded", "Post: T20 under water."),
    ("09:25", "brigade", "community", "C12", "needs_aid", "Brigade 5: El Paraiso needs food kits and blankets."),
    ("09:30", "brigade", "road_segment", "T8", "open", "Brigade 3: T8 open, some debris on the road."),
    ("09:35", "social_media", "community", "C03", "needs_aid", "Post: Los Amates has no drinking water."),
    ("09:40", "brigade", "road_segment", "T10", "open", "Brigade 3: T10 open."),
    ("09:45", "official", "road_segment", "T6", "open", "Road bulletin: T6 open."),
    ("09:50", "brigade", "community", "C06", "stable", "Brigade 4: Rio Blanco families stable, supplies for 24 hours."),
]

# Column order of every CSV (matches the tables in AGENTS.md section 6).
COLUMNS = {
    "communities": ["id", "name", "population", "pct_children", "pct_elderly", "vulnerability",
                    "elevation_m", "lat", "lon", "road_node"],
    "shelters": ["id", "name", "capacity", "current_occupancy", "road_node"],
    "warehouses": ["id", "name", "road_node"],
    "inventory": ["warehouse_id", "resource", "quantity", "unit_weight_kg"],
    "road_nodes": ["id", "lat", "lon"],
    "road_segments": ["id", "origin", "destination", "distance_km", "surface", "official_status"],
    "vehicles": ["id", "type", "capacity_kg", "can_ford", "warehouse_id"],
    "field_reports": ["id", "timestamp", "source", "object_type", "object_id", "reported_status", "detail"],
    "rainfall": ["datetime", "precipitation_mm"],
}


def build_scenario(seed: int = SEED) -> dict[str, list[dict]]:
    """Build every scenario table except rainfall. Same seed -> same output."""
    rng = random.Random(seed)

    communities = []
    for community_id, name, node in COMMUNITIES:
        lat, lon, (low, high) = NODES[node]
        lowland = node in LOWLAND_NODES
        communities.append({
            "id": community_id,
            "name": name,
            "population": rng.randrange(150, 2500, 10),
            "pct_children": round(rng.uniform(25, 42), 1),
            "pct_elderly": round(rng.uniform(5, 15), 1),
            "vulnerability": rng.randint(3, 5) if lowland else rng.randint(1, 4),
            "elevation_m": rng.randint(low, high),
            "lat": round(lat + rng.uniform(-0.004, 0.004), 5),
            "lon": round(lon + rng.uniform(-0.004, 0.004), 5),
            "road_node": node,
        })

    shelters = [
        {"id": sid, "name": name, "capacity": capacity,
         "current_occupancy": rng.randint(low, high), "road_node": node}
        for sid, name, capacity, (low, high), node in SHELTERS
    ]

    warehouses = [{"id": wid, "name": name, "road_node": node} for wid, name, node in WAREHOUSES]

    inventory = [
        {"warehouse_id": wid, "resource": resource,
         "quantity": rng.randint(low, high), "unit_weight_kg": RESOURCES[resource]}
        for wid, ranges in STOCK_RANGES.items()
        for resource, (low, high) in ranges.items()
    ]

    road_nodes = [{"id": node, "lat": lat, "lon": lon} for node, (lat, lon, _) in NODES.items()]

    road_segments = [
        {"id": sid, "origin": origin, "destination": destination, "distance_km": km,
         "surface": surface, "official_status": status}
        for sid, origin, destination, km, surface, status in ROAD_SEGMENTS
    ]

    vehicles = [
        {"id": vid, "type": vtype, "capacity_kg": capacity,
         "can_ford": str(can_ford).lower(), "warehouse_id": wid}
        for vid, vtype, capacity, can_ford, wid in VEHICLES
    ]

    field_reports = [
        {"id": f"R{index:03d}", "timestamp": f"{SCENARIO_DATE}T{hhmm}:00", "source": source,
         "object_type": object_type, "object_id": object_id,
         "reported_status": status, "detail": detail}
        for index, (hhmm, source, object_type, object_id, status, detail)
        in enumerate(FIELD_REPORTS, start=1)
    ]

    return {
        "communities": communities,
        "shelters": shelters,
        "warehouses": warehouses,
        "inventory": inventory,
        "road_nodes": road_nodes,
        "road_segments": road_segments,
        "vehicles": vehicles,
        "field_reports": field_reports,
    }


def fetch_rainfall() -> list[dict]:
    """Hourly precipitation from Open-Meteo's archive, up to the decision time."""
    import requests

    response = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": REFERENCE_LAT,
            "longitude": REFERENCE_LON,
            "start_date": RAINFALL_START,
            "end_date": SCENARIO_DATE,
            "hourly": "precipitation",
            "timezone": "America/Guatemala",
        },
        timeout=60,
    )
    response.raise_for_status()
    hourly = response.json()["hourly"]
    return [
        {"datetime": time, "precipitation_mm": precipitation}
        for time, precipitation in zip(hourly["time"], hourly["precipitation"])
        if time <= SCENARIO_TIME and precipitation is not None
    ]


def write_csv(rows: list[dict], path: Path, columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_scenario(tables: dict[str, list[dict]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for table, rows in tables.items():
        write_csv(rows, out_dir / f"{table}.csv", COLUMNS[table])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="output folder (default: data/sample)")
    parser.add_argument("--seed", type=int, default=SEED, help=f"random seed (default: {SEED})")
    parser.add_argument("--fetch-rainfall", action="store_true",
                        help="download rainfall.csv from Open-Meteo (needs internet)")
    args = parser.parse_args(argv)

    tables = build_scenario(args.seed)
    if args.fetch_rainfall:
        tables["rainfall"] = fetch_rainfall()
    elif not (args.out / "rainfall.csv").exists():
        print("rainfall.csv not found: run again with --fetch-rainfall", file=sys.stderr)

    write_scenario(tables, args.out)
    for table, rows in tables.items():
        print(f"{table:15} {len(rows):4} rows -> {args.out / (table + '.csv')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
