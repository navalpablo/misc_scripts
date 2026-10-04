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
from places import PEAKS, TOWNS, AREAS, RIVERS, RESERVOIRS, VALLEYS, POIS, POIS_WD, NATURAL, PARKS, PASSES, EXITS
import pickle, math
import re
import linework

Image.MAX_IMAGE_PIXELS = None
F = int(sys.argv[1]) if len(sys.argv) > 1 else 4
STYLE = sys.argv[2] if len(sys.argv) > 2 else "clasico"   # "clasico" | "color"
SUFFIX = "" if STYLE == "clasico" else "_color"
S = 1 / F                                     # escala de todo lo dibujado
# Versión alternativa (VARIANT=alt): mismos datos y rótulos, con retoques de acabado:
# túneles en discontinuo, halos de texto más finos y nítidos y marco graduado cada 5′.
ALT = os.environ.get("VARIANT", "") == "alt"
OUTSUF = SUFFIX + ("_alt" if ALT else "")
HALO_K, HALO_BLUR, HALO_OP = (0.72, 2.6, 0.86) if ALT else (1.0, 5.0, 0.80)

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
# espacios naturales protegidos (contorno OSM, 04b_osm_parks.py), por debajo de ríos y carreteras
# Desactivado: con los contornos y los nombres largos de los parques la lámina quedaba demasiado cargada.
DRAW_PARKS = False
PARK_GEO = pickle.load(open("work/parks.pkl", "rb")) if DRAW_PARKS and os.path.exists("work/parks.pkl") else {}
if DRAW_PARKS:
    linework.draw_parks(canvas, OX, OY, F, MW, MH, PARK_GEO, {p[1]: p[2] for p in PARKS}, sea_mask=sea_mask)
TUNNELS = pickle.load(open("work/tunnels.pkl", "rb")) if ALT and os.path.exists("work/tunnels.pkl") else None
river_geo = linework.draw_all(canvas, OX, OY, F, MW, MH, sea_mask=sea_mask, tunnels=TUNNELS)
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
    hw = int(halo_w * S * HALO_K)
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

def river_label(c, s_mid, txt, f, color, gap, tracking=0, halo_w=8, dry=False, shifts=(0, -0.6, 0.6, -1.2, 1.2, -2.0, 2.0)):
    adv = [f.getlength(ch) + tracking * S for ch in txt]
    L = sum(adv) - tracking * S
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
    for span in (0.85, 1.15, 1.5):
        for shift in shifts:
            if seg[-1] < 1.05 * L:
                return False
            sm = float(np.clip(s_mid + shift * L, 0.55 * L, seg[-1] - 0.55 * L))
            res = _river_label(c, sm, txt, f, color, gap, tracking, halo_w, span, dry)
            if res:
                return res
    return False

def _river_label(c, s_mid, txt, f, color, gap, tracking, halo_w, span, dry=False):
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
    hw = int(halo_w * S * HALO_K)
    if dry:                                   # solo las cajas de cada letra, sin dibujar
        out = []
        for ch, a_ in zip(txt, adv):
            sc_ = pos + (a_ - tracking * S) / 2; pos += a_
            if ch == " ": continue
            x = np.interp(sc_, ss, P[:, 0]); y = np.interp(sc_, ss, P[:, 1])
            out.append((x - a_ / 2, y - cap * 1.05, x + a_ / 2, y + cap * 0.3))
        return out
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

def place_block(cands, lines, halo_w=10, strict=False):
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
    if strict and ov > 0:
        return None
    cy = by
    for (t, f, c, tr), w, (m0, m1), hh in zip(lines, ws, mets, hs):
        lx = {"l": bx, "m": bx + (BW - w) / 2, "r": bx + BW - w}[anc[0]]
        _draw_run(layer(c), hd, lx - (f.getbbox(t)[0] if tr == 0 else 0), cy - m0, t, f, tr, int(halo_w * S * HALO_K))
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
for name, lon, lat, pos, *rest in POIS:
    x, y = ll2px(lon, lat)
    small = bool(rest) and rest[0] == 2
    poi_pts.append((name, x + OX, y + OY, pos, small))
    symbols.append(("poi", x + OX, y + OY, 11 if small else 15))
