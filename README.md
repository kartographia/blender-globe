# WGS 84 Globe — Blender + Natural Earth

A geographically accurate 3D Earth built in Blender and driven programmatically
through the [blender-mcp](https://github.com/ahujasid/blender-mcp) server. The
globe is a true **WGS 84 ellipsoid** (EPSG:4326 datum) with real vector data
from [Natural Earth](https://www.naturalearthdata.com/) draped onto its surface,
lit by a physically-placed sun. A **photo** style adds public-domain NASA rasters (Blue Marble day color,
Black Marble city lights, clouds, elevation relief) and an atmosphere; a **vector** style keeps the original
flat-colored Natural Earth look.

![Stylized night view: Europe and Africa city lights, lit Atlantic limb](renders/readme/globe_night_fill.jpg)

| `night`: physical lighting | `day`: physical lighting | `--style vector` |
|:---:|:---:|:---:|
| ![night](renders/readme/globe_night.jpg) | ![day](renders/readme/globe_day.jpg) | ![vector](renders/readme/globe_vector.jpg) |

*Top: `night_fill`, the same instant as `night` with art-directed fill lights, 2× relief, dimmer city lights
and a blue rim around the night limb.*

---

## Quick start

Requires **Blender 5.1** (tested) and **[uv](https://docs.astral.sh/uv/)**.

```bash
git clone https://github.com/kartographia/blender-globe.git
cd blender-globe
uv sync                              # Python 3.13 venv with the GIS toolkit
./scripts/fetch_data.sh              # download Natural Earth layers into Data/

# triangulate the polygon layers (→ Data/*.npz)
uv run python scripts/build_land_mesh.py
for l in ne_10m_lakes ne_10m_glaciated_areas ne_10m_antarctic_ice_shelves_polys; do
  uv run python scripts/build_land_mesh.py Data/$l/$l.shp Data/$l.npz 1.0
done

# NASA rasters for the photoreal style (Blue Marble, Black Marble, clouds, elevation -> Data/rasters/)
bash scripts/fetch_rasters.sh
uv run python scripts/prepare_rasters.py

# build the scene + render headlessly (macOS path shown; use your blender binary)
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  --python scripts/build_all.py -- --save
```

Output: `renders/globe_photo_night.png` and `Globe.blend`. Options after `--`:
`--view day|night|night_fill` picks a preset (see [Views](#views)); `--style vector` renders the original
flat-colored Natural Earth look (`renders/globe_render.png`, no rasters needed). A full build + EEVEE render
takes ~15 s on an RTX 5080. To build interactively
via [blender-mcp](https://github.com/ahujasid/blender-mcp) instead, step through
**[RECIPE.md](RECIPE.md)**.

---

## What's in the scene

| Object | Source layer | Representation |
|--------|--------------|----------------|
| **Globe** | — | WGS 84 ellipsoid (oblate), ocean-blue surface |
| **Land** | `ne_10m_land` | Triangulated fill, per-vertex latitude/climate colors |
| **Lakes** | `ne_10m_lakes` | Triangulated blue fill |
| **Rivers** | `ne_10m_rivers_lake_centerlines` | Blue beveled-curve lines |
| **Glaciers** | `ne_10m_glaciated_areas` | White fill (Greenland, Arctic, alpine) |
| **IceShelves** | `ne_10m_antarctic_ice_shelves_polys` | White fill around Antarctica |
| **Oceans** | `ne_10m_ocean` | Coastline reference curves *(hidden in render)* |
| **Equator / PrimeMeridian** | — | Reference bands *(hidden in render)* |
| **Sun** | computed | Directional light aimed at the subsolar point |
| **GlobeCam** | — | Framed render camera |
| **Clouds** *(photo)* | NASA Blue Marble cloud composite | Transparent shell, 25 km up, casts shadows |
| **Atmosphere** *(photo)* | — | Emissive limb-glow shell, 120 km up, sunlit side (+ optional night rim) |
| **FillLight** *(photo)* | — | Fill light near the camera so night-side relief reads (no specular) |
| **KickerLight1, 2…** *(night_fill)* | — | Soft warm point lights 8,000 km up over chosen regions |

In the **photo** style (default) the Globe/Land/Lakes/Glaciers/IceShelves meshes keep their geometry but
get NASA rasters: **Blue Marble NG** day color (render month), **Black Marble** city lights emitted only on the
night side, **GEBCO** elevation as relief bump on land, and glossy water (sun glint) on ocean + lakes. The
vector land mesh is the land/water mask. Textures are looked up with an exact geodetic lon/lat computed in the
shader, so they register with the WGS 84 vector layers. Rivers are hidden. Stars, bloom and AgX finish it.

---

## Views

Presets live in `VIEWS` at the top of `scripts/render_globe.py`; each has a UTC instant (which places the sun,
the terminator, the night-side city lights and the atmosphere glow) and a camera.

| View | UTC instant | Camera | Lighting |
|------|-------------|--------|----------|
| `day` | 2026-07-08 12:00 | sunlit side, rotated 52° about Z | physical: one sun + faint fill |
| `night` | 2026-10-03 18:30 | over 17° E, 24° N (North Africa) | physical: sun just past the western limb |
| `night_fill` | same as `night` | same as `night` | stylized (below) |

`night_fill` is art-directed after a cinematic reference, not physical (there's only one sun). It overrides:

- `fill`: a brighter neutral fill from the upper left, so night-side land reads as muted brown-grey;
- `kickers`: soft warm point lights 8 units (8,000 km) above the Caspian (51° E, 42° N) and the southern
  Indian Ocean (51° E, 30° S). A point light only reaches the cap inside its own horizon, so each one washes
  its region (Middle East / Iran; southern and eastern Africa) and leaves the rest alone;
- `relief: 80` (2× the default bump exaggeration), `lights: 3.6` (city lights at 80%),
  `cloud_night: 0.22` (night clouds faintly visible), `atmo_night: 0.22` (a soft blue rim around the night limb).

Add a view by copying an entry; the output is `renders/globe_photo_<view>.png`. If the month changes, fetch and
prepare that Blue Marble month (`bash scripts/fetch_rasters.sh MM`), else the nearest prepared month is used.
Global look constants (water tint, atmosphere color/thickness, star density, bloom…) are at the top of
`add_photoreal.py` and `render_globe.py`.

---

## Key design decisions

- **Ellipsoid, not a sphere.** A UV sphere is scaled to WGS 84 axes
  (a = 6,378,137 m, b = 6,356,752 m, 1/f = 298.257223563) and the scale is
  *applied* to the mesh, so the geometry is a genuine oblate ellipsoid.
- **Scale: 1 Blender unit = 1000 km.** So a ≈ 6.378 units, b ≈ 6.357 units.
  Earth centered at the world origin (0, 0, 0).
- **Orientation:** lon 0° (Greenwich) → **+X**, lon 90° E → **+Y**, North Pole → **+Z**.
- **Exact geodetic → ECEF mapping.** Vector data is placed with the full
  geodetic formula (prime-vertical radius `N`, eccentricity `e²`), landing every
  point precisely on the ellipsoid surface — not a naive spherical projection.
- **Layers are stacked by a tiny radial offset** so higher layers win visually:
  `ocean 0 < coastlines 0.006 < land 0.010 < lakes 0.012 < rivers 0.013 < glaciers/shelves 0.016
  < clouds 0.025 < atmosphere 0.12`.
- **Rasters register with the vectors.** Textures are sampled through a `GeodeticUV` shader node group that
  computes geodetic lon/lat from object-space position (latitude via `atan2(z, (1 − e²)·√(x² + y²))`), not mesh
  UVs, so the NASA rasters line up with the Natural Earth layers. The vector land mesh is the land/water mask.
- **Lighting follows the clock.** Photo materials read the sun direction from a `SunDir` node that
  `render_globe.py` re-syncs at render time, so city lights appear only on the night side and the atmosphere
  glows on the sunlit limb for whatever instant a view uses.
- **Physically-placed sun.** The sun is aimed at the real **subsolar point**
  (sun-overhead lat/lon) for a chosen UTC instant, so the correct hemisphere is
  lit and the day/night terminator is an accurate great circle. Solar
  declination provides the seasonal tilt, so no separate axial tilt is applied.

---

## Two-interpreter architecture

There are **two** Python environments, by necessity:

1. **Project venv** (`.venv`, Python 3.13, managed by [uv](https://docs.astral.sh/uv/)) —
   heavyweight GIS libraries (`pyshp`, `pyproj`, `shapely`, `triangle`) used to
   **preprocess** shapefiles (read, repair, triangulate) *outside* Blender, plus `pillow` to downsample the
   NASA rasters (21600×10800 → 8192×4096).
2. **Blender's bundled Python** (3.13) — runs the scene-building code via the MCP
   `execute_blender_code` tool. It cannot use the venv's compiled libraries, so
   `pyshp` is **vendored** as a single pure-Python file at `vendor/shapefile.py`,
   and heavy preprocessing hands Blender clean intermediate data (`.npz` meshes).

```
shapefile (.shp, EPSG:4326)
      │  venv: pyshp + shapely + triangle
      ▼
triangulated mesh (.npz: lon/lat verts + faces)
      │  Blender: numpy maps lon/lat → ECEF, builds mesh
      ▼
geometry draped on the ellipsoid + materials
```

---

## Project layout

```
blender-globe/
├── README.md                  # this file
├── RECIPE.md                  # step-by-step recreation guide
├── pyproject.toml / uv.lock   # uv project (pyshp, pyproj, shapely, triangle, pillow)
├── .python-version            # pins Python 3.13 (matches Blender)
├── vendor/
│   ├── shapefile.py           # vendored pyshp, importable inside Blender
│   └── LICENSE-pyshp.txt
├── scripts/
│   ├── fetch_data.sh          # (shell)   download Natural Earth layers → Data/
│   ├── build_land_mesh.py     # (venv)    triangulate a polygon shapefile → .npz
│   ├── build_all.py           # (Blender) run every Blender step below in order
│   ├── create_globe.py        # (Blender) WGS 84 ellipsoid + reference bands
│   ├── shapefile_to_globe.py  # (Blender) drape lines/polygons as beveled curves
│   ├── fill_land_ocean.py     # (Blender) ocean material + climate-colored land
│   ├── add_polygon_layers.py  # (Blender) lakes / glaciers / ice shelves fills
│   ├── add_rivers.py          # (Blender) rivers + lake centerlines
│   ├── fetch_rasters.sh       # (shell)   download NASA rasters → Data/rasters_src/
│   ├── prepare_rasters.py     # (venv)    downsample them → Data/rasters/ (8192×4096)
│   ├── add_photoreal.py       # (Blender) raster materials, clouds + atmosphere shells
│   └── render_globe.py        # (Blender) subsolar sun + view presets + render
└── renders/
    ├── globe_render.png       # vector-style render
    └── readme/                # README images (JPEG copies of the photo renders)
```

Not committed (see `.gitignore`), all regenerable: `.venv/`, `Data/`
(Natural Earth and NASA downloads, `.npz` caches, prepared rasters), other `renders/`, and `*.blend` scenes.

Scripts locate the project root from their own path, so the repo can live
anywhere. Override with the `GLOBE_PROJECT` environment variable if needed.

---

## Tooling

- **Blender 5.1** (tested), optionally with the blender-mcp add-on
  (socket on `127.0.0.1:9876`) for interactive, AI-driven building.
- **uv** for the project venv and Python pin.
- **Natural Earth 1:10m** vector layers; **NASA** Blue Marble / Black Marble / GEBCO rasters (photo style).

## Credits & licenses

- Map data: [Natural Earth](https://www.naturalearthdata.com/), public domain.
- Rasters (photo style): NASA Visible Earth / Earth Observatory — Blue Marble Next Generation
  (Reto Stöckli, NASA GSFC), Black Marble 2016 (Suomi NPP VIIRS), Blue Marble cloud composite,
  GEBCO_08 elevation; public domain (NASA).
- `vendor/shapefile.py`: [pyshp](https://github.com/GeospatialPython/pyshp),
  MIT License (see `vendor/LICENSE-pyshp.txt`).

See **[RECIPE.md](RECIPE.md)** to rebuild the whole thing from scratch.
