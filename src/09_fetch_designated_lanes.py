"""
Fetch OSM ways carrying explicit bus/taxi/psv lane-designation tags within
the Dublin City boundary -- i.e. actual road segments legally restricted to
those vehicle classes, not full service route paths. Distinct query from the
bus_routes.geojson (route=bus relations) fetched earlier.

Tags queried (this is the real OSM vocabulary for lane-level restrictions):
  busway / busway:both / busway:right / busway:left = lane|opposite_lane   (dedicated bus lane scheme)
  bus = designated                                                         (whole way bus-designated)
  lanes:bus / bus:lanes:*                                                  (per-lane bus designation)
  taxi = designated
  lanes:taxi / taxi:lanes:*
  psv = designated        (PSV = Public Service Vehicle = bus + taxi, standard UK/IE usage)
  lanes:psv / psv:lanes:*
"""
import json
import time
import urllib.request

AREA_ID = 3601109531  # Dublin City Council boundary, same area used throughout this analysis
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERY = f"""
[out:json][timeout:180];
area({AREA_ID})->.searchArea;
(
  way["busway"](area.searchArea);
  way["busway:both"](area.searchArea);
  way["busway:right"](area.searchArea);
  way["busway:left"](area.searchArea);
  way["bus"="designated"](area.searchArea);
  way["lanes:bus"](area.searchArea);
  way["taxi"="designated"](area.searchArea);
  way["lanes:taxi"](area.searchArea);
  way["psv"="designated"](area.searchArea);
  way["lanes:psv"](area.searchArea);
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

import urllib.parse
data = fetch(QUERY)
print("elements returned:", len(data["elements"]))
with open("../data/osm_lanes/designated_lanes_raw.json", "w", encoding="utf-8") as f:
    json.dump(data, f)
print("saved raw response")
