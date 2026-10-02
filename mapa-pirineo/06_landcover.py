"""
06 · Cobertura del suelo ESA WorldCover 10 m (2021) reproyectada al grid del mapa (27 m).

Entrada : landcover/ESA_WorldCover_10m_2021_v200_*_Map.tif
Salida  : work/landcover_lcc.tif  (uint8, clases WorldCover; resampleo por moda)

Clases: 10 árbol · 20 matorral · 30 pasto/prado · 40 cultivo · 50 urbano · 60 suelo desnudo/roca
        70 nieve/hielo · 80 agua · 90 humedal · 95 manglar · 100 musgo/liquen
"""
import glob
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

ref = rasterio.open("work/dem_lcc.tif")
out = np.zeros((ref.height, ref.width), np.uint8)
for f in sorted(glob.glob("landcover/ESA_WorldCover_10m_2021_v200_*_Map.tif")):
    tmp = np.zeros_like(out)
    with rasterio.open(f) as s:
        reproject(rasterio.band(s, 1), tmp, src_nodata=0, dst_transform=ref.transform,
                  dst_crs=ref.crs, dst_nodata=0, resampling=Resampling.mode, num_threads=2,
                  warp_mem_limit=1024)
    out = np.where(out == 0, tmp, out)
    print(f.split("_")[-2], "ok")

prof = dict(driver="GTiff", width=ref.width, height=ref.height, count=1, dtype="uint8",
            crs=ref.crs, transform=ref.transform, nodata=0, compress="deflate", tiled=True)
with rasterio.open("work/landcover_lcc.tif", "w", **prof) as d:
    d.write(out, 1)
vals, cnt = np.unique(out, return_counts=True)
print({int(v): round(c / out.size * 100, 2) for v, c in zip(vals, cnt)})
