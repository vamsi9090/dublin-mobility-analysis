"""
Route-by-route comparison: OSM route=bus relations vs GTFS routes_dublin.csv.

Key correction applied here (found during column profiling): OSM's route=bus
relation set for the Dublin City area includes intercity/airport coach
operators (Bus Eireann, Aircoach, J.J. Kavanagh & Sons, Translink, Wexford
Bus, Collins Coaches, Dublin Express, Dublin Tour, ...) that fall outside the
scope of the government feed, which is pre-filtered to Dublin Bus / Go-Ahead
Ireland Dublin routes / Nitelink only. Comparing the raw 155-ref OSM set
against the 172-ref Gov set would overstate "OSM-only" routes with routes
that were never meant to be in scope. We restrict OSM to operator in
{Dublin Bus, Go-Ahead Ireland} before comparing (matching the Gov filter's
agency intent), and separately report the excluded non-Dublin operators as
its own finding rather than silently dropping them.
"""
import csv
import json
from collections import Counter

with open("../data/osm/bus_routes_raw.json", encoding="utf-8") as f:
    osm_raw = json.load(f)
rels = [e for e in osm_raw["elements"] if e["type"] == "relation"]

DUBLIN_URBAN_OPERATORS = {"Dublin Bus", "Go-Ahead Ireland"}

osm_all_refs = set()
osm_urban_refs = set()
osm_excluded_by_operator = Counter()
osm_ref_operator_map = {}
for r in rels:
    tags = r.get("tags", {})
    ref = (tags.get("ref") or "").strip()
    op = tags.get("operator", "<none>")
    if not ref:
        continue
    osm_all_refs.add(ref)
    if op in DUBLIN_URBAN_OPERATORS:
        osm_urban_refs.add(ref)
        osm_ref_operator_map.setdefault(ref, set()).add(op)
    else:
        osm_excluded_by_operator[op] += 1

with open("../data/gov/routes_dublin.csv", encoding="utf-8-sig") as f:
    gov_routes = list(csv.DictReader(f))
gov_refs_raw = {row["route_short_name"].strip() for row in gov_routes}


def norm(ref_set):
    return {r.strip().upper(): r for r in ref_set}


osm_norm = norm(osm_urban_refs)
gov_norm = norm(gov_refs_raw)

matched = sorted(set(osm_norm) & set(gov_norm))
osm_only = sorted(set(osm_norm) - set(gov_norm))
gov_only = sorted(set(gov_norm) - set(osm_norm))

report = {
    "osm_total_relations": len(rels),
    "osm_all_refs_any_operator_count": len(osm_all_refs),
    "osm_urban_refs_dublinbus_goahead_only_count": len(osm_urban_refs),
    "osm_refs_excluded_non_dublin_operators": dict(osm_excluded_by_operator),
    "gov_refs_count": len(gov_refs_raw),
    "matched_count": len(matched),
    "matched_refs": [osm_norm[m] for m in matched],
    "osm_only_count": len(osm_only),
    "osm_only_refs": [osm_norm[m] for m in osm_only],
    "gov_only_count": len(gov_only),
    "gov_only_refs": [gov_norm[m] for m in gov_only],
    "coverage_pct_of_gov_routes_present_in_osm": round(100 * len(matched) / len(gov_norm), 1),
    "coverage_pct_of_osm_urban_routes_present_in_gov": round(100 * len(matched) / len(osm_norm), 1),
}

with open("../data/route_comparison.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print(f"OSM relations total: {report['osm_total_relations']}")
print(f"OSM distinct refs (ANY operator, incl. intercity coach): {report['osm_all_refs_any_operator_count']}")
print(f"OSM distinct refs (Dublin Bus + Go-Ahead Ireland only):  {report['osm_urban_refs_dublinbus_goahead_only_count']}")
print(f"  -> excluded (non-Dublin operator) relation counts: {report['osm_refs_excluded_non_dublin_operators']}")
print(f"Gov (GTFS agency-filtered) distinct route_short_names:   {report['gov_refs_count']}")
print()
print(f"MATCHED (in both, case-normalized): {report['matched_count']}")
print(f"OSM-only (tagged in OSM, not in Gov Dublin GTFS filter): {report['osm_only_count']} -> {report['osm_only_refs']}")
print(f"Gov-only (in GTFS filter, not tagged/found in OSM):      {report['gov_only_count']} -> {report['gov_only_refs']}")
print()
print(f"Coverage: {report['coverage_pct_of_gov_routes_present_in_osm']}% of official Dublin routes are represented in OSM")
print(f"Coverage: {report['coverage_pct_of_osm_urban_routes_present_in_gov']}% of OSM-tagged Dublin urban routes match an official GTFS route")
