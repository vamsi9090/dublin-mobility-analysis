# Dublin Transport Infrastructure: OpenStreetMap vs. Government Open Data
### Full analysis report — every number sourced, cross-checked, and where I got something wrong, corrected in the open

**Primary comparison extent:** Dublin City Council administrative boundary (OSM relation 1109531, admin_level=7), area **117.60 km²**. A second pass extends key metrics to the full **Greater Dublin Area** (4 local authorities — Dublin City, Fingal, South Dublin, Dún Laoghaire-Rathdown — union area **921 km²**) where noted.

---

## 1. Methodology

Three corrections were significant enough to change conclusions, and are documented here rather than silently fixed:

1. **Area mismatch.** Government datasets (GTFS, NTA cycle network) cover the Greater Dublin Area by default; OSM was queried against the smaller Dublin City boundary. All comparisons below are area-normalized (government data spatially clipped to match) unless explicitly marked GDA-wide.
2. **A boundary-clipping bug.** An early draft of this analysis used a Python `cond and A or B` conditional-expression pattern to sort points into "inside"/"outside" buckets. Because the `inside` accumulator list starts empty (falsy), the expression always evaluated to `B` regardless of `cond` — so 100% of government bus stops were (wrongly) classified as outside Dublin City. Caught by cross-checking against a known-good baseline (OSM stops, verified 100% inside by a different code path) before being reported. Fixed and rerun.
3. **Exact-geometry overlap between independently-digitized datasets.** Comparing the 2007 government bus lane survey against a 2021 government cycling survey's bus-lane attribute using exact coordinate matching found ~0% overlap — not because the surveys disagree, but because two datasets digitized 14 years apart in *different coordinate reference systems* (TM65 Irish Grid vs. modern ITM) will never share exact vertices even when tracing the same physical lane. A buffer-tolerant re-analysis (Section 6.4) gives the real picture.

All lengths use either the source data's native projected CRS (accurate) or a local equirectangular projection centered on Dublin's latitude (accurate to well under 0.1% at city scale) — never raw lat/lon coordinate differences, which would be meaningless as a distance unit.

---

## 2. Bus stops

| | OSM | Government (GTFS) |
|---|---|---|
| Stops within Dublin City boundary | **2,098** | **1,879** |
| Matched to the other source (≤30m) | 1,929 (91.9%) | 1,786 (95.1%) |
| Unmatched | 169 | 93 |

