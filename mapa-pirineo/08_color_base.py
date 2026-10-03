"""
08 · Color de base "natural" para la versión en color (antes del sombreado).

Combina, en espacio CIELAB:
  - las clases de ESA WorldCover (bosque, matorral, prado, cultivo, roca, urbano…) con una
    paleta cartográfica clara, ajustada por altitud (bosque de coníferas más oscuro arriba,
    pasto alpino más pardo);
  - el tono regional real de Sentinel-2 cloudless (secano del Ebro, verde atlántico,
    huertas y parcelas), aclarado y suavizado para impresión;
  - una capa de nieve calculada a partir del DEM: la cota de nieve baja en las caras norte
    y sube en las sur, no cuaja en paredes de más de ~45° y se acumula en canales.

Uso: python3 08_color_base.py [factor] [mezcla_satélite 0..1]
Salida: work/base_color_f{F}.png
"""
import sys
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window
from scipy import ndimage as nd
from skimage.color import rgb2lab, lab2rgb
from PIL import Image

F = int(sys.argv[1]) if len(sys.argv) > 1 else 4
SAT = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
SNOW_CREST_DROP = float(sys.argv[3]) if len(sys.argv) > 3 else 400.0   # m que baja la nieve en cumbres   # 0 = solo paleta · 1 = solo satélite

def sstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)

def C(*rgb): return np.array(rgb, np.float32) / 255
lowhigh = {   # clase: (color en llano, color en altura, cota_baja, cota_alta)
    10:  (C(134, 154, 104), C(110, 134, 102), 700, 1700),   # bosque: frondosas -> coníferas
    20:  (C(172, 170, 122), C(160, 156, 124), 600, 1800),  # matorral
    30:  (C(204, 208, 152), C(198, 190, 150), 900, 2200),  # prado -> pasto alpino
    40:  (C(228, 216, 168), C(222, 212, 168), 300, 1200),  # cultivo
    50:  (C(200, 184, 174), C(200, 184, 174), 0, 1),       # urbano
    60:  (C(224, 206, 172), C(214, 208, 198), 600, 1800),  # suelo desnudo: badlands -> roca
    70:  (C(250, 251, 253), C(250, 251, 253), 0, 1),       # nieve/hielo
    80:  (C(150, 178, 190), C(150, 178, 190), 0, 1),       # agua
    90:  (C(176, 190, 162), C(176, 190, 162), 0, 1),       # humedal
    95:  (C(150, 170, 140), C(150, 170, 140), 0, 1),
    100: (C(190, 188, 160), C(196, 194, 180), 1200, 2400), # musgo/liquen
}
snowc = np.array([97.5, -0.5, -2.5], np.float32)

