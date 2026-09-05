"""
Classify OSM cycling infrastructure by real-world type, using the actual
tags already present (highway, cycleway, foot, segregated) rather than
treating all 1,600 ways as one undifferentiated "cycling" layer:

  - on-road painted lane      : cycleway=lane on a normal road (shares carriageway)
  - separated track by road   : cycleway=track on a normal road (own space, road-adjacent)
  - shared lane / sharrow     : cycleway=shared_lane|soft_lane (markings only, no space)
  - dedicated cycle-only track: standalone highway=cycleway, pedestrians not allowed
  - shared path (unsegregated): standalone highway=cycleway, foot=yes/designated, not segregated
  - shared corridor (segregated): same but segregated=yes (each mode has its own marked side)
  - cycling on sidewalk       : cycleway=sidewalk
  - crossing                  : cycleway=crossing (a road crossing, not a route segment)

This mirrors the government NTA dataset's own categories (BIKE_LANE,
SEPARATE_TRAIL, BIKE_FRIENDLY_PEDESTRIAN_PATH, ...), so the two are now
comparable type-for-type, not just as one lump total.
"""
import json
import math
from collections import Counter

ROAD_TYPES = {"secondary", "tertiary", "residential", "unclassified", "service", "secondary_link", "tertiary_link"}

LABELS = {
    "on_road_lane": "On-road painted bike lane (shares carriageway)",
    "on_road_track": "Separated track alongside road",
    "on_road_shared_lane": "Shared lane with traffic (sharrow, no dedicated space)",
    "dedicated_track": "Dedicated cycle-only track (no pedestrians)",
    "shared_unsegregated": "Shared path - bike + pedestrian (unsegregated)",
    "shared_segregated": "Shared corridor - bike + pedestrian (physically segregated)",
    "shared_sidewalk": "Cycling permitted on sidewalk/footway",
    "crossing": "Crossing (not a route segment)",
    "other": "Other/unclassified",
}
COLORS = {
    "on_road_lane": "#2e9e5b",
    "on_road_track": "#0d7a3f",
    "on_road_shared_lane": "#8bc34a",
    "dedicated_track": "#1565c0",
    "shared_unsegregated": "#f9a825",
    "shared_segregated": "#fb8c00",
    "shared_sidewalk": "#ef6c00",
    "crossing": "#bdbdbd",
    "other": "#999999",
}


def classify(props: dict) -> str:
    highway = props.get("highway")
    cycleway = props.get("cycleway")
    foot = props.get("foot")
    segregated = props.get("segregated")

    if cycleway == "crossing":
        return "crossing"
    if cycleway == "sidewalk":
        return "shared_sidewalk"
    if highway in ROAD_TYPES:
        if cycleway == "lane":
            return "on_road_lane"
        if cycleway == "track":
            return "on_road_track"
        if cycleway in ("shared_lane", "soft_lane"):
            return "on_road_shared_lane"
        return "other"
    if highway == "cycleway":
        if foot in ("yes", "designated"):
            return "shared_segregated" if segregated == "yes" else "shared_unsegregated"
        return "dedicated_track"
    return "other"


with open("../data/osm/cycling.geojson", encoding="utf-8") as f:
    fc = json.load(f)

counts = Counter()
lengths = Counter()
for feat in fc["features"]:
    cat = classify(feat["properties"])
    feat["properties"]["cycle_type"] = cat
    feat["properties"]["cycle_type_label"] = LABELS[cat]
    feat["properties"]["color"] = COLORS[cat]
    length_km = feat["properties"].get("length_m", 0) / 1000.0
    counts[cat] += 1
    lengths[cat] += length_km

with open("../data/osm_cycling_classified.geojson", "w", encoding="utf-8") as f:
    json.dump(fc, f, separators=(",", ":"))

summary = {
    "by_category_count": dict(counts),
    "by_category_length_km": {k: round(v, 2) for k, v in lengths.items()},
    "total_length_km": round(sum(lengths.values()), 2),
}
with open("../data/osm_cycling_classification_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"{'Category':40s} {'Segments':>9s} {'Length km':>10s}")
for cat in sorted(counts, key=lambda c: -lengths[c]):
    print(f"{LABELS[cat]:40s} {counts[cat]:9d} {lengths[cat]:10.2f}")
print(f"{'TOTAL':40s} {sum(counts.values()):9d} {sum(lengths.values()):10.2f}")
