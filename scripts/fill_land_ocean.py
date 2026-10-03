"""
fill_land_ocean.py  (run inside Blender via execute_blender_code)

- Colors the globe sphere as OCEAN (blue).
- Loads Data/land_mesh.npz (built by build_land_mesh.py), maps the lon/lat
  vertices to the WGS84 ellipsoid (geodetic -> ECEF, vectorized with numpy),
  builds a filled LAND mesh draped slightly above the surface, and shades it
  with a per-vertex latitude/climate color ramp (ice caps white, tundra,
  temperate + tropical greens, arid drylands tan).
"""
import os
import bpy
import numpy as np

# Project root: $GLOBE_PROJECT if set, else the parent of this scripts/ folder.
PROJECT = os.environ.get("GLOBE_PROJECT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# WGS84 (matches shapefile_to_globe.py)
A_M = 6378137.0
INV_F = 298.257223563
F_FLAT = 1.0 / INV_F
E2 = F_FLAT * (2.0 - F_FLAT)
UNIT_M = 1.0e6

LAND_OFFSET = 0.010   # ~10 km outward, keeps land above the ocean sphere despite triangle sag

# Latitude -> RGB anchors (signed degrees, ascending). Linearly interpolated per channel.
# Approximates real biomes by latitude: polar ice, tundra, temperate/tropical greens,
# and subtropical arid bands (deserts). Tuned for a natural look, not survey accuracy.
CLIMATE_LAT = np.array([-90, -70, -63, -55, -45, -30, -15,  0, 15, 25, 35, 45, 55, 63, 72, 90], dtype=np.float64)
CLIMATE_RGB = np.array([
    (0.93, 0.95, 0.98),  # -90  Antarctica ice
    (0.88, 0.92, 0.96),  # -70  ice
    (0.80, 0.83, 0.82),  # -63  ice/rock edge
    (0.45, 0.50, 0.42),  # -55  sub-antarctic tundra
    (0.22, 0.40, 0.20),  # -45  temperate (Patagonia)
    (0.52, 0.47, 0.29),  # -30  arid (Atacama/Kalahari/outback)
    (0.19, 0.42, 0.16),  # -15  tropical
    (0.15, 0.40, 0.13),  #   0  equatorial lush
    (0.29, 0.44, 0.18),  #  15  savanna
    (0.62, 0.55, 0.34),  #  25  desert (Sahara/Arabia)
    (0.40, 0.45, 0.23),  #  35  semi-arid -> green
    (0.21, 0.42, 0.18),  #  45  temperate
    (0.26, 0.40, 0.24),  #  55  boreal
    (0.48, 0.53, 0.47),  #  63  tundra
    (0.80, 0.85, 0.90),  #  72  snow
    (0.90, 0.93, 0.96),  #  90  Arctic ice
], dtype=np.float64)


def climate_colors(lat_deg):
    r = np.interp(lat_deg, CLIMATE_LAT, CLIMATE_RGB[:, 0])
    g = np.interp(lat_deg, CLIMATE_LAT, CLIMATE_RGB[:, 1])
    b = np.interp(lat_deg, CLIMATE_LAT, CLIMATE_RGB[:, 2])
    a = np.ones_like(r)
    return np.column_stack([r, g, b, a]).astype(np.float32)


def make_material(name, rgb, roughness=0.8, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Metallic"].default_value = metallic
    return mat


def make_vertexcolor_material(name, attr="Col", roughness=0.9):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = roughness
    vc = nt.nodes.get("LandVC") or nt.nodes.new("ShaderNodeVertexColor")
    vc.name = "LandVC"
    vc.layer_name = attr
    vc.location = (-320, 0)
    nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


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


def build_land():
    data = np.load(os.path.join(PROJECT, "Data", "land_mesh.npz"))
    V = data["vertices"].astype(np.float64)   # (N,2) lon/lat
    Fc = data["faces"].astype(np.int32)       # (M,3)
    XYZ = geodetic_to_xyz_np(V, LAND_OFFSET)
    col = climate_colors(V[:, 1])             # per-vertex color from latitude

    old = bpy.data.objects.get("Land")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)

    mesh = bpy.data.meshes.new("Land")
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

    ca = mesh.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='POINT')
    ca.data.foreach_set("color", col.ravel())

    obj = bpy.data.objects.new("Land", mesh)
    obj.data.materials.append(make_vertexcolor_material("LandMat", attr="Col", roughness=0.9))
    bpy.context.scene.collection.objects.link(obj)
    return len(XYZ), len(Fc)


def color_ocean():
    globe = bpy.data.objects.get("Globe")
    globe.data.materials.clear()
    globe.data.materials.append(
        make_material("OceanMat", (0.015, 0.10, 0.30), roughness=0.30))


if __name__ == "__main__":
    color_ocean()
    nv, nf = build_land()
    print({"land_vertices": nv, "land_triangles": nf})
