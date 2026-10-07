"""
create_globe.py  (run inside Blender)

Create the base WGS 84 ellipsoid ("Globe") centered at the world origin, plus
the Equator and Prime Meridian reference bands.

- UV sphere (256 x 128: smooth limb at close framing), scaled X/Y -> a and Z -> b, scale baked into the mesh
  (object scale stays 1,1,1).
- Scale: 1 Blender unit = 1000 km.  a ~ 6.378, b ~ 6.357 units.
- Orientation: lon 0 -> +X, lon 90E -> +Y, North Pole -> +Z.
"""
import math
import bpy
from mathutils import Matrix

# --- WGS 84 ellipsoid (EPSG:7030) ---
A_M = 6378137.0
INV_F = 298.257223563
B_M = A_M * (1.0 - 1.0 / INV_F)
UNIT_M = 1.0e6
A_U = A_M / UNIT_M
B_U = B_M / UNIT_M

BAND_TUBE = 0.06   # reference band tube radius (~60 km)
SEGMENTS, RINGS = 256, 128


def _remove(name):
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)


def _smooth(mesh):
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.update()


def _emissive_material(name, rgb, strength=0.6):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    if "Emission Color" in b.inputs:
        b.inputs["Emission Color"].default_value = (*rgb, 1.0)
        b.inputs["Emission Strength"].default_value = strength
    return mat


def create_ellipsoid():
    _remove("Cube")      # default startup cube, if present
    _remove("Light")     # default startup 1000 W point light: sits 0.9 units above Scandinavia and burns a hotspot
    _remove("Globe")
    bpy.ops.mesh.primitive_uv_sphere_add(segments=SEGMENTS, ring_count=RINGS, radius=1.0,
                                         location=(0.0, 0.0, 0.0))
    globe = bpy.context.active_object
    globe.name = "Globe"
    globe.data.transform(Matrix.Diagonal((A_U, A_U, B_U, 1.0)))   # bake WGS 84 axes into mesh
    _smooth(globe.data)
    return globe


def _torus(name):
    _remove(name)
    bpy.ops.mesh.primitive_torus_add(major_radius=A_U, minor_radius=BAND_TUBE,
                                     major_segments=192, minor_segments=16,
                                     location=(0.0, 0.0, 0.0))
    o = bpy.context.active_object
    o.name = name
    return o


def create_bands():
    eq = _torus("Equator")                          # lies in the XY (equatorial) plane
    _smooth(eq.data)
    eq.data.materials.append(_emissive_material("EquatorMat", (1.0, 0.82, 0.10)))

    pm = _torus("PrimeMeridian")                    # stand up into XZ plane, flatten to b/a
    pm.data.transform(Matrix.Diagonal((1.0, 1.0, B_U / A_U, 1.0))
                      @ Matrix.Rotation(math.radians(90), 4, 'X'))
    _smooth(pm.data)
    pm.data.materials.append(_emissive_material("PrimeMeridianMat", (0.10, 0.70, 1.0)))
    return eq, pm


if __name__ == "__main__":
    g = create_ellipsoid()
    create_bands()
    print({"globe_dimensions": [round(d, 4) for d in g.dimensions],
           "equatorial_radius": round(A_U, 6), "polar_radius": round(B_U, 6)})
