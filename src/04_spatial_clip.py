"""
Spatially clip the Gov datasets (which span the Greater Dublin Area) to the
exact Dublin City Council boundary polygon OSM was queried against, so the
km/count comparisons are area-normalized instead of comparing a big region
to a small one. Also clips OSM data to the same boundary as a sanity check
(should be ~100% inside, since it was Overpass area-filtered already).

Uses a local equirectangular projection (accurate to well under 0.1% at
city scale) instead of pyproj, since geopandas/pyproj are intentionally not
installed for this task -- shapely + a manual meters transform is enough.
"""
import csv
import json
import math

from shapely.geometry import shape, Point, LineString, MultiLineString, mapping
from shapely.ops import transform as shp_transform

with open("../data/boundary_dublin_city.geojson", encoding="utf-8") as f:
    boundary_feat = json.load(f)
boundary_poly = shape(boundary_feat["geometry"])

centroid = boundary_poly.centroid
lat0 = centroid.y
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))


def to_m(lon, lat):
    return ((lon) * M_PER_DEG_LON, (lat) * M_PER_DEG_LAT)


def project(geom):
    return shp_transform(lambda x, y, z=None: to_m(x, y), geom)


boundary_poly_m = project(boundary_poly)
boundary_area_km2 = boundary_poly_m.area / 1_000_000
print(f"Dublin City boundary area (from polygon): {boundary_area_km2:.2f} km^2")

results = {"boundary_area_km2": round(boundary_area_km2, 2)}

# ---------------------------------------------------------------
# 1. Gov GTFS stops clipped to boundary
# ---------------------------------------------------------------
with open("../data/gov/stops_dublin.csv", encoding="utf-8-sig") as f:
    gov_stops = list(csv.DictReader(f))

inside, outside = [], []
for row in gov_stops:
    try:
        lat, lon = float(row["stop_lat"]), float(row["stop_lon"])
    except (KeyError, ValueError):
        continue
    if Point(lon, lat).within(boundary_poly):
        inside.append(row)
    else:
        outside.append(row)

results["gov_stops_total"] = len(gov_stops)
results["gov_stops_inside_dublin_city_boundary"] = len(inside)
results["gov_stops_outside_boundary_greater_dublin_area"] = len(outside)

with open("../data/gov_stops_clipped_inside.geojson", "w", encoding="utf-8") as f:
    json.dump({
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(r["stop_lon"]), float(r["stop_lat"])]},
             "properties": {"stop_id": r["stop_id"], "stop_name": r["stop_name"], "stop_code": r.get("stop_code")}}
            for r in inside
        ],
    }, f)

# ---------------------------------------------------------------
# 2. OSM bus stops -- sanity check, should be ~100% inside
# ---------------------------------------------------------------
with open("../data/osm/bus_stops.geojson", encoding="utf-8") as f:
    osm_stops_fc = json.load(f)

osm_inside = sum(
    1 for feat in osm_stops_fc["features"]
    if Point(feat["geometry"]["coordinates"]).within(boundary_poly)
)
results["osm_stops_total"] = len(osm_stops_fc["features"])
results["osm_stops_inside_boundary"] = osm_inside
results["osm_stops_pct_inside"] = round(100 * osm_inside / len(osm_stops_fc["features"]), 1)

# ---------------------------------------------------------------
# 3. NTA cycle network clipped to boundary (length inside only)
# ---------------------------------------------------------------
with open("../data/gov/cycle_network_dublin.geojson", encoding="utf-8") as f:
    gov_cycle_fc = json.load(f)

gov_cycle_len_total_km = 0.0
gov_cycle_len_inside_km = 0.0
by_type_inside = {}
for feat in gov_cycle_fc["features"]:
    geom = shape(feat["geometry"])
    geom_m = project(geom)
    total_len = geom_m.length / 1000.0
    gov_cycle_len_total_km += total_len
    clipped = geom_m.intersection(boundary_poly_m)
    clipped_len = clipped.length / 1000.0 if not clipped.is_empty else 0.0
    gov_cycle_len_inside_km += clipped_len
    btype = feat["properties"].get("BIKE", "UNKNOWN")
    by_type_inside[btype] = by_type_inside.get(btype, 0.0) + clipped_len

results["gov_cycle_total_km_greater_dublin_area"] = round(gov_cycle_len_total_km, 2)
results["gov_cycle_km_inside_dublin_city_boundary"] = round(gov_cycle_len_inside_km, 2)
results["gov_cycle_by_type_inside_boundary_km"] = {k: round(v, 2) for k, v in by_type_inside.items()}

# ---------------------------------------------------------------
# 4. OSM cycling -- recompute clipped length as a cross-check of the
#    Overpass-area-filter result (should match closely)
# ---------------------------------------------------------------
with open("../data/osm/cycling.geojson", encoding="utf-8") as f:
    osm_cycle_fc = json.load(f)

osm_cycle_len_inside_km = 0.0
for feat in osm_cycle_fc["features"]:
    geom_m = project(shape(feat["geometry"]))
    clipped = geom_m.intersection(boundary_poly_m)
    osm_cycle_len_inside_km += (clipped.length / 1000.0 if not clipped.is_empty else 0.0)

results["osm_cycle_km_inside_boundary_reprojected"] = round(osm_cycle_len_inside_km, 2)
results["osm_cycle_km_original_haversine_report"] = 125.525

# ---------------------------------------------------------------
# 5. OSM walking -- clipped length cross-check
# ---------------------------------------------------------------
with open("../data/osm/walking.geojson", encoding="utf-8") as f:
    osm_walk_fc = json.load(f)

osm_walk_len_inside_km = 0.0
for feat in osm_walk_fc["features"]:
    geom_m = project(shape(feat["geometry"]))
    clipped = geom_m.intersection(boundary_poly_m)
    osm_walk_len_inside_km += (clipped.length / 1000.0 if not clipped.is_empty else 0.0)

results["osm_walk_km_inside_boundary_reprojected"] = round(osm_walk_len_inside_km, 2)
results["osm_walk_km_original_haversine_report"] = 1033.537

# ---------------------------------------------------------------
# 6. Taxi ranks -- OSM sanity check inside boundary
# ---------------------------------------------------------------
with open("../data/osm/taxi_ranks.geojson", encoding="utf-8") as f:
    osm_taxi_fc = json.load(f)

def taxi_point(feat):
    g = feat["geometry"]
    if g["type"] == "Point":
        return Point(g["coordinates"])
    # way (polygon/line) taxi feature -> use centroid
    return shape(g).centroid

osm_taxi_inside = sum(1 for feat in osm_taxi_fc["features"] if taxi_point(feat).within(boundary_poly))
results["osm_taxi_total"] = len(osm_taxi_fc["features"])
results["osm_taxi_inside_boundary"] = osm_taxi_inside

with open("../data/spatial_clip_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

for k, v in results.items():
    print(f"{k}: {v}")
