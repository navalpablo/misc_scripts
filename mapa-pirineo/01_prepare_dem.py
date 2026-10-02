"""
01 · Mosaico y reproyección del DEM Copernicus GLO-30 para el Pirineo.

Entrada : dem/Copernicus_DSM_COG_10_*.tif  (tiles 1x1°, 30 m, de s3://copernicus-dem-30m)
Salida  : work/dem_lcc.tif  (cónica conforme de Lambert centrada en el Pirineo)

La proyección LCC con meridiano central 0.7°E evita que la cordillera
salga girada (en UTM 30/31 el extremo opuesto aparece rotado ~3°).
"""
import glob, os
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling, transform as tx
from rasterio.transform import from_origin
from rasterio.crs import CRS

PIX = float(os.environ.get("PIX", 27.0))     # m/píxel del mapa final (~300 dpi a 150 cm)
LON0, LON1 = -2.05, 3.42                      # de Donostia al Cap de Creus
LAT0, LAT1 = 42.02, 43.56

DST = CRS.from_proj4("+proj=lcc +lat_1=42.2 +lat_2=43.2 +lat_0=42.7 +lon_0=0.72 "
                     "+x_0=0 +y_0=0 +ellps=GRS80 +units=m +no_defs")

os.makedirs("work", exist_ok=True)
srcs = [rasterio.open(p) for p in sorted(glob.glob("dem/*.tif"))]
mosaic, mtr = merge(srcs, nodata=-9999, bounds=(LON0 - 0.25, 41.90, LON1 + 0.25, LAT1 + 0.15))
src_crs = srcs[0].crs
mosaic = mosaic[0].astype(np.float32)
print("mosaico", mosaic.shape)

# Caja de destino: x desde los extremos lon a lat media; y desde LAT0/LAT1 en el meridiano central
xs, _ = tx("EPSG:4326", DST, [LON0, LON1], [42.72, 42.72])
_, ys = tx("EPSG:4326", DST, [0.72, 0.72], [LAT0, LAT1])
x0, x1 = xs; y0, y1 = ys
W = int(round((x1 - x0) / PIX)); H = int(round((y1 - y0) / PIX))
print(f"destino {W} x {H} px  ({(x1-x0)/1000:.0f} x {(y1-y0)/1000:.0f} km)")
dtr = from_origin(x0, y1, PIX, PIX)
out = np.full((H, W), -9999, np.float32)
reproject(mosaic, out, src_transform=mtr, src_crs=src_crs, src_nodata=-9999,
          dst_transform=dtr, dst_crs=DST, dst_nodata=-9999,
          resampling=Resampling.cubic, num_threads=2)
prof = dict(driver="GTiff", width=W, height=H, count=1, dtype="float32", crs=DST,
            transform=dtr, nodata=-9999, compress="deflate", predictor=3, tiled=True)
with rasterio.open("work/dem_lcc.tif", "w", **prof) as d:
    d.write(out, 1)
v = out[out > -9000]
print("min/max", v.min(), v.max())