pass_pts = []
for name, ele, lon, lat, prio in PASSES:
    if prio != 1: continue
    x, y = ll2px(lon, lat)
    pass_pts.append((name, ele, x + OX, y + OY))
    symbols.append(("pass", x + OX, y + OY, 16))
for kind, x, y, rad in symbols:
    rr = (rad + 2) * S
    BOXES.append((x - rr, y - rr, x + rr, y + rr))



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

# ---------------- rosa de los vientos con el norte geográfico, en el golfo de Bizkaia
# En la cónica de Lambert los meridianos convergen: el norte geográfico solo coincide con la vertical
# en el meridiano central (0°43′ E). La rosa se orienta según el meridiano que pasa por ella.
def north_angle(lon, lat):
    x0, y0 = ll2px(lon, lat); x1, y1 = ll2px(lon, lat + 0.05)
    return math.degrees(math.atan2(x1 - x0, -(y1 - y0)))      # + : el norte se inclina hacia la derecha

def find_rose():
    from scipy import ndimage as _nd
    s4 = np.load("work/mask_sea_f4.npy")
    h4, w4 = s4.shape
    reg = s4[: h4 // 3, : w4 // 5]
    pad = np.zeros((reg.shape[0] + 2, reg.shape[1] + 2), bool); pad[1:-1, 1:-1] = reg
    d4 = _nd.distance_transform_edt(pad)[1:-1, 1:-1] * 4 / F       # holgura hasta tierra o marco (px de lámina)
    for R_ in (230 * S, 205 * S, 180 * S, 160 * S):
        best = None
        for r4 in range(0, reg.shape[0], 4):
            for c4 in range(0, reg.shape[1], 4):
                cl = d4[r4, c4]
                if cl < R_ + 70 * S: continue
                cx, cy = c4 * 4 / F, r4 * 4 / F
                ny = cy - R_ - 85 * S
                if ny - 70 * S < 60 * S: continue
                box = (cx - R_ + OX, ny - 60 * S + OY, cx + R_ + OX, cy + R_ + OY)
                if overlap(box) > 0: continue
                if best is None or cl > best[0]:
                    best = (cl, cx + OX, cy + OY, R_, box)
        if best: return best
    return None
ROSE = find_rose()
if ROSE:
    _, RX0, RY0, ROSE_R, rbox = ROSE
    BOXES.append(rbox)
    _x, _y = src.xy((RY0 - OY) * SX, (RX0 - OX) * SX)
    _lon, _lat = tx(src.crs, "EPSG:4326", [_x], [_y])
    ROSE_ANG = north_angle(_lon[0], _lat[0])
    print(f"  rosa en {_lon[0]:.2f}, {_lat[0]:.2f}  radio {ROSE_R / S:.0f} px  giro {ROSE_ANG:+.2f}°")
else:
    print("  aviso: sin sitio para la rosa")

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

# puertos imprescindibles: nombre y altitud
fpass, fpass_h = font(EB, 42, 500), font(EB_I, 38, 420)
for name, ele, x, y in pass_pts:
    ov = place_block(point_cands(x, y, "r", 30 * S),
                     [(name, fpass, INK, 0), (f"{ele:,}".replace(",", "."), fpass_h, INK_SOFT, 0)], halo_w=8)
    if ov > 0: print("  aviso: solape en", name, int(ov))

# monumentos: rombo y nombre en cursiva
fpoi = font(EB_I, 44, 470)
fpoi_s = font(EB_I, 36, 470)
for name, x, y, pos, small in poi_pts:
    ov = place_block(point_cands(x, y, pos, (24 if small else 30) * S), [(name, fpoi_s if small else fpoi, INK, 0)],
                     halo_w=7 if small else 8)
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

# ---------------- parajes naturales (cursiva verde) y nombres de espacios protegidos
NAT_INK = (44, 94, 50)
fnat = font(EB_I, 44, 500)
for label, lon, lat in NATURAL:
    x, y = ll2px(lon, lat); x += OX; y += OY
    d = 36 * S
    cands = [(x, y, "mm"), (x, y - d, "mb"), (x, y + d, "mt"), (x + d, y, "lm"), (x - d, y, "rm"),
             (x, y - 2.2 * d, "mb"), (x, y + 2.2 * d, "mt")]
    ov = place_block(cands, [(label, fnat, NAT_INK, 6)], halo_w=8)
    if ov > 0: print("  aviso: solape en", label, int(ov))

import shapely
fpark = {1: font(EB_I, 52, 520), 2: font(EB_I, 44, 480), 3: font(EB_I, 44, 470)}
for label, pat, kind, lon, lat in (PARKS if DRAW_PARKS else []):
    g = PARK_GEO.get(pat)
    if g is None:
        print("  sin contorno para", label.replace("\n", " ")); continue
    lines = [(t, fpark[kind], NAT_INK, 10 if kind == 1 else 6) for t in label.split("\n")]
    # caja del rótulo para comprobar que queda dentro del espacio
    ws = [text_size(t, f_, tr)[0] for t, f_, c_, tr in lines]
    hh = sum(line_metrics(f_)[1] - line_metrics(f_)[0] for t, f_, c_, tr in lines)
    BW_, BH_ = max(ws) * F, hh * F                       # en px de resolución completa
    px_, py_ = ll2px(lon, lat); px_, py_ = px_ * F, py_ * F
    minx, miny, maxx, maxy = g.bounds
    step = 50.0
    gx, gy = np.meshgrid(np.arange(minx, maxx, step), np.arange(miny, maxy, step))
    gx, gy = gx.ravel(), gy.ravel()
    order = np.argsort(np.hypot(gx - px_, gy - py_))
    gx, gy = gx[order], gy[order]
    gg = g.buffer(60)
    inside_all = np.ones(len(gx), bool)
    for dx_, dy_ in ((0, 0), (-.5, -.5), (.5, -.5), (-.5, .5), (.5, .5), (-.5, 0), (.5, 0)):
        inside_all &= shapely.contains_xy(gg, gx + dx_ * BW_, gy + dy_ * BH_)
    placed = False
    for strict_inside in (True, False):
        idx = np.nonzero(inside_all)[0] if strict_inside else np.nonzero(shapely.contains_xy(g, gx, gy))[0]
        for i in idx[:600]:
            cx_, cy_ = gx[i] / F + OX, gy[i] / F + OY
            if place_block([(cx_, cy_, "mm")], lines, halo_w=8, strict=True) is not None:
                placed = True; break
        if placed: break
    if not placed:
        print("  sin hueco para", label.replace("\n", " "))

# ================= rótulos automáticos (09_select_labels.py): mismo criterio en todo el mapa =================
# Se colocan después de todo lo elegido a mano y SOLO si caben sin pisar nada; si no, se descartan.
import json as _json
AUTO = _json.load(open("work/auto_labels.json")) if os.path.exists("work/auto_labels.json") else {}

def try_symbol_label(kind, x, y, rad, cands, lines, halo_w):
    rr = (rad + 2) * S
    sbox = (x - rr, y - rr, x + rr, y + rr)
    if overlap(sbox) > 0:
        return False
    BOXES.append(sbox)
    if place_block(cands, lines, halo_w=halo_w, strict=True) is None:
        BOXES.remove(sbox); return False
    symbols.append((kind, x, y, rad)); return True

def try_river_text(cc_, s_mid, label, fnt, color, gap, tracking, halo_w):
    """Rótulo curvo junto a la polilínea cc_ (px de lámina) solo si no pisa nada."""
    boxes = river_label(cc_, s_mid, label, fnt, color, gap=gap, tracking=tracking, halo_w=halo_w,
                        dry=True, shifts=(0,))
    if not boxes or any(overlap(b) > 0 for b in boxes):
        return False
    river_label(cc_, s_mid, label, fnt, color, gap=gap, tracking=tracking, halo_w=halo_w, shifts=(0,))
    return True

# ---- ríos: todos los que drenan ≥ 300 km² dentro del mapa (área de cuenca del DEM)
def clean_river(n):
    n = n.split(" / ")[0].strip()
    n = re.sub(r"^(?:r[ií]o|riu|arriu|rivière|ribera)\s+", "", n, flags=re.I)
    n = re.sub(r"^(?:de\s+la|de\s+les|de\s+los|dels|del|de|d['’])\s*", "", n, flags=re.I)
    n = re.sub(r"^(?:el|la|les|los|las|lo|le)\s+|^l['’]", "", n, flags=re.I)
    n = re.sub(r"\s+(?:ibaia|erreka)$", "", n)
    return n[:1].upper() + n[1:]
SKIP_RIVER = re.compile(r"^(Barranc|Ruisseau|Canal|Rec\b|Arroyo|Regata|Torrent|Riera|Rambla|Acequia|Ravin|Fosse|Ríu)", re.I)
used = ([re.compile(p) for _, p, *_ in RIVERS] + [re.compile(v[1]) for v in VALLEYS if isinstance(v[1], str)]
        + [re.compile(r"^Aragoi|Garona|^Segre|^Cinca|^Ebro|^Ebre|^R[ií]o Ara$|Gállego|sera$|Ribagor")])
rcands = []
for name, items in river_geo.items():
    if not name or any(p.search(name) for p in used) or SKIP_RIVER.search(name):
        continue
    amax = max(float(a.max()) for c, w, a in items)
    if amax < 300: continue
    rcands.append((amax, name, items))
n_riv = 0
for amax, name, items in sorted(rcands, key=lambda t: -t[0]):
    label = clean_river(name)
    fr = font(EB_I, 54 if amax >= 2000 else 46, 460)
    L = sum(fr.getlength(ch) + 8 * S for ch in label)
    c, w, a = max(items, key=lambda t: len(t[0]))
    cc_ = c * S + np.array([OX, OY])
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(cc_, axis=0).T))]
    if seg[-1] < L * 1.3: continue
    placed = []
    for fr_ in (0.5, 0.35, 0.65, 0.25, 0.75, 0.15, 0.85):
        sm = fr_ * seg[-1]
        if any(abs(sm - p) < 2400 * S for p in placed): continue      # 2.º rótulo a ≥ 65 km del 1.º
        wj = w[min(len(w) - 1, int(np.searchsorted(seg, sm)))]
        if try_river_text(cc_, sm, label, fr, RIVER_INK, wj * S / 2 + 14 * S, 8, 7):
            placed.append(sm); n_riv += 1
            if len(placed) >= (2 if seg[-1] > 4400 * S else 1): break
