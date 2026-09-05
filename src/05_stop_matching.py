"""
Point-level nearest-neighbor matching between OSM bus stops and GTFS stops
(both already clipped to the Dublin City boundary), instead of just comparing
counts. This tells us how much of the "gap" is really the same physical stop
mapped by both sources vs. genuinely one-sided coverage.
"""
import json
import math

import numpy as np
from scipy.spatial import cKDTree

with open("../data/boundary_dublin_city.geojson", encoding="utf-8") as f:
    boundary_feat = json.load(f)
lat0 = 53.35  # Dublin City centroid latitude, matches 04_spatial_clip.py
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))


def to_m(lon, lat):
    return (lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT)


with open("../data/osm/bus_stops.geojson", encoding="utf-8") as f:
    osm_fc = json.load(f)
with open("../data/gov_stops_clipped_inside.geojson", encoding="utf-8") as f:
    gov_fc = json.load(f)

osm_pts = np.array([to_m(*feat["geometry"]["coordinates"]) for feat in osm_fc["features"]])
gov_pts = np.array([to_m(*feat["geometry"]["coordinates"]) for feat in gov_fc["features"]])

tree_gov = cKDTree(gov_pts)
dist_osm_to_gov, idx_osm_to_gov = tree_gov.query(osm_pts, k=1)

tree_osm = cKDTree(osm_pts)
dist_gov_to_osm, idx_gov_to_osm = tree_osm.query(gov_pts, k=1)

# Look at the distance distribution before picking a threshold
pcts = [10, 25, 50, 75, 90, 95, 99]
print("OSM -> nearest GTFS stop distance percentiles (m):")
for p in pcts:
    print(f"  p{p}: {np.percentile(dist_osm_to_gov, p):.1f} m")

THRESHOLD_M = 30.0  # same-stop-pair heuristic: two independently surveyed points for
                     # the same physical bus stop are typically a few meters to ~25m apart

osm_matched_mask = dist_osm_to_gov <= THRESHOLD_M
gov_matched_mask = dist_gov_to_osm <= THRESHOLD_M

n_osm = len(osm_pts)
n_gov = len(gov_pts)
n_osm_matched = int(osm_matched_mask.sum())
n_gov_matched = int(gov_matched_mask.sum())

result = {
    "threshold_m": THRESHOLD_M,
    "osm_stops_in_boundary": n_osm,
    "gov_stops_in_boundary": n_gov,
    "osm_stops_with_gtfs_match_within_threshold": n_osm_matched,
    "osm_stops_with_no_gtfs_match": n_osm - n_osm_matched,
    "gov_stops_with_osm_match_within_threshold": n_gov_matched,
    "gov_stops_with_no_osm_match": n_gov - n_gov_matched,
    "pct_osm_stops_matched": round(100 * n_osm_matched / n_osm, 1),
    "pct_gov_stops_matched": round(100 * n_gov_matched / n_gov, 1),
    "distance_percentiles_m": {f"p{p}": round(float(np.percentile(dist_osm_to_gov, p)), 1) for p in pcts},
}

with open("../data/stop_matching_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

# Save unmatched layers for the map
osm_unmatched_features = [feat for feat, m in zip(osm_fc["features"], osm_matched_mask) if not m]
gov_unmatched_features = [feat for feat, m in zip(gov_fc["features"], gov_matched_mask) if not m]

with open("../data/osm_stops_unmatched.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": osm_unmatched_features}, f)
with open("../data/gov_stops_unmatched.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": gov_unmatched_features}, f)

print()
for k, v in result.items():
    print(f"{k}: {v}")
