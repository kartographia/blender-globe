"""
prepare_rasters.py  (run in the project venv:  uv run python scripts/prepare_rasters.py)

Downsample the NASA source rasters in Data/rasters_src/ (scripts/fetch_rasters.sh) to Blender-friendly
equirectangular textures in Data/rasters/ (lon -180..180 left->right, lat 90..-90 top->bottom, EPSG:4326 grid):

    day_MM.jpg     Blue Marble NG month MM (color)          <- world.topo.bathy.2004MM.3x21600x10800.jpg
    night.jpg      Black Marble 2016 city lights (gray)     <- BlackMarble_2016_3km_gray.jpg
    clouds.jpg     cloud composite (gray)                   <- cloud_combined_8192.tif
    elevation.png  land elevation (gray, Lanczos-smoothed + dithered) <- gebco_08_rev_elev_21600x10800.png

The 21600x10800 sources would cost ~1 GB of RAM each inside Blender; 8192x4096 is plenty for a
1500 px render (the visible hemisphere spans ~4096 texels). Skips outputs that are newer than their source.

Usage:
    uv run python scripts/prepare_rasters.py [width]      # default width 8192
"""
import glob
import os
import re
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None   # the NASA sources are 233 Mpx

PROJECT = os.environ.get("GLOBE_PROJECT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJECT, "Data", "rasters_src")
OUT = os.path.join(PROJECT, "Data", "rasters")
WIDTH = int(sys.argv[1]) if len(sys.argv) > 1 else 8192


def fresh(src, dst):
    return os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src)


def resize(img):
    return img.resize((WIDTH, WIDTH // 2), Image.LANCZOS, reducing_gap=3.0)


def save_jpg(src, dst, mode):
    if fresh(src, dst):
        print("ok", os.path.basename(dst)); return
    img = resize(Image.open(src).convert(mode))
    img.save(dst, quality=93, optimize=True)
    print("->", os.path.basename(dst), img.size, mode)


def save_elevation(src, dst):
    """8-bit elevation is enough for bump mapping if it is resampled in float and dithered when re-quantizing
    (otherwise the 25 m steps of the source show up as contour terraces in the bump)."""
    if fresh(src, dst):
        print("ok", os.path.basename(dst)); return
    img = resize(Image.open(src).convert("F"))
    a = np.array(img, dtype=np.float32)            # Lanczos 21600->8192 already low-passes
    a += np.random.default_rng(0).uniform(-0.5, 0.5, a.shape).astype(np.float32)
    Image.fromarray(np.clip(np.rint(a), 0, 255).astype(np.uint8), "L").save(dst, optimize=True)
    print("->", os.path.basename(dst), img.size)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    days = sorted(glob.glob(os.path.join(SRC, "world.topo.bathy.2004??.3x21600x10800.jpg")))
    if not days:
        sys.exit("no Blue Marble month in Data/rasters_src — run: bash scripts/fetch_rasters.sh")
    for p in days:
        mm = re.search(r"2004(\d\d)", os.path.basename(p)).group(1)
        save_jpg(p, os.path.join(OUT, f"day_{mm}.jpg"), "RGB")
    save_jpg(os.path.join(SRC, "BlackMarble_2016_3km_gray.jpg"), os.path.join(OUT, "night.jpg"), "L")
    save_jpg(os.path.join(SRC, "cloud_combined_8192.tif"), os.path.join(OUT, "clouds.jpg"), "L")
    save_elevation(os.path.join(SRC, "gebco_08_rev_elev_21600x10800.png"), os.path.join(OUT, "elevation.png"))
    print("Done ->", OUT)