print("  ríos automáticos:", n_riv)

# ---- monumentos y patrimonio más relevantes (antes que los municipios automáticos)
n_m = 0
POI_PLACED = []
def auto_poi(p):
    x, y = ll2px(p["lon"], p["lat"]); x += OX; y += OY
    ok = try_symbol_label("poi", x, y, 15, point_cands(x, y, "r", 30 * S), [(p["name"], fpoi, INK, 0)], 8)
    if ok: POI_PLACED.append(p)
    return ok
def fixed_poi(name, lon, lat, pos):
    """Monumento fijado en places.POIS_WD: entra sin pisar nada si puede; si no, se coloca igualmente."""
    x, y = ll2px(lon, lat); x += OX; y += OY
    if try_symbol_label("poi", x, y, 15, point_cands(x, y, pos, 30 * S), [(name, fpoi, INK, 0)], 8):
        return
    symbols.append(("poi", x, y, 15)); rr = 17 * S; BOXES.append((x - rr, y - rr, x + rr, y + rr))
    ov = place_block(point_cands(x, y, pos, 30 * S), [(name, fpoi, INK, 0)], halo_w=8)
    print("  aviso: monumento fijado con solape", name, int(ov))
for name, lon, lat, pos, stage in POIS_WD:
    if stage == 1: fixed_poi(name, lon, lat, pos)

