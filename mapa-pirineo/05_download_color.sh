#!/usr/bin/env bash
# 05 · Datos para la versión en color natural
#   - ESA WorldCover 10 m v200 (2021), tiles 3x3°   (CC BY 4.0)
#   - Sentinel-2 cloudless 2023 de EOX, teselas z13  (CC BY-NC-SA 4.0, uso no comercial)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p landcover s2
for t in N39W003 N39E000 N39E003 N42W003 N42E000 N42E003; do
  f="landcover/ESA_WorldCover_10m_2021_v200_${t}_Map.tif"
  [ -s "$f" ] || curl -sf -o "$f" "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_${t}_Map.tif" &
done
python3 - <<'PY'
import math, os, subprocess, concurrent.futures as cf
Z = 13
def t(lon, lat):
    n = 2 ** Z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
x0, y0 = t(-2.15, 43.65); x1, y1 = t(3.55, 41.93)
jobs = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
base = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2023_3857/default/g"
def get(j):
    x, y = j; p = f"s2/{Z}_{x}_{y}.jpg"
    if os.path.exists(p) and os.path.getsize(p) > 0: return 0
    for _ in range(3):
        if subprocess.run(["curl", "-sf", "--max-time", "60", "-o", p, f"{base}/{Z}/{y}/{x}.jpg"]).returncode == 0:
            return 0
    return 1
with cf.ThreadPoolExecutor(6) as ex:
    print("S2 teselas:", len(jobs), "fallos:", sum(ex.map(get, jobs)))
PY
wait
ls -la landcover
