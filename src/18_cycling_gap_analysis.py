"""
Same buffered-overlap methodology as the bus lane gap analysis, applied to
cycling: OSM (125.5km) vs the two government sources (NTA regional network,
DCC/Smart Dublin protected infrastructure), all clipped to Dublin City
boundary, to find real coverage vs data gaps in each direction.
"""
import json
import math

from shapely.geometry import shape, LineString
from shapely.ops import transform as shp_transform, unary_union

BUFFER_M = 15.0  # tighter than bus lanes (20m) since cycle infra is narrower/more precisely surveyed
lat0 = 53.35
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))


def to_m(lon, lat):
    return (lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT)


def project(geom):
    return shp_transform(lambda x, y, z=None: to_m(x, y), geom)


with open("../data/boundary_dublin_city.geojson", encoding="utf-8") as f:
    boundary_m = project(shape(json.load(open("../data/boundary_dublin_city.geojson", encoding="utf-8"))["geometry"]))


def load_clipped_union(path, coord_key=None):
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    lines_m = []
    for feat in fc["features"]:
        geom = shape(feat["geometry"])
        if geom.geom_type not in ("LineString", "MultiLineString"):
            continue
        g_m = project(geom).intersection(boundary_m)
        if not g_m.is_empty:
            lines_m.append(g_m)
    return unary_union(lines_m), sum(g.length for g in lines_m) / 1000.0


osm_union, osm_km = load_clipped_union("../data/osm/cycling.geojson")
nta_union, nta_km = load_clipped_union("../data/map_layers/gov_cycle_dublin_city.geojson")
dcc_union, dcc_km = load_clipped_union("../data/gov_extra/protected_cycle_infra_2023.geojson")

print(f"OSM cycling (Dublin City):        {osm_km:.2f} km")
print(f"NTA regional network (clipped):   {nta_km:.2f} km")
print(f"DCC protected/segregated (2023):  {dcc_km:.2f} km")
print()


def coverage(a_union, a_km, b_union, label_a, label_b, buffer_m=BUFFER_M):
    b_buffer = b_union.buffer(buffer_m)
    covered = a_union.intersection(b_buffer)
    covered_km = covered.length / 1000.0
    gap_km = a_km - covered_km
    print(f"{label_a} covered by {label_b} (within {buffer_m:.0f}m): {covered_km:6.2f} km ({100*covered_km/a_km:.1f}%)")
    print(f"{label_a} NOT covered by {label_b}:                  {gap_km:6.2f} km ({100*gap_km/a_km:.1f}%)")
    return covered_km, gap_km


print("--- OSM vs NTA ---")
osm_in_nta, osm_gap_nta = coverage(osm_union, osm_km, nta_union, "OSM", "NTA")
nta_in_osm, nta_gap_osm = coverage(nta_union, nta_km, osm_union, "NTA", "OSM")
print()
print("--- OSM vs DCC protected ---")
osm_in_dcc, osm_gap_dcc = coverage(osm_union, osm_km, dcc_union, "OSM", "DCC")
dcc_in_osm, dcc_gap_osm = coverage(dcc_union, dcc_km, osm_union, "DCC", "OSM")
print()
print("--- NTA vs DCC (two government sources vs each other) ---")
nta_in_dcc, nta_gap_dcc = coverage(nta_union, nta_km, dcc_union, "NTA", "DCC")
dcc_in_nta, dcc_gap_nta = coverage(dcc_union, dcc_km, nta_union, "DCC", "NTA")

summary = {
    "buffer_tolerance_m": BUFFER_M,
    "osm_km": round(osm_km, 2), "nta_km": round(nta_km, 2), "dcc_km": round(dcc_km, 2),
    "osm_covered_by_nta_km": round(osm_in_nta, 2), "osm_gap_vs_nta_km": round(osm_gap_nta, 2),
    "nta_covered_by_osm_km": round(nta_in_osm, 2), "nta_gap_vs_osm_km": round(nta_gap_osm, 2),
    "osm_covered_by_dcc_km": round(osm_in_dcc, 2), "osm_gap_vs_dcc_km": round(osm_gap_dcc, 2),
    "dcc_covered_by_osm_km": round(dcc_in_osm, 2), "dcc_gap_vs_osm_km": round(dcc_gap_osm, 2),
    "nta_covered_by_dcc_km": round(nta_in_dcc, 2), "nta_gap_vs_dcc_km": round(nta_gap_dcc, 2),
    "dcc_covered_by_nta_km": round(dcc_in_nta, 2), "dcc_gap_vs_nta_km": round(dcc_gap_nta, 2),
}
with open("../data/cycling_gap_analysis_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)


def unproject(x, y, z=None):
    return (x / M_PER_DEG_LON, y / M_PER_DEG_LAT)


nta_gap_geom = nta_union.difference(osm_union.buffer(BUFFER_M))
gap_lines = []
if nta_gap_geom.geom_type == "LineString":
    gap_lines = [nta_gap_geom]
elif nta_gap_geom.geom_type == "MultiLineString":
    gap_lines = list(nta_gap_geom.geoms)
elif nta_gap_geom.geom_type == "GeometryCollection":
    gap_lines = [g for g in nta_gap_geom.geoms if g.geom_type == "LineString"]

gap_features = []
for g in gap_lines:
    if g.length < 5:
        continue
    g_wgs = shp_transform(unproject, g)
    gap_features.append({
        "type": "Feature", "geometry": {"type": "LineString", "coordinates": [list(c) for c in g_wgs.coords]},
        "properties": {"length_m": round(g.length, 1)},
    })

with open("../data/cycling_data_gap.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": gap_features}, f, separators=(",", ":"))
print(f"\n{len(gap_features)} distinct 'OSM cycling data gap vs NTA' segments saved for the map.")
