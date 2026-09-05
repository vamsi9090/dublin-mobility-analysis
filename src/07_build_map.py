"""
Build the interactive Dublin OSM-vs-Government comparison map.

v3: replaces Folium's default flat Leaflet layer-control checkbox list with
a custom-built control panel that groups layers by data provenance (Base Map
/ OpenStreetMap Data / Government Data), since that separation is the whole
point of this comparison and a flat undifferentiated list obscured it.
Multi-category layers (lanes, cycling) get an inline color-key legend rather
than being split into a dozen separate toggles.
"""
import json

import folium
from shapely.geometry import shape

DATA = "../data"
ML = "../data/map_layers"

LAYER_REGISTRY = []  # [{var, label, group, kind, color, legend, count}]


def register(layer_obj, label, group, color=None, legend=None, count=None, kind="overlay", default=False):
    LAYER_REGISTRY.append({
        "var": layer_obj.get_name(), "label": label, "group": group, "kind": kind,
        "color": color, "legend": legend or [], "count": count, "default": default,
    })


def street_view_url(lat, lon):
    return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"


def osm_url(osm_type, osm_id):
    return None if osm_id in (None, "") else f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def representative_latlon(geom_dict):
    geom = shape(geom_dict)
    gt = geom.geom_type
    if gt == "Point":
        return geom.y, geom.x
    if gt == "LineString":
        p = geom.interpolate(0.5, normalized=True)
        return p.y, p.x
    if gt == "MultiLineString":
        longest = max(geom.geoms, key=lambda g: g.length)
        p = longest.interpolate(0.5, normalized=True)
        return p.y, p.x
    return geom.centroid.y, geom.centroid.x


def popup_html(properties, lat, lon, title=None, osm_type=None, osm_id_field="osm_id"):
    rows = [f"<tr><td style='padding:2px 8px 2px 0;color:#666;white-space:nowrap;'>{k}</td>"
            f"<td style='padding:2px 0;'>{v}</td></tr>"
            for k, v in properties.items() if k not in ("color", "_style_key") and v not in (None, "")]
    table = f"<table style='font-size:11px;'>{''.join(rows)}</table>" if rows else ""
    title_html = f"<b style='font-size:13px;'>{title}</b><br>" if title else ""
    links = [f"<a href='{street_view_url(lat, lon)}' target='_blank' rel='noopener'>Google Street View</a>"]
    if osm_type and properties.get(osm_id_field):
        link = osm_url(osm_type, properties.get(osm_id_field))
        if link:
            links.append(f"<a href='{link}' target='_blank' rel='noopener'>Open in OSM</a>")
    return (f"<div style='font-family:sans-serif; max-width:300px;'>{title_html}{table}"
            f"<div style='margin-top:6px;'>{' &nbsp;|&nbsp; '.join(links)}</div></div>")


def add_geojson_layer(m, geojson_path, label, group, style_function, show, osm_type=None,
                       title_field=None, keep_fields=None, full_popup=True, color=None, legend=None):
    with open(geojson_path, encoding="utf-8") as f:
        fc = json.load(f)
    if keep_fields is not None:
        for feat in fc["features"]:
            feat["properties"] = {k: v for k, v in feat["properties"].items() if k in keep_fields}

    if full_popup:
        for feat in fc["features"]:
            lat, lon = representative_latlon(feat["geometry"])
            title = feat["properties"].get(title_field) if title_field else None
            feat["properties"]["_popup"] = popup_html(feat["properties"], lat, lon, title=title, osm_type=osm_type)
        layer = folium.GeoJson(
            fc, style_function=style_function, show=show,
            popup=folium.GeoJsonPopup(fields=["_popup"], labels=False, parse_html=True, max_width=320),
        )
    else:
        tooltip_fields = [f for f in (keep_fields or fc["features"][0]["properties"].keys()) if f != "osm_id"][:4]
        layer = folium.GeoJson(
            fc, style_function=style_function, show=show,
            tooltip=folium.GeoJsonTooltip(fields=tooltip_fields) if tooltip_fields else None,
        )
    layer.add_to(m)
    register(layer, label, group, color=color, legend=legend, count=len(fc["features"]), default=show)
    return fc


m = folium.Map(location=[53.3498, -6.2603], zoom_start=13, tiles=None, prefer_canvas=True, zoom_control="bottomright")

