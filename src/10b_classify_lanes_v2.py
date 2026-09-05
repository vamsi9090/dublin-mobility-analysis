"""
Reclassify designated bus/taxi/PSV lanes using the expanded v2 query, which
also caught per-direction and time-conditional tagging (psv:lanes:forward,
lanes:psv:conditional, bus:forward:conditional, taxi:conditional, etc.) --
common for Dublin's Quality Bus Corridors, many of which are peak-hour-only
restrictions rather than 24/7 bus lanes. Conditional lanes are flagged as
their own attribute (not silently merged into "permanent"), since a
peak-hours-only restriction is a materially different thing on the ground.
"""
import json
import math
from collections import Counter

with open("../data/osm_lanes/designated_lanes_raw_v2.json", encoding="utf-8") as f:
    raw = json.load(f)
ways = [e for e in raw["elements"] if e["type"] == "way"]


def has_prefix(tags, *prefixes):
    return any(any(k.startswith(p) for p in prefixes) for k in tags)


def classify(tags: dict):
    vehicles = set()
    basis = []
    conditional = False

    if any(tags.get(k) in ("lane", "opposite_lane") for k in ("busway", "busway:both", "busway:right", "busway:left")):
        vehicles.add("bus"); basis.append("busway=lane")
    if tags.get("bus") in ("designated", "yes") or tags.get("bus:forward") in ("designated", "yes") or tags.get("bus:backward") in ("designated", "yes"):
        vehicles.add("bus"); basis.append("bus=designated/yes")
    if has_prefix(tags, "lanes:bus", "bus:lanes"):
        vehicles.add("bus"); basis.append("lanes:bus/bus:lanes present")

    if tags.get("taxi") in ("designated", "yes"):
        vehicles.add("taxi"); basis.append("taxi=designated/yes")
    if has_prefix(tags, "lanes:taxi", "taxi:lanes"):
        vehicles.add("taxi"); basis.append("lanes:taxi/taxi:lanes present")

    if tags.get("psv") in ("designated", "yes") or has_prefix(tags, "lanes:psv", "psv:lanes"):
        vehicles.add("bus"); vehicles.add("taxi"); basis.append("psv (bus+taxi)")

    if tags.get("bicycle") in ("designated", "yes") and vehicles:
        vehicles.add("bike"); basis.append(f"bicycle={tags.get('bicycle')}")

    # time-restriction signal: any conditional-suffixed key among the relevant tags
    for k in tags:
        if "conditional" in k and any(p in k for p in ("bus", "psv", "taxi")):
            conditional = True
            basis.append(f"{k}={tags[k]}")
            break

    return vehicles, basis, conditional


lat0 = 53.35
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))

features = []
counts = Counter()
lengths = Counter()
conditional_counts = Counter()
conditional_lengths = Counter()

EXCLUDED_NON_ROAD = 0
for w in ways:
    tags = w.get("tags", {})
    vehicles, basis, conditional = classify(tags)
    if not vehicles:
        continue
    if not tags.get("highway"):
        # Not a road at all -- e.g. ferry routes (Dublin-Heysham, Dublin-Liverpool,
        # Isle of Man-Dublin) legitimately carry psv=yes for passenger-vehicle
        # classification, and an "NTA Coach Park" facility way. Neither is a
        # road-segment bus/taxi lane; including them inflated v2 to 632km.
        EXCLUDED_NON_ROAD += 1
        continue
    category = "+".join(sorted(vehicles))
    geom = w.get("geometry")
    if not geom or len(geom) < 2:
        continue
    coords = [[pt["lon"], pt["lat"]] for pt in geom]
    length_m = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(coords[:-1], coords[1:]):
        dx = (lon2 - lon1) * M_PER_DEG_LON
        dy = (lat2 - lat1) * M_PER_DEG_LAT
        length_m += (dx**2 + dy**2) ** 0.5
    length_km = length_m / 1000.0

    counts[category] += 1
    lengths[category] += length_km
    if conditional:
        conditional_counts[category] += 1
        conditional_lengths[category] += length_km

    features.append({
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "osm_id": w["id"], "name": tags.get("name", ""), "highway": tags.get("highway", ""),
            "category": category, "conditional": conditional, "basis": "; ".join(basis),
            "length_km": round(length_km, 3),
        },
    })

with open("../data/osm_lanes/designated_lanes_v2.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))

summary = {
    "total_segments": len(features),
    "total_length_km": round(sum(lengths.values()), 2),
    "by_category_count": dict(counts),
    "by_category_length_km": {k: round(v, 2) for k, v in lengths.items()},
    "conditional_time_restricted_count": dict(conditional_counts),
    "conditional_time_restricted_length_km": {k: round(v, 2) for k, v in conditional_lengths.items()},
    "v1_comparison_total_length_km": 14.98,
    "v1_comparison_total_segments": 159,
}
with open("../data/osm_lanes/summary_v2.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"v1 (narrow query):  159 segments, 14.98 km")
print(f"v2 (expanded query): {len(features)} segments, {sum(lengths.values()):.2f} km")
print(f"  (excluded {EXCLUDED_NON_ROAD} non-road ways: ferry routes / coach park with psv/bus tags but no highway=* tag)")
print()
for cat in sorted(counts):
    print(f"  {cat:16s}  {counts[cat]:3d} segments   {lengths[cat]:7.2f} km   (of which {conditional_counts.get(cat,0)} conditional/time-restricted, {conditional_lengths.get(cat,0.0):.2f} km)")
