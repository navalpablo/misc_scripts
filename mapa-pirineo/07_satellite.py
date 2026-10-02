"""
07 · Mosaico Sentinel-2 cloudless 2023 (EOX) reproyectado al grid del mapa.

Entrada : s2/13_{x}_{y}.jpg  (teselas Web Mercator z13, ~14 m/px)
Salida  : work/s2_lcc.tif  (RGB uint8, 27 m/px, mismo grid que work/dem_lcc.tif)
"""
import glob, math, re
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from rasterio.windows import Window
from PIL import Image

Z = 13
files = glob.glob(f"s2/{Z}_*.jpg")
xy = np.array([list(map(int, re.findall(r"_(\d+)_(\d+)", f)[0])) for f in files])
x0, y0 = xy.min(0); x1, y1 = xy.max(0)
W, H = (x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256
R = 6378137.0
res = 2 * math.pi * R / (256 * 2 ** Z)
ox = -math.pi * R + x0 * 256 * res
oy = math.pi * R - y0 * 256 * res
tr = from_origin(ox, oy, res, res)
prof = dict(driver="GTiff", width=W, height=H, count=3, dtype="uint8", crs="EPSG:3857",
            transform=tr, tiled=True, blockxsize=256, blockysize=256, compress="deflate")
with rasterio.open("work/s2_3857.tif", "w", **prof) as d:
    for f, (x, y) in zip(files, xy):
        a = np.asarray(Image.open(f).convert("RGB")).transpose(2, 0, 1)
        d.write(a, window=Window((x - x0) * 256, (y - y0) * 256, 256, 256))
print("mosaico 3857", W, H)

ref = rasterio.open("work/dem_lcc.tif")
out = np.zeros((3, ref.height, ref.width), np.uint8)
with rasterio.open("work/s2_3857.tif") as s:
    for b in range(3):
        reproject(rasterio.band(s, b + 1), out[b], dst_transform=ref.transform, dst_crs=ref.crs,
                  resampling=Resampling.average, num_threads=2, warp_mem_limit=1024)
prof = dict(driver="GTiff", width=ref.width, height=ref.height, count=3, dtype="uint8",
            crs=ref.crs, transform=ref.transform, compress="deflate", tiled=True, photometric="RGB")
with rasterio.open("work/s2_lcc.tif", "w", **prof) as d:
    d.write(out)
print("ok", out.shape)