street = folium.TileLayer("OpenStreetMap", control=False)
street.add_to(m)
register(street, "Street map", "base", kind="base", default=True)
satellite = folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Tiles &copy; Esri", control=False, show=False,
)
satellite.add_to(m)
register(satellite, "Satellite", "base", kind="base", default=False)

# ============================== OSM DATA ==============================
with open(f"{DATA}/boundary_dublin_city.geojson", encoding="utf-8") as f:
    boundary = json.load(f)
boundary_layer = folium.GeoJson(
    boundary, style_function=lambda x: {"color": "#222222", "weight": 2, "fill": False, "dashArray": "6,4"},
    show=True,
)
boundary_layer.add_to(m)
register(boundary_layer, "Dublin City boundary", "osm", color="#222222", default=True)

LANE_COLORS = {
    "bus": "#1f5fd6", "taxi": "#ffb300", "bus+taxi": "#7b1fa2",
    "bus+taxi+bike": "#00897b", "bike+bus": "#2e9e5b", "bike+bus+taxi": "#00897b",
}
add_geojson_layer(
    m, f"{DATA}/osm_lanes/designated_lanes_v2.geojson", "Designated bus/taxi lanes (334 segments, 24.3 km)", "osm",
    style_function=lambda x: {"color": LANE_COLORS.get(x["properties"]["category"], "#999"), "weight": 5, "opacity": 0.9},
    show=True, osm_type="way", title_field="name", color="#7b1fa2",
    legend=[("Bus only", "#1f5fd6"), ("Bus + Taxi (PSV)", "#7b1fa2"), ("Bus + Taxi + Bike", "#00897b"),
            ("Bike + Bus", "#2e9e5b"), ("Taxi only", "#ffb300")],
)

CYCLE_TYPE_COLORS = {
    "on_road_lane": "#2e9e5b", "on_road_track": "#0d7a3f", "on_road_shared_lane": "#8bc34a",
    "dedicated_track": "#1565c0", "shared_unsegregated": "#f9a825", "shared_segregated": "#fb8c00",
    "shared_sidewalk": "#ef6c00", "crossing": "#bdbdbd", "other": "#999999",
}
cyc = add_geojson_layer(
    m, f"{DATA}/osm_cycling_classified.geojson", "Cycling infrastructure (125.5 km, by type)", "osm",
    style_function=lambda x: {"color": CYCLE_TYPE_COLORS.get(x["properties"]["cycle_type"], "#999"), "weight": 2.5, "opacity": 0.85},
    show=False, osm_type="way", title_field="cycle_type_label",
    keep_fields={"osm_id", "name", "highway", "cycleway", "surface", "foot", "segregated", "length_m", "cycle_type", "cycle_type_label"},
    color="#1565c0",
    legend=[("Dedicated track (bikes only)", "#1565c0"), ("On-road painted lane", "#2e9e5b"),
            ("Shared path w/ pedestrians", "#f9a825"), ("Segregated shared corridor", "#fb8c00"),
            ("On-road separated track", "#0d7a3f"), ("Sidewalk cycling", "#ef6c00"),
            ("Shared lane / sharrow", "#8bc34a"), ("Crossing", "#bdbdbd")],
)

with open(f"{ML}/osm__bus_stops.geojson", encoding="utf-8") as f:
    osm_stops = json.load(f)
with open(f"{DATA}/osm_stops_unmatched.geojson", encoding="utf-8") as f:
    osm_unmatched = json.load(f)
osm_unmatched_ids = {feat["properties"]["osm_id"] for feat in osm_unmatched["features"]}
matched_fg = folium.FeatureGroup(show=False)
gap_osm_fg = folium.FeatureGroup(show=True)
for feat in osm_stops["features"]:
    lon, lat = feat["geometry"]["coordinates"]
    props = feat["properties"]
    html = popup_html(props, lat, lon, title=props.get("name", "Bus stop"), osm_type="node")
    is_gap = props["osm_id"] in osm_unmatched_ids
    folium.CircleMarker(
        [lat, lon], radius=3.5 if is_gap else 2, color="#b3001b" if is_gap else "#1f5fd6",
        fill=True, fill_opacity=0.85, weight=1, popup=folium.Popup(html, max_width=320),
    ).add_to(gap_osm_fg if is_gap else matched_fg)
matched_fg.add_to(m); gap_osm_fg.add_to(m)
register(matched_fg, "Bus stops - matched with Gov (≤30m)", "osm", color="#1f5fd6", count=len(osm_stops["features"]) - len(osm_unmatched["features"]), default=True)
register(gap_osm_fg, "Bus stops - OSM only (no Gov match)", "osm", color="#b3001b", count=len(osm_unmatched["features"]), default=True)

