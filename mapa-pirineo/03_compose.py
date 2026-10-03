"""
03 · Composición final para imprimir: paspartú, marco, gratícula, rotulación y cartela.

Entrada : work/relief[_color]_f{F}.png, work/dem_lcc.tif
Uso     : python3 03_compose.py [factor] [clasico|color]
Salida  : output/pirineo_150cm.png / .tif  (F=1)   o  work/compose_f{F}.png (vista previa)
Requiere haber ejecutado antes 01, 02 y 04.

Mapa de 140 cm de ancho dentro de una lámina de 150 cm (~301 ppp).
"""
import sys, os
import numpy as np
import rasterio
from rasterio.warp import transform as tx
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from places import PEAKS, TOWNS, AREAS, RIVERS, RESERVOIRS, VALLEYS, POIS
import re
import linework

Image.MAX_IMAGE_PIXELS = None
F = int(sys.argv[1]) if len(sys.argv) > 1 else 4
STYLE = sys.argv[2] if len(sys.argv) > 2 else "clasico"   # "clasico" | "color"
SUFFIX = "" if STYLE == "clasico" else "_color"
S = 1 / F                                     # escala de todo lo dibujado

relief = Image.open(f"work/relief{SUFFIX}_f{F}.png").convert("RGB")
MW, MH = relief.size
src = rasterio.open("work/dem_lcc.tif")
dem = src.read(1, out_shape=(MH, MW))
SX = src.width / MW

# ---------------- lámina
PAPER = (244, 240, 230)
INK = (58, 52, 46)
INK_SOFT = (96, 88, 78)
WATER_INK = (70, 108, 124)
MARGIN = int(570 * S)
BAND = int(1380 * S)
CW, CH = MW + 2 * MARGIN, MH + MARGIN + BAND
canvas = Image.new("RGB", (CW, CH), PAPER)
canvas.paste(relief, (MARGIN, MARGIN))
del relief
OX, OY = MARGIN, MARGIN

# ---------------- hidrografía, carreteras y frontera (OpenStreetMap)
sea_mask = np.load(f"work/mask_sea_f{F}.npy")
river_geo = linework.draw_all(canvas, OX, OY, F, MW, MH, sea_mask=sea_mask)
del sea_mask

FD = "fonts/"
def font(name, size, wght=None):
    f = ImageFont.truetype(FD + name, max(6, int(size * S)))
    if wght is not None:
        try: f.set_variation_by_axes([wght])
        except Exception: pass
    return f
SERIF = "CormorantGaramond[wght].ttf"
SERIF_I = "CormorantGaramond-Italic[wght].ttf"
EB = "EBGaramond[wght].ttf"
EB_I = "EBGaramond-Italic[wght].ttf"
SANS = "JosefinSans[wght].ttf"

def ll2px(lon, lat):
    xs, ys = tx("EPSG:4326", src.crs, [lon], [lat])
    r, c = src.index(xs[0], ys[0])
    return c / SX, r / SX

# ---------------- capas de texto: halo (papel difuminado) + tinta por color
halo = Image.new("L", (CW, CH), 0)
hd = ImageDraw.Draw(halo)
layers = {}
def layer(color):
    if color not in layers:
        im = Image.new("L", (CW, CH), 0)
        layers[color] = (im, ImageDraw.Draw(im))
    return layers[color][1]

def text_size(txt, f, tracking=0):
    if tracking == 0:
        b = f.getbbox(txt); return b[2] - b[0], b[3] - b[1], b
    w = sum(f.getlength(ch) for ch in txt) + tracking * S * (len(txt) - 1)
    b = f.getbbox("H"); return w, b[3] - b[1], (0, b[1], w, b[3])

BOXES = []        # cajas ya ocupadas (rótulos y símbolos) en coordenadas de lámina

def put_text(x, y, txt, f, color, anchor="lm", tracking=0, halo_w=10, rotate=0, reg=True):
    """Dibuja texto (con espaciado opcional) y su halo. x, y en coordenadas de lámina."""
    w, h, b = text_size(txt, f, tracking)
    ax = {"l": 0, "m": -w / 2, "r": -w}[anchor[0]]
    ay = {"t": -b[1], "m": -(b[1] + b[3]) / 2, "b": -b[3]}[anchor[1]]
    if reg and not rotate:
        BOXES.append((x + ax, y + ay + b[1], x + ax + w, y + ay + b[3]))
    hw = int(halo_w * S)
    if rotate:
        pad = hw * 3 + 4
        tw, th = int(w + 2 * pad), int(b[3] + 2 * pad)
        ti = Image.new("L", (tw, th), 0); hi = Image.new("L", (tw, th), 0)
        _draw_run(ImageDraw.Draw(ti), ImageDraw.Draw(hi), pad, pad, txt, f, tracking, hw)
        ti = ti.rotate(rotate, expand=True, resample=Image.BICUBIC)
        hi = hi.rotate(rotate, expand=True, resample=Image.BICUBIC)
        px, py = int(x - ti.width / 2), int(y - ti.height / 2)
        layer(color)
        layers[color][0].paste(ti, (px, py), ti)
        halo.paste(hi, (px, py), hi)
        return
    _draw_run(layer(color), hd, x + ax, y + ay, txt, f, tracking, hw)