def base_color(dem, lc, s2, pix):
    """Color de base para un bloque (dem float m, lc uint8 clases, s2 HxWx3 uint8)."""
    zs = nd.gaussian_filter(dem, 0.8 / F ** 0.5)
    gy, gx = np.gradient(zs, pix)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
    south = (-gy / (np.hypot(gx, gy) + 1e-6)).astype(np.float32)      # +1 cara sur, -1 cara norte
    del gx, gy
    tpi = (zs - nd.gaussian_filter(zs, 400 / pix)).astype(np.float32) # <0 canal, >0 cresta
    # posición relativa en su entorno (~3 km): 0 fondo de valle, 1 cumbre o cordal
    win = max(3, int(3000 / pix) | 1)
    zmax = nd.maximum_filter(zs, win); zmin = nd.minimum_filter(zs, win)
    rel = ((zs - zmin) / np.maximum(zmax - zmin, 50)).astype(np.float32)
    del zs, zmax, zmin
    pal = np.empty(dem.shape + (3,), np.float32)
    pal[:] = C(204, 208, 152)
    for k, (lo, hi, z0, z1) in lowhigh.items():
        m = lc == k
        if not m.any(): continue
        t = sstep(dem[m], z0, z1)[:, None]
        pal[m] = lo * (1 - t) + hi * t
    # por encima del límite del bosque, lo que no es bosque tiende a roca/pasto pedregoso
    alp = (sstep(dem, 2200, 2700) * (lc != 10))[..., None]
    pal = pal * (1 - 0.55 * alp) + C(206, 200, 190) * 0.55 * alp
    del alp
    sig = 1.2 / F                                   # transición suave entre clases
    if sig > 0.3:
        for i in range(3): pal[..., i] = nd.gaussian_filter(pal[..., i], sig)
    Lp = rgb2lab(pal).astype(np.float32); del pal
    Ls = rgb2lab(s2.astype(np.float32) / 255).astype(np.float32)
    # satélite: luminosidad comprimida y aclarada; menos contraste propio en montaña
    # (sus sombras vienen del SE y contradirían el sombreado del NO)
    flat = 1 - sstep(slope, 4, 18)
    Lsat = np.clip(74 + 0.55 * (Ls[..., 0] - 40) * (0.35 + 0.65 * flat), 52, 93)
    sat = np.stack([Lsat, Ls[..., 1] * 0.72, Ls[..., 2] * 0.72], -1); del Ls, Lsat
    w = np.array([SAT * 0.45, SAT, SAT], np.float32)     # el satélite aporta sobre todo el tono
    lab = Lp * (1 - w) + sat * w; del Lp, sat
    # ---- nieve (manto de final de primavera, derivado del relieve)
    zline = 2450 + 200 * south * sstep(slope, 3, 15)          # manto general: N ~2250 m · S ~2650 m
    snow = sstep(dem - zline, -110, 180)
    # en cumbres y cordales la nieve baja ~400 m más (N ~1850 m · S ~2250 m); fondos y laderas bajas, no
    crest = sstep(rel, 0.45, 0.8)
    snow = np.maximum(snow, sstep(dem - (zline - SNOW_CREST_DROP), -60, 200) * crest)
    snow *= 1 - 0.75 * sstep(slope, 38, 58)                   # paredes sin nieve
    snow = np.clip(snow + 0.35 * snow * np.tanh(-tpi / 40), 0, 1)  # canales con más nieve
    lab = lab * (1 - snow[..., None]) + snowc * snow[..., None]
    rgb = np.clip(lab2rgb(lab.astype(np.float64)), 0, 1)
    return (rgb * 255 + 0.5).astype(np.uint8)

with rasterio.open("work/dem_lcc.tif") as sd, rasterio.open("work/landcover_lcc.tif") as sl_, \
     rasterio.open("work/s2_lcc.tif") as ss:
    H, W = sd.height // F, sd.width // F
    pix = sd.transform.a * (sd.width / W)
    print(f"factor {F}: {W}x{H}")
    base = np.empty((H, W, 3), np.uint8)
    if F > 1:
        dem = sd.read(1, out_shape=(H, W), resampling=Resampling.average)
        lc = sl_.read(1, out_shape=(H, W), resampling=Resampling.mode)
        s2 = ss.read(out_shape=(3, H, W), resampling=Resampling.average).transpose(1, 2, 0)
        dem[dem < -9000] = 0
        base[:] = base_color(dem, lc, s2, pix)
    else:
        STEP, M = 700, 90                        # franjas con margen para los filtros
        for r0 in range(0, H, STEP):
            r1 = min(H, r0 + STEP); m0, m1 = max(0, r0 - M), min(H, r1 + M)
            win = Window(0, m0, W, m1 - m0)
            dem = sd.read(1, window=win); dem[dem < -9000] = 0
            lc = sl_.read(1, window=win)
            s2 = ss.read(window=win).transpose(1, 2, 0)
            base[r0:r1] = base_color(dem, lc, s2, pix)[r0 - m0:r0 - m0 + (r1 - r0)]
            print(f"  filas {r0}-{r1}", flush=True)

Image.fromarray(base).save(f"work/base_color_f{F}.png")
print("ok")
