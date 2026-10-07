# RECIPE — Recreate the WGS 84 Globe from scratch

A reproducible, ordered guide to rebuild the scene described in
[README.md](README.md). Paths are relative to the repo root; scripts find the
root from their own location (override with `GLOBE_PROJECT=/path/to/repo`).

> **In a hurry?** Steps 1–3 then `scripts/build_all.py` does steps 4–9 in one
> shot — see the README *Quick start*. The step-by-step version below is for
> building interactively and understanding each layer.

Two execution contexts appear throughout:
- **[shell]** — a terminal in the repo root (uses the `.venv` via `uv run`).
- **[Blender]** — Python run *inside Blender*: via the blender-mcp
  `execute_blender_code` tool, or Blender's Text Editor / Python console. Each
  Blender step just execs a script file (use the absolute path to your clone):
  ```python
  path = "/path/to/blender-globe/scripts/<script>.py"
  exec(compile(open(path).read(), path, "exec"), {"__name__": "__main__", "__file__": path})
  ```
  (Passing `__file__` matters: that's how each script finds the repo root.)

---

## 0. Prerequisites

- **Blender 5.1** (tested; bundled Python 3.13).
- **[uv](https://docs.astral.sh/uv/)** (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- *(Optional, for AI-driven building)* **blender-mcp** registered with your MCP
  client and its add-on connected in Blender:
  ```bash
  claude mcp add blender -e UV_PYTHON_PREFERENCE=only-managed -- uvx --python 3.11 blender-mcp
  ```
  In Blender: install the blender-mcp `addon.py`, enable *Interface: Blender MCP*,
  then N-panel → **BlenderMCP** → **Connect to Claude** (listens on `127.0.0.1:9876`).

---

## 1. Project environment  [shell]

```bash
git clone https://github.com/kartographia/blender-globe.git
cd blender-globe
uv sync          # creates .venv on Python 3.13 with pyshp, pyproj, shapely, triangle
```

`vendor/shapefile.py` is a vendored copy of pyshp's single pure-Python module,
so **Blender's** Python can read shapefiles without the venv's compiled
libraries (and without shadowing Blender's own numpy). To refresh it after
upgrading pyshp:
```bash
cp "$(uv run python -c 'import shapefile,sys; sys.stdout.write(shapefile.__file__)')" vendor/shapefile.py
```

---

## 2. Get the data  [shell]

```bash
./scripts/fetch_data.sh
```
Downloads and unzips these **Natural Earth 1:10m** physical layers into `Data/`
(skips any already present):

| Layer | Used for |
|-------|----------|
| `ne_10m_ocean` | coastline reference curves |
| `ne_10m_land` | land fill |
| `ne_10m_lakes` | lakes |
| `ne_10m_rivers_lake_centerlines` | rivers |
| `ne_10m_glaciated_areas` | glaciers (Greenland/Arctic/alpine) |
| `ne_10m_antarctic_ice_shelves_polys` | Antarctic ice shelves |

All layers are already **EPSG:4326** (lon/lat degrees), so no reprojection is
needed. (Use `pyproj` only if you bring in a projected shapefile.)

---

## 3. Preprocess the polygon layers  [shell]

Triangulate each polygon layer to an `.npz` mesh (lon/lat verts + faces):

```bash
uv run python scripts/build_land_mesh.py          # land → Data/land_mesh.npz
for l in ne_10m_lakes ne_10m_glaciated_areas ne_10m_antarctic_ice_shelves_polys; do
  uv run python scripts/build_land_mesh.py Data/$l/$l.shp Data/$l.npz 1.0
done
```
The 3rd arg is the interior grid spacing in degrees (smaller = hugs the
ellipsoid tighter, more triangles).

The triangulator is **hang-proof**: `buffer(0)` repair → plain Delaunay over
boundary vertices + a 1° interior grid → keep only triangles whose centroid is
inside the polygon (drops exterior + holes). Constrained triangulation is
avoided because some Natural Earth rings self-intersect and make `triangle`'s
`p` mode hang.

---

## 4. Build the ellipsoid + reference bands  [Blender]

Run `scripts/create_globe.py`:
- removes the default Cube, adds a 64×32 UV sphere named **Globe**,
- bakes WGS 84 axes into the mesh: a = 6,378,137 m, b = a(1−1/298.257223563)
  = 6,356,752 m, at 1 unit = 1000 km → a ≈ 6.378, b ≈ 6.357 units,
- adds **Equator** (gold torus, XY plane) and **PrimeMeridian** (cyan torus,
  XZ plane, flattened to b/a). These are for orientation and are hidden from
  the final render.

---

## 5. Drape the coastlines  [Blender]

Run `scripts/shapefile_to_globe.py`. Reads `ne_10m_ocean` and builds the
**Oceans** coastline curves (closed rings, beveled tubes) via the exact
geodetic → ECEF mapping.

---

## 6. Fill land + ocean, with climate colors  [Blender]

Run `scripts/fill_land_ocean.py`. It:
- gives **Globe** an ocean-blue material,
- loads `Data/land_mesh.npz`, maps lon/lat → ECEF (vectorized numpy), and builds
  the **Land** mesh via `foreach_set`,
- assigns a **per-vertex latitude/climate color ramp** (ice caps white, tundra,
  temperate/tropical greens, subtropical arid tan) through a `FLOAT_COLOR`
  attribute + a Vertex-Color → Base-Color material.

---

## 7. Add lakes, glaciers, ice shelves  [Blender]

Run `scripts/add_polygon_layers.py`. Builds three flat-colored fill meshes from
their `.npz` files at stacked offsets:
- **Lakes**: blue, offset 0.012
- **Glaciers**: white, offset 0.016 (paints Greenland/Arctic white)
- **IceShelves**: white, offset 0.016 (extends past the Antarctic coast)

---

## 8. Add rivers  [Blender]

Run `scripts/add_rivers.py`. Drapes `ne_10m_rivers_lake_centerlines` as
**open** polylines (`closed=False`, so river ends aren't joined), thin blue
curves at offset 0.013.

---

## 8b. Photoreal surface, clouds, atmosphere  [shell + Blender]  *(optional)*

Shell, once: `bash scripts/fetch_rasters.sh` (Blue Marble for the render month(s) — pass months like
`07 10` — plus Black Marble, clouds, GEBCO elevation; ~86 MB into `Data/rasters_src/`), then
`uv run python scripts/prepare_rasters.py` (→ 8192×4096 `Data/rasters/*`, ~22 MB).

Blender: run `scripts/add_photoreal.py`. It builds a `GeodeticUV` node group (object position →
geodetic lon/lat → equirectangular UV), gives land meshes a rough relief-bumped Blue Marble material and
Globe/Lakes a glossy water one, both emitting Black Marble city lights where `dot(normal, SunDir) < 0`, adds a
`Clouds` shell (offset 0.025) and an emissive `Atmosphere` shell (offset 0.12, no shadows), and hides Rivers.
Tuning constants are at the top of the script. `render_globe.py` detects the photo scene by the `Atmosphere`
object and adds the fill light, stars, bloom and AgX.

---

## 9. Lighting + render  [Blender]

Run `scripts/render_globe.py`. Pick a preset in `VIEWS` at the top (UTC instant `(Y, MO, D, HH, MM)`
plus camera; `-- --view NAME` when run headless). It:
- computes the **subsolar point** (sun-overhead lat/lon) for that UTC,
- aims a **SUN** lamp there (parallel rays, 0.526° angular size), so exactly
  the correct hemisphere is lit,
- adds a framed **GlobeCam** and a dark space world,
- hides reference geometry (Equator/PrimeMeridian/Oceans) from the render,
- renders EEVEE → `renders/globe_render.png` (vector) or `renders/globe_photo_<view>.png` (photo).

> The script picks `BLENDER_EEVEE_NEXT` (Blender 4.2–4.x) or `BLENDER_EEVEE`
> (5.x) automatically. Set `scene.render.engine = 'CYCLES'` for higher-quality
> global illumination.

Save the scene with **File → Save As** (or pass `--save` to `build_all.py`).

---

## Adding a new layer later

1. **Polygon layer** → `build_land_mesh.py <shp> <out.npz> [grid_deg]`, then a
   `build_layer(...)` call (see `add_polygon_layers.py`) with a color + offset.
2. **Line layer** (borders, roads) → `drape_shapefile(shp, name=..., closed=False)`
   (see `add_rivers.py`).
3. Add any new Natural Earth layer to `LAYERS` in `scripts/fetch_data.sh`.
4. Reproject first with `pyproj` only if the source isn't EPSG:4326.
