#!/usr/bin/env bash
# Download the NASA rasters used by the photoreal look into Data/rasters_src/
# (all public domain, NASA Visible Earth / Earth Observatory). Safe to re-run: existing files are skipped.
#
#   bash scripts/fetch_rasters.sh            # Blue Marble months of the VIEWS presets in scripts/render_globe.py
#   bash scripts/fetch_rasters.sh 01 07      # specific Blue Marble months
#
# Then downsample to Blender-friendly sizes (venv, Pillow):  uv run python scripts/prepare_rasters.py
#
#   world.topo.bathy.2004MM  Blue Marble Next Generation (monthly, 21600x10800, ~29 MB)  -> day color
#   BlackMarble_2016_3km_gray  Black Marble 2016 city lights (13500x6750, ~3 MB)         -> night lights
#   cloud_combined_8192        Blue Marble cloud composite (8192x4096 TIFF, ~36 MB)      -> cloud layer
#   gebco_08_rev_elev          GEBCO/SRTM land elevation (21600x10800 PNG, ~18 MB)       -> relief (bump)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/Data/rasters_src"
mkdir -p "$SRC"

if [ $# -gt 0 ]; then
  MONTHS=("$@")
else
  # months from the presets' "utc": (Y, MO, D, HH, MM) tuples
  mapfile -t MONTHS < <(sed -nE 's/.*"utc": *\( *[0-9]+, *([0-9]+),.*/\1/p' "$ROOT/scripts/render_globe.py" | sort -un)
  [ ${#MONTHS[@]} -gt 0 ] || MONTHS=(7)
fi

# Visible Earth record id per Blue Marble NG month (2004)
declare -A BMNG_ID=([01]=73580 [02]=73605 [03]=73630 [04]=73655 [05]=73701 [06]=73726
                    [07]=73751 [08]=73776 [09]=73801 [10]=73826 [11]=73884 [12]=73909)
EO="https://eoimages.gsfc.nasa.gov/images/imagerecords"

get() {  # url
  local f="$SRC/$(basename "$1")"
  if [ -s "$f" ]; then echo "✓ $(basename "$f") (already present)"; return; fi
  echo "↓ $(basename "$f")"
  curl -fSL --retry 3 "$1" -o "$f.part" && mv "$f.part" "$f"
}

for m in "${MONTHS[@]}"; do
  m=$(printf '%02d' "$((10#$m))")
  get "$EO/73000/${BMNG_ID[$m]}/world.topo.bathy.2004${m}.3x21600x10800.jpg"
done
get "$EO/144000/144897/BlackMarble_2016_3km_gray.jpg"
get "$EO/57000/57747/cloud_combined_8192.tif"
get "$EO/73000/73934/gebco_08_rev_elev_21600x10800.png"
echo "Done. Sources are in $SRC — next: uv run python scripts/prepare_rasters.py"