# ---- municipios (por relevancia)
n_t = 0
for t in AUTO.get("towns", []):
    x, y = ll2px(t["lon"], t["lat"]); x += OX; y += OY
    tt = pop_t(t["pop"]); rad = muni_radius(t["pop"])
    fm = font(EB, 42 + 18 * tt, int(460 + 120 * tt))
    if try_symbol_label("muni", x, y, rad, point_cands(x, y, "r", (rad + 16) * S),
                        [(t["name"], fm, INK, 0)], 8 + 3 * tt):
        n_t += 1
print("  municipios automáticos:", n_t, "de", len(AUTO.get("towns", [])))

# ---- valles: a lo largo del río más cercano (≤ 2,5 km) o rótulo recto
n_v = 0
for v in AUTO.get("valleys", []):
    ax_, ay_ = ll2px(v["lon"], v["lat"])
    L = sum(fv2.getlength(ch) + 5 * S for ch in v["name"])
    best = None
    for name, items in river_geo.items():
        for c, w, a in items:
            cc_ = c * S
            dd = np.hypot(cc_[:, 0] - ax_, cc_[:, 1] - ay_); j = int(dd.argmin())
            if dd[j] < 93 * S and (best is None or dd[j] < best[0]):
                best = (dd[j], cc_, j, w)
    ok = False
    if best is not None:
        _, cc_, j, w = best
        seg = np.r_[0, np.cumsum(np.hypot(*np.diff(cc_, axis=0).T))]
        if seg[-1] >= L * 1.1:
            sm = float(np.clip(seg[j], 0.55 * L, seg[-1] - 0.55 * L))
            ok = try_river_text(cc_ + np.array([OX, OY]), sm, v["name"], fv2, INK_SOFT,
                                w[min(len(w) - 1, j)] * S / 2 + 14 * S, 5, 7)
    if not ok:
        x, y = ax_ + OX, ay_ + OY
        ok = place_block([(x, y, "mm"), (x, y - 40 * S, "mm"), (x, y + 40 * S, "mm"), (x + 40 * S, y, "lm"),
                          (x - 40 * S, y, "rm")], [(v["name"], fv2, INK_SOFT, 5)], halo_w=7, strict=True) is not None
    n_v += ok
