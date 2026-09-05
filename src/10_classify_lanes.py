"""
Classify each designated-lane way by exactly which vehicle classes are
permitted (bus / taxi / bike, in any combination), using real OSM lane-
restriction tags rather than full route paths.

PSV (Public Service Vehicle) is the standard UK/Ireland legal category
covering licensed buses AND taxis together -- psv=designated or lanes:psv
therefore implies both 'bus' and 'taxi' access unless a more specific tag
says otherwise. This is a documented convention, not a guess, but it's
still an inference layered on the raw tags, so it's flagged in the output
properties (basis field) for anyone auditing this.
"""
import json
from collections import Counter

with open("../data/osm_lanes/designated_lanes_raw.json", encoding="utf-8") as f:
    raw = json.load(f)

ways = [e for e in raw["elements"] if e["type"] == "way"]


def classify(tags: dict) -> tuple[set, list]:
    vehicles = set()
    basis = []

    busway_vals = [tags.get(k) for k in ("busway", "busway:both", "busway:right", "busway:left")]
    has_busway = any(v in ("lane", "opposite_lane") for v in busway_vals)
    has_bus_tag = tags.get("bus") in ("designated", "yes")
    has_lanes_bus = "lanes:bus" in tags or any(k.startswith("bus:lanes") for k in tags)

    has_taxi_tag = tags.get("taxi") in ("designated", "yes")
    has_lanes_taxi = "lanes:taxi" in tags or any(k.startswith("taxi:lanes") for k in tags)

    psv_val = tags.get("psv")
    has_psv = psv_val in ("designated", "yes") or "lanes:psv" in tags or any(
        k.startswith("psv:lanes") and "designated" in str(v) for k, v in tags.items()
    ) or any(k.startswith("psv:lanes") for k in tags)

    if has_busway:
        vehicles.add("bus"); basis.append(f"busway={[v for v in busway_vals if v][0]}")
    if has_bus_tag:
        vehicles.add("bus"); basis.append(f"bus={tags.get('bus')}")
    if has_lanes_bus:
        vehicles.add("bus"); basis.append("lanes:bus/bus:lanes present")
    if has_taxi_tag:
        vehicles.add("taxi"); basis.append(f"taxi={tags.get('taxi')}")
    if has_lanes_taxi:
        vehicles.add("taxi"); basis.append("lanes:taxi/taxi:lanes present")
    if has_psv:
        vehicles.add("bus"); vehicles.add("taxi"); basis.append(f"psv={psv_val or 'lanes:psv present'} (PSV = bus+taxi)")

    if tags.get("bicycle") in ("designated", "yes") and vehicles:
        vehicles.add("bike"); basis.append(f"bicycle={tags.get('bicycle')}")

    return vehicles, basis


CATEGORY_COLOR = {
    "bus": "#1f5fd6",              # blue
    "taxi": "#ffb300",             # yellow/amber
    "bus+taxi": "#7b1fa2",         # purple
    "bus+taxi+bike": "#00897b",    # teal
    "bus+bike": "#2e9e5b",         # green-blue
    "taxi+bike": "#c77c02",        # amber-green mix
}

features = []
category_counts = Counter()
category_length_km = Counter()

import math
lat0 = 53.35
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))

for w in ways:
    tags = w.get("tags", {})
    vehicles, basis = classify(tags)
    if not vehicles:
        continue
    category = "+".join(sorted(vehicles))
    geom = w.get("geometry")
    if not geom or len(geom) < 2:
        continue
    coords = [[pt["lon"], pt["lat"]] for pt in geom]

    # length in km via equirectangular approx (consistent with rest of analysis)
    length_m = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(coords[:-1], coords[1:]):
        dx = (lon2 - lon1) * M_PER_DEG_LON
        dy = (lat2 - lat1) * M_PER_DEG_LAT
        length_m += (dx**2 + dy**2) ** 0.5
    length_km = length_m / 1000.0

    category_counts[category] += 1
    category_length_km[category] += length_km

    features.append({
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "osm_id": w["id"],
            "name": tags.get("name", ""),
            "highway": tags.get("highway", ""),
            "category": category,
            "basis": "; ".join(basis),
            "length_km": round(length_km, 3),
            "color": CATEGORY_COLOR.get(category, "#999999"),
        },
    })

with open("../data/osm_lanes/designated_lanes.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))

summary = {
    "total_segments": len(features),
    "by_category_count": dict(category_counts),
    "by_category_length_km": {k: round(v, 2) for k, v in category_length_km.items()},
    "total_length_km": round(sum(category_length_km.values()), 2),
}
with open("../data/osm_lanes/summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"Classified {len(features)} designated-lane road segments (from {len(ways)} raw ways)")
print()
for cat in sorted(category_counts):
    print(f"  {cat:16s}  {category_counts[cat]:3d} segments   {category_length_km[cat]:6.2f} km")
print(f"  {'TOTAL':16s}  {len(features):3d} segments   {sum(category_length_km.values()):6.2f} km")
