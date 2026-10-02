"""
02 · Render del relieve sombreado del Pirineo.

Todo sale del DEM real (Copernicus GLO-30). Nada generado por IA:
  - sombreado multidireccional (luz principal NO, convención cartográfica)
  - sombreado por pendiente y "oclusión" de valles (DEM - DEM suavizado)
  - tintas hipsométricas por cota
  - perspectiva aérea: las zonas bajas se velan ligeramente
  - lagos y embalses: Copernicus aplana las láminas de agua a cota constante,
    así que se detectan como zonas perfectamente planas del propio DEM.

Uso: python3 02_render_relief.py [factor]   (factor 1 = resolución completa; 4 = vista previa)
Salida: work/relief_f{factor}.png  + work/mask_water_f{factor}.npy
"""
import sys
import numpy as np
import rasterio
from rasterio.enums import Resampling
from scipy import ndimage as nd
from PIL import Image

F = int(sys.argv[1]) if len(sys.argv) > 1 else 4
Z = 1.7            # exageración vertical del sombreado (no de la geometría)

with rasterio.open("work/dem_lcc.tif") as src:
    H, W = src.height // F, src.width // F
    dem = src.read(1, out_shape=(H, W), resampling=Resampling.average if F > 1 else Resampling.nearest)
    pix = src.transform.a * (src.width / W)
print(f"factor {F}: {W}x{H}, {pix:.1f} m/px")

nodata = dem < -9000
dem[nodata] = 0
# ---- mar: cota <=0 conectada al borde del mapa
low = dem <= 0.5
lab, n = nd.label(low)
edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
sea = np.isin(lab, edge[edge > 0])
del lab, low
dem[sea] = 0

# ---- lagos y embalses: zonas planas (rango 3x3 < 5 cm) de cierto tamaño
rng = nd.maximum_filter(dem, 3)
rng -= nd.minimum_filter(dem, 3)
flat = (rng < 0.05) & ~sea
del rng
flat = nd.binary_opening(flat, iterations=1)
lab, n = nd.label(flat)
sizes = nd.sum(flat, lab, index=np.arange(1, n + 1))
min_px = max(8, int(0.06e6 / pix**2))      # >= 6 ha
keep = np.zeros(n + 1, bool); keep[1:] = sizes >= min_px
water = keep[lab]
water = nd.binary_closing(water, iterations=1) & ~sea
del lab, flat
print("lagos/embalses detectados:", int(keep.sum()))
np.save(f"work/mask_water_f{F}.npy", water)
np.save(f"work/mask_sea_f{F}.npy", sea)

# ---- sombreado multidireccional
def hillshade(z, az, alt):
    gy, gx = np.gradient(z * Z, pix)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    azr, altr = np.radians(360 - az + 90), np.radians(alt)
    return (np.sin(altr) * np.cos(slope) +
            np.cos(altr) * np.sin(slope) * np.cos(azr - aspect)).clip(0, 1).astype(np.float32)

# suavizado ligero para que a 27 m el detalle no parezca "ruido" de DSM (bosques, edificios)
zs = nd.gaussian_filter(dem, 0.8 if F == 1 else 0.4).astype(np.float32)