with open(f"{ML}/osm__taxi_ranks.geojson", encoding="utf-8") as f:
    osm_taxi = json.load(f)
taxi_fg = folium.FeatureGroup(show=True)
for feat in osm_taxi["features"]:
    if feat["geometry"]["type"] != "Point":
        continue
    lon, lat = feat["geometry"]["coordinates"]
    props = feat["properties"]
    html = popup_html(props, lat, lon, title=props.get("name", props.get("addr:street", "Taxi rank")), osm_type="node")
    folium.CircleMarker(
        [lat, lon], radius=5, color="#c9a300", fill=True, fill_color="#ffd400", fill_opacity=0.95, weight=1.5,
        popup=folium.Popup(html, max_width=320),
    ).add_to(taxi_fg)
taxi_fg.add_to(m)
register(taxi_fg, "Taxi ranks", "osm", color="#ffd400", count=len(osm_taxi["features"]), default=True)

add_geojson_layer(
    m, f"{ML}/osm__walking.geojson", "Walking paths (1,033.5 km)", "osm",
    style_function=lambda x: {"color": "#7a7a7a", "weight": 1, "opacity": 0.5}, show=False,
    keep_fields={"highway", "surface"}, full_popup=False, color="#7a7a7a",
)

# =========================== GOVERNMENT DATA ===========================
add_geojson_layer(
    m, f"{DATA}/lane_data_gap.geojson",
    "OSM data gap - Gov 2007 lane with no OSM tag nearby (74.1km, 83% of 2007 survey)", "gov",
    style_function=lambda x: {"color": "#ff5252", "weight": 3, "opacity": 0.6, "dashArray": "1,5"},
    show=True, keep_fields={"length_m"}, color="#ff5252",
)
add_geojson_layer(
    m, f"{DATA}/cycling_data_gap.geojson",
    "OSM data gap - NTA cycle lane with no OSM tag nearby (129.5km, 50% of NTA network)", "gov",
    style_function=lambda x: {"color": "#ff8a65", "weight": 2.5, "opacity": 0.55, "dashArray": "1,5"},
    show=False, keep_fields={"length_m"}, color="#ff8a65",
)

add_geojson_layer(
    m, f"{DATA}/gov_bikelife_2021_buslanes.geojson",
    "Bus lanes - Gov BikeLife 2021 survey (1,184 seg, 133.6km GDA)", "gov",
    style_function=lambda x: {"color": "#ad1457", "weight": 3.5, "opacity": 0.7},
    show=False, color="#ad1457",
)

CYCLETRACK_2007_COLORS = {
    "On Street": "#6a1b9a", "Adjacent to carriageway": "#8e24aa", "Off-road track/cycleway": "#4a148c",
    "Bus lane only": "#c62828", "Advanced Cycle Stopping Area": "#ab47bc",
}
add_geojson_layer(
    m, f"{ML}/gov_2007_cycletracks_simplified.geojson",
    "Cycling - Gov 2007 cycletrack survey (691.8km GDA, by category)", "gov",
    style_function=lambda x: {"color": CYCLETRACK_2007_COLORS.get(x["properties"].get("Category"), "#8e24aa"), "weight": 2, "opacity": 0.6},
    show=False, full_popup=False,
    keep_fields={"Category", "Length (m)"}, color="#8e24aa",
    legend=[("On Street", "#6a1b9a"), ("Adjacent to carriageway", "#8e24aa"), ("Off-road track/cycleway", "#4a148c"),
            ("Bus lane only", "#c62828"), ("Advanced Cycle Stopping Area", "#ab47bc")],
)


def humanize(src_path, dst_path, transform_fn):
    with open(src_path, encoding="utf-8") as f:
        fc = json.load(f)
    for feat in fc["features"]:
        feat["properties"] = transform_fn(feat["properties"])
    with open(dst_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, separators=(",", ":"))
    return dst_path


