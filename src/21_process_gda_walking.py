"""
Process the walking-verification agent's raw per-council Overpass responses
into one clean, deduplicated, boundary-clipped, size-optimized GeoJSON for
the GDA-scope map. The agent only saved raw responses, not a final mappable
file, so this reconstructs it (using the same clip/simplify methodology
validated elsewhere in this analysis).
"""
import json
import math

from shapely.geometry import shape, LineString, mapping
from shapely.ops import transform as shp_transform

RAW_DIR = "../data/osm_gda_walking_verify"
FILES = ["raw_dublin_city.json", "raw_fingal.json", "raw_south_dublin.json", "raw_dlr.json"]

with open("../data/boundary_greater_dublin_region.geojson", encoding="utf-8") as f:
    boundary_poly = shape(json.load(f)["geometry"])

lat0 = 53.35
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))


def to_m(lon, lat):
    return (lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT)


def project(geom):
    return shp_transform(lambda x, y, z=None: to_m(x, y), geom)


boundary_m = project(boundary_poly)

ways_by_id = {}
for fname in FILES:
    with open(f"{RAW_DIR}/{fname}", encoding="utf-8") as f:
        data = json.load(f)
    for el in data["elements"]:
        if el["type"] != "way" or not el.get("geometry"):
            continue
        ways_by_id[el["id"]] = el  # dedupe: last write wins, identical across council queries

print(f"Deduplicated to {len(ways_by_id)} unique ways")

TOLERANCE_DEG = 0.00006
ROUND_DP = 5


def round_coords(obj):
    if isinstance(obj, float):
        return round(obj, ROUND_DP)
    if isinstance(obj, list):
        return [round_coords(x) for x in obj]
    return obj


features = []
total_km = 0.0
for way in ways_by_id.values():
    coords = [(pt["lon"], pt["lat"]) for pt in way["geometry"]]
    if len(coords) < 2:
        continue
    line_m = project(LineString(coords))
    clipped = line_m.intersection(boundary_m)
    if clipped.is_empty:
        continue
    clipped_km = clipped.length / 1000.0
    total_km += clipped_km

    geom_simplified = LineString(coords).simplify(TOLERANCE_DEG, preserve_topology=False)
    geom_dict = mapping(geom_simplified)
    geom_dict["coordinates"] = round_coords(geom_dict["coordinates"])

    tags = way.get("tags", {})
    features.append({
        "type": "Feature", "geometry": geom_dict,
        "properties": {"osm_id": way["id"], "highway": tags.get("highway"), "surface": tags.get("surface")},
    })

print(f"Final: {len(features)} features, {total_km:.1f} km (clipped to actual GDA polygon)")

with open("../data/map_layers/gda_walking.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))

import os
size_kb = os.path.getsize("../data/map_layers/gda_walking.geojson") / 1024
print(f"File size: {size_kb:.0f} KB")
