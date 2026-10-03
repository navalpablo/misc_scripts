#!/usr/bin/env bash
# Genera las dos láminas (≈ 10 min y ~4 GB de RAM).
#   ./run_all.sh               -> output/pirineo_150cm.* (clásica) y output/pirineo_color_150cm.* (color)
#   F=4 ./run_all.sh           -> vistas previas a 1/4 en work/compose*_f4.png
#   STYLES=color ./run_all.sh  -> solo una de las dos
set -euo pipefail
cd "$(dirname "$0")"
F=${F:-1}
STYLES=${STYLES:-"clasico color"}
./00_download.sh
python3 01_prepare_dem.py
python3 04_osm_hydro_roads.py
[ -f work/mask_sea_f4.npy ] || python3 02_render_relief.py 4 clasico     # máscara de mar para 09
./05b_wikidata.sh
python3 09_select_labels.py          # rótulos automáticos con el mismo criterio en todo el mapa
for st in $STYLES; do
  if [ "$st" = "color" ]; then
    ./05_download_color.sh
    python3 06_landcover.py
    python3 07_satellite.py
    python3 08_color_base.py "$F"
  fi
  python3 02_render_relief.py "$F" "$st"
  python3 03_compose.py "$F" "$st"
done
