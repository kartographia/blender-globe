"""
render_globe.py  (run inside Blender via execute_blender_code)

Physically-meaningful lighting + finished render:
- A SUN lamp (parallel rays) aimed at the real subsolar point for a given UTC
  datetime, so exactly the correct hemisphere is lit and the day/night
  terminator is a correctly-placed great circle. Solar declination handles the
  seasonal tilt (Arctic polar day / Antarctic polar night in July).
- Dark "space" world, framed camera, EEVEE render to Data/../renders/.

Views (VIEWS below; pick with `-- --view NAME`; default "day" for the vector style, "night" for photo):
- day    the original framing: sunlit side, camera rotated 52 deg about Z so the terminator shows on one limb.
- night  camera over North Africa, sun just past the western limb: Europe/Africa city lights, lit Atlantic limb.
Photo style (the scene contains "Atmosphere" from add_photoreal.py) additionally gets a faint fill light so the
night-side relief reads, a star field, bloom, AgX, and writes renders/globe_photo_<view>.png.
"""
import os
import sys
import math
import bpy
from mathutils import Vector, Matrix

# Project root: $GLOBE_PROJECT if set, else the parent of this scripts/ folder.
PROJECT = os.environ.get("GLOBE_PROJECT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- views: UTC instant (Y, MO, D, HH, MM) to light for + camera.
#     cam=None -> sunlit side rotated 52 deg about Z; cam=(lon, lat) -> camera above that point.
#     Optional photo-style overrides: "fill" = {"energy", "rgb", "right", "up"} (FillLight; right/up = offset of its
#     direction from the camera axis, in camera-frame units), "kickers" (see setup_kickers), "cloud_night"
#     (night-side cloud albedo), "relief" (bump exaggeration), "lights" (city-light strength) and "atmo_night"
#     (atmosphere glow kept on the night limb, 0..1); the last four are read by add_photoreal.py.
VIEWS = {
    "day":   {"utc": (2026, 7, 8, 12, 0),   "cam": None,         "dist": 34.0, "lens": 55.0},
    "night": {"utc": (2026, 10, 3, 18, 30), "cam": (17.0, 24.0), "dist": 23.0, "lens": 55.0},
}
# Same instant and framing, but a strong neutral fill so the night side reads as in the cinematic reference
# (not physical: there is only one sun; think "art-directed earthshine"), plus soft warm "kicker" point lights
# along 51 deg E: over the Caspian (Middle East / Iran wash) and over the southern Indian Ocean.
VIEWS["night_fill"] = {**VIEWS["night"],
                       "fill": {"energy": 0.40, "rgb": (0.74, 0.78, 0.90), "right": -0.35, "up": 0.75},
                       "kickers": [
                           {"lonlat": (51.0, 42.0), "height": 8.0, "power": 900.0, "rgb": (1.0, 0.94, 0.86), "soft": 3.0},
                           {"lonlat": (51.0, -30.0), "height": 8.0, "power": 900.0, "rgb": (1.0, 0.94, 0.86), "soft": 3.0},
                       ],
                       "cloud_night": 0.22,
                       "relief": 80.0,      # 2x the default 40: Himalaya / Zagros / Atlas read clearly
                       "lights": 3.6,       # city lights at 80% of the default 4.5
                       "atmo_night": 0.22}  # soft blue rim around the night limb (22% of the sunlit glow)

RENDER_OUT = os.path.join(PROJECT, "renders", "globe_render.png")       # vector style (README hero)
PHOTO_OUT = os.path.join(PROJECT, "renders", "globe_photo_{view}.png")  # photo style
RES = 1500
SAMPLES = 48

# --- photo style ---
FILL_ENERGY = 0.15              # faint cool fill (earthshine / moonlight stand-in), no specular
FILL_RGB = (0.62, 0.72, 1.0)
STAR_SCALE = 250.0              # voronoi cells per radian of view direction (~1 cell / 10 px)
STAR_FRACTION = 0.14            # fraction of cells holding a visible star
STAR_STRENGTH = 3.0
BLOOM_STRENGTH = 0.5
BLOOM_THRESHOLD = 0.8


def is_photo():
    return bpy.data.objects.get("Atmosphere") is not None


def resolve_view(name=None, photo=None):
    """View dict (+ 'name') from the argument, `--view NAME` after `--`, or the style's default
    (photo: is_photo() unless given; add_photoreal passes True since its Atmosphere doesn't exist yet)."""
    if name is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
        if "--view" in argv:
            name = argv[argv.index("--view") + 1]
    if name is None:
        name = "night" if (is_photo() if photo is None else photo) else "day"
    if name not in VIEWS:
        raise ValueError(f"unknown view {name!r}; choose from {sorted(VIEWS)}")
    return {"name": name, **VIEWS[name]}


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


def _remove(name):
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)