print("  valles automáticos:", n_v, "de", len(AUTO.get("valleys", [])))

# ---- cimas (dominan 8 km a la redonda)
n_p = 0
for p in AUTO.get("peaks", []):
    x, y = ll2px(p["lon"], p["lat"])
    c, r = int(round(x)), int(round(y))
    w = dem[max(0, r - R):r + R, max(0, c - R):c + R]
    i, j = np.unravel_index(np.argmax(w), w.shape)
    x, y = max(0, c - R) + j + OX, max(0, r - R) + i + OY
    fn = font(EB, 62 if p["ele"] >= 3000 else 54, 580 if p["ele"] >= 3000 else 500)
    if try_symbol_label("peak", x, y, 18, point_cands(x, y, "r", 50 * S),
                        [(p["name"], fn, INK, 0), (f"{p['ele']:,}".replace(",", "."), fh, INK_SOFT, 0)], 10):
        n_p += 1
print("  cimas automáticas:", n_p, "de", len(AUTO.get("peaks", [])))

# ---- monumentos fijados (tanda 2)
for name, lon, lat, pos, stage in POIS_WD:
    if stage == 2: fixed_poi(name, lon, lat, pos)

# ---- puertos de montaña secundarios: solo si caben sin pisar nada
n_pass = 0
for name, ele, lon, lat, prio in PASSES:
    if prio == 1: continue
    x, y = ll2px(lon, lat); x += OX; y += OY
    if try_symbol_label("pass", x, y, 16, point_cands(x, y, "r", 30 * S),
                        [(name, fpass, INK, 0), (f"{ele:,}".replace(",", "."), fpass_h, INK_SOFT, 0)], 8):
        n_pass += 1; print("  puerto:", name)
print("  puertos opcionales:", n_pass, "de", sum(1 for p in PASSES if p[4] != 1))

# ---- más patrimonio cultural por toda la lámina: solo donde quepa sin pisar nada
for p in AUTO.get("pois", []):
    n_m += auto_poi(p)
print("  monumentos automáticos nuevos:", n_m, "de", len(AUTO.get("pois", [])))
_json.dump(POI_PLACED, open(f"work/pois_placed{SUFFIX}_f{F}.json", "w"), ensure_ascii=False, indent=0)

