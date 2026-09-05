"""
Independently verify the claimed 2007-vs-BikeLife-2021 bus lane overlap.
A ~0.35km overlap out of a combined 312km (0.1%) between two surveys of
allegedly the same real-world feature (Dublin bus lanes) 14 years apart is
implausibly low if using any reasonable spatial tolerance -- it's the
signature of an EXACT-geometry union that fails to recognize the same
physical lane digitized twice with slightly different vertices. Testing
with a realistic 15m buffer (matching methodology already validated
elsewhere in this analysis) to see the true picture.
"""
import json
import math

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import LineString
from shapely.ops import transform as shp_transform, unary_union

lat0 = 53.35
M_PER_DEG_LAT = 110574.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))


def to_m(lon, lat):
    return (lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT)


def project(geom):
    return shp_transform(lambda x, y, z=None: to_m(x, y), geom)


# --- 2007 survey, BL_CATEG=1 only (matching the user's filter) ---
sf2007 = shapefile.Reader("../data/gov_2007/buslanes_2007/Buslanes/Buslane_dissolve_by_category.shp")
with open("../data/gov_2007/buslanes_2007/Buslanes/Buslane_dissolve_by_category.prj", encoding="utf-8") as f:
    crs2007 = CRS.from_wkt(f.read())
t2007 = Transformer.from_crs(crs2007, CRS.from_epsg(4326), always_xy=True)

lines_2007_m = []
for sr in sf2007.iterShapeRecords():
    if sr.record["BL_CATEG"] != 1.0:
        continue
    pts = sr.shape.points
    if len(pts) < 2:
        continue
    lonlat = [t2007.transform(x, y) for x, y in pts]
    lines_2007_m.append(project(LineString(lonlat)))

len_2007 = sum(g.length for g in lines_2007_m) / 1000.0
print(f"2007 BL_CATEG=1: {len(lines_2007_m)} segments, {len_2007:.2f} km")

# --- BikeLife 2021, buslane=1 only ---
sf_bl = shapefile.Reader("../data/gov_bikelife_2021/bikelife_shp/BikeLife_Final_Data_Issue V2_210817/BikeLife_Final_Data_Issue V2_210817.shp")
with open("../data/gov_bikelife_2021/bikelife_shp/BikeLife_Final_Data_Issue V2_210817/BikeLife_Final_Data_Issue V2_210817.prj", encoding="utf-8") as f:
    crs_bl = CRS.from_wkt(f.read())
t_bl = Transformer.from_crs(crs_bl, CRS.from_epsg(4326), always_xy=True)

lines_bl_m = []
for sr in sf_bl.iterShapeRecords():
    rec = sr.record.as_dict()
    if str(rec.get("buslane", "")).strip() != "1":
        continue
    pts = sr.shape.points
    if len(pts) < 2:
        continue
    lonlat = [t_bl.transform(x, y) for x, y in pts]
    lines_bl_m.append(project(LineString(lonlat)))

len_bl = sum(g.length for g in lines_bl_m) / 1000.0
print(f"BikeLife 2021 buslane=1: {len(lines_bl_m)} segments, {len_bl:.2f} km")

stacked = len_2007 + len_bl
print(f"\nStacked (naive sum): {stacked:.2f} km")

union_2007 = unary_union(lines_2007_m)
union_bl = unary_union(lines_bl_m)

# Exact-geometry overlap (replicating what the user's tool likely did)
exact_overlap = union_2007.intersection(union_bl)
exact_overlap_km = exact_overlap.length / 1000.0 if not exact_overlap.is_empty else 0.0
print(f"\nExact-geometry overlap (no buffer tolerance): {exact_overlap_km:.2f} km")
print(f"  -> 'union dedup' total under this method: {stacked - exact_overlap_km:.2f} km")

# Buffered overlap at several tolerances
for buf in (5, 10, 15, 20, 25):
    bl_buffered = union_bl.buffer(buf)
    covered_2007 = union_2007.intersection(bl_buffered)
    covered_km = covered_2007.length / 1000.0
    print(f"\n2007 lanes within {buf}m of a BikeLife bus-lane segment: {covered_km:.2f} km ({100*covered_km/len_2007:.1f}% of 2007 total)")

    twenty07_buffered = union_2007.buffer(buf)
    covered_bl = union_bl.intersection(twenty07_buffered)
    covered_bl_km = covered_bl.length / 1000.0
    print(f"BikeLife lanes within {buf}m of a 2007 segment:          {covered_bl_km:.2f} km ({100*covered_bl_km/len_bl:.1f}% of BikeLife total)")
