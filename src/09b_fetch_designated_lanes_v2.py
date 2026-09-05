"""
Expanded re-query: the v1 query missed the per-direction lane-array tagging
style (bus:lanes:forward=yes|designated, psv:lanes:forward, etc.), which is
common for Dublin's bus lanes -- a way using ONLY that style was never
returned by the narrower v1 query at all (the classifier checked for it, but
only on already-fetched data). Adding all per-direction variants now.
"""
import json
import time
import urllib.request
import urllib.parse

AREA_ID = 3601109531
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

KEYS = [
    "busway", "busway:both", "busway:right", "busway:left",
    "bus", "lanes:bus", "bus:lanes", "bus:lanes:forward", "bus:lanes:backward",
    "taxi", "lanes:taxi", "taxi:lanes", "taxi:lanes:forward", "taxi:lanes:backward",
    "psv", "lanes:psv", "psv:lanes", "psv:lanes:forward", "psv:lanes:backward",
    "lanes:psv:forward", "lanes:psv:backward", "lanes:bus:forward", "lanes:bus:backward",
]

clauses = "\n".join(f'  way["{k}"](area.searchArea);' for k in KEYS)
QUERY = f"""
[out:json][timeout:180];
area({AREA_ID})->.searchArea;
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

data = fetch(QUERY)
ways = [e for e in data["elements"] if e["type"] == "way"]
print("total ways returned:", len(ways))
with open("../data/osm_lanes/designated_lanes_raw_v2.json", "w", encoding="utf-8") as f:
    json.dump(data, f)
print("saved")
