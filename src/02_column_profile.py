"""
Column-level profiling of every dataset (OSM + Gov), not just headline counts.
For each attribute/tag we report fill-rate and, for low-cardinality fields,
the value distribution -- this is what actually tells us what each source is
useful for filtering/segmenting by, and surfaces data-quality issues (e.g.
inconsistent casing, free-text vs coded fields) before we try to compare them.
"""
import json
import csv
from collections import Counter, defaultdict

OSM_DIR = "../data/osm"
GOV_DIR = "../data/gov"


def profile_geojson(path, label, max_features=None):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    feats = d["features"]
    if max_features:
        feats = feats[:max_features]
    n = len(feats)
    field_fill = Counter()
    field_values = defaultdict(Counter)
    for feat in feats:
        props = feat.get("properties", {}) or {}
        for k, v in props.items():
            if v not in (None, "", "NaN"):
                field_fill[k] += 1
                if len(field_values[k]) < 30:  # cap cardinality tracking
                    field_values[k][str(v)] += 1

    profile = {"dataset": label, "n_features": n, "fields": {}}
    for k, count in sorted(field_fill.items(), key=lambda x: -x[1]):
        vals = field_values[k]
        entry = {"fill_rate_pct": round(100 * count / n, 1), "non_null_count": count}
        if len(vals) <= 15:
            entry["distinct_values"] = dict(vals.most_common(15))
            entry["cardinality"] = "low"
        else:
            entry["cardinality"] = "high (free text / id-like)"
            entry["sample_values"] = [v for v, _ in vals.most_common(5)]
        profile["fields"][k] = entry
    return profile


def profile_csv(path, label):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    n = len(rows)
    field_fill = Counter()
    field_values = defaultdict(Counter)
    for row in rows:
        for k, v in row.items():
            if v not in (None, ""):
                field_fill[k] += 1
                if len(field_values[k]) < 30:
                    field_values[k][v] += 1
    profile = {"dataset": label, "n_rows": n, "fields": {}}
    for k, count in sorted(field_fill.items(), key=lambda x: -x[1]):
        vals = field_values[k]
        entry = {"fill_rate_pct": round(100 * count / n, 1) if n else 0, "non_null_count": count}
        if len(vals) <= 15:
            entry["distinct_values"] = dict(vals.most_common(15))
            entry["cardinality"] = "low"
        else:
            entry["cardinality"] = "high (free text / id-like)"
            entry["sample_values"] = [v for v, _ in vals.most_common(5)]
        profile["fields"][k] = entry
    return profile


profiles = {}
profiles["osm_bus_stops"] = profile_geojson(f"{OSM_DIR}/bus_stops.geojson", "OSM bus stops")
profiles["osm_platforms"] = profile_geojson(f"{OSM_DIR}/platforms.geojson", "OSM PT platforms")
profiles["osm_taxi_ranks"] = profile_geojson(f"{OSM_DIR}/taxi_ranks.geojson", "OSM taxi ranks")
profiles["osm_cycling"] = profile_geojson(f"{OSM_DIR}/cycling.geojson", "OSM cycling ways")
profiles["osm_walking"] = profile_geojson(f"{OSM_DIR}/walking.geojson", "OSM walking ways")
profiles["osm_bus_routes"] = profile_geojson(f"{OSM_DIR}/bus_routes.geojson", "OSM bus route segments", max_features=20000)

profiles["gov_stops"] = profile_csv(f"{GOV_DIR}/stops_dublin.csv", "GTFS Dublin stops")
profiles["gov_routes"] = profile_csv(f"{GOV_DIR}/routes_dublin.csv", "GTFS Dublin routes")
profiles["gov_bus_shapes"] = profile_geojson(f"{GOV_DIR}/bus_routes_dublin.geojson", "GTFS Dublin route shapes")
profiles["gov_cycle_network"] = profile_geojson(f"{GOV_DIR}/cycle_network_dublin.geojson", "NTA cycle network")

with open("../data/column_profile.json", "w", encoding="utf-8") as f:
    json.dump(profiles, f, indent=2)

# Print a compact human-readable summary
for key, p in profiles.items():
    n = p.get("n_features", p.get("n_rows"))
    print(f"\n=== {p['dataset']} (n={n}) ===")
    for field, entry in list(p["fields"].items())[:12]:
        if entry["cardinality"] == "low":
            vals_preview = ", ".join(f"{k}={v}" for k, v in list(entry["distinct_values"].items())[:6])
        else:
            vals_preview = "e.g. " + ", ".join(entry["sample_values"][:3])
        print(f"  {field:30s} fill={entry['fill_rate_pct']:5.1f}%  {vals_preview}")

print("\nSaved full profile to ../data/column_profile.json")
