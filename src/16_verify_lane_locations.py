"""
Systematic location verification for the designated bus/taxi lanes layer.
For every segment, reverse-geocode its midpoint via Nominatim and compare
the real-world street name there against the OSM way's own 'name' tag.
A mismatch is real evidence of a geometry/location problem; a match across
the board means the locations are correct and the user's complaint lies
elsewhere (e.g. a genuine OSM tagging inaccuracy on the ground, which is a
data-quality issue in OSM itself, not a bug in this analysis).
"""
import json
import time
import urllib.request
import urllib.parse
import difflib

with open("../data/osm_lanes/designated_lanes_v2.geojson", encoding="utf-8") as f:
    fc = json.load(f)

features = [f for f in fc["features"] if f["properties"].get("name")]
print(f"{len(features)} of {len(fc['features'])} segments have a name tag to verify against")


def midpoint(coords):
    n = len(coords)
    return coords[n // 2]


def reverse_geocode(lat, lon):
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode({
        "format": "json", "lat": lat, "lon": lon, "zoom": 17, "addressdetails": 0,
    })
    req = urllib.request.Request(url, headers={"User-Agent": "european-mobility-analytics/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def name_similarity(a, b):
    a, b = a.lower().strip(), b.lower().strip()
    if a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


results = []
for i, feat in enumerate(features):
    coords = feat["geometry"]["coordinates"]
    lon, lat = midpoint(coords)
    osm_name = feat["properties"]["name"]
    try:
        geo = reverse_geocode(lat, lon)
        display_name = geo.get("display_name", "")
        road_guess = display_name.split(",")[0] if display_name else ""
        sim = name_similarity(osm_name, road_guess)
        results.append({
            "osm_id": feat["properties"]["osm_id"], "osm_name": osm_name, "lat": lat, "lon": lon,
            "reverse_geocoded_road": road_guess, "similarity": round(sim, 2), "match": sim > 0.5,
        })
    except Exception as e:
        results.append({"osm_id": feat["properties"]["osm_id"], "osm_name": osm_name, "error": str(e)})
    time.sleep(1.1)
    if (i + 1) % 50 == 0:
        print(f"  ...{i+1}/{len(features)} checked")

matches = [r for r in results if r.get("match")]
mismatches = [r for r in results if r.get("match") is False]
errors = [r for r in results if "error" in r]

print(f"\nChecked: {len(results)}")
print(f"Matched (Nominatim road name agrees with OSM tag): {len(matches)}")
print(f"MISMATCHED: {len(mismatches)}")
print(f"Errors: {len(errors)}")

if mismatches:
    print("\n--- Mismatches (potential real location problems) ---")
    for r in mismatches:
        print(f"  osm_id={r['osm_id']}  OSM name='{r['osm_name']}'  ->  reverse-geocoded='{r['reverse_geocoded_road']}'  (sim={r['similarity']}) https://www.openstreetmap.org/way/{r['osm_id']}")

with open("../data/lane_location_verification.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
