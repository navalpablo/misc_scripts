#!/usr/bin/env bash
# Genera la lámina completa (≈ 5 min y ~4 GB de RAM).  Vista previa rápida: F=4 ./run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
F=${F:-1}
./00_download.sh
python3 01_prepare_dem.py
python3 02_render_relief.py "$F"
python3 04_osm_hydro_roads.py
python3 03_compose.py "$F"
