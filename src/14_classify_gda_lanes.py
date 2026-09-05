"""
Classify + precisely clip the Greater-Dublin-region lane query to the actual
union polygon of the 4 local authorities (the Overpass bbox query is a
rectangle superset that also catches slivers of Meath/Kildare/Wicklow).
Reuses the same classification and non-road (ferry/facility) exclusion logic
validated in 10b_classify_lanes_v2.py.
"""
import json
import math

from shapely.geometry import shape, LineString
from shapely.ops import transform as shp_transform

with open("../data/boundary_greater_dublin_region.geojson", encoding="utf-8") as f:
    boundary_feat = json.load(f)
boundary_poly = shape(boundary_feat["geometry"])

lat0 = 53.35
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))


def to_m(lon, lat):
    return (lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT)


def project(geom):
    return shp_transform(lambda x, y, z=None: to_m(x, y), geom)


boundary_poly_m = project(boundary_poly)
print(f"Greater Dublin region area: {boundary_poly_m.area/1_000_000:.1f} km^2")

with open("../data/osm_lanes/gda_lanes_raw.json", encoding="utf-8") as f:
    raw = json.load(f)
ways = [e for e in raw["elements"] if e["type"] == "way"]


def has_prefix(tags, *prefixes):
    return any(any(k.startswith(p) for p in prefixes) for k in tags)


def classify(tags: dict):
    vehicles = set()
    if any(tags.get(k) in ("lane", "opposite_lane") for k in ("busway", "busway:both", "busway:right", "busway:left")):
        vehicles.add("bus")
    if tags.get("bus") in ("designated", "yes") or tags.get("bus:forward") in ("designated", "yes") or tags.get("bus:backward") in ("designated", "yes"):
        vehicles.add("bus")
    if has_prefix(tags, "lanes:bus", "bus:lanes"):
        vehicles.add("bus")
    if tags.get("taxi") in ("designated", "yes"):
        vehicles.add("taxi")
    if has_prefix(tags, "lanes:taxi", "taxi:lanes"):
        vehicles.add("taxi")
    if tags.get("psv") in ("designated", "yes") or has_prefix(tags, "lanes:psv", "psv:lanes"):
        vehicles.add("bus"); vehicles.add("taxi")
    if tags.get("bicycle") in ("designated", "yes") and vehicles:
        vehicles.add("bike")
    return vehicles


from collections import Counter
counts = Counter()
lengths = Counter()
excluded_no_highway = 0
excluded_outside_polygon = 0
features = []

for w in ways:
    tags = w.get("tags", {})
    vehicles = classify(tags)
    if not vehicles:
        continue
    if not tags.get("highway"):
        excluded_no_highway += 1
        continue
    geom = w.get("geometry")
    if not geom or len(geom) < 2:
        continue
    coords = [(pt["lon"], pt["lat"]) for pt in geom]
    line = LineString(coords)
    line_m = project(line)
    clipped = line_m.intersection(boundary_poly_m)
    clipped_len_km = (clipped.length / 1000.0) if not clipped.is_empty else 0.0
    if clipped_len_km == 0.0:
        excluded_outside_polygon += 1
        continue

    category = "+".join(sorted(vehicles))
    counts[category] += 1
    lengths[category] += clipped_len_km
    features.append({
        "type": "Feature", "geometry": {"type": "LineString", "coordinates": [list(c) for c in coords]},
        "properties": {"osm_id": w["id"], "name": tags.get("name", ""), "highway": tags.get("highway", ""),
                       "category": category, "length_km_clipped": round(clipped_len_km, 3)},
    })

with open("../data/osm_lanes/gda_designated_lanes.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))

print(f"\nRaw ways from bbox query: {len(ways)}")
print(f"Excluded (no highway tag - ferries/facilities): {excluded_no_highway}")
print(f"Excluded (outside the actual 4-county polygon, bbox-only slivers): {excluded_outside_polygon}")
print(f"Final road-segment count: {len(features)}")
print(f"TOTAL LENGTH within Greater Dublin region: {sum(lengths.values()):.2f} km")
print()
for cat in sorted(counts):
    print(f"  {cat:16s}  {counts[cat]:3d} segments   {lengths[cat]:7.2f} km")
print()
print("Comparison:")
print(f"  Dublin City Council only (117.6 km^2):  24.31 km")
print(f"  Greater Dublin region (~{boundary_poly_m.area/1_000_000:.0f} km^2): {sum(lengths.values()):.2f} km")
