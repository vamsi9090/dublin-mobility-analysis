"""Fetch the real Dublin City Council administrative boundary polygon (OSM relation
1109531) via Nominatim, so downstream scripts can spatially clip the (larger,
Greater-Dublin-Area) government datasets to the exact same extent OSM was queried
against. Without this, area-size differences masquerade as data-completeness gaps.
"""
import json
import time
import urllib.request

OUT_PATH = "../data/boundary_dublin_city.geojson"

url = (
    "https://nominatim.openstreetmap.org/lookup"
    "?osm_ids=R1109531&format=geojson&polygon_geojson=1"
)
req = urllib.request.Request(url, headers={"User-Agent": "european-mobility-analytics/1.0"})

with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))

assert data["features"], "Nominatim returned no features for relation 1109531"
feature = data["features"][0]
geom_type = feature["geometry"]["type"]
print("Fetched boundary geometry type:", geom_type)
print("Properties:", {k: feature["properties"].get(k) for k in ("osm_id", "osm_type", "display_name", "type")})

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(feature, f)

print("Saved to", OUT_PATH)