# ---------------- gratícula en el marco
def edge_crossings(step_lon=0.5, step_lat=0.25):
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
        step = step_lon if side in ("top", "bottom") else step_lat
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

# ---------------- salidas por el borde: flecha en el margen y destino (p. ej. A-23 hacia Zaragoza)
exit_marks = []
fex, fref = font(EB_I, 40, 440), font(SANS, 30, 400)
for lines_, lon, lat, ref in EXITS:
    x, _ = ll2px(lon, lat); x += OX
    y0 = OY + MH + 46 * S                          # bajo el filete exterior del marco
    exit_marks.append((x, y0))
    yy = y0 + 104 * S
    if ref:
        put_text(x, yy, ref, fref, INK_SOFT, "mt", tracking=2, halo_w=0); yy += 50 * S
    for t in lines_:
        put_text(x, yy, t, fex, INK_SOFT, "mt", halo_w=0); yy += 50 * S

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
key_items = [("peak", "Cima · altitud en metros"), ("muni", "Municipio"), ("poi", "Monumento · patrimonio cultural"),
             ("natlabel", "Paraje natural"), ("pass", "Puerto de montaña · altitud"),
             *((("park1", "Parque nacional"), ("park2", "Parque natural o regional")) if DRAW_PARKS else ()),
             ("river", "Río"), ("border", "Frontera"),
             ("major", "Autopista · autovía"), ("primary", "Carretera principal"), ("secondary", "Carretera secundaria")]
key_lines = []
for k, (kind, label) in enumerate(key_items):
    col, row = divmod(k, 4)
    x = KX + col * 860 * S; y = KY + row * ROW + 30 * S
    if kind == "peak":
        symbols.append(("peak", x + 45 * S, y, 18))
    elif kind == "poi":
        symbols.append(("poi", x + 45 * S, y, 15))
    elif kind == "muni":                       # tres puntos: ~500, ~10.000 y ~200.000 hab.
        for dx_, pp in ((12, 500), (42, 10000), (84, 200000)):
            symbols.append(("muni", x + dx_ * S, y, muni_radius(pp)))
    elif kind == "pass":
        symbols.append(("pass", x + 45 * S, y, 16))
    elif kind == "natlabel":
        put_text(x + 48 * S, y, "Abc", fnat, NAT_INK, "mm", tracking=6, halo_w=0)
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
    ("Ríos, embalses, carreteras, puertos, fronteras, municipios y monumentos: © colaboradores de OpenStreetMap (ODbL)", EB),
    ("Selección de municipios, monumentos, patrimonio y valles por relevancia: Wikidata (CC0)", EB),
    ("Proyección cónica conforme de Lambert · paralelos 42°12′ y 43°12′ N · la rosa marca el norte geográfico", EB),
    ("Jaca · 2026", EB_I),
]
for k, (t, fname) in enumerate(cred):
    put_text(RX, SB_Y - 40 * S + 70 * k * S, t, font(fname, 42, 440), INK_SOFT, "rb", halo_w=0)

# ---------------- componer halos y tintas
halo_b = halo.filter(ImageFilter.GaussianBlur(max(1, HALO_BLUR * S)))
halo_b = halo_b.point(lambda v: int(min(255, v * HALO_OP)))
canvas.paste(Image.new("RGB", (CW, CH), PAPER), (0, 0), halo_b)
del halo, halo_b

# símbolos y líneas: dibujar en una capa RGBA a 1x (PIL antialias limitado: supersample local)
draw = ImageDraw.Draw(canvas)
lw = max(1, int(5 * S))
draw.rectangle(FR, outline=INK, width=lw)
draw.rectangle((FR[0] - int(26 * S), FR[1] - int(26 * S), FR[2] + int(26 * S), FR[3] + int(26 * S)),
               outline=INK_SOFT, width=max(1, int(2 * S)))
