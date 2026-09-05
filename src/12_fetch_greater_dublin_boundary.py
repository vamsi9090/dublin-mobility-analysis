import json, urllib.request, urllib.parse, time

AREAS = {
    "Dublin City": "R1109531",
    "Fingal": None,
    "South Dublin": None,
    "Dun Laoghaire-Rathdown": None,
}

def nominatim_search(q):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": q, "format": "json", "polygon_geojson": 0, "addressdetails": 1, "limit": 5,
    })
    req = urllib.request.Request(url, headers={"User-Agent": "european-mobility-analytics/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

for name in ["Fingal, Ireland", "South Dublin, Ireland", "Dun Laoghaire-Rathdown, Ireland"]:
    results = nominatim_search(name)
    time.sleep(1.1)
    print(f"\n=== {name} ===")
    for r in results:
        print(r.get("osm_type"), r.get("osm_id"), r.get("class"), r.get("type"), "-", r.get("display_name"))
