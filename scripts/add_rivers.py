"""
add_rivers.py  (run inside Blender)

Drape Natural Earth rivers + lake centerlines onto the globe as thin, open
(non-cyclic) beveled curves, just above the land/lake layers.
"""
import importlib.util
import os

# Project root: $GLOBE_PROJECT if set, else the parent of this scripts/ folder.
PROJECT = os.environ.get("GLOBE_PROJECT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location(
    "shapefile_to_globe", os.path.join(PROJECT, "scripts", "shapefile_to_globe.py"))
s2g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s2g)

RIVERS_SHP = os.path.join(PROJECT, "Data", "ne_10m_rivers_lake_centerlines",
                          "ne_10m_rivers_lake_centerlines.shp")

if __name__ == "__main__":
    obj, nlines, npts = s2g.drape_shapefile(
        RIVERS_SHP, name="Rivers",
        offset_units=0.013,      # above land (0.010) and lakes (0.012)
        bevel_units=0.0022,      # ~2 km line thickness
        rgb=(0.15, 0.45, 0.85),
        closed=False)            # rivers are open polylines
    print({"rivers_lines": nlines, "rivers_points": npts})