def _draw_run(td, hdraw, x, y, txt, f, tracking, hw):
    if tracking == 0:
        if hw > 0: hdraw.text((x, y), txt, font=f, fill=255, stroke_width=hw, stroke_fill=255)
        td.text((x, y), txt, font=f, fill=255)
        return
    cx = x
    for ch in txt:
        if hw > 0: hdraw.text((cx, y), ch, font=f, fill=255, stroke_width=hw, stroke_fill=255)
        td.text((cx, y), ch, font=f, fill=255)
        cx += f.getlength(ch) + tracking * S

def offset(pos, d):
    return {"r": (d, 0, "lm"), "l": (-d, 0, "rm"), "t": (0, -d, "mb"), "b": (0, d, "mt"),
            "tr": (d * .7, -d * .7, "lb"), "tl": (-d * .7, -d * .7, "rb"),
            "br": (d * .7, d * .7, "lt"), "bl": (-d * .7, d * .7, "rt")}[pos]

def river_label(c, s_mid, txt, f, color, gap, tracking=0, halo_w=8):
    adv = [f.getlength(ch) + tracking * S for ch in txt]
    L = sum(adv) - tracking * S
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
    for span in (0.85, 1.15, 1.5):
        for shift in (0, -0.6, 0.6, -1.2, 1.2, -2.0, 2.0):
            if seg[-1] < 1.05 * L:
                return False
            sm = float(np.clip(s_mid + shift * L, 0.55 * L, seg[-1] - 0.55 * L))
            if _river_label(c, sm, txt, f, color, gap, tracking, halo_w, span):
                return True
    return False

def _river_label(c, s_mid, txt, f, color, gap, tracking, halo_w, span):
    """Rótulo de río a lo largo de una curva suave (parábola ajustada al cauce en el
    tramo del rótulo), desplazada para no tocar el cauce. c: polilínea en px de lámina."""
    adv = [f.getlength(ch) + tracking * S for ch in txt]
    L = sum(adv) - tracking * S
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
    tt = np.arange(max(0, s_mid - span * L), min(seg[-1], s_mid + span * L), 1.5)
    sub = np.column_stack([np.interp(tt, seg, c[:, 0]), np.interp(tt, seg, c[:, 1])])
    if len(sub) < 10:
        return False
    m = sub.mean(0)
    _, _, vt = np.linalg.svd(sub - m, full_matrices=False)
    d = vt[0]
    if d[0] < 0 or (abs(d[0]) < 0.25 and d[1] > 0):   # leer de izq. a dcha. (o de abajo arriba)
        d = -d
    n = np.array([d[1], -d[0]])                         # normal "hacia arriba"/izquierda
    u = (sub - m) @ d; v = (sub - m) @ n
    if u.max() - u.min() < L * 1.02:
        return False
    if span > 0.85 and np.ptp(v) > 0.45 * L:            # demasiado sinuoso para un rótulo limpio
        return False
    A, B, C = np.polyfit(u, v, 2)
    lim = 0.10 * L / (L / 2) ** 2                       # flecha máxima 10 % de la longitud
    A = float(np.clip(A, -lim, lim))
    B, C = np.polyfit(u, v - A * u ** 2, 1)
    r = v - (A * u ** 2 + B * u + C)
    cap = f.getbbox("H")[3] - f.getbbox("H")[1]
    asc = -f.getbbox("x")[1] + f.getbbox("x")[3]
    up = r.max() + gap
    down = -r.min() + gap + cap
    side = 1 if up <= down * 1.35 else -1
    off = up if side == 1 else -down
    # centro del rótulo: proyección del punto s_mid
    pm = np.array([np.interp(s_mid, seg, c[:, 0]), np.interp(s_mid, seg, c[:, 1])])
    u0 = float(np.clip((pm - m) @ d, u.min() + L / 2, u.max() - L / 2))
    uu = np.linspace(u0 - L, u0 + L, 800)
    vv = A * uu ** 2 + B * uu + C + off
    P = m + np.outer(uu, d) + np.outer(vv, n)
    ss = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    smid = np.interp(u0, uu, ss)
    pos = smid - L / 2
    hw = int(halo_w * S)
    for ch, a_ in zip(txt, adv):
        sc_ = pos + (a_ - tracking * S) / 2
        pos += a_
        if ch == " ":
            continue
        x = np.interp(sc_, ss, P[:, 0]); y = np.interp(sc_, ss, P[:, 1])
        x2 = np.interp(sc_ + 2, ss, P[:, 0]); y2 = np.interp(sc_ + 2, ss, P[:, 1])
        x1 = np.interp(sc_ - 2, ss, P[:, 0]); y1 = np.interp(sc_ - 2, ss, P[:, 1])
        ang = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        pad_ = hw * 2 + int(cap) + 6
        size = int(f.getlength(ch) + 2 * pad_)
        ti = Image.new("L", (size, size), 0); hi = Image.new("L", (size, size), 0)
        o = (size / 2, size / 2)
        ImageDraw.Draw(ti).text(o, ch, font=f, fill=255, anchor="ms")
        if hw > 0:
            ImageDraw.Draw(hi).text(o, ch, font=f, fill=255, anchor="ms", stroke_width=hw, stroke_fill=255)
        ti = ti.rotate(-ang, center=o, resample=Image.BICUBIC)
        hi = hi.rotate(-ang, center=o, resample=Image.BICUBIC)
        X, Y = int(round(x - o[0])), int(round(y - o[1]))
        BOXES.append((x - a_ / 2, y - cap * 1.05, x + a_ / 2, y + cap * 0.3))
        layer(color); layers[color][0].paste(ti, (X, Y), ti)
        if hw > 0: halo.paste(hi, (X, Y), hi)
    return True