buslane_display = humanize(
    f"{DATA}/gov_2007_buslanes.geojson", f"{ML}/gov_2007_buslanes_display.geojson",
    lambda p: {"Category": p.get("category"), "Length (km)": round(p.get("length_km_field") or 0, 3),
               "Source": "2007 GDA Bus Lane Survey (Dublin Transportation Office / NTA)",
               "Note": "Only 2 attributes exist in the original 2007 source data - this is not a trimmed-down view"},
)
add_geojson_layer(
    m, buslane_display,
    "Bus lanes - Gov 2007 survey (555 seg, 186.6km GDA / 89.1km in Dublin City)", "gov",
    style_function=lambda x: {"color": "#c62828", "weight": 4, "opacity": 0.75},
    show=False, color="#c62828",
)

with open(f"{DATA}/gov_stops_unmatched.geojson", encoding="utf-8") as f:
    gov_unmatched = json.load(f)
gap_gov_fg = folium.FeatureGroup(show=True)
for feat in gov_unmatched["features"]:
    lon, lat = feat["geometry"]["coordinates"]
    props = feat["properties"]
    html = popup_html(props, lat, lon, title=props.get("stop_name", "GTFS stop"))
    folium.CircleMarker(
        [lat, lon], radius=3.5, color="#7b1fa2", fill=True, fill_opacity=0.9, weight=1,
        popup=folium.Popup(html, max_width=320),
    ).add_to(gap_gov_fg)
gap_gov_fg.add_to(m)
register(gap_gov_fg, "Bus stops - Gov only (missing from OSM)", "gov", color="#7b1fa2", count=len(gov_unmatched["features"]), default=True)

nta_cycle_display = humanize(
    f"{ML}/gov_cycle_dublin_city.geojson", f"{ML}/nta_cycle_display.geojson",
    lambda p: {"Infrastructure type": p.get("BIKE"), "Direction": p.get("DIR"),
               "Length (m)": round(float(p.get("Shape_Leng") or 0), 1),
               "Source": "NTA Active Travel Cycle Network (Feb 2025)", "_style_key": p.get("BIKE")},
)
add_geojson_layer(
    m, nta_cycle_display, "Cycling - NTA regional network (259.9 km, clipped)", "gov",
    style_function=lambda x: {"color": "#7fd97f", "weight": 2, "opacity": 0.75, "dashArray": "4,3"},
    show=False, color="#7fd97f",
)

PROTECTED_CYCLE_COLORS = {
    "SegregatedCycleLane": "#00695c", "TrafficFree": "#004d40", "SignedRoute": "#26a69a",
    "SharedUse": "#80cbc4", "SurfaceChange": "#b2dfdb", "CycleLane": "#009688",
}
TWOWAY_LABELS = {"0": "One-way", "1": "Two-way", "0.0": "One-way", "1.0": "Two-way"}
BOLLARD_LABELS = {"0": "Not bollard-protected", "1": "Bollard-protected", "0.0": "Not bollard-protected", "1.0": "Bollard-protected"}
dcc_cycle_display = humanize(
    "../data/gov_extra/protected_cycle_infra_2023.geojson", f"{ML}/dcc_cycle_display.geojson",
    lambda p: {"Infrastructure type": p.get("cdo"),
               "Direction": TWOWAY_LABELS.get(str(p.get("twoway")), p.get("twoway")),
               "Protection": BOLLARD_LABELS.get(str(p.get("bollardpro")), p.get("bollardpro")),
               "Length (m)": round(float(p.get("Shape_Leng") or 0), 1),
               "Source": "DCC/Smart Dublin Protected Cycle Infrastructure (2013-2023)", "_style_key": p.get("cdo")},
)
add_geojson_layer(
    m, dcc_cycle_display, "Cycling - DCC/Smart Dublin protected & segregated (2023)", "gov",
    style_function=lambda x: {"color": PROTECTED_CYCLE_COLORS.get(x["properties"].get("_style_key"), "#009688"), "weight": 3, "opacity": 0.8},
    show=False, color="#00695c",
    legend=[("Segregated cycle lane", "#00695c"), ("Traffic-free", "#004d40"), ("Signed route", "#26a69a"),
            ("Shared use", "#80cbc4"), ("Surface change", "#b2dfdb")],
)

# =========================== REGIONAL DATA (GDA) ===========================
# Greater Dublin Area (all 4 councils, 921 km^2) OSM cycling + walking --
# a wider-scope companion to the Dublin-City-only layers above, merged into
# this single map/link (rather than a second file) with its own panel
# section so scope is never ambiguous. Off by default and tooltip-only
# (not full click-popups) given the feature counts involved (21.5k / 55k).
with open(f"{DATA}/boundary_greater_dublin_region.geojson", encoding="utf-8") as f:
    gda_boundary = json.load(f)
