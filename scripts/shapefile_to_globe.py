"""
shapefile_to_globe.py

Drape an EPSG:4326 (WGS84 geographic, lon/lat degrees) shapefile onto the
WGS84 ellipsoid globe in Blender as renderable curve geometry.

Runs inside Blender's bundled Python. Uses the vendored pure-Python pyshp
reader at <project>/vendor/shapefile.py (no external deps needed in Blender).

Mapping is the exact geodetic -> ECEF transform:
    N = a / sqrt(1 - e^2 sin^2(lat))          (prime vertical radius of curvature)
    X = (N + h) cos(lat) cos(lon)
    Y = (N + h) cos(lat) sin(lon)
    Z = (N (1 - e^2) + h) sin(lat)
With h = 0 this lands points exactly on the ellipsoid surface x^2/a^2 + y^2/a^2
+ z^2/b^2 = 1 -- the same surface as the scaled-UV-sphere globe mesh.

Convention: lon 0 (Greenwich) -> +X, lon 90E -> +Y, north pole -> +Z.
Scale: 1 Blender unit = 1000 km.
"""
import bpy
import math
import os
import sys

# Project root: $GLOBE_PROJECT if set, else the parent of this scripts/ folder.
PROJECT = os.environ.get("GLOBE_PROJECT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(PROJECT, "vendor")
if VENDOR not in sys.path:
    sys.path.insert(0, VENDOR)
import shapefile  # pyshp (vendored)

# --- WGS 84 ellipsoid (EPSG:7030) ---
A_M = 6378137.0                 # semi-major axis, meters
INV_F = 298.257223563           # inverse flattening
F = 1.0 / INV_F
E2 = F * (2.0 - F)              # first eccentricity squared
UNIT_M = 1.0e6                  # 1 Blender unit = 1000 km


def geodetic_to_xyz(lon_deg, lat_deg, height_units=0.0):
    """Geodetic lon/lat (deg) on WGS84 -> Blender-unit ECEF XYZ."""
    lon = math.radians(lon_deg)
    lat = math.radians(lat_deg)
    slat, clat = math.sin(lat), math.cos(lat)
    slon, clon = math.sin(lon), math.cos(lon)
    n = A_M / math.sqrt(1.0 - E2 * slat * slat)
    h = height_units * UNIT_M
    x = (n + h) * clat * clon
    y = (n + h) * clat * slon
    z = (n * (1.0 - E2) + h) * slat
    return (x / UNIT_M, y / UNIT_M, z / UNIT_M)


def iter_parts(shp, closed=True):
    """Yield each part of a shape as a list of (lon, lat).

    closed=True  -> polygon rings; drop the duplicate closing vertex
                    (the spline closes itself via use_cyclic_u).
    closed=False -> open polylines (rivers); keep every vertex as-is.
    """
    pts = shp.points
    starts = list(shp.parts) + [len(pts)]
    for i in range(len(starts) - 1):
        part = pts[starts[i]:starts[i + 1]]
        if closed and len(part) >= 2 and tuple(part[0]) == tuple(part[-1]):
            part = part[:-1]  # drop duplicated closing vertex
        if len(part) >= 2:
            yield part


def make_material(name, rgb, emission=0.35):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def drape_shapefile(shp_path, name="Oceans", offset_units=0.006,
                    bevel_units=0.006, rgb=(0.05, 0.35, 0.9), closed=True):
    """Read an EPSG:4326 shapefile and build a beveled curve draped on the globe.

    closed=True for polygon boundaries (coastlines), False for open lines (rivers).
    """
    sf = shapefile.Reader(shp_path)

    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = bevel_units       # gives the line real, renderable thickness
    cu.bevel_resolution = 0            # 4-sided tube -> light geometry
    cu.use_fill_caps = True

    n_rings = 0
    n_points = 0
    for shp in sf.shapes():
        for ring in iter_parts(shp, closed=closed):
            sp = cu.splines.new('POLY')
            sp.use_cyclic_u = closed   # close polygon rings, leave rivers open
            sp.points.add(len(ring) - 1)  # one point already exists
            flat = []
            for lon, lat in ring:
                x, y, z = geodetic_to_xyz(lon, lat, offset_units)
                flat += [x, y, z, 1.0]
            sp.points.foreach_set('co', flat)
            n_rings += 1
            n_points += len(ring)

    # replace any existing object/curve of this name
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)

    obj = bpy.data.objects.new(name, cu)
    obj.data.materials.append(make_material(name + "Mat", rgb))
    bpy.context.scene.collection.objects.link(obj)
    return obj, n_rings, n_points


def _set_material_shading():
    try:
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces[0].shading.type = 'MATERIAL'
    except Exception:
        pass


if __name__ == "__main__":
    shp = os.path.join(PROJECT, "Data", "ne_10m_ocean", "ne_10m_ocean.shp")
    obj, nr, npts = drape_shapefile(shp, name="Oceans")
    _set_material_shading()
    print({"object": obj.name, "rings": nr, "points": npts})