symbols = []   # (tipo, x, y) se dibujan sobre el relieve con antialias via supersample

# ---------------- áreas (debajo del resto)
for txt, lon, lat, style in AREAS:
    x, y = ll2px(lon, lat); x += OX; y += OY
    if style == "country":
        put_text(x, y, txt, font(SERIF, 150, 500), (110, 100, 90) if STYLE == "clasico" else (84, 76, 68), "mm",
                 tracking=120, halo_w=0 if STYLE == "clasico" else 7)
    elif style == "small_country":
        put_text(x, y, txt, font(SERIF, 78, 600), (110, 100, 90), "mm", tracking=48, halo_w=8)
    elif style == "valley":
        put_text(x, y, txt, font(EB_I, 58, 420), INK_SOFT, "mm", tracking=8, halo_w=8)
    elif style == "sea":
        put_text(x, y, txt, font(EB_I, 80, 420), WATER_INK, "mm", tracking=18, halo_w=0)
# Mediterráneo, en vertical sobre el mar
mx, my = ll2px(3.30, 42.45)
put_text(mx + OX, my + OY, "Mar Mediterráneo", font(EB_I, 80, 420), WATER_INK, "mm",
         tracking=14, halo_w=0, rotate=90)

# ---------------- valles largos y estrechos: rótulo a lo largo del río que los recorre
def label_along_river(label, axis, lon, lat, fnt, color, tracking, gap, halo_w):
    """Rótulo curvo a lo largo de un río OSM (regex) o de un eje de valle dado como [(lon, lat), ...]."""
    ax_, ay_ = ll2px(lon, lat)
    L = sum(fnt.getlength(ch) + tracking * S for ch in label)
    cands = []
    if isinstance(axis, str):
        for name, items in river_geo.items():
            if not re.search(axis, name): continue
            for c, w, a in items:
                cc_ = c * S
                seg = np.r_[0, np.cumsum(np.hypot(*np.diff(cc_, axis=0).T))]
                dd = np.hypot(cc_[:, 0] - ax_, cc_[:, 1] - ay_)
                j = int(dd.argmin())
                cands.append((dd[j], cc_, seg, j, w))       # tramo más cercano, aunque sea corto
    else:
        cc_ = np.array([ll2px(lo, la) for lo, la in axis], float)
        seg = np.r_[0, np.cumsum(np.hypot(*np.diff(cc_, axis=0).T))]
        tt = np.arange(0, seg[-1], 2.0)
        cc_ = np.column_stack([np.interp(tt, seg, cc_[:, 0]), np.interp(tt, seg, cc_[:, 1])])
        seg = tt
        dd = np.hypot(cc_[:, 0] - ax_, cc_[:, 1] - ay_)
        cands.append((dd.min(), cc_, seg, int(dd.argmin()), np.zeros(len(cc_))))
    cands.sort(key=lambda t: t[0])
    if not cands or cands[0][0] > 700 * S:
        print("  sin eje para", label); return False
    _, cc_, seg, j, w = cands[0]
    s_mid = float(np.clip(seg[j], 0.55 * L, seg[-1] - 0.55 * L))
    wj = w[min(len(w) - 1, int(np.searchsorted(seg, s_mid)))]
    ok = seg[-1] >= L * 1.1 and river_label(cc_ + np.array([OX, OY]), s_mid, label, fnt, color,
                     gap=wj * S / 2 + gap * S, tracking=tracking, halo_w=halo_w)
    if not ok:
        # valle corto: rótulo recto centrado sobre el eje, en la misma letra
        if isinstance(axis, str):      # junto al río, a la altura del punto indicado
            put_text(cc_[j, 0] + OX + wj * S / 2 + 16 * S, cc_[j, 1] + OY, label, fnt, color, "lm",
                     tracking=tracking, halo_w=halo_w)
        else:                          # sin río dibujado: centrado sobre el eje del valle
            m = len(cc_) // 2
            put_text(cc_[m, 0] + OX, cc_[m, 1] + OY - 4 * S, label, fnt, color, "mm", tracking=tracking, halo_w=halo_w)
        print("  rótulo recto para", label)
    return True