def _sun_lamp(name, energy, color, direction, angle_deg=0.526, shadow=True, specular=1.0):
    _remove(name)
    ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, 'SUN')
    ld.energy = energy
    ld.angle = math.radians(angle_deg)
    ld.color = color
    ld.use_shadow = shadow
    ld.specular_factor = specular
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()   # +Z -> light, so -Z (rays) -> globe
    return o


def setup_sun(sublat, sublon):
    _remove("CheckSun")
    d = dir_from_lonlat(sublon, sublat)          # direction TO the sun
    sun = _sun_lamp("Sun", 3.2, (1.0, 0.97, 0.92), d)   # real angular diameter -> soft terminator
    # photo materials mask city lights / atmosphere glow with a copy of the sun direction
    for mat in bpy.data.materials:
        if mat.node_tree and "SunDir" in mat.node_tree.nodes:
            for i, c in enumerate(d):
                mat.node_tree.nodes["SunDir"].inputs[i].default_value = c
    return sun, d


def setup_camera(sun_dir, view):
    _remove("GlobeCam")
    cd = bpy.data.cameras.get("GlobeCam") or bpy.data.cameras.new("GlobeCam")
    cd.lens = view["lens"]
    cd.clip_end = 1000.0
    cam = bpy.data.objects.new("GlobeCam", cd)
    bpy.context.scene.collection.objects.link(cam)
    if view["cam"] is None:
        # view from the sunlit side, rotated 52 deg around Z so the terminator shows on one limb
        v = (Matrix.Rotation(math.radians(52), 4, 'Z') @ sun_dir).normalized()
    else:
        v = dir_from_lonlat(*view["cam"])
    cam.location = v * view["dist"]
    look = (-cam.location).normalized()
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    return cam


def setup_fill(cam, view=None):
    """Fill light near the camera axis (default: faint, cool, from the upper right) so night-side relief and
    clouds read; a view's "fill" dict overrides it. No specular, so it adds no second glint on the ocean."""
    f = {"energy": FILL_ENERGY, "rgb": FILL_RGB, "right": 0.8, "up": 0.6, **((view or {}).get("fill") or {})}
    bpy.context.view_layer.update()
    m = cam.matrix_world.to_3x3()
    d = (cam.location.normalized() + f["right"] * m.col[0] + f["up"] * m.col[1]).normalized()
    return _sun_lamp("FillLight", f["energy"], f["rgb"], d, angle_deg=2.0, shadow=False, specular=0.0)


def _remove_kickers():
    for o in [o for o in bpy.data.objects if o.name.startswith("KickerLight")]:
        bpy.data.objects.remove(o, do_unlink=True)


def setup_kickers(view):
    """Optional view "kickers": a list of POINT lamps, each `height` units above its lonlat. A lamp only reaches the
    cap inside its own horizon (acos(R / (R + height)): ~47 deg for 3.0, ~64 deg for 8.0), so it washes that region
    and leaves the rest of the globe alone. Named KickerLight1, KickerLight2, ... No shadows, no specular."""
    _remove_kickers()
    lamps = []
    for i, k in enumerate(view.get("kickers") or [], 1):
        name = f"KickerLight{i}"
        ld = bpy.data.lights.get(name)
        if ld and ld.type != 'POINT':
            bpy.data.lights.remove(ld)
            ld = None
        ld = ld or bpy.data.lights.new(name, 'POINT')
        ld.energy = k["power"]
        ld.color = k["rgb"]
        ld.shadow_soft_size = k.get("soft", 0.5)
        ld.use_shadow = False
        ld.specular_factor = 0.0
        o = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(o)
        o.location = dir_from_lonlat(*k["lonlat"]) * (6.378 + k["height"])
        lamps.append(o)
    return lamps