# oclusión de valles: posición topográfica relativa a ~1.2 km y ~5 km (calculada a 1/4)
def blur_big(z, meters):
    q = max(1, 4 // F) if F < 4 else 1
    small = z[::q, ::q] if q > 1 else z
    b = nd.gaussian_filter(small, meters / (pix * q))
    if q > 1:
        b = nd.zoom(b, (z.shape[0] / b.shape[0], z.shape[1] / b.shape[1]), order=1)
    return b.astype(np.float32)
q4 = 4 if F == 1 else 1
t = np.tanh((zs - blur_big(zs, 1200)) / 250) * 0.6
t += np.tanh((zs - blur_big(zs, 5000)) / 600) * 0.4
occl = (0.5 + 0.5 * t).astype(np.float32)   # 0 valle hondo, 1 cresta
del t

# distancia a la costa (a 1/4 de resolución basta: las líneas de agua son suaves)
q = 4 if F == 1 else 1
dist = nd.distance_transform_edt(sea[::q, ::q]).astype(np.float32) * pix * q
if q > 1:
    dist = nd.zoom(dist, (H / dist.shape[0], W / dist.shape[1]), order=1)[:H, :W]

stops = [  # cota m, color  (paleta sobria, de papel)
    (0,    (226, 229, 210)),
    (200,  (224, 228, 204)),
    (500,  (232, 230, 202)),
    (900,  (238, 230, 196)),
    (1300, (238, 220, 184)),
    (1700, (230, 205, 174)),
    (2100, (218, 194, 172)),
    (2500, (212, 202, 196)),
    (2800, (228, 226, 226)),
    (3100, (246, 246, 246)),
    (3500, (255, 255, 255)),
]
zz = np.array([s[0] for s in stops], np.float32)
cc = np.array([s[1] for s in stops], np.float32) / 255
gam = np.array([1.12, 1.08, 0.90], np.float32)     # sombras frías
lake = np.array([0.62, 0.72, 0.76], np.float32)
seac = np.array([0.80, 0.85, 0.86], np.float32)
water_edge = water & ~nd.binary_erosion(water, iterations=max(1, 2 // F))
coast = sea & ~nd.binary_erosion(sea, iterations=max(1, 3 // F))

def render(r0, r1):
    """Renderiza las filas r0:r1 (con margen para los gradientes)."""
    m0, m1 = max(0, r0 - 2), min(H, r1 + 2)
    z = zs[m0:m1]
    hs = (0.55 * hillshade(z, 315, 42) + 0.20 * hillshade(z, 270, 50) +
          0.15 * hillshade(z, 0, 50) + 0.10 * hillshade(z, 225, 60))
    gy, gx = np.gradient(z, pix)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    sl = slice(r0 - m0, r0 - m0 + (r1 - r0))
    hs, slope = hs[sl], slope[sl]
    d = dem[r0:r1]
    rgb = np.empty(d.shape + (3,), np.float32)
    for i in range(3):
        rgb[..., i] = np.interp(d, zz, cc[:, i])
    rock = (np.clip((slope - 32) / 20, 0, 1) * np.clip((d - 900) / 600, 0, 1))[..., None]
    rgb = rgb * (1 - 0.35 * rock) + np.array([0.80, 0.78, 0.76], np.float32) * 0.35 * rock
    shade = hs / np.sin(np.radians(45))
    shade = np.clip(1.0 + 0.78 * (shade - 1), 0.30, 1.25) * (0.90 + 0.12 * occl[r0:r1])
    light = shade[..., None]
    out = rgb * np.clip(light, 0.05, 1.0) ** gam
    out = out + (1 - out) * np.clip(light - 1, 0, None) * 1.6
    haze = (np.clip(1 - d / 1800, 0, 1) ** 2 * 0.10)[..., None]
    out = out * (1 - haze) + np.array([0.93, 0.93, 0.90], np.float32) * haze
    # agua
    w = water[r0:r1]; out[w] = lake; out[water_edge[r0:r1]] = lake * 0.82
    s_ = sea[r0:r1]; ds = dist[r0:r1]
    lines = np.zeros(ds.shape, bool)
    for k, dkm in enumerate([0.6, 1.4, 2.4, 3.6, 5.0, 6.6]):
        lines |= np.abs(ds - dkm * 1000) < (90 + 10 * k) / 2 * max(1, F / 2)
    fade = np.clip(1 - ds / 8000, 0, 1)
    sea_rgb = np.broadcast_to(seac, out.shape).copy()
    sea_rgb[lines] = seac * (1 - 0.10 * fade[lines][:, None])
    out[s_] = sea_rgb[s_]
    out[coast[r0:r1]] = seac * 0.70
    out[(nodata[r0:r1]) & ~s_] = seac
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)

img = np.empty((H, W, 3), np.uint8)
STEP = 600
for r in range(0, H, STEP):
    img[r:r + STEP] = render(r, min(H, r + STEP))
    print(f"  filas {r}-{min(H, r + STEP)}", flush=True)
Image.fromarray(img).save(f"work/relief_f{F}.png")
print("ok", img.shape)