fv1, fv2 = font(EB_I, 58, 420), font(EB_I, 44, 430)
for label, axis, lon, lat, size in VALLEYS:
    if size == 1:
        label_along_river(label, axis, lon, lat, fv1, INK_SOFT, 8, 22, 8)
    else:
        label_along_river(label, axis, lon, lat, fv2, INK_SOFT, 5, 14, 7)

# ---------------- nombres de ríos
RIVER_INK = (52, 96, 126)
for label, pat, lon, lat, rank in RIVERS:
    ax_, ay_ = ll2px(lon, lat)
    fr = font(EB_I, 54 if rank == 1 else 46, 460)
    L = sum(fr.getlength(ch) + 6 * S for ch in label)
    cands = []
    for name, items in river_geo.items():
        if not re.search(pat, name): continue
        for c, w, a in items:
            cc_ = c * S
            seg = np.r_[0, np.cumsum(np.hypot(*np.diff(cc_, axis=0).T))]
            if seg[-1] < L * 1.3: continue
            dd = np.hypot(cc_[:, 0] - ax_, cc_[:, 1] - ay_)
            j = int(dd.argmin())
            cands.append((dd[j], cc_, seg, j, w))
    cands.sort(key=lambda t: t[0])
    if not cands or cands[0][0] > 700 * S:
        print("  sin río para", label, None if not cands else round(cands[0][0] / S)); continue
    _, cc_, seg, j, w = cands[0]
    s_mid = float(np.clip(seg[j], 0.85 * L, seg[-1] - 0.85 * L))
    wj = w[min(len(w) - 1, int(np.searchsorted(seg, s_mid)))]
    if not river_label(cc_ + np.array([OX, OY]), s_mid, label, fr, RIVER_INK,
                       gap=wj * S / 2 + 14 * S, tracking=8, halo_w=7):
        print("  río demasiado corto para el rótulo:", label)

# ---------------- colocación de rótulos puntuales sin solapes
MAPBOX = (OX, OY, OX + MW, OY + MH)
PAD = 6 * S

def overlap(box):
    x0, y0, x1, y1 = box[0] - PAD, box[1] - PAD, box[2] + PAD, box[3] + PAD
    tot = 0.0
    for b0, b1, b2, b3 in BOXES:
        w = min(x1, b2) - max(x0, b0); h = min(y1, b3) - max(y0, b1)
        if w > 0 and h > 0: tot += w * h
    # fuera del marco del mapa: penalización fuerte
    out = (max(0, MAPBOX[0] - box[0]) + max(0, box[2] - MAPBOX[2]) +
           max(0, MAPBOX[1] - box[1]) + max(0, box[3] - MAPBOX[3]))
    return tot + out * 1e4

def line_metrics(f):
    bb = f.getbbox("Hg"); return bb[1], bb[3]

def place_block(cands, lines, halo_w=10):
    """cands: [(x, y, anchor)] en orden de preferencia; lines: [(texto, fuente, color, tracking)].
    Coloca el bloque de líneas en el primer candidato libre (o en el de menor solape)."""
    ws = [text_size(t, f, tr)[0] for t, f, c, tr in lines]
    mets = [line_metrics(f) for t, f, c, tr in lines]
    hs = [m1 - m0 for m0, m1 in mets]
    gap = -0.08 * max(hs)
    BW = max(ws); BH = sum(hs) + gap * (len(lines) - 1)
    best = None
    for x, y, anc in cands:
        bx = {"l": x, "m": x - BW / 2, "r": x - BW}[anc[0]]
        by = {"t": y, "m": y - BH / 2, "b": y - BH}[anc[1]]
        box = (bx, by, bx + BW, by + BH)
        ov = overlap(box)
        if best is None or ov < best[0]:
            best = (ov, bx, by, anc, box)
        if ov == 0:
            break
    ov, bx, by, anc, box = best
    cy = by
    for (t, f, c, tr), w, (m0, m1), hh in zip(lines, ws, mets, hs):
        lx = {"l": bx, "m": bx + (BW - w) / 2, "r": bx + BW - w}[anc[0]]
        _draw_run(layer(c), hd, lx - (f.getbbox(t)[0] if tr == 0 else 0), cy - m0, t, f, tr, int(halo_w * S))
        cy += hh + gap
    BOXES.append(box)
    return ov

ORDER = ["r", "l", "t", "b", "tr", "tl", "br", "bl"]
def point_cands(x, y, pref, d):
    out = []
    for p in [pref] + [q for q in ORDER if q != pref]:
        dx, dy, anc = offset(p, d)
        out.append((x + dx, y + dy, anc))
    return out