gda_boundary_layer = folium.GeoJson(
    gda_boundary, style_function=lambda x: {"color": "#000000", "weight": 2.5, "fill": False, "dashArray": "8,4"},
    show=False,
)
gda_boundary_layer.add_to(m)
register(gda_boundary_layer, "Greater Dublin Area boundary (4 councils, 921 km²)", "regional", color="#000000", default=False)

add_geojson_layer(
    m, f"{ML}/gda_cycling_strict.geojson",
    "OSM cycling - strict, GDA-wide (698.2 km, cycleway/lane/track only)", "regional",
    style_function=lambda x: {"color": "#1e8f3e", "weight": 2, "opacity": 0.85},
    show=False, full_popup=False, keep_fields={"highway"}, color="#1e8f3e",
)
add_geojson_layer(
    m, f"{ML}/gda_cycling_broad.geojson",
    "OSM cycling - broad, GDA-wide (2,374.3 km, incl. bicycle-permitted paths)", "regional",
    style_function=lambda x: {"color": "#8bc34a", "weight": 1.2, "opacity": 0.5},
    show=False, full_popup=False, keep_fields={"highway"}, color="#8bc34a",
)
add_geojson_layer(
    m, f"{ML}/gda_walking.geojson",
    "OSM walking, GDA-wide (4,245.0 km, 55,100 features)", "regional",
    style_function=lambda x: {"color": "#7a7a7a", "weight": 0.8, "opacity": 0.45},
    show=False, full_popup=False, keep_fields={"highway", "surface"}, color="#7a7a7a",
)


# ============================== CONTROL PANEL ==============================
panel_css = """
<style>
#layer-panel { position: fixed; top: 12px; right: 12px; z-index: 9999; width: 300px;
  max-height: 92vh; overflow-y: auto; background: #ffffff; border-radius: 10px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.18); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 13px; color: #1d1d1f; }
#layer-panel .lp-header { display:flex; align-items:center; justify-content:space-between;
  padding: 12px 14px; border-bottom: 1px solid #eee; font-weight: 600; font-size: 14px; }
#layer-panel .lp-header button { background:none; border:none; cursor:pointer; font-size:16px; color:#888; padding:2px 6px; }
#layer-panel .lp-body.collapsed, #layer-panel .collapsed { display:none; }
#layer-panel .lp-section-title { padding: 10px 14px 4px; font-size: 11px; font-weight: 700;
  letter-spacing: 0.06em; text-transform: uppercase; color: #6e6e73; }
#layer-panel .lp-section-sub { padding: 0 14px 6px; font-size: 11px; color: #a0a0a5; }
#layer-panel .lp-row { display:flex; align-items:center; padding: 6px 14px; cursor:pointer; }
#layer-panel .lp-row:hover { background:#f5f5f7; }
#layer-panel .lp-swatch { width:11px; height:11px; border-radius:3px; margin-right:9px; flex-shrink:0; border:1px solid rgba(0,0,0,0.15); }
#layer-panel .lp-swatch.dot { border-radius:50%; }
#layer-panel .lp-label { flex:1; line-height:1.3; }
#layer-panel .lp-count { font-size: 10.5px; color:#a0a0a5; background:#f0f0f2; border-radius:8px; padding:1px 7px; margin-left:6px; }
#layer-panel .lp-divider { height:1px; background:#eee; margin: 6px 0; }
#layer-panel .lp-legend { padding: 2px 14px 10px 33px; display:flex; flex-wrap:wrap; gap: 5px 10px; }
#layer-panel .lp-legend-item { font-size: 10.5px; color:#6e6e73; display:flex; align-items:center; }
#layer-panel .lp-legend-item .lp-swatch { width:8px; height:8px; margin-right:4px; }
#layer-panel input[type=checkbox], #layer-panel input[type=radio] { margin-right:9px; accent-color:#1f5fd6; cursor:pointer; }
#layer-panel .lp-group-osm .lp-section-title { color:#1f5fd6; }
#layer-panel .lp-group-gov .lp-section-title { color:#b35a00; }
#layer-panel .lp-group-regional .lp-section-title { color:#6a1b9a; }
#layer-panel .lp-collapsible-toggle { cursor:pointer; user-select:none; }
#layer-panel .lp-collapsible-toggle:hover { text-decoration: underline; }
</style>
"""

