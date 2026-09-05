"""
Are the gaps between OSM-tagged bus/taxi lane segments real (the physical
lane genuinely starts/stops there) or a data gap (OSM just never tagged an
in-between stretch that the government survey shows as continuous)?

Method: buffer every 2007 government bus-lane segment by 20m (generous for
a legacy survey's digitizing tolerance + real-world lane width) in projected
meters, then measure what fraction of OSM's lane network falls inside that
buffer (= "OSM agrees with gov here") vs outside it (= "OSM has this but gov
doesn't, e.g. a newer post-2007 lane"). Symmetrically, measure what fraction
of the GOV network is NOT covered by any OSM-tagged lane within 20m -- that
figure is the best available estimate of how much of Dublin's real bus-lane
network is simply missing from OSM's tagging, as opposed to a live road
having no lane at all.
"""
import json
import math

from shapely.geometry import shape, LineString
from shapely.ops import transform as shp_transform, unary_union

BUFFER_M = 20.0
lat0 = 53.35
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))


def to_m(lon, lat):
    return (lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT)


def project(geom):
    return shp_transform(lambda x, y, z=None: to_m(x, y), geom)


with open("../data/gov_2007_buslanes.geojson", encoding="utf-8") as f:
    gov_fc = json.load(f)
with open("../data/osm_lanes/designated_lanes_v2.geojson", encoding="utf-8") as f:
    osm_fc = json.load(f)
with open("../data/boundary_dublin_city.geojson", encoding="utf-8") as f:
    boundary = json.load(f)
boundary_m = project(shape(boundary["geometry"]))

gov_lines_m = [project(LineString(f["geometry"]["coordinates"])) for f in gov_fc["features"]]
gov_lines_m = [g.intersection(boundary_m) for g in gov_lines_m]
gov_lines_m = [g for g in gov_lines_m if not g.is_empty]

osm_lines_m = [project(LineString(f["geometry"]["coordinates"])) for f in osm_fc["features"]]

gov_union = unary_union(gov_lines_m)
osm_union = unary_union(osm_lines_m)

gov_buffer = gov_union.buffer(BUFFER_M)
osm_buffer = osm_union.buffer(BUFFER_M)

gov_len_total = sum(g.length for g in gov_lines_m) / 1000.0
osm_len_total = sum(o.length for o in osm_lines_m) / 1000.0

# Gov length that IS within `BUFFER_M` of an OSM-tagged lane (i.e. OSM agrees)
gov_covered = gov_union.intersection(osm_buffer)
gov_covered_km = gov_covered.length / 1000.0
gov_gap_km = gov_len_total - gov_covered_km

# OSM length that is NOT within `BUFFER_M` of any 2007 gov lane (newer than 2007, or gov survey missed it)
osm_not_in_gov = osm_union.difference(gov_buffer)
osm_not_in_gov_km = osm_not_in_gov.length / 1000.0
osm_agrees_km = osm_len_total - osm_not_in_gov_km

print(f"Dublin City boundary, {BUFFER_M:.0f}m buffer tolerance")
print(f"2007 Gov bus lanes within boundary: {gov_len_total:.2f} km")
print(f"OSM designated lanes within boundary: {osm_len_total:.2f} km")
print()
print(f"Gov lane length WITH an OSM-tagged counterpart nearby:    {gov_covered_km:6.2f} km ({100*gov_covered_km/gov_len_total:.1f}%)")
print(f"Gov lane length with NO OSM tag nearby (= likely OSM data gap): {gov_gap_km:6.2f} km ({100*gov_gap_km/gov_len_total:.1f}%)")
print()
print(f"OSM lane length WITH a 2007-gov counterpart nearby:       {osm_agrees_km:6.2f} km ({100*osm_agrees_km/osm_len_total:.1f}%)")
print(f"OSM lane length with NO 2007-gov counterpart (new since 2007, or gov survey missed it): {osm_not_in_gov_km:6.2f} km ({100*osm_not_in_gov_km/osm_len_total:.1f}%)")

# Save the "OSM data gap" geometry (gov lanes not covered by OSM) for the map
gap_geom = gov_union.difference(osm_buffer)
gap_lines = []
if gap_geom.geom_type == "LineString":
    gap_lines = [gap_geom]
elif gap_geom.geom_type == "MultiLineString":
    gap_lines = list(gap_geom.geoms)
elif gap_geom.geom_type == "GeometryCollection":
    gap_lines = [g for g in gap_geom.geoms if g.geom_type in ("LineString", "MultiLineString")]


def unproject(x, y, z=None):
    return (x / M_PER_DEG_LON, y / M_PER_DEG_LAT)


gap_features = []
for g in gap_lines:
    if g.length < 5:  # drop sub-5m slivers from floating point noise
        continue
    g_wgs = shp_transform(unproject, g)
    coords = list(g_wgs.coords) if g_wgs.geom_type == "LineString" else None
    if coords:
        gap_features.append({
            "type": "Feature", "geometry": {"type": "LineString", "coordinates": [list(c) for c in coords]},
            "properties": {"length_m": round(g.length, 1)},
        })

with open("../data/lane_data_gap.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": gap_features}, f, separators=(",", ":"))

summary = {
    "buffer_tolerance_m": BUFFER_M,
    "gov_2007_km_in_boundary": round(gov_len_total, 2),
    "osm_2026_km_in_boundary": round(osm_len_total, 2),
    "gov_km_confirmed_by_osm": round(gov_covered_km, 2),
    "gov_km_missing_from_osm": round(gov_gap_km, 2),
    "gov_pct_missing_from_osm": round(100 * gov_gap_km / gov_len_total, 1),
    "osm_km_confirmed_by_2007_gov": round(osm_agrees_km, 2),
    "osm_km_not_in_2007_gov": round(osm_not_in_gov_km, 2),
    "osm_pct_not_in_2007_gov": round(100 * osm_not_in_gov_km / osm_len_total, 1),
    "gap_features_count": len(gap_features),
}
with open("../data/lane_gap_analysis_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)
print(f"\n{len(gap_features)} distinct 'OSM data gap' segments saved for the map.")