# posiciones de todos los símbolos primero, para que ningún rótulo los tape
R = max(3, int(45 / SX))
peak_pts = []
for name, h, lon, lat, pos in PEAKS:
    x, y = ll2px(lon, lat)
    c, r = int(round(x)), int(round(y))
    w = dem[r - R:r + R, c - R:c + R]
    i, j = np.unravel_index(np.argmax(w), w.shape)    # cima ajustada al máximo real del DEM (~1.2 km)
    peak_pts.append((name, h, c - R + j + OX, r - R + i + OY, pos))
def pop_t(pop):
    """0 para municipios de ~250 hab., 1 para ~200.000 hab. (escala logarítmica)."""
    return float(np.clip((np.log10(max(pop, 1)) - 2.4) / 2.9, 0, 1))
def muni_radius(pop):
    return 7.5 + 10.5 * pop_t(pop)            # px a resolución completa
town_pts = []
for name, lon, lat, pos, pop in TOWNS:
    x, y = ll2px(lon, lat)
    town_pts.append((name, x + OX, y + OY, pos, pop))
for name, h, x, y, pos in peak_pts:
    symbols.append(("peak", x, y, 18))
for name, x, y, pos, pop in town_pts:
    symbols.append(("muni", x, y, muni_radius(pop)))
poi_pts = []
for name, lon, lat, pos in POIS:
    x, y = ll2px(lon, lat)
    poi_pts.append((name, x + OX, y + OY, pos))
    symbols.append(("poi", x + OX, y + OY, 15))
for kind, x, y, rad in symbols:
    rr = (rad + 2) * S
    BOXES.append((x - rr, y - rr, x + rr, y + rr))

# cimas (de mayor a menor altitud)
fh = font(EB_I, 44, 420)
for name, h, x, y, pos in sorted(peak_pts, key=lambda t: -t[1]):
    big = h >= 3000
    fn = font(EB, 62 if big else 54, 580 if big else 500)
    place_block(point_cands(x, y, pos, 50 * S),
                [(name, fn, INK, 0), (f"{h:,}".replace(",", "."), fh, INK_SOFT, 0)])

# municipios: un único estilo; punto y nombre crecen con la población (los grandes se colocan antes)
for name, x, y, pos, pop in sorted(town_pts, key=lambda t: -t[4]):
    t = pop_t(pop)
    fm = font(EB, 42 + 18 * t, int(460 + 120 * t))
    ov = place_block(point_cands(x, y, pos, (muni_radius(pop) + 16) * S), [(name, fm, INK, 0)], halo_w=8 + 3 * t)
    if ov > 0: print("  aviso: solape en", name, int(ov))

# monumentos: rombo y nombre en cursiva
fpoi = font(EB_I, 44, 470)
for name, x, y, pos in poi_pts:
    ov = place_block(point_cands(x, y, pos, 30 * S), [(name, fpoi, INK, 0)], halo_w=8)
    if ov > 0: print("  aviso: solape en", name, int(ov))

# embalses y lagunas: rótulo junto a la lámina de agua real (OSM)
from shapely.geometry import Point as _Pt
WATER_LABEL = (44, 88, 116)
fw = font(EB_I, 44, 460)
for label, lon, lat in RESERVOIRS:
    x, y = ll2px(lon, lat)
    p = _Pt(x * SX, y * SX)                       # osm.pkl está en px de resolución completa
    near = [g for g in linework.OSM["water"] if g.distance(p) < 111]
    if not near:
        print("  sin agua para", label); continue
    disk = p.buffer(222)
    g = max(near, key=lambda g: g.intersection(disk).area).intersection(disk)
    x0, y0, x1, y1 = [v / SX for v in g.bounds]
    x0 += OX; x1 += OX; y0 += OY; y1 += OY
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    gap = 14 * S
    cands = [(x1 + gap, cy, "lm"), (x0 - gap, cy, "rm"), (cx, y0 - gap, "mb"), (cx, y1 + gap, "mt"),
             (x1 + gap, y0, "lb"), (x0 - gap, y0, "rb"), (x1 + gap, y1, "lt"), (x0 - gap, y1, "rt")]
    if (x1 - x0) > 2.2 * (y1 - y0):               # embalse alargado E-O: mejor encima o debajo
        cands = cands[2:4] + cands[:2] + cands[4:]
    ov = place_block(cands, [(label, fw, WATER_LABEL, 0)], halo_w=8)
    if ov > 0: print("  aviso: solape en", label, int(ov))

# ---------------- gratícula en el marco
def edge_crossings():
    """Cruces de meridianos (bordes sup/inf) y paralelos (bordes izq/der)."""
    out = []
    inv = lambda c, r: tx(src.crs, "EPSG:4326", *src.xy(r * SX, c * SX))
    # recorrer bordes en píxeles y detectar cambios de 0.5°
    for side in ("top", "bottom", "left", "right"):
        if side in ("top", "bottom"):
            r = 0 if side == "top" else MH
            cs = np.arange(0, MW + 1, 2)
            rows = [r * SX] * len(cs); cols = list(cs * SX)
        else:
            c = 0 if side == "left" else MW
            rs = np.arange(0, MH + 1, 2)
            rows = list(rs * SX); cols = [c * SX] * len(rs)
        xs, ys = rasterio.transform.xy(src.transform, rows, cols, offset="ul")
        lon, lat = tx(src.crs, "EPSG:4326", xs, ys)
        v = np.array(lon if side in ("top", "bottom") else lat)
        step = 0.5 if side in ("top", "bottom") else 0.25
        k = np.floor(v / step)
        for i in np.nonzero(np.diff(k))[0]:
            val = (max(k[i], k[i + 1])) * step
            frac = (val - v[i]) / (v[i + 1] - v[i])
            pos = (i + frac) * 2
            out.append((side, pos, val))
    return out

