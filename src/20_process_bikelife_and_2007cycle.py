"""
Process the two verified-but-not-yet-mapped government datasets:
  1. BikeLife 2021 bus lanes (buslane=1 filter) -- CRS: IRENET95/ITM
  2. 2007 GDA cycletracks survey, by CATEGORY -- CRS: TM65 Irish Grid
Both reprojected to WGS84 for the map.
"""
import json
import math

import shapefile
from pyproj import CRS, Transformer

# --- 1. BikeLife 2021 bus lanes ---
shp_path = "../data/gov_bikelife_2021/bikelife_shp/BikeLife_Final_Data_Issue V2_210817/BikeLife_Final_Data_Issue V2_210817.shp"
prj_path = shp_path.replace(".shp", ".prj")
with open(prj_path, encoding="utf-8") as f:
    crs_bl = CRS.from_wkt(f.read())
t_bl = Transformer.from_crs(crs_bl, CRS.from_epsg(4326), always_xy=True)

sf = shapefile.Reader(shp_path)
features = []
for sr in sf.iterShapeRecords():
    rec = sr.record.as_dict()
    if str(rec.get("buslane", "")).strip() != "1":
        continue
    pts = sr.shape.points
    if len(pts) < 2:
        continue
    lonlat = [list(t_bl.transform(x, y)) for x, y in pts]
    features.append({
        "type": "Feature", "geometry": {"type": "LineString", "coordinates": lonlat},
        "properties": {
            "Route": rec.get("Route_No"), "Infrastructure type": rec.get("cdo") or "Bus lane (unclassified)",
            "Length (m)": round(float(rec.get("Shape_Leng") or 0), 1),
            "Source": "NTA BikeLife Survey (2013-2021, published Feb 2021)",
        },
    })
print(f"BikeLife bus lanes: {len(features)} segments")
with open("../data/gov_bikelife_2021_buslanes.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))

# --- 2. 2007 GDA cycletracks, by category ---
shp2 = "../data/gov_2007/cycletracks_2007/Cycletracks/Cycle_Track_230908.shp"
prj2 = shp2.replace(".shp", ".prj")
with open(prj2, encoding="utf-8") as f:
    crs2007 = CRS.from_wkt(f.read())
t2007 = Transformer.from_crs(crs2007, CRS.from_epsg(4326), always_xy=True)

sf2 = shapefile.Reader(shp2)
n = sf2.numRecords
features2 = []
skipped = 0
for i in range(n):
    try:
        shp_i = sf2.shape(i)
        pts = shp_i.points
        if not pts or len(pts) < 2:
            skipped += 1
            continue
        length_m = sum(math.dist(pts[j], pts[j + 1]) for j in range(len(pts) - 1))
        rec = sf2.record(i).as_dict()
        lonlat = [list(t2007.transform(x, y)) for x, y in pts]
        features2.append({
            "type": "Feature", "geometry": {"type": "LineString", "coordinates": lonlat},
            "properties": {
                "Category": rec.get("CATEGORY") or "Unspecified", "Description": rec.get("CT_DESC") or "",
                "Width (m)": rec.get("CT_WIDTH"), "Length (m)": round(length_m, 1),
                "Source": "2007 GDA Cycletrack Survey (Dublin Transportation Office)",
            },
        })
    except Exception:
        skipped += 1

print(f"2007 cycletracks: {len(features2)} segments parsed, {skipped} skipped (malformed in source)")
with open("../data/gov_2007_cycletracks.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features2}, f, separators=(",", ":"))
