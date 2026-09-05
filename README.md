<h1 align="center">Dublin Transport Infrastructure: OpenStreetMap vs. Government Open Data</h1>
<p align="center"><i>A live-data comparison of bus, taxi, cycling and walking infrastructure between OpenStreetMap and eight official Irish government datasets.</i></p>

---

## Why I built this

I wanted to know a simple-sounding question — **how complete and accurate is OpenStreetMap's picture of Dublin's transport infrastructure, compared to what the government actually says exists?** — and it turned out to have a genuinely interesting, non-obvious answer that took real cross-referencing to get right.

This isn't a toy dataset. Every number below comes from live OSM Overpass API queries and eight real Irish government open-data sources, cross-verified against each other with actual spatial analysis (point matching, buffered overlap, route-by-route diffing) rather than eyeballed comparisons. Where my own first-pass analysis was wrong, I've left that in the methodology notes rather than quietly fixing it — the corrections are part of the finding.

## What's in here

- **One interactive map** (open directly in any browser, no server needed) — Dublin City comparison as the primary view, with the full Greater Dublin Area cycling/walking data available as a collapsible third panel section, same file
- **A full written analysis** with every headline number sourced and cross-checked
- **All the source code** that produced them, in the order it was run
- **Processed datasets** backing every figure in the report

## Headline findings

| Question | Answer |
|---|---|
| How well does OSM cover Dublin's official bus routes? | **50.6%** — only half of the 172 official Dublin Bus/Go-Ahead routes have a matching OSM relation. Go-Ahead Ireland's network is especially under-mapped. |
| How well does OSM cover Dublin's bus stops? | Very well — **91.9–95.1%** mutual match rate against the official GTFS feed (median distance 4.8m). |
| How much of the government's documented bus lane network is missing from OSM? | **83.2%** — a rigorously verified gap, not a fluke of one query. Confirmed 2007 government survey vs. current OSM tagging. |
| Are there taxi-only lanes in Dublin? | No — every taxi-permitted road segment I found is also bus-permitted (Ireland's shared PSV lane convention). |
| Is OSM's cycling data comparable to the government's? | Only if you match definitions carefully — a naive comparison overstates the gap by ~4x, once mixed area scopes and "strict vs. broad" cycling-infrastructure definitions are properly reconciled. |
| Does an official government footpath dataset exist? | No — confirmed by genuine search of every known Irish open-data portal, not assumed. OSM is the only usable source for Dublin's pedestrian network. |

Full detail, methodology, and every caveat: **[`reports/ANALYSIS_REPORT.md`](reports/ANALYSIS_REPORT.md)**

## The map

**[`maps/dublin_osm_vs_gov_map.html`](maps/dublin_osm_vs_gov_map.html)** — one file, three panel sections:

| Section | Scope | What's on it |
|---|---|---|
| **OpenStreetMap Data** | Dublin City Council (117.6 km²) | Designated bus/taxi lanes (by allowed vehicle type), cycling infrastructure (classified by type: dedicated track, on-road lane, shared path...), bus stops (matched / OSM-only), taxi ranks, walking paths |
| **Government Data** | Dublin City Council, clipped to match | GTFS-only bus stops, NTA/DCC cycling networks, the 2007 bus lane & cycletrack surveys, BikeLife 2021, and the computed OSM-data-gap layers |
| **Regional Data (Greater Dublin Area)** — collapsed by default | Full GDA (921 km², all 4 local authorities) | OSM cycling under two definitions (strict vs. broad) and the full walking network, for the wider-scope picture beyond the city core |

Satellite view, full click-for-detail popups with Google Street View links on every feature (city-scope layers; regional-scope layers use lightweight hover tooltips given their size — 21.5k / 55k features). Download the file and open it in a browser — everything is self-contained except map tiles, which need an internet connection.

## Data sources

**OpenStreetMap** — live Overpass API queries, September 2026.

**Government (8 sources):**
| Dataset | Publisher | Year |
|---|---|---|
| NTA static GTFS feed | National Transport Authority | 2026 (current) |
| Taxi Rank Bye-Laws (Schedules 1-4) | Dublin City Council | current |
| Active Travel Cycle Network | NTA | 2025 |
| Existing Protected Cycle Infrastructure | DCC / Smart Dublin | 2013-2023 |
| GDA Bus Lane Survey | Dublin Transportation Office / NTA | 2007 |
| GDA Cycletrack Survey | Dublin Transportation Office | 2007 |
| BikeLife Survey | NTA | 2013-2021 |

## Repository structure

```
dublin-mobility-analysis/
├── README.md                    this file
├── LICENSE
├── requirements.txt
├── reports/
│   └── ANALYSIS_REPORT.md       full write-up: every number, sourced and cross-checked
├── maps/                        the two deliverables — open directly in a browser
│   ├── dublin_osm_vs_gov_map.html
│   └── dublin_gda_cycling_walking_map.html
├── src/                         all analysis code, in the order it was run (01 -> 22)
│   ├── 01_fetch_boundary.py             resolve the real Dublin City Council polygon
│   ├── 02_column_profile.py             profile every field in every dataset (not just headline counts)
│   ├── 03_route_comparison.py           OSM vs. GTFS bus route diffing
│   ├── 04_spatial_clip.py               clip government data to a matching boundary
│   ├── 05_stop_matching.py              nearest-neighbor bus stop matching
│   ├── 06-08                            map-layer preparation & size optimization
│   ├── 09-14                            designated bus/taxi lane extraction & classification (city + regional)
│   ├── 15                               process the 2007 government bus lane survey (CRS reprojection)
│   ├── 16                               reverse-geocode verification of lane locations
│   ├── 17-18                            spatial gap analysis: OSM vs. government, bus lanes & cycling
│   ├── 19                               overlap-detection methodology check (2007 vs. 2021 gov surveys)
│   ├── 20-21                            process BikeLife 2021 + 2007 cycletracks + regional walking data
│   └── 22                               build the regional companion map
└── data/processed/               every intermediate result and map layer, so nothing here is a black box
```

Raw source downloads (GTFS zip, shapefiles, raw Overpass API responses) aren't committed — they're large, and every download URL is in the relevant script's docstring so the whole pipeline is reproducible from scratch.

## Reproducing this

```bash
pip install -r requirements.txt
cd src
python 01_fetch_boundary.py
python 02_column_profile.py
# ... run in numeric order; each script documents what it needs in its docstring
```

Everything hits live public APIs (Overpass, Nominatim, data.gov.ie, data.smartdublin.ie) — no API keys required.

## Methodology honesty

A few things I want on the record rather than buried:

- I caught and fixed a real bug in my own boundary-clipping code mid-analysis (a Python `and/or`-as-ternary mistake that briefly made it look like 0% of government stops were in Dublin City). It's documented in the report, not quietly patched out.
- The 2007-vs-2021 government bus lane "overlap" figure in one early pass of this analysis used exact-geometry matching between two datasets in *different coordinate systems* — which by construction finds ~0% overlap regardless of the real answer. The corrected, buffer-tolerant figure is in the report.
- Two OSM statistics I checked (a 2,464km cycling figure and a 60,276 walkway-feature count) turned out to be real numbers under different definitions/boundaries than I'd first assumed, not fabricated — the report shows exactly how they were reconciled.

## License

MIT — see [`LICENSE`](LICENSE). Government data used here is republished under the license terms of the original sources (Creative Commons Attribution 4.0 for the data.gov.ie / Smart Dublin datasets); OpenStreetMap data is © OpenStreetMap contributors, ODbL.
