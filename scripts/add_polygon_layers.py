"""
add_polygon_layers.py  (run inside Blender via execute_blender_code)

Build filled polygon layers from the .npz meshes produced by build_land_mesh.py
and drape them on the WGS84 globe:
    Lakes       -> blue,  just above land
    Glaciers    -> white, above land (paints Greenland / alpine / Arctic ice white)
    IceShelves  -> white, over the ocean around Antarctica

Radial offsets (units; 1 unit = 1000 km) stack the layers so higher ones win:
    ocean sphere 0.000 < land 0.010 < lakes 0.012 < rivers 0.013 < glaciers/shelves 0.016
"""
import os
import bpy
import numpy as np

# Project root: $GLOBE_PROJECT if set, else the parent of this scripts/ folder.
PROJECT = os.environ.get("GLOBE_PROJECT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

A_M = 6378137.0
INV_F = 298.257223563
F_FLAT = 1.0 / INV_F
E2 = F_FLAT * (2.0 - F_FLAT)
UNIT_M = 1.0e6


def geodetic_to_xyz_np(lonlat, offset_units):
    lon = np.radians(lonlat[:, 0])
    lat = np.radians(lonlat[:, 1])
    slat, clat = np.sin(lat), np.cos(lat)
    slon, clon = np.sin(lon), np.cos(lon)
    n = A_M / np.sqrt(1.0 - E2 * slat * slat)
    h = offset_units * UNIT_M
    x = (n + h) * clat * clon
    y = (n + h) * clat * slon
    z = (n * (1.0 - E2) + h) * slat
    return np.column_stack([x, y, z]) / UNIT_M


def make_material(name, rgb, roughness=0.85):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = roughness
    return mat


def build_layer(npz_path, name, rgb, offset, roughness=0.85):
    data = np.load(os.path.join(PROJECT, npz_path))
    V = data["vertices"].astype(np.float64)
    Fc = data["faces"].astype(np.int32)
    XYZ = geodetic_to_xyz_np(V, offset)

    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)

    mesh = bpy.data.meshes.new(name)
    mesh.vertices.add(len(XYZ))
    mesh.vertices.foreach_set("co", XYZ.ravel())
    loops = Fc.ravel()
    mesh.loops.add(len(loops))
    mesh.loops.foreach_set("vertex_index", loops)
    mesh.polygons.add(len(Fc))
    mesh.polygons.foreach_set("loop_start", np.arange(0, len(loops), 3, dtype=np.int32))
    mesh.polygons.foreach_set("loop_total", np.full(len(Fc), 3, dtype=np.int32))
    mesh.polygons.foreach_set("use_smooth", np.ones(len(Fc), dtype=bool))
    mesh.update(calc_edges=True)
    mesh.validate()

    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(make_material(name + "Mat", rgb, roughness))
    bpy.context.scene.collection.objects.link(obj)
    return len(XYZ), len(Fc)


LAYERS = [
    ("Data/ne_10m_lakes.npz",                    "Lakes",      (0.03, 0.16, 0.42), 0.012, 0.30),
    ("Data/ne_10m_glaciated_areas.npz",          "Glaciers",   (0.93, 0.95, 0.98), 0.016, 0.85),
    ("Data/ne_10m_antarctic_ice_shelves_polys.npz", "IceShelves", (0.90, 0.93, 0.97), 0.016, 0.85),
]

if __name__ == "__main__":
    for npz, name, rgb, off, rough in LAYERS:
        nv, nf = build_layer(npz, name, rgb, off, rough)
        print({name: {"vertices": nv, "triangles": nf}})
