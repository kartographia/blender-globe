"""
render_globe.py  (run inside Blender via execute_blender_code)

Physically-meaningful lighting + finished render:
- A SUN lamp (parallel rays) aimed at the real subsolar point for a given UTC
  datetime, so exactly the correct hemisphere is lit and the day/night
  terminator is a correctly-placed great circle. Solar declination handles the
  seasonal tilt (Arctic polar day / Antarctic polar night in July).
- Dark "space" world, framed camera, EEVEE render to Data/../renders/.
"""
import os
import math
import bpy
from mathutils import Vector, Matrix

# Project root: $GLOBE_PROJECT if set, else the parent of this scripts/ folder.
PROJECT = os.environ.get("GLOBE_PROJECT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- UTC instant to light for ---
Y, MO, D, HH, MM = 2026, 7, 8, 12, 0

RENDER_OUT = os.path.join(PROJECT, "renders", "globe_render.png")
RES = 1500
SAMPLES = 48


def subsolar_point(y, mo, d, hh, mm, ss=0):
    """Return (sublat, sublon) degrees: the point where the sun is overhead at this UTC."""
    yy, mm2 = (y, mo)
    if mm2 <= 2:
        yy -= 1
        mm2 += 12
    A = yy // 100
    B = 2 - A + A // 4
    jd = (int(365.25 * (yy + 4716)) + int(30.6001 * (mm2 + 1)) + d + B - 1524.5
          + (hh + mm / 60.0 + ss / 3600.0) / 24.0)
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360.0
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    decl = math.asin(math.sin(eps) * math.sin(lam))
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    gmst = (280.46061837 + 360.98564736629 * n) % 360.0
    sublon = (math.degrees(ra) - gmst + 180.0) % 360.0 - 180.0
    return math.degrees(decl), sublon


def dir_from_lonlat(lon_deg, lat_deg):
    lo, la = math.radians(lon_deg), math.radians(lat_deg)
    return Vector((math.cos(la) * math.cos(lo),
                   math.cos(la) * math.sin(lo),
                   math.sin(la))).normalized()


def setup_sun(sublat, sublon):
    for nm in ("CheckSun", "Sun"):
        o = bpy.data.objects.get(nm)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
    ld = bpy.data.lights.new("Sun", 'SUN')
    ld.energy = 3.2
    ld.angle = math.radians(0.526)      # real angular diameter -> soft terminator
    ld.color = (1.0, 0.97, 0.92)
    sun = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(sun)
    d = dir_from_lonlat(sublon, sublat)          # direction TO the sun
    sun.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()   # +Z -> sun, so -Z (light) -> globe
    return sun, d


def setup_camera(sun_dir):
    cam = bpy.data.objects.get("GlobeCam")
    if cam:
        bpy.data.objects.remove(cam, do_unlink=True)
    cd = bpy.data.cameras.new("GlobeCam")
    cd.lens = 55.0
    cam = bpy.data.objects.new("GlobeCam", cd)
    bpy.context.scene.collection.objects.link(cam)
    # view from the sunlit side, rotated 52 deg around Z so the terminator shows on one limb
    view = (Matrix.Rotation(math.radians(52), 4, 'Z') @ sun_dir).normalized()
    dist = 34.0
    cam.location = view * dist
    look = (-cam.location).normalized()
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    return cam


def setup_world():
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.004, 0.005, 0.008, 1.0)  # faint space fill
    bg.inputs["Strength"].default_value = 1.0


def setup_render():
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):   # 4.2-4.x vs 5.x naming
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    sc.render.resolution_x = RES
    sc.render.resolution_y = RES
    sc.render.film_transparent = False
    sc.render.use_stamp_filename = False   # don't embed the local .blend path in PNG metadata
    try:
        sc.eevee.taa_render_samples = SAMPLES
    except Exception:
        pass
    try:
        sc.view_settings.view_transform = 'Filmic'
        sc.view_settings.look = 'Medium Contrast'
    except TypeError:
        pass  # keep the version's default view transform
    # keep the realistic Earth clean: hide reference geometry from the render
    for nm in ("Equator", "PrimeMeridian", "Oceans"):
        o = bpy.data.objects.get(nm)
        if o:
            o.hide_render = True
    os.makedirs(os.path.dirname(RENDER_OUT), exist_ok=True)
    sc.render.filepath = RENDER_OUT
    sc.render.image_settings.file_format = 'PNG'


if __name__ == "__main__":
    sublat, sublon = subsolar_point(Y, MO, D, HH, MM)
    sun, sdir = setup_sun(sublat, sublon)
    setup_camera(sdir)
    setup_world()
    setup_render()
    print({"subsolar_lat": round(sublat, 2), "subsolar_lon": round(sublon, 2),
           "sun_dir": tuple(round(c, 3) for c in sdir)})
    bpy.ops.render.render(write_still=True)
    print("rendered ->", RENDER_OUT)
