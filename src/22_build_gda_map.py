"""
Second map: Greater Dublin Area (regional scope) OSM cycling & walking,
kept separate from the main Dublin-City-focused comparison map because
including all of it there would double the file size past the delivery
limit. Same visual language (custom grouped control panel, satellite
option) as the main map for consistency.

Full click-popups are NOT used here (tooltip-only) -- at 21,517 (broad
cycling) and 55,100 (walking) features, per-feature Leaflet popup DOM/JS
overhead alone would run 50-80MB, the exact problem solved earlier in the
main map by switching large background layers to tooltips.
"""
import json

import folium
from shapely.geometry import shape

ML = "../data/map_layers"
DATA = "../data"

LAYER_REGISTRY = []


def register(layer_obj, label, group, color=None, count=None, kind="overlay", default=False):
    LAYER_REGISTRY.append({"var": layer_obj.get_name(), "label": label, "group": group,
                            "kind": kind, "color": color, "count": count, "default": default})


def add_tooltip_layer(m, path, label, group, style_function, show, tooltip_fields, color):
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    layer = folium.GeoJson(
        fc, style_function=style_function, show=show,
        tooltip=folium.GeoJsonTooltip(fields=tooltip_fields) if tooltip_fields else None,
    )
    layer.add_to(m)
    register(layer, label, group, color=color, count=len(fc["features"]), default=show)


m = folium.Map(location=[53.42, -6.25], zoom_start=11, tiles=None, prefer_canvas=True, zoom_control="bottomright")

street = folium.TileLayer("OpenStreetMap", control=False)
street.add_to(m)
register(street, "Street map", "base", kind="base", default=True)
satellite = folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Tiles &copy; Esri", control=False, show=False,
)
satellite.add_to(m)
register(satellite, "Satellite", "base", kind="base", default=False)

with open(f"{DATA}/boundary_greater_dublin_region.geojson", encoding="utf-8") as f:
    gda_boundary = json.load(f)
gda_layer = folium.GeoJson(
    gda_boundary, style_function=lambda x: {"color": "#000000", "weight": 2.5, "fill": False, "dashArray": "8,4"},
    show=True,
)
gda_layer.add_to(m)
register(gda_layer, "Greater Dublin Area boundary (4 councils, 921 km²)", "osm", color="#000000", default=True)

with open(f"{DATA}/boundary_dublin_city.geojson", encoding="utf-8") as f:
    dcc_boundary = json.load(f)
dcc_layer = folium.GeoJson(
    dcc_boundary, style_function=lambda x: {"color": "#555555", "weight": 1.5, "fill": False, "dashArray": "3,3"},
    show=True,
)
dcc_layer.add_to(m)
register(dcc_layer, "Dublin City boundary (for reference, 117.6 km²)", "osm", color="#555555", default=True)

add_tooltip_layer(
    m, f"{ML}/gda_cycling_strict.geojson",
    "OSM cycling - strict (698.2 km, cycleway/lane/track only)", "osm",
    style_function=lambda x: {"color": "#1e8f3e", "weight": 2, "opacity": 0.85},
    show=True, tooltip_fields=["highway"], color="#1e8f3e",
)
add_tooltip_layer(
    m, f"{ML}/gda_cycling_broad.geojson",
    "OSM cycling - broad (2,374.3 km, incl. bicycle-permitted paths/footways)", "osm",
    style_function=lambda x: {"color": "#8bc34a", "weight": 1.2, "opacity": 0.5},
    show=False, tooltip_fields=["highway"], color="#8bc34a",
)
add_tooltip_layer(
    m, f"{ML}/gda_walking.geojson",
    "OSM walking (4,245.0 km, 55,100 features)", "osm",
    style_function=lambda x: {"color": "#7a7a7a", "weight": 0.8, "opacity": 0.45},
    show=False, tooltip_fields=["highway", "surface"], color="#7a7a7a",
)