def setup_world(stars=False):
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    for nm in ("StarCoord", "StarVoronoi", "StarPick", "StarDot", "StarMul", "StarAdd"):
        if nm in nt.nodes:
            nt.nodes.remove(nt.nodes[nm])
    if not stars:
        bg.inputs["Color"].default_value = (0.004, 0.005, 0.008, 1.0)  # faint space fill
        bg.inputs["Strength"].default_value = 1.0
        return world

    def add(kind, name, loc):
        n = nt.nodes.new(kind)
        n.name = name
        n.location = loc
        return n

    bg.inputs["Strength"].default_value = 1.0
    tc = add("ShaderNodeTexCoord", "StarCoord", (-1000, 300))
    vo = add("ShaderNodeTexVoronoi", "StarVoronoi", (-800, 300))
    vo.inputs["Scale"].default_value = STAR_SCALE
    nt.links.new(tc.outputs["Generated"], vo.inputs["Vector"])
    # a star only in cells whose random value is in the top STAR_FRACTION; brightness from that value
    pick = add("ShaderNodeMapRange", "StarPick", (-550, 400))
    pick.clamp = True
    pick.inputs["From Min"].default_value = 1.0 - STAR_FRACTION
    pick.inputs["From Max"].default_value = 1.0
    nt.links.new(vo.outputs["Color"], pick.inputs["Value"])
    dot = add("ShaderNodeMapRange", "StarDot", (-550, 150))      # small soft dot at the feature point
    dot.clamp = True
    dot.interpolation_type = 'SMOOTHSTEP'
    dot.inputs["From Min"].default_value = 0.12
    dot.inputs["From Max"].default_value = 0.0
    nt.links.new(vo.outputs["Distance"], dot.inputs["Value"])
    mul = add("ShaderNodeMath", "StarMul", (-300, 300))
    mul.operation = 'MULTIPLY'
    nt.links.new(pick.outputs["Result"], mul.inputs[0])
    nt.links.new(dot.outputs["Result"], mul.inputs[1])
    sc = add("ShaderNodeMath", "StarAdd", (-150, 300))            # strength * stars + faint fill
    sc.operation = 'MULTIPLY_ADD'
    sc.inputs[1].default_value = STAR_STRENGTH
    sc.inputs[2].default_value = 0.004
    nt.links.new(mul.outputs[0], sc.inputs[0])
    nt.links.new(sc.outputs[0], bg.inputs["Color"])
    return world


def setup_bloom(enable):
    """Blender 5.x compositor: scene.compositing_node_group (Render Layers -> Glare/Bloom -> Group Output)."""
    sc = bpy.context.scene
    if not hasattr(sc, "compositing_node_group"):
        return False                                    # pre-5.0 API: skip bloom
    if not enable:
        sc.compositing_node_group = None
        return False
    ng = bpy.data.node_groups.get("GlobeComp")
    if ng:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new("GlobeComp", "CompositorNodeTree")
    ng.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    out = ng.nodes.new("NodeGroupOutput")
    rl.location, gl.location, out.location = (-400, 0), (0, 0), (300, 0)
    gl.inputs["Type"].default_value = 'Bloom'
    gl.inputs["Threshold"].default_value = BLOOM_THRESHOLD
    gl.inputs["Strength"].default_value = BLOOM_STRENGTH
    gl.inputs["Size"].default_value = 0.6
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], out.inputs["Image"])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True
    return True


def setup_render(out_path, photo):
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
    view_look = ('AgX', 'Medium High Contrast') if photo else ('Filmic', 'Medium Contrast')
    try:
        sc.view_settings.view_transform, sc.view_settings.look = view_look
    except TypeError:
        try:
            sc.view_settings.look = 'AgX - ' + view_look[1]     # some versions prefix looks
        except TypeError:
            pass  # keep the version's default view transform
    # keep the realistic Earth clean: hide reference geometry from the render
    for nm in ("Equator", "PrimeMeridian", "Oceans"):
        o = bpy.data.objects.get(nm)
        if o:
            o.hide_render = True
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sc.render.filepath = out_path
    sc.render.image_settings.file_format = 'PNG'


def setup(view_name=None):
    """Lights, camera, world and render settings for the view; returns (view, out_path, info)."""
    view = resolve_view(view_name)
    photo = is_photo()
    sublat, sublon = subsolar_point(*view["utc"])
    sun, sdir = setup_sun(sublat, sublon)
    cam = setup_camera(sdir, view)
    if photo:
        setup_fill(cam, view)
        setup_kickers(view)
    else:
        _remove("FillLight")
        _remove_kickers()
    setup_world(stars=photo)
    setup_bloom(photo)
    out = PHOTO_OUT.format(view=view["name"]) if photo else RENDER_OUT
    setup_render(out, photo)
    info = {"style": "photo" if photo else "vector", "view": view["name"], "utc": view["utc"],
            "subsolar_lat": round(sublat, 2), "subsolar_lon": round(sublon, 2),
            "sun_dir": tuple(round(c, 3) for c in sdir)}
    return view, out, info


if __name__ == "__main__":
    view, out, info = setup()
    print(info)
    bpy.ops.render.render(write_still=True)
    print("rendered ->", out)