def fmt(val, kind):
    a = abs(val); d = int(a); m = int(round((a - d) * 60))
    hemi = ("N" if val >= 0 else "S") if kind == "lat" else ("E" if val >= 0 else "O")
    return f"{d}°{m:02d}′ {hemi}" if m else f"{d}° {hemi}"

FR = (MARGIN - 0, MARGIN - 0, MARGIN + MW, MARGIN + MH)
TL = int(26 * S)
grat = []
fg = font(EB, 32, 450)
for side, p, val in edge_crossings():
    if side == "top":
        x = OX + p; grat.append(((x, OY - TL), (x, OY)))
        put_text(x, OY - TL - 10 * S, fmt(val, "lon"), fg, INK_SOFT, "mb", halo_w=0)
    elif side == "bottom":
        x = OX + p; grat.append(((x, OY + MH), (x, OY + MH + TL)))
        put_text(x, OY + MH + TL + 10 * S, fmt(val, "lon"), fg, INK_SOFT, "mt", halo_w=0)
    elif side == "left":
        y = OY + p; grat.append(((OX - TL, y), (OX, y)))
        put_text(OX - TL - 12 * S, y, fmt(val, "lat"), fg, INK_SOFT, "mm", halo_w=0, rotate=90)
    else:
        y = OY + p; grat.append(((OX + MW, y), (OX + MW + TL, y)))
        put_text(OX + MW + TL + 12 * S, y, fmt(val, "lat"), fg, INK_SOFT, "mm", halo_w=0, rotate=-90)

# ---------------- cartela inferior
BY = OY + MH + int(150 * S)
cx = CW / 2
put_text(cx, BY + 20 * S, "PIRINEOS", font(SERIF, 330, 400), INK, "mt", tracking=150, halo_w=0)
put_text(cx, BY + 420 * S, "Pirineus  ·  Pyrénées  ·  Pirinioak  ·  Pirenèus", font(SERIF_I, 92, 450),
         INK_SOFT, "mt", tracking=4, halo_w=0)
put_text(cx, BY + 590 * S, "DEL GOLFO DE BIZKAIA AL CABO DE CREUS", font(SANS, 38, 300),
         INK_SOFT, "mt", tracking=30, halo_w=0)

# izquierda: escala gráfica + leyenda de altitudes
LX = OX
fs = font(EB, 42, 460)
fl = font(EB_I, 46, 420)
km_px = 1000 / (src.transform.a * SX)
SB_Y = BY + 260 * S
put_text(LX, SB_Y - 40 * S, "Escala 1:320.000", fl, INK_SOFT, "lb", halo_w=0)
bars = [0, 5, 10, 20, 30]
bar_rects = []
for i in range(len(bars) - 1):
    x0 = LX + bars[i] * km_px; x1 = LX + bars[i + 1] * km_px
    bar_rects.append((x0, SB_Y, x1, SB_Y + 22 * S, i % 2 == 0))
for b_ in bars:
    put_text(LX + b_ * km_px, SB_Y + 40 * S, f"{b_}" + (" km" if b_ == bars[-1] else ""), fs, INK_SOFT, "mt", halo_w=0)

LG_Y = SB_Y + 270 * S
LG_W = 30 * km_px
swatches = []
if STYLE == "clasico":
    put_text(LX, LG_Y - 30 * S, "Altitud", fl, INK_SOFT, "lb", halo_w=0)
    for h in (0, 1000, 2000, 3000):
        put_text(LX + LG_W * h / 3400, LG_Y + 70 * S, f"{h:,}".replace(",", ".") + (" m" if h == 3000 else ""),
                 fs, INK_SOFT, "mt", halo_w=0)
