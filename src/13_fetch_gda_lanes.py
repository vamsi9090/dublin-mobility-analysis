"""
Fetch designated bus/taxi/PSV lane segments across the full Dublin region
(all 4 local authorities: Dublin City, Fingal, South Dublin, Dun Laoghaire-
Rathdown), not just Dublin City Council, to test whether a wider boundary
accounts for a much larger bus-lane network than the ~24km found within the
city boundary alone.
"""
import json
import time
import urllib.request
import urllib.parse

from shapely.geometry import shape
from shapely.ops import unary_union

RELATIONS = {
    "Dublin City": 1109531,
    "Fingal": 1114164,
    "South Dublin": 1117469,
    "Dun Laoghaire-Rathdown": 1115720,
}

def nominatim_lookup(osm_id):
    url = "https://nominatim.openstreetmap.org/lookup?" + urllib.parse.urlencode({
        "osm_ids": f"R{osm_id}", "format": "geojson", "polygon_geojson": 1,
    })
    req = urllib.request.Request(url, headers={"User-Agent": "european-mobility-analytics/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

polys = []
for name, osm_id in RELATIONS.items():
    data = nominatim_lookup(osm_id)
    geom = shape(data["features"][0]["geometry"])
    polys.append(geom)
    print(f"{name}: area proxy (deg^2)={geom.area:.5f}")
    time.sleep(1.1)

union_poly = unary_union(polys)
minx, miny, maxx, maxy = union_poly.bounds
print(f"\nUnion bbox: south={miny}, north={maxy}, west={minx}, east={maxx}")

with open("../data/boundary_greater_dublin_region.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "Feature", "geometry": json.loads(
        __import__("shapely").geometry.mapping.__self__ and "{}" or "{}"
    ) if False else __import__("shapely.geometry", fromlist=["mapping"]).mapping(union_poly),
        "properties": {"name": "Dublin Region (4 local authorities union)"}}, f)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
KEYS = [
    "busway", "busway:both", "busway:right", "busway:left",
    "bus", "lanes:bus", "bus:lanes", "bus:lanes:forward", "bus:lanes:backward",
    "taxi", "lanes:taxi", "taxi:lanes", "taxi:lanes:forward", "taxi:lanes:backward",
    "psv", "lanes:psv", "psv:lanes", "psv:lanes:forward", "psv:lanes:backward",
    "lanes:psv:forward", "lanes:psv:backward", "lanes:bus:forward", "lanes:bus:backward",
]
bbox = f"{miny},{minx},{maxy},{maxx}"
clauses = "\n".join(f'  way["{k}"]({bbox});' for k in KEYS)
QUERY = f"""
[out:json][timeout:180];
(
{clauses}
);
out geom;
"""

def fetch(query, attempts=6):
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                OVERPASS_URL, data=f"data={urllib.parse.quote(query)}".encode(),
                headers={"User-Agent": "european-mobility-analytics/1.0"},
            )
            with urllib.request.urlopen(req, timeout=200) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            wait = 20 * (i + 1)
            print(f"attempt {i+1} failed ({e}); retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError("all attempts failed")

print("\nQuerying Overpass across Greater Dublin bbox...")
data = fetch(QUERY)
ways = [e for e in data["elements"] if e["type"] == "way"]
print("total ways returned (bbox, before polygon clip):", len(ways))
with open("../data/osm_lanes/gda_lanes_raw.json", "w", encoding="utf-8") as f:
    json.dump(data, f)
print("saved")
