#!/usr/bin/env bash
# Download and unzip the Natural Earth 1:10m physical layers used by this project
# into ./Data. Safe to re-run: existing layers are skipped.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$ROOT/Data"
BASE="https://naciscdn.org/naturalearth/10m/physical"
LAYERS=(
  ne_10m_ocean
  ne_10m_land
  ne_10m_lakes
  ne_10m_rivers_lake_centerlines
  ne_10m_glaciated_areas
  ne_10m_antarctic_ice_shelves_polys
)

mkdir -p "$DATA"
for layer in "${LAYERS[@]}"; do
  if [ -f "$DATA/$layer/$layer.shp" ]; then
    echo "✓ $layer (already present)"
    continue
  fi
  echo "↓ $layer"
  curl -fsSL "$BASE/$layer.zip" -o "$DATA/$layer.zip"
  unzip -oq "$DATA/$layer.zip" -d "$DATA/$layer"
done
echo "Done. Shapefiles are in $DATA"