else:
    # muestras tomadas del propio mapa renderizado (mediana de píxeles llanos de cada cobertura)
    from rasterio.enums import Resampling as _R
    with rasterio.open("work/landcover_lcc.tif") as _s:
        lcF = _s.read(1, out_shape=(MH, MW), resampling=_R.mode if F > 1 else _R.nearest)
    rel = np.asarray(Image.open(f"work/relief{SUFFIX}_f{F}.png").convert("RGB"))
    gy_, gx_ = np.gradient(dem, src.transform.a * SX)
    slp = np.degrees(np.arctan(np.hypot(gx_, gy_))); del gy_, gx_
    def med(mask):
        return tuple(int(v) for v in np.median(rel[mask], axis=0))
    items = [("Bosque", med((lcF == 10) & (slp < 8))),
             ("Prado y pasto", med((lcF == 30) & (slp < 8))),
             ("Cultivo", med((lcF == 40) & (slp < 4))),
             ("Roca y pedregal", med((dem > 2300) & (dem < 2550) & (lcF == 60) & (slp < 30))),
             ("Nieve", med((dem > 3000) & (slp < 30)))]
    del rel, lcF, slp
    put_text(LX, LG_Y - 30 * S, "Cobertura del suelo", fl, INK_SOFT, "lb", halo_w=0)
    for k, (lab_, col_) in enumerate(items):
        cx_, cy_ = LX + (k % 2) * LG_W / 2, LG_Y + (k // 2) * 78 * S
        swatches.append((cx_, cy_, col_))
        put_text(cx_ + 80 * S, cy_ + 22 * S, lab_, fs, INK_SOFT, "lm", halo_w=0)

# leyenda de signos (segunda columna)
KX = LX + LG_W + 230 * S
KY = SB_Y - 40 * S
ROW = 92 * S
key_items = [("peak", "Cima · altitud en metros"), ("muni", "Municipio"), ("poi", "Monumento"),
             ("river", "Río"), ("border", "Frontera"),
             ("major", "Autopista · autovía"), ("primary", "Carretera principal"), ("secondary", "Carretera secundaria")]
key_lines = []
for k, (kind, label) in enumerate(key_items):
    col, row = divmod(k, 3)
    x = KX + col * 860 * S; y = KY + row * ROW + 30 * S
    if kind == "peak":
        symbols.append(("peak", x + 45 * S, y, 18))
    elif kind == "poi":
        symbols.append(("poi", x + 45 * S, y, 15))
    elif kind == "muni":                       # tres puntos: ~500, ~10.000 y ~200.000 hab.
        for dx_, pp in ((12, 500), (42, 10000), (84, 200000)):
            symbols.append(("muni", x + dx_ * S, y, muni_radius(pp)))
    else:
        key_lines.append((kind, x, y))
    put_text(x + 120 * S, y, label, fs, INK_SOFT, "lm", halo_w=0)

# derecha: créditos
RX = OX + MW
cred = [
    ("Relieve sombreado calculado a partir del modelo digital de elevaciones Copernicus DEM GLO-30", EB_I),
    ("© DLR e.V. 2010–2014 y © Airbus Defence and Space GmbH 2014–2018,", EB),
    ("proporcionado bajo el programa Copernicus por la Unión Europea y la ESA", EB),
]
if STYLE == "color":
    cred += [
        ("Cobertura del suelo: ESA WorldCover 10 m 2021 (© ESA, CC BY 4.0)", EB),
        ("Tono del terreno: Sentinel-2 cloudless 2023, s2maps.eu, EOX IT Services GmbH", EB),
        ("(datos Copernicus Sentinel modificados, CC BY-NC-SA 4.0)", EB),
        ("Nieve: manto estacional modelado según cota, orientación y pendiente", EB),
    ]
cred += [
    ("Ríos, embalses, carreteras, fronteras, municipios y monumentos: © colaboradores de OpenStreetMap (ODbL)", EB),
    ("Proyección cónica conforme de Lambert · paralelos 42°12′ y 43°12′ N", EB),
    ("Jaca · 2026", EB_I),
]
for k, (t, fname) in enumerate(cred):
    put_text(RX, SB_Y - 40 * S + 70 * k * S, t, font(fname, 42, 440), INK_SOFT, "rb", halo_w=0)

# ---------------- componer halos y tintas
halo_b = halo.filter(ImageFilter.GaussianBlur(max(1, 5 * S)))
halo_b = halo_b.point(lambda v: int(min(255, v * 0.80)))
canvas.paste(Image.new("RGB", (CW, CH), PAPER), (0, 0), halo_b)
del halo, halo_b

# símbolos y líneas: dibujar en una capa RGBA a 1x (PIL antialias limitado: supersample local)
draw = ImageDraw.Draw(canvas)
lw = max(1, int(5 * S))
draw.rectangle(FR, outline=INK, width=lw)
draw.rectangle((FR[0] - int(26 * S), FR[1] - int(26 * S), FR[2] + int(26 * S), FR[3] + int(26 * S)),
               outline=INK_SOFT, width=max(1, int(2 * S)))
for a, b in grat:
    draw.line([a, b], fill=INK, width=max(1, int(3 * S)))
for x0, y0, x1, y1, fill in bar_rects:
    draw.rectangle((x0, y0, x1, y1), fill=INK if fill else PAPER, outline=INK, width=max(1, int(2 * S)))
# leyenda hipsométrica: muestras del propio relieve sin sombra (paleta del render)
stops = [(0, (226, 229, 210)), (200, (224, 228, 204)), (500, (232, 230, 202)), (900, (238, 230, 196)),
         (1300, (238, 220, 184)), (1700, (230, 205, 174)), (2100, (218, 194, 172)), (2500, (212, 202, 196)),
         (2800, (228, 226, 226)), (3100, (246, 246, 246)), (3500, (255, 255, 255))]
zz = np.array([s[0] for s in stops]); cc = np.array([s[1] for s in stops])
if STYLE == "clasico":
    n = int(LG_W)
    grad = np.stack([np.interp(np.linspace(0, 3400, n), zz, cc[:, i]) for i in range(3)], -1).astype(np.uint8)
    gh = int(36 * S)
    canvas.paste(Image.fromarray(np.repeat(grad[None], gh, 0)), (int(LX), int(LG_Y)))
    draw.rectangle((LX, LG_Y, LX + n, LG_Y + gh), outline=INK, width=max(1, int(2 * S)))
    for h in (0, 1000, 2000, 3000):
        xx = LX + LG_W * h / 3400
        draw.line([(xx, LG_Y + gh), (xx, LG_Y + gh + 14 * S)], fill=INK, width=max(1, int(2 * S)))
for cx_, cy_, col_ in swatches:
    draw.rectangle((cx_, cy_, cx_ + 56 * S, cy_ + 44 * S), fill=col_, outline=INK, width=max(1, int(2 * S)))

LW = lambda w: max(1, int(round(w * S)))
blend = lambda col, op: tuple(int(round(p * (1 - op) + c * op)) for p, c in zip(PAPER, col))
for kind, x, y in key_lines:
    x0, x1 = x, x + 96 * S
    if kind == "river":
        pts = [(x0 + t_, y + 9 * S * np.sin(t_ / (90 * S) * 2 * np.pi)) for t_ in np.linspace(0, 90 * S, 30)]
        draw.line(pts, fill=linework.RIVER, width=LW(6), joint="curve")
    elif kind == "major":
        draw.line([(x0, y), (x1, y)], fill=blend(linework.ROAD_MAJOR, 0.80), width=LW(4.4))
    elif kind == "primary":
        draw.line([(x0, y), (x1, y)], fill=blend(linework.ROAD_PRIMARY, 0.68), width=LW(3))
    elif kind == "secondary":
        draw.line([(x0, y), (x1, y)], fill=blend(linework.ROAD_SECONDARY, 0.40), width=LW(2))
    elif kind == "border":
        draw.line([(x0, y), (x1, y)], fill=blend(linework.BORDER, 0.24), width=LW(34))
        xx = x0
        for L_, on in [(46, 1), (16, 0), (9, 1), (16, 0), (46, 1)]:
            if on: draw.line([(xx, y), (min(x1, xx + L_ * S), y)], fill=linework.BORDER, width=LW(6.5))
            xx += L_ * S

def ss_symbol(kind, x, y, rad):
    """Símbolo dibujado a 4x y reducido (antialias)."""
    k = 4
    size = int(58 * S * k) + 8
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size / 2
    if kind == "peak":
        a = 18 * S * k
        pts = [(c, c - a * 1.05), (c - a, c + a * 0.7), (c + a, c + a * 0.7)]
        d.polygon(pts, fill=INK + (255,), outline=PAPER + (255,), width=int(3 * S * k))
    elif kind == "poi":                         # rombo con centro de papel
        a = rad * S * k
        d.polygon([(c, c - a), (c + a, c), (c, c + a), (c - a, c)], fill=INK + (255,), outline=PAPER + (255,),
                  width=max(1, int(2.5 * S * k)))
        b = a * 0.38
        d.polygon([(c, c - b), (c + b, c), (c, c + b), (c - b, c)], fill=PAPER + (255,))
    elif kind == "muni":
        a = rad * S * k
        d.ellipse((c - a, c - a, c + a, c + a), fill=INK + (255,), outline=PAPER + (255,),
                  width=max(1, int((2.5 + rad * 0.08) * S * k)))
    im = im.resize((size // k, size // k), Image.LANCZOS)
    canvas.paste(im, (int(x - im.width / 2), int(y - im.height / 2)), im)

for kind, x, y, rad in symbols:
    ss_symbol(kind, x, y, rad)

for color, (im, _) in layers.items():
    canvas.paste(Image.new("RGB", (CW, CH), color), (0, 0), im)

os.makedirs("output", exist_ok=True)
if F == 1:
    dpi = MW / (140 / 2.54)
    canvas.save(f"output/pirineo{SUFFIX}_150cm.tif", dpi=(dpi, dpi), compression="tiff_lzw")
    canvas.save(f"output/pirineo{SUFFIX}_150cm.png", dpi=(dpi, dpi))
    canvas.resize((CW // 4, CH // 4), Image.LANCZOS).save(f"output/pirineo{SUFFIX}_preview.jpg", quality=90)
    print(f"lámina {CW}x{CH} px · {CW / dpi * 2.54:.1f} x {CH / dpi * 2.54:.1f} cm a {dpi:.0f} ppp")
else:
    canvas.save(f"work/compose{SUFFIX}_f{F}.png")
    print("vista previa", CW, CH)