panel_css = """
<style>
#layer-panel { position: fixed; top: 12px; right: 12px; z-index: 9999; width: 320px;
  max-height: 92vh; overflow-y: auto; background: #ffffff; border-radius: 10px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.18); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 13px; color: #1d1d1f; }
#layer-panel .lp-header { display:flex; align-items:center; justify-content:space-between;
  padding: 12px 14px; border-bottom: 1px solid #eee; font-weight: 600; font-size: 14px; }
#layer-panel .lp-header button { background:none; border:none; cursor:pointer; font-size:16px; color:#888; padding:2px 6px; }
#layer-panel .lp-body.collapsed { display:none; }
#layer-panel .lp-section-title { padding: 10px 14px 4px; font-size: 11px; font-weight: 700;
  letter-spacing: 0.06em; text-transform: uppercase; color: #6e6e73; }
#layer-panel .lp-section-sub { padding: 0 14px 6px; font-size: 11px; color: #a0a0a5; }
#layer-panel .lp-row { display:flex; align-items:center; padding: 6px 14px; cursor:pointer; }
#layer-panel .lp-row:hover { background:#f5f5f7; }
#layer-panel .lp-swatch { width:11px; height:11px; border-radius:50%; margin-right:9px; flex-shrink:0; border:1px solid rgba(0,0,0,0.15); }
#layer-panel .lp-label { flex:1; line-height:1.3; }
#layer-panel .lp-count { font-size: 10.5px; color:#a0a0a5; background:#f0f0f2; border-radius:8px; padding:1px 7px; margin-left:6px; }
#layer-panel .lp-divider { height:1px; background:#eee; margin: 6px 0; }
#layer-panel input[type=checkbox], #layer-panel input[type=radio] { margin-right:9px; accent-color:#1f5fd6; cursor:pointer; }
#layer-panel .lp-group-osm .lp-section-title { color:#1f5fd6; }
</style>
"""

osm_items = [it for it in LAYER_REGISTRY if it["group"] == "osm"]
base_items = [it for it in LAYER_REGISTRY if it["kind"] == "base"]


def rows_for(items):
    out = []
    for item in items:
        swatch = f"<span class='lp-swatch' style='background:{item['color'] or '#999'}'></span>"
        count_html = f"<span class='lp-count'>{item['count']:,}</span>" if item["count"] else ""
        checked = "checked" if item["default"] else ""
        out.append(
            f"<div class='lp-row' onclick=\"lpToggle(this)\">"
            f"<input type='checkbox' {checked} data-var='{item['var']}' onclick='event.stopPropagation()' onchange=\"lpApply(this)\">"
            f"{swatch}<span class='lp-label'>{item['label']}</span>{count_html}</div>"
        )
    return "".join(out)


base_rows = []
for item in base_items:
    checked = "checked" if item["default"] else ""
    base_rows.append(
        f"<div class='lp-row' onclick=\"lpToggleRadio(this)\">"
        f"<input type='radio' name='lp-base' {checked} data-var='{item['var']}' onclick='event.stopPropagation()' onchange=\"lpApplyRadio(this)\">"
        f"<span class='lp-label'>{item['label']}</span></div>"
    )

map_var = m.get_name()
panel_html = f"""
{panel_css}
<div id="layer-panel">
  <div class="lp-header">
    <span>Greater Dublin Area: OSM Cycling &amp; Walking</span>
    <button onclick="document.getElementById('lp-body').classList.toggle('collapsed')">&#8722;</button>
  </div>
  <div id="lp-body" class="lp-body">
    <div class="lp-section-title">Base Map</div>
    {''.join(base_rows)}
    <div class="lp-divider"></div>
    <div class="lp-group-osm">
      <div class="lp-section-title">OpenStreetMap Data (regional scope)</div>
      <div class="lp-section-sub">All 4 Dublin local authorities, ~921 km² -- companion to the Dublin-City-only main comparison map</div>
      {rows_for(osm_items)}
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

out_path = "../output/dublin_gda_cycling_walking_map.html"
m.save(out_path)
print("Saved to", out_path)
print(f"Registered {len(LAYER_REGISTRY)} layers ({len(osm_items)} OSM, {len(base_items)} base)")
