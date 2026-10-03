"""
build_all.py — rebuild the whole globe scene in one go.

Headless (no MCP needed), from the project root:
    blender -b --factory-startup --python scripts/build_all.py -- [--no-render] [--save]

Or inside a running Blender (MCP execute_blender_code / Text Editor):
    p = "<repo>/scripts/build_all.py"
    exec(compile(open(p).read(), p, "exec"), {"__name__": "__main__", "__file__": p})

Requires the Natural Earth data (scripts/fetch_data.sh) and the triangulated
.npz meshes (see RECIPE.md step 3) to exist first.

Flags (after `--`):
    --no-render   skip the final render
    --save        save the scene to <repo>/Globe.blend
"""
import os
import sys

import bpy

# Project root: $GLOBE_PROJECT if set, else the parent of this scripts/ folder.
PROJECT = os.environ.get("GLOBE_PROJECT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(PROJECT, "scripts")

STEPS = [
    "create_globe.py",        # WGS 84 ellipsoid + equator / prime meridian bands
    "shapefile_to_globe.py",  # coastline curves (ne_10m_ocean)
    "fill_land_ocean.py",     # ocean material + climate-colored land
    "add_polygon_layers.py",  # lakes, glaciers, Antarctic ice shelves
    "add_rivers.py",          # rivers + lake centerlines
]

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def run(script):
    path = os.path.join(SCRIPTS, script)
    print(f"--> {script}")
    exec(compile(open(path).read(), path, "exec"), {"__name__": "__main__", "__file__": path})


if __name__ == "__main__":
    for step in STEPS:
        run(step)
    if "--no-render" not in args:
        run("render_globe.py")
    if "--save" in args:
        out = os.path.join(PROJECT, "Globe.blend")
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print("saved ->", out)
