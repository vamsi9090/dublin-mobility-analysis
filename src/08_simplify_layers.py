"""
Simplify + round-precision the geometry-heavy layers before mapping.
Overpass 'out geom' and the GTFS shapes.txt give full-precision (7 decimal
place, sub-cm) coordinates and dense vertex spacing -- massive overkill for
a city-overview web map and the reason the raw map came out at 61MB. A ~6m
simplification tolerance and 5-decimal (~1.1m) coordinate rounding are both
far below what's visually distinguishable at any zoom level a user would
actually view this map at, so this loses no visible information.
"""
import json

from shapely.geometry import shape, mapping

TOLERANCE_DEG = 0.00006  # ~6-7m at Dublin's latitude
ROUND_DP = 5  # ~1.1m precision


def round_coords(obj):
    if isinstance(obj, float):
        return round(obj, ROUND_DP)
    if isinstance(obj, list):
        return [round_coords(x) for x in obj]
    return obj


import os

MAP_LAYER_DIR = "../data/map_layers"
os.makedirs(MAP_LAYER_DIR, exist_ok=True)


def simplify_file(src_path, out_path, is_line=True):
    with open(src_path, encoding="utf-8") as f:
        fc = json.load(f)
    before = len(json.dumps(fc))
    for feat in fc["features"]:
        geom = shape(feat["geometry"])
        if is_line:
            geom = geom.simplify(TOLERANCE_DEG, preserve_topology=False)
        feat["geometry"] = mapping(geom)
        feat["geometry"]["coordinates"] = round_coords(feat["geometry"]["coordinates"])
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, separators=(",", ":"))
    after = len(json.dumps(fc))
    print(f"{src_path} -> {out_path}: {before/1024:.0f} KB -> {after/1024:.0f} KB ({len(fc['features'])} features)")


# Source (untouched, kept as downloaded/derived) -> simplified copy for the map only
LINE_LAYERS = [
    "gov/bus_routes_dublin.geojson",
    "osm_bus_routes_urban.geojson",
    "osm_bus_routes_other.geojson",
    "osm/walking.geojson",
    "osm/cycling.geojson",
    "gov_cycle_dublin_city.geojson",
]
POINT_LAYERS = ["osm/bus_stops.geojson", "osm/taxi_ranks.geojson"]

for rel_path in LINE_LAYERS:
    out_name = rel_path.replace("/", "__")
    simplify_file(f"../data/{rel_path}", f"{MAP_LAYER_DIR}/{out_name}", is_line=True)

for rel_path in POINT_LAYERS:
    out_name = rel_path.replace("/", "__")
    simplify_file(f"../data/{rel_path}", f"{MAP_LAYER_DIR}/{out_name}", is_line=False)
