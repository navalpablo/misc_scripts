#!/usr/bin/env bash
# 00 · Descarga de datos reales (nada generado por IA)
#   - Copernicus DEM GLO-30 (tiles 1x1°) desde el bucket público de AWS
#   - Teselas vectoriales OpenMapTiles (datos © OpenStreetMap) desde OpenFreeMap, zoom 11
#   - Tipografías Cormorant Garamond, EB Garamond y Josefin Sans (OFL) desde google/fonts
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dem tiles fonts work output

echo "· DEM Copernicus GLO-30"
for lat in 41 42 43; do for lon in -3 -2 -1 0 1 2 3; do
  if [ $lon -lt 0 ]; then L=$(printf "W%03d" $((-lon))); else L=$(printf "E%03d" $lon); fi
  n="Copernicus_DSM_COG_10_N${lat}_00_${L}_00_DEM"
  [ -s dem/$n.tif ] || curl -sf -o dem/$n.tif "https://copernicus-dem-30m.s3.amazonaws.com/$n/$n.tif" || echo "  (sin tile $n: mar)"
done; done

echo "· Teselas OpenStreetMap (OpenFreeMap)"
python3 - <<'PY'
import math, os, json, subprocess, urllib.request, concurrent.futures as cf
Z = 11
tj = json.load(urllib.request.urlopen("https://tiles.openfreemap.org/planet"))
base = tj["tiles"][0].split("/{z}")[0]
def t(lon, lat):
    n = 2 ** Z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
x0, y0 = t(-2.2, 43.7); x1, y1 = t(3.6, 41.9)
jobs = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
def get(j):
    x, y = j; p = f"tiles/{Z}_{x}_{y}.pbf"
    if os.path.exists(p) and os.path.getsize(p) > 0: return 0
    return subprocess.run(["curl", "-sf", "--compressed", "-o", p, f"{base}/{Z}/{x}/{y}.pbf"]).returncode
with cf.ThreadPoolExecutor(6) as ex: print("  fallos:", sum(1 for r in ex.map(get, jobs) if r), "de", len(jobs))
PY

echo "· Tipografías"
B=https://raw.githubusercontent.com/google/fonts/main/ofl
for f in "cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf" "cormorantgaramond/CormorantGaramond-Italic%5Bwght%5D.ttf" \
         "ebgaramond/EBGaramond%5Bwght%5D.ttf" "ebgaramond/EBGaramond-Italic%5Bwght%5D.ttf" "josefinsans/JosefinSans%5Bwght%5D.ttf"; do
  n=$(basename "$f" | sed 's/%5B/[/;s/%5D/]/'); [ -s "fonts/$n" ] || curl -sfL -o "fonts/$n" "$B/$f"
done
echo "ok"