if ALT:
    # marco graduado de grabado: banda de 5′ en 5′ alternando tinta y papel junto al filete
    b0, b1 = 14 * S, 26 * S                   # entre un filete fino y el filete exterior
    by_side = {}
    for side, p, val in edge_crossings(1 / 12, 1 / 12):
        by_side.setdefault(side, []).append((p, val))
    for side, lst in by_side.items():
        lst.sort()
        L_ = MW if side in ("top", "bottom") else MH
        cuts = [0.0] + [p for p, _ in lst] + [float(L_)]
        k0 = int(round(lst[0][1] * 12)) if lst else 0
        for i in range(len(cuts) - 1):
            if (k0 + i) % 2: continue
            a_, b_ = cuts[i], cuts[i + 1]
            if side == "top":
                draw.rectangle((OX + a_, OY - b1, OX + b_, OY - b0), fill=INK)
            elif side == "bottom":
                draw.rectangle((OX + a_, OY + MH + b0, OX + b_, OY + MH + b1), fill=INK)
            elif side == "left":
                draw.rectangle((OX - b1, OY + a_, OX - b0, OY + b_), fill=INK)
            else:
                draw.rectangle((OX + MW + b0, OY + a_, OX + MW + b1, OY + b_), fill=INK)
    draw.rectangle((OX - b0, OY - b0, OX + MW + b0, OY + MH + b0), outline=INK, width=max(1, int(2 * S)))
    draw.rectangle((OX - b1, OY - b1, OX + MW + b1, OY + MH + b1), outline=INK, width=max(1, int(2 * S)))
for a, b in grat:
    draw.line([a, b], fill=INK, width=max(1, int(3 * S)))