base_rows = []
for item in LAYER_REGISTRY:
    if item["kind"] != "base":
        continue
    checked = "checked" if item["default"] else ""
    base_rows.append(
        f"<div class='lp-row' onclick=\"lpToggleRadio(this)\">"
        f"<input type='radio' name='lp-base' {checked} data-var='{item['var']}' onclick='event.stopPropagation()' onchange=\"lpApplyRadio(this)\">"
        f"<span class='lp-label'>{item['label']}</span></div>"
    )

osm_items = [it for it in LAYER_REGISTRY if it["group"] == "osm"]
gov_items = [it for it in LAYER_REGISTRY if it["group"] == "gov"]
regional_items = [it for it in LAYER_REGISTRY if it["group"] == "regional"]


def rows_for(items):
    out = []
    for item in items:
        legend_html = ""
        if item["legend"]:
            chips = "".join(
                f"<div class='lp-legend-item'><span class='lp-swatch dot' style='background:{c}'></span>{lbl}</div>"
                for lbl, c in item["legend"]
            )
            legend_html = f"<div class='lp-legend'>{chips}</div>"
        swatch = f"<span class='lp-swatch dot' style='background:{item['color'] or '#999'}'></span>"
        count_html = f"<span class='lp-count'>{item['count']:,}</span>" if item["count"] else ""
        checked = "checked" if item["default"] else ""
        out.append(
            f"<div class='lp-row' onclick=\"lpToggle(this)\">"
            f"<input type='checkbox' {checked} data-var='{item['var']}' onclick='event.stopPropagation()' onchange=\"lpApply(this)\">"
            f"{swatch}<span class='lp-label'>{item['label']}</span>{count_html}</div>{legend_html}"
        )
    return "".join(out)


map_var = m.get_name()

panel_html = f"""
{panel_css}
<div id="layer-panel">
  <div class="lp-header">
    <span>Dublin: OSM vs. Government</span>
    <button onclick="document.getElementById('lp-body').classList.toggle('collapsed')">&#8722;</button>
  </div>
  <div id="lp-body" class="lp-body">
    <div class="lp-section-title">Base Map</div>
    {''.join(base_rows)}
    <div class="lp-divider"></div>
    <div class="lp-group-osm">
      <div class="lp-section-title">OpenStreetMap Data</div>
      <div class="lp-section-sub">Community-mapped, live Overpass API</div>
      {rows_for(osm_items)}
    </div>
    <div class="lp-divider"></div>
    <div class="lp-group-gov">
      <div class="lp-section-title">Government Data</div>
      <div class="lp-section-sub">NTA / Dublin City Council / Smart Dublin official open data</div>
      {rows_for(gov_items)}
    </div>
    <div class="lp-divider"></div>
    <div class="lp-group-regional">
      <div class="lp-section-title lp-collapsible-toggle" onclick="document.getElementById('lp-regional-body').classList.toggle('collapsed')">Regional Data (Greater Dublin Area) &#9662;</div>
      <div class="lp-section-sub">Optional wider scope (921 km², all 4 councils) -- OSM cycling &amp; walking beyond the Dublin City boundary above. Off by default.</div>
      <div id="lp-regional-body" class="collapsed">
        {rows_for(regional_items)}
      </div>
    </div>
  </div>
</div>
<script>
function lpToggle(row) {{ const cb = row.querySelector('input'); cb.checked = !cb.checked; lpApply(cb); }}
function lpToggleRadio(row) {{ const rb = row.querySelector('input'); rb.checked = true; lpApplyRadio(rb); }}
function lpApply(cb) {{
  const layer = window[cb.getAttribute('data-var')];
  if (!layer) return;
  if (cb.checked) {{ {map_var}.addLayer(layer); }} else {{ {map_var}.removeLayer(layer); }}
}}
function lpApplyRadio(rb) {{
  document.querySelectorAll("input[name='lp-base']").forEach(function(r) {{
    const l = window[r.getAttribute('data-var')];
    if (l) {map_var}.removeLayer(l);
  }});
  const layer = window[rb.getAttribute('data-var')];
  if (layer) {map_var}.addLayer(layer);
}}
</script>
"""

m.get_root().html.add_child(folium.Element(panel_html))

out_path = "../output/dublin_osm_vs_gov_map.html"
m.save(out_path)
print("Saved map to", out_path)
print(f"Registered {len(LAYER_REGISTRY)} toggleable layers ({len(osm_items)} OSM, {len(gov_items)} Gov, {len([i for i in LAYER_REGISTRY if i['kind']=='base'])} base)")
