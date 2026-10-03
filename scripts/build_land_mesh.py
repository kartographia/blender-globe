"""
build_land_mesh.py  (run in the project venv:  uv run python scripts/build_land_mesh.py)

Triangulate an EPSG:4326 polygon shapefile (polygons with holes) in lon/lat
space so the resulting triangles are small enough to hug the WGS84 ellipsoid
when mapped to 3D.

Method (hang-proof): plain Delaunay over the polygon's boundary vertices PLUS a
regular interior grid of Steiner points, then keep only the triangles whose
centroid lies inside the polygon. The grid keeps triangles small (good sphere
hugging); the centroid test removes exterior triangles and holes. This avoids
Triangle's constrained ('p') mode, which can hang on Natural Earth's messy /
self-intersecting rings.

Usage:
    uv run python scripts/build_land_mesh.py <in.shp> <out.npz> [grid_deg]
    uv run python scripts/build_land_mesh.py            # default: land layer

Output npz:
    vertices : float64 (N, 2)  lon/lat degrees
    faces    : int32   (M, 3)  triangle vertex indices (global)

Blender then maps the vertices to ECEF and builds the mesh (numpy is available
in Blender's bundled Python; triangle/shapely are not, hence this preprocess).
"""
import glob
import os

import numpy as np
import triangle as tr
from shapely import contains_xy
from shapely.geometry import shape as shp_shape

import shapefile  # pyshp (from venv)

# Project root: $GLOBE_PROJECT if set, else the parent of this scripts/ folder.
PROJECT = os.environ.get("GLOBE_PROJECT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRID_DEG = 1.0   # interior Steiner-point spacing in degrees; smaller -> hugs tighter, more tris


def _polygons_of(geom):
    """Flatten a shapely geometry into a list of non-empty Polygons."""
    t = geom.geom_type
    if t == "Polygon":
        return [geom] if not geom.is_empty else []
    if t in ("MultiPolygon", "GeometryCollection"):
        out = []
        for g in geom.geoms:
            out.extend(_polygons_of(g))
        return out
    return []


def _ring_xy(coords):
    c = [(float(x), float(y)) for x, y, *_ in coords]
    if len(c) >= 2 and c[0] == c[-1]:
        c = c[:-1]
    return c


def triangulate_polygon(poly, grid_deg=GRID_DEG):
    """shapely Polygon -> (vertices Nx2, triangles Mx3), hang-proof grid+Delaunay."""
    pts = list(_ring_xy(poly.exterior.coords))
    for interior in poly.interiors:
        pts.extend(_ring_xy(interior.coords))
    if len(pts) < 3:
        return None, None

    # interior Steiner grid (vectorized point-in-polygon)
    minx, miny, maxx, maxy = poly.bounds
    gx = np.arange(minx + grid_deg * 0.5, maxx, grid_deg)
    gy = np.arange(miny + grid_deg * 0.5, maxy, grid_deg)
    if gx.size and gy.size:
        mx, my = np.meshgrid(gx, gy)
        inside = contains_xy(poly, mx.ravel(), my.ravel())
        if inside.any():
            pts.extend(zip(mx.ravel()[inside], my.ravel()[inside]))

    P = np.asarray(pts, dtype=np.float64)
    # de-duplicate coincident points (Delaunay dislikes them)
    P = np.unique(P, axis=0)
    if len(P) < 3:
        return None, None

    t = tr.triangulate({"vertices": P})   # plain Delaunay, no constraints -> never hangs
    if "triangles" not in t:
        return None, None
    V = t["vertices"]
    T = t["triangles"]
    # keep triangles whose centroid is inside the polygon (drops exterior + holes)
    cent = V[T].mean(axis=1)
    keep = contains_xy(poly, cent[:, 0], cent[:, 1])
    T = T[keep]
    if len(T) == 0:
        return None, None
    return V, T


def triangulate_shapefile(in_shp, out_npz, grid_deg=GRID_DEG):
    """Triangulate every polygon in an EPSG:4326 polygon shapefile -> .npz (vertices, faces)."""
    sf = shapefile.Reader(in_shp)
    all_v, all_f, voff, npoly = [], [], 0, 0
    for s in sf.shapes():
        geom = shp_shape(s.__geo_interface__)
        if not geom.is_valid:
            geom = geom.buffer(0)   # repair self-intersecting rings
        for poly in _polygons_of(geom):
            if poly.is_empty or poly.area == 0.0:
                continue
            v, f = triangulate_polygon(poly, grid_deg)
            if v is None:
                continue
            all_v.append(np.asarray(v, dtype=np.float64))
            all_f.append(np.asarray(f, dtype=np.int64) + voff)
            voff += len(v)
            npoly += 1

    V = np.vstack(all_v)
    F = np.vstack(all_f).astype(np.int32)
    np.savez(out_npz, vertices=V, faces=F)
    info = {"polygons": npoly, "vertices": int(V.shape[0]),
            "triangles": int(F.shape[0]), "out": out_npz}
    print(info)
    return info


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        in_shp, out_npz = sys.argv[1], sys.argv[2]
        grid = float(sys.argv[3]) if len(sys.argv) >= 4 else GRID_DEG
        triangulate_shapefile(in_shp, out_npz, grid)
    else:
        shp = glob.glob(os.path.join(PROJECT, "Data/ne_10m_land/*.shp"))[0]
        triangulate_shapefile(shp, os.path.join(PROJECT, "Data", "land_mesh.npz"))