Median nearest-neighbor distance: **4.8m** (p90 = 23m, p95 = 54m — 30m is a clean, well-separated threshold). The two sources agree closely at the point level. Naive unclipped counts (2,098 vs. GTFS's full 5,033, which includes commuter stops in Kildare/Wicklow/Fingal) would have implied a 2.4x gap that doesn't actually exist within the comparable area — within Dublin City, OSM has *more* distinct stop points than GTFS, not fewer.

## 3. Bus routes

| | Count |
|---|---|
| OSM relations, any operator | 358 (155 distinct refs — includes intercity/airport coach) |
| OSM relations, Dublin Bus + Go-Ahead Ireland only | 220 relations, **108 distinct refs** |
| Government (GTFS, Dublin-filtered) distinct routes | **172** |
| Matched | 87 |
| OSM-only | 21 |
| **Government-only (missing from OSM)** | **85** |

**Only 50.6% of official Dublin bus routes have a corresponding OSM relation.** The gap concentrates almost entirely in Go-Ahead Ireland's network (routes like 102, 104, 111, 114, 116, 142, 150, 151, 161, 197, and the entire "L" Local Link series have no OSM relation at all) plus most lettered variants and night-service (`n`-suffix) routes. Most of the 21 "OSM-only" refs aren't extra routes — they're OSM's finer branch-level tagging (120A/B/E/F/X) that GTFS folds under one base route number.

**Data quality find:** OSM ref `"DB 104"` (note the stray prefix) is almost certainly GTFS route `"104"`, mistagged. Routes `49` and `747` (Dublin Bus's Airlink) appear in OSM but not the current GTFS filter — either discontinued/renumbered services with stale OSM data, or a gap in the agency filter.

## 4. Taxi infrastructure

| | OSM | Government |
|---|---|---|
| Count | **61** (58 nodes + 3 ways) | **195** bye-law schedule entries |
| Geometry | Yes | **None** — legal text only |

The government dataset (DCC Taxi Rank Bye-Laws, Schedules 1-4) has no coordinates and its own note flags that a stand can recur across schedules, so 195 is a row count, not a unique-location count. **OSM is the only source that lets you place Dublin's taxi ranks on a map.**

## 5. Designated bus/taxi lane road segments

This is distinct from Section 3 — bus *routes* are the end-to-end service path; this section is about which specific road segments are legally restricted to bus/taxi/PSV traffic.

### 5.1 OSM (current, live)

| Scope | Segments | Length |
|---|---|---|
| Dublin City boundary | 334 | **24.31 km** |
| Full Greater Dublin Area | 652 | **61.26 km** |

By allowed-vehicle category (Dublin City): bus-only 92 (5.03km), bus+taxi/PSV 179 (13.79km), bike+bus+taxi 50 (4.66km), bike+bus 12 (0.70km), taxi-only 1 (0.13km). **No taxi-exclusive lanes were found anywhere** — every taxi-permitted segment is also bus-permitted, matching Ireland's PSV (Public Service Vehicle) legal category that covers both.

*Note on the initial query:* the first pass of this only searched whole-way tags (`busway=lane`, `bus=designated`, etc.) and missed Dublin's common per-direction lane-array tagging (`bus:lanes:forward`, `psv:lanes:backward`, time-conditional variants). Expanding the query more than doubled the segment count found (159 → 334) — a real gap in the first query, not a data problem.

### 5.2 Government — 2007 GDA Bus Lane Survey (Dublin Transportation Office / NTA)

| Scope | Segments | Length |
|---|---|---|
| Full Greater Dublin Area | 555 | **186.58 km** |
| — of which category BL_CATEG=1 only | 470 | 178.71 km |
| Clipped to Dublin City boundary | — | **89.08 km** |

### 5.3 The gap, quantified spatially (not just by raw totals)

Buffered overlap analysis (20m tolerance, accounting for realistic digitizing/GPS offset) between OSM's current tagging and the 2007 government survey, within Dublin City:

| | Confirmed by the other source | Gap |
|---|---|---|
| 2007 government lanes vs. OSM | 16.8% (14.95 km) | **83.2% (74.13 km)** |
| OSM lanes vs. 2007 government | 60.9% (14.79 km) | 39.1% (9.52 km, plausibly newer lanes built since 2007) |

**Conclusion: 83.2% of the bus lane network a government survey documented in 2007 has no corresponding OSM tag today.** This is the headline finding of this analysis — OSM significantly under-tags Dublin's bus lanes relative to even an 18-year-old official survey.

### 5.4 A second government source, and a real methodology correction

A separate 2021 government survey (**NTA BikeLife**, itself primarily a cycling-infrastructure survey that incidentally flags roads with a `buslane` attribute) gives **1,184 segments / 133.55 km** GDA-wide for that flag.

An early combination of the 2007 and BikeLife datasets used *exact-geometry* overlap detection and found only ~0.35 km shared between them — implying a "deduplicated" combined total of ~312 km. **This significantly overstates reality.** Two independently-digitized surveys of the same physical road, done 14 years apart in different coordinate systems, will not share exact vertices even where they trace the identical lane. Re-run with a realistic 15m buffer tolerance:

| Tolerance | 2007 confirmed by BikeLife | BikeLife confirmed by 2007 |
|---|---|---|
| 0m (exact) | 0.0% | 0.0% |
| 10m | 42.2% | 53.1% |
| **15m** | **56.0%** | **66.5%** |
| 20m | 58.2% | 69.8% |

The smooth climb from 0% to 56%+ as tolerance increases is the signature of "same physical feature, different digitization" — not two genuinely disjoint lane networks. **Corrected combined unique total: ~217 km** (177.91 + 133.00 − ~94 km real overlap), not the naive ~312 km.

### 5.5 Where a widely-cited "~340km" figure actually comes from

This isn't any of the *existing*-infrastructure numbers above. It matches **BusConnects Dublin**, the NTA's current program: ~230 km of *planned* dedicated bus priority + 200 km of *planned* cycling infrastructure across 12 Core Bus Corridors — still moving from planning into construction as of late 2025. It's a future-network figure, not a measurement of what's on the ground today, which is why it doesn't match any live-data query against OSM or the historical surveys.

Separately, if you want a same-methodology "existing infrastructure, no double-counting" total: 2007 bus lanes (89.08 km, Dublin City) + NTA's current cycling network (259.88 km, which already includes DCC's protected-cycling subset — see §6.3) = **348.96 km**, coincidentally close to 340.

## 6. Cycling infrastructure

### 6.1 OSM, classified by real-world type (not treated as one lump category)

| Type | Segments | Length |
|---|---|---|
| Dedicated cycle-only track | 612 | 38.84 km |
| Shared corridor (segregated bike+pedestrian) | 110 | 26.04 km |
| On-road painted lane | 266 | 25.58 km |
| Shared path (unsegregated bike+pedestrian) | 350 | 24.54 km |
| Separated track alongside road | 25 | 5.15 km |
| Shared lane / sharrow | 12 | 2.30 km |
| Crossing | 189 | 1.70 km |
| Cycling on sidewalk | 36 | 1.37 km |
| **Total (Dublin City)** | **1,600** | **125.52 km** |

### 6.2 Government sources

- **NTA Active Travel Cycle Network (2025):** 973.55 km GDA-wide; **259.88 km** clipped to Dublin City.
- **DCC/Smart Dublin Protected & Segregated Infrastructure (2013-2023):** 96.56 km clipped to Dublin City, by type (SegregatedCycleLane, TrafficFree, SharedUse, SignedRoute, SurfaceChange).
- **2007 GDA Cycletrack Survey:** **691.75 km**, GDA-wide, by category — On Street 360.62 km, Adjacent to carriageway 232.17 km, Off-road track/cycleway 97.15 km, Bus lane only 1.59 km, Advanced Cycle Stopping Area 0.15 km. (740 of 11,049 source records were malformed/null in the original 2007 shapefile — a data-quality issue in the source, not this analysis.)

### 6.3 Three-way gap analysis (Dublin City, 15m buffer tolerance)

| | Confirmed by other source | Gap |
|---|---|---|
| OSM vs. NTA | 78.5% | 21.5% |
| NTA vs. OSM | 50.0% | **50.0%** |
| OSM vs. DCC protected | 44.0% | 56.0% |
| DCC protected vs. OSM | 58.5% | 41.5% |
| NTA vs. DCC protected | 39.5% | 60.5% |
| **DCC protected vs. NTA** | **98.2%** | **1.8%** |

The last row is an important internal-consistency check: DCC's protected-cycle dataset is **98.2% a subset of** NTA's broader network — two independent government sources agree with each other almost perfectly where their scopes overlap. That agreement is what makes the OSM gap (50% of NTA's network has no OSM tag) trustworthy rather than a measurement artifact.

### 6.4 Regional-scope verification (resolves a disputed comparison)

A separate figure claimed "OSM Bike: 2,464 km" for the Greater Dublin Area — nearly 20x the 125.52 km Dublin-City figure above. Live re-verification, precisely clipped to the actual 919.75 km² GDA boundary polygon (not just a bounding box):

| Definition | Ways | Length |
|---|---|---|
| Strict (same rule as the 125.52 km Dublin City figure) | 6,798 | 698.19 km |
| Broad (+ bicycle-permitted footways/paths/tracks, + any `cycleway:left/right/both`) | 21,517 | **2,374.27 km** |

**The 2,464 km figure is real** — it matches the *broad* definition (within 3.6%) — but comparing it directly to the *strict*-definition 125.52 km figure was an invalid comparison of two different definitions, not a real ~20x gap. The genuine area/density-adjusted increase, same definition both times, is **5.6x** (698.19 / 125.52) — consistent with GDA being 7.8x the area of Dublin City but cycling infrastructure being denser in the city core.

## 7. Walking infrastructure

| | OSM |
|---|---|
| Dublin City | 15,119 features, **1,033.5 km** |
| Full Greater Dublin Area | 55,100 features, **4,245.0 km** |

**No official government footpath/footway dataset exists** — confirmed by genuine search across data.gov.ie and data.smartdublin.ie, not assumed. Rejected candidates included a 2012-13 mobile-app usage-log dataset, a road-schedule dataset with no footpath geometry, and a Dún Laoghaire-Rathdown-only layer. OSM is the only usable source for Dublin's pedestrian network.

A separately disputed figure claimed 60,276 GDA-wide features. Re-verification (per-council Overpass queries, precisely polygon-clipped) gives 55,100 — the 60,276 figure was traced to an *unclipped bounding-box* query that leaks into neighboring Meath/Kildare/Wicklow, a 9.4% overcount from boundary imprecision rather than fabrication.

## 8. Location-accuracy verification

To check whether OSM's lane geometry is actually positioned correctly (not just tagged), every named designated-lane segment (303 of 334) was reverse-geocoded via Nominatim and compared against its own OSM `name` tag:

- **288 / 303 (95%) matched exactly.**
- The 15 "mismatches" are every one a bridge, quay, or short interconnecting street where the geocoder returned an *immediately adjacent* street name (e.g. Rosie Hackett Bridge → Burgh Quay, next to it) — the signature of a geocoding-precision artifact at junctions, not misplaced data.

**Conclusion: the underlying coordinate data is accurate.**

## 9. Recommendations

1. Prioritize mapping Go-Ahead Ireland's bus route network in OSM — the single largest routing gap.
2. Fix the `"DB 104"` ref tag.
3. The single biggest infrastructure-completeness opportunity in OSM Dublin is bus lane tagging — 83% of a legacy government survey's documented network is untagged. Even accounting for lanes removed since 2007, this is a large, addressable gap.
4. Re-run the cycling comparison with the "broad" tag definition to separate genuine infrastructure gaps from tagging-scheme differences (shared pedestrian/cycle paths in particular).
5. When combining multiple government datasets that might describe the same real-world features, always use buffer-tolerant spatial matching — exact-geometry deduplication between independently-produced surveys will systematically overstate any "combined total."
