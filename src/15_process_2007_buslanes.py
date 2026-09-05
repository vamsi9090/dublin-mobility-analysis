"""
Process the 2007 GDA Bus Lane Survey (Dublin Transportation Office / NTA,
via data.gov.ie) -- the actual government dataset for bus lane road
segments that was missing from the comparison. Source CRS is TM65 Irish
Grid (a historical Irish projection, not WGS84), so this reprojects to
lon/lat using the exact WKT from the shapefile's .prj (safer than guessing
an EPSG code for a legacy datum).

Note on age: this is a 2007 survey (~18 years old at analysis time). It is
the best available *existing government bus lane geometry* dataset found,
but it is not current -- the map/report label this clearly rather than
implying it's an up-to-date official layer.
"""
import json
import math

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import shape, LineString, mapping
from shapely.ops import transform as shp_transform

SHP_PATH = "../data/gov_2007/buslanes_2007/Buslanes/Buslane_dissolve_by_category.shp"
PRJ_PATH = "../data/gov_2007/buslanes_2007/Buslanes/Buslane_dissolve_by_category.prj"

with open(PRJ_PATH, encoding="utf-8") as f:
    source_wkt = f.read()
source_crs = CRS.from_wkt(source_wkt)
transformer = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)

sf = shapefile.Reader(SHP_PATH)
features = []
skipped = 0
for sr in sf.iterShapeRecords():
    try:
        pts = sr.shape.points
        if not pts or len(pts) < 2:
            skipped += 1
            continue
        lonlat_pts = [transformer.transform(x, y) for x, y in pts]
        rec = sr.record.as_dict()
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [list(p) for p in lonlat_pts]},
            "properties": {"category": f"Category {int(rec.get('BL_CATEG', 0))}", "length_km_field": rec.get("lght")},
        })
    except Exception:
        skipped += 1

print(f"Parsed {len(features)} bus lane segments, skipped {skipped} malformed records")

# length via the projected (meters) source geometry -- more accurate than
# reprojecting to WGS84 and approximating, since Irish Grid is already meters
total_len_km_native = 0.0
for sr in sf.iterShapeRecords():
    try:
        pts = sr.shape.points
        if not pts or len(pts) < 2:
            continue
        length_m = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        total_len_km_native += length_m / 1000.0
    except Exception:
        continue

field_sum_km = sum(f["properties"]["length_km_field"] or 0 for f in features)
print(f"Total length (native-CRS geometry calc): {total_len_km_native:.2f} km")
print(f"Total length (sum of source 'lght' field): {field_sum_km:.2f} km")

with open("../data/gov_2007_buslanes.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))

# --- clip to Dublin City boundary for an apples-to-apples figure vs the OSM 24.3km ---
with open("../data/boundary_dublin_city.geojson", encoding="utf-8") as f:
    boundary = json.load(f)
boundary_poly = shape(boundary["geometry"])

lat0 = 53.35
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))


def to_m(lon, lat):
    return (lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT)


def project(geom):
    return shp_transform(lambda x, y, z=None: to_m(x, y), geom)


boundary_m = project(boundary_poly)
clipped_total_km = 0.0
for feat in features:
    line_m = project(LineString(feat["geometry"]["coordinates"]))
    clipped = line_m.intersection(boundary_m)
    clipped_total_km += (clipped.length / 1000.0) if not clipped.is_empty else 0.0

print(f"\nClipped to Dublin City Council boundary: {clipped_total_km:.2f} km")
print(f"(compare: OSM designated bus/taxi lanes within same boundary: 24.31 km)")
print(f"(compare: Greater Dublin region, all lanes, OSM 2026: 61.26 km)")
print(f"(2007 survey, full Greater Dublin Area extent: {total_len_km_native:.2f} km)")

summary = {
    "source": "2007 GDA Bus Lane Survey (Dublin Transportation Office, via data.gov.ie/NTA)",
    "survey_period": "2007-06-01 to 2007-08-31",
    "segments_parsed": len(features), "segments_skipped": skipped,
    "total_length_km_full_gda": round(total_len_km_native, 2),
    "total_length_km_clipped_to_dublin_city": round(clipped_total_km, 2),
    "comparison_osm_dublin_city_2026_km": 24.31,
    "comparison_osm_greater_dublin_2026_km": 61.26,
}
with open("../data/gov_2007_buslanes_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)
