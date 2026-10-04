"""
11 · Archivos de descarga de las láminas terminadas, para el visor web.

  - Lámina completa en JPEG de máxima calidad: 17.731 × 8.286 px, 301 ppp, calidad 95 sin
    submuestreo de color (4:4:4), JPEG básico (no progresivo) para que el visor pueda envolverlo
    tal cual en un PDF de imprenta de 150 × 70 cm sin recomprimir.
  - JPEG de pantalla: 7.680 px de ancho (8K), calidad 90.
  - Trozos de 14 MiB de la lámina completa («.parteN.jpg»): el visor de claude.ai solo sirve
    archivos de hasta 15 MB, así que el navegador los descarga y los vuelve a unir.

Uso: python3 11_descargas.py   ->  output/descargas/  y  output/descargas/descargas.json
"""
import hashlib, json, os
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
OUT = "output/descargas"
PART = 14 * 1024 * 1024
os.makedirs(OUT, exist_ok=True)
manifest = {}
for key, src, base in (("color", "output/pirineo_color_150cm.png", "pirineos_color"),
                       ("clasico", "output/pirineo_150cm.png", "pirineos_clasica")):
    im = Image.open(src).convert("RGB")
    W, H = im.size
    full = f"{OUT}/{base}_150x70cm.jpg"
    im.save(full, quality=95, subsampling=0, optimize=True, progressive=False, dpi=(301, 301))
    w2 = 7680
    scr = f"{OUT}/{base}_pantalla.jpg"
    im.resize((w2, round(H * w2 / W)), Image.LANCZOS).save(scr, quality=90, optimize=True, progressive=True,
                                                          dpi=(96, 96))
    del im
    data = open(full, "rb").read()
    parts = []
    for i in range(0, len(data), PART):
        name = f"{base}_150x70cm.parte{i // PART + 1}.jpg"
        open(f"{OUT}/{name}", "wb").write(data[i:i + PART])
        parts.append(name)
    manifest[key] = dict(full=os.path.basename(full), size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                         parts=parts, width=W, height=H, dpi=301,
                         screen=os.path.basename(scr), screen_size=os.path.getsize(scr),
                         screen_width=w2, screen_height=round(H * w2 / W))
    print(key, f"{len(data) / 1e6:.1f} MB en {len(parts)} trozos; pantalla {os.path.getsize(scr) / 1e6:.1f} MB")
json.dump(manifest, open(f"{OUT}/descargas.json", "w"), indent=1)