for x, y0 in exit_marks:                       # flecha: trazo fino y punta llena hacia fuera del mapa
    draw.line([(x, y0), (x, y0 + 62 * S)], fill=INK_SOFT, width=max(1, int(3 * S)))
    draw.polygon([(x - 13 * S, y0 + 56 * S), (x + 13 * S, y0 + 56 * S), (x, y0 + 88 * S)], fill=INK_SOFT)
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
    elif kind in ("park1", "park2"):
        bw_, bop_, lw_, _ = linework.PARK_STYLE[1 if kind == "park1" else 2]
        y0_, y1_ = y - 24 * S, y + 24 * S
        nb_ = max(1, min(int(bw_ * 0.5 * S), int(20 * S)))
        for i_ in range(nb_, 0, -1):                          # cinta que se difumina hacia dentro
            op_ = bop_ * (1 - (i_ - 1) / nb_) ** 0.8
            draw.rectangle((x0 + i_, y0_ + i_, x1 - i_, y1_ - i_), outline=blend(linework.NATURE_BAND, op_ * 0.6))
        draw.rectangle((x0, y0_, x1, y1_), outline=blend(linework.NATURE, 0.85), width=LW(lw_))
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
    elif kind == "pass":                        # «)(»: dos arcos enfrentados, la carretera pasa por la cintura
        a = rad * S * k; g = a * 0.30; r_ = a * 1.25; w_ = max(1, int(3.4 * S * k))
        for sgn in (-1, 1):
            cx_ = c + sgn * (g + r_)
            ang0 = 180 - 38 if sgn > 0 else -38
            d.arc((cx_ - r_, c - r_, cx_ + r_, c + r_), ang0, ang0 + 76, fill=PAPER + (255,), width=w_ + int(3 * S * k))
            d.arc((cx_ - r_, c - r_, cx_ + r_, c + r_), ang0, ang0 + 76, fill=INK + (255,), width=w_)
    elif kind == "muni":
        a = rad * S * k
        d.ellipse((c - a, c - a, c + a, c + a), fill=INK + (255,), outline=PAPER + (255,),
                  width=max(1, int((2.5 + rad * 0.08) * S * k)))
    im = im.resize((size // k, size // k), Image.LANCZOS)
    canvas.paste(im, (int(x - im.width / 2), int(y - im.height / 2)), im)

def draw_rose(cx, cy, R, ang):
    """Rosa de ocho puntas al estilo de grabado, girada según el meridiano local; «N» sobre la punta norte."""
    k = 3
    pad = 150 * S
    size = int(2 * (R + pad) * k)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size / 2
    Rk = R * k
    def P(r, a):                                # a: grados desde el norte, en sentido horario
        t = math.radians(a + ang)
        return (c + r * math.sin(t), c - r * math.cos(t))
    ink, paper = INK + (255,), PAPER + (255,)
    soft = INK_SOFT + (255,)
    # halo de papel suave bajo la rosa
    hal = Image.new("L", (size, size), 0)
    ImageDraw.Draw(hal).ellipse((c - Rk * 0.86, c - Rk * 0.86, c + Rk * 0.86, c + Rk * 0.86), fill=140)
    hal = hal.filter(ImageFilter.GaussianBlur(Rk * 0.08))
    im = Image.new("RGBA", (size, size), PAPER + (0,))
    im.putalpha(hal)
    d = ImageDraw.Draw(im)
    # anillos y graduación cada 10°
    lw1, lw2 = max(1, int(2.6 * S * k)), max(1, int(1.6 * S * k))
    for rr, w in ((0.80, lw1), (0.72, lw2)):
        d.ellipse((c - Rk * rr, c - Rk * rr, c + Rk * rr, c + Rk * rr), outline=ink, width=w)
    for a in range(0, 360, 10):
        r0 = 0.72 if a % 90 else 0.66
        d.line([P(Rk * r0, a), P(Rk * 0.80, a)], fill=ink if a % 30 == 0 else soft, width=lw2)
    # puntas: dos mitades, tinta y papel
    def point(a, L, w):
        tip, left, right, o = P(Rk * L, a), P(Rk * w, a - 45), P(Rk * w, a + 45), (c, c)
        d.polygon([o, tip, left], fill=paper, outline=ink, width=lw2)
        d.polygon([o, tip, right], fill=ink, outline=ink, width=lw2)
    for a in (45, 135, 225, 315):
        point(a, 0.60, 0.11)
    for a in (0, 90, 180, 270):
        point(a, 1.0, 0.17)
    rc = Rk * 0.05
    d.ellipse((c - rc, c - rc, c + rc, c + rc), fill=paper, outline=ink, width=lw2)
    # «N» girada con la rosa
    fN = ImageFont.truetype(FD + SERIF, max(8, int(118 * S * k)))
    try: fN.set_variation_by_axes([600])
    except Exception: pass
    tb = fN.getbbox("N")
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    ti = Image.new("RGBA", (int(tw * 1.8), int(th * 1.8)), (0, 0, 0, 0))
    ImageDraw.Draw(ti).text((ti.width / 2 - tw / 2 - tb[0], ti.height / 2 - th / 2 - tb[1]), "N", font=fN, fill=ink)
    ti = ti.rotate(-ang, resample=Image.BICUBIC, expand=True)
    nx, ny = P(Rk + 26 * S * k + th / 2, 0)
    im.alpha_composite(ti, (int(nx - ti.width / 2), int(ny - ti.height / 2)))
    im = im.resize((size // k, size // k), Image.LANCZOS)
    canvas.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)

if ROSE:
    draw_rose(RX0, RY0, ROSE_R, ROSE_ANG)

for kind, x, y, rad in symbols:
    ss_symbol(kind, x, y, rad)

for color, (im, _) in layers.items():
    canvas.paste(Image.new("RGB", (CW, CH), color), (0, 0), im)

os.makedirs("output", exist_ok=True)
if F == 1:
    dpi = MW / (140 / 2.54)
    canvas.save(f"output/pirineo{OUTSUF}_150cm.tif", dpi=(dpi, dpi), compression="tiff_lzw")
    canvas.save(f"output/pirineo{OUTSUF}_150cm.png", dpi=(dpi, dpi))
    canvas.resize((CW // 4, CH // 4), Image.LANCZOS).save(f"output/pirineo{OUTSUF}_preview.jpg", quality=90)
    print(f"lámina {CW}x{CH} px · {CW / dpi * 2.54:.1f} x {CH / dpi * 2.54:.1f} cm a {dpi:.0f} ppp")
else:
    canvas.save(f"work/compose{OUTSUF}_f{F}.png")
    print("vista previa", CW, CH)
