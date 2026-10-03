"""
10 · Teselas Deep Zoom (DZI) para ver la lámina completa en el navegador con OpenSeadragon.

Uso: python3 10_deepzoom.py <png> <nombre> [carpeta_salida]
Genera <salida>/<nombre>.dzi y <salida>/<nombre>_files/<nivel>/<col>_<fila>.jpg
(teselas de 2048 px, JPEG calidad 82, sin solape).
"""
import math, os, sys
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SRC, NAME = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else "web"
TILE, Q = 2048, 82

im = Image.open(SRC).convert("RGB")
W, H = im.size
maxlvl = math.ceil(math.log2(max(W, H)))
os.makedirs(f"{OUT}/{NAME}_files", exist_ok=True)
with open(f"{OUT}/{NAME}.dzi", "w") as f:
    f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<Image xmlns="http://schemas.microsoft.com/deepzoom/2008" Format="jpg" Overlap="0" TileSize="{TILE}">'
            f'<Size Width="{W}" Height="{H}"/></Image>\n')
n = 0
cur = im
for lvl in range(maxlvl, -1, -1):
    s = 2 ** (maxlvl - lvl)
    w, h = max(1, math.ceil(W / s)), max(1, math.ceil(H / s))
    if cur.size != (w, h):
        cur = cur.resize((w, h), Image.LANCZOS)
    d = f"{OUT}/{NAME}_files/{lvl}"
    os.makedirs(d, exist_ok=True)
    for cx in range(math.ceil(w / TILE)):
        for cy in range(math.ceil(h / TILE)):
            box = (cx * TILE, cy * TILE, min(w, (cx + 1) * TILE), min(h, (cy + 1) * TILE))
            cur.crop(box).save(f"{d}/{cx}_{cy}.jpg", quality=Q, optimize=True, progressive=True)
            n += 1
print(NAME, f"{W}x{H}", "niveles", maxlvl + 1, "teselas", n)
