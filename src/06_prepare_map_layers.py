"""
Prepare browser-friendly map layers:
 - OSM bus routes: collapse 113,249 raw way-segments into one MultiLineString
   feature per route relation (358 features), split into "Dublin urban"
   (Dublin Bus / Go-Ahead Ireland) vs "other operator" (intercity/airport
   coach) so the map doesn't mix scopes.
 - Gov cycle network: keep only features that actually intersect the Dublin
   City boundary (drop the Greater Dublin Area features entirely outside it).
"""
import json
from collections import defaultdict

from shapely.geometry import shape, mapping

with open("../data/osm/bus_routes_raw.json", encoding="utf-8") as f:
    raw = json.load(f)

nodes = {}
ways = {}
for el in raw["elements"]:
    if el["type"] == "node":
        nodes[el["id"]] = (el["lon"], el["lat"])
    elif el["type"] == "way":
        ways[el["id"]] = el

relations = [el for el in raw["elements"] if el["type"] == "relation"]

DUBLIN_URBAN_OPERATORS = {"Dublin Bus", "Go-Ahead Ireland"}
urban_features, other_features = [], []

for rel in relations:
    tags = rel.get("tags", {})
    lines = []
    for member in rel.get("members", []):
        if member["type"] != "way":
            continue
        # Overpass "out geom" on the relation directly gives geometry on members
        geom = member.get("geometry")
        if geom:
            coords = [[pt["lon"], pt["lat"]] for pt in geom]
            if len(coords) >= 2:
                lines.append(coords)
    if not lines:
        continue
    feature = {
        "type": "Feature",
        "geometry": {"type": "MultiLineString", "coordinates": lines},
        "properties": {
            "relation_id": rel["id"],
            "ref": tags.get("ref", ""),
            "name": tags.get("name", ""),
            "operator": tags.get("operator", ""),
            "network": tags.get("network", ""),
        },
    }
    if tags.get("operator") in DUBLIN_URBAN_OPERATORS:
        urban_features.append(feature)
    else:
        other_features.append(feature)

print(f"Dublin urban route relations (with geometry): {len(urban_features)}")
print(f"Other-operator route relations (with geometry): {len(other_features)}")

with open("../data/osm_bus_routes_urban.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": urban_features}, f)
with open("../data/osm_bus_routes_other.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": other_features}, f)

# --- Gov cycle network: keep only features intersecting the boundary ---
with open("../data/boundary_dublin_city.geojson", encoding="utf-8") as f:
    boundary_feat = json.load(f)
boundary_poly = shape(boundary_feat["geometry"])

with open("../data/gov/cycle_network_dublin.geojson", encoding="utf-8") as f:
    gov_cycle = json.load(f)

inside_features = [
    feat for feat in gov_cycle["features"]
    if shape(feat["geometry"]).intersects(boundary_poly)
]
print(f"Gov cycle network features intersecting Dublin City boundary: {len(inside_features)} / {len(gov_cycle['features'])}")

with open("../data/gov_cycle_dublin_city.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": inside_features}, f)
