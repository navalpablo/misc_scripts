"""
Dibujo de la red hidrográfica, carreteras y frontera (datos © OpenStreetMap)
sobre el relieve, con antialias por supermuestreo 2x.
"""
import pickle
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as nd

RIVER = (78, 124, 152)
LAKE_FILL = (168, 196, 208)
LAKE_EDGE = (98, 138, 160)
ROAD_MAJOR = (160, 82, 62)
ROAD_PRIMARY = (140, 108, 88)
BORDER = (112, 66, 104)

OSM = pickle.load(open("work/osm.pkl", "rb"))
ACC = np.load("work/acc_km2_q4.npy")
Q = OSM["Q"]
MIN_KM2 = 50            # tramos de río con menos cuenca no se dibujan (cabeceras)


def river_profile(coords):
    """Área de cuenca (km²) a lo largo de la línea, orientada aguas abajo y monótona."""
    r = np.clip((coords[:, 1] / Q).astype(int), 0, ACC.shape[0] - 1)
    c = np.clip((coords[:, 0] / Q).astype(int), 0, ACC.shape[1] - 1)
    a = nd.median_filter(ACC[r, c], size=min(9, len(coords) | 1), mode="nearest")
    rev = a[0] > a[-1]
    if rev:
        a = a[::-1]
    a = np.maximum.accumulate(a)
    return (a[::-1] if rev else a)


def river_width(a):
    """Grosor en píxeles a resolución completa (~301 ppp)."""
    return np.clip(1.5 + 2.5 * np.log10(np.maximum(a, 20) / 20), 1.5, 9.5)


def densify(coords, step):
    out = [coords[0]]
    for p, q in zip(coords[:-1], coords[1:]):
        d = np.hypot(*(q - p))
        n = max(1, int(d / step))
        for k in range(1, n + 1):
            out.append(p + (q - p) * k / n)
    return np.array(out)


def draw_all(canvas, OX, OY, F, MW, MH, sea_mask=None):
    S = 1 / F
    K = 2                     # supermuestreo
    sc = S * K

    def new_mask():
        return Image.new("L", (MW * K, MH * K), 0)

    def composite(mask, color, opacity=1.0, blur=0):
        m = mask.resize((MW, MH), Image.BOX)
        if blur:
            m = m.filter(ImageFilter.GaussianBlur(blur))
        if opacity < 1:
            m = m.point(lambda v: int(v * opacity))
        canvas.paste(Image.new("RGB", (MW, MH), color), (OX, OY), m)

    def poly_line(d, coords, width):
        pts = [tuple(p) for p in (coords * sc)]
        if len(pts) > 1:
            d.line(pts, fill=255, width=max(1, int(round(width * sc))), joint="curve")

    # ---------- carreteras (discretas, por debajo de todo)
    for key, col, w, op in (("primary", ROAD_PRIMARY, 2.4, 0.42), ("major", ROAD_MAJOR, 3.4, 0.55)):
        m = new_mask(); d = ImageDraw.Draw(m)
        for ln in OSM["roads"][key]:
            poly_line(d, np.asarray(ln.coords), w)
        composite(m, col, op)
        del m

    # ---------- frontera: cinta suave + línea de trazo y punto
    m = new_mask(); d = ImageDraw.Draw(m)
    for ln in OSM["border"]:
        poly_line(d, np.asarray(ln.coords), 30)
    composite(m, BORDER, 0.16, blur=max(1, 6 * S))
    m = new_mask(); d = ImageDraw.Draw(m)
    pattern = [(38, True), (14, False), (6, True), (14, False)]   # trazo, hueco, punto, hueco
    plen = sum(p[0] for p in pattern)
    for ln in OSM["border"]:
        c = densify(np.asarray(ln.coords), 2.0)
        seg = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
        phase = seg % plen
        on = np.zeros(len(c), bool); acc = 0
        for L, flag in pattern:
            if flag:
                on |= (phase >= acc) & (phase < acc + L)
            acc += L
        run = []
        for p, o in zip(c, on):
            if o:
                run.append(p)
            elif run:
                if len(run) > 1: poly_line(d, np.array(run), 4.5)
                run = []
        if len(run) > 1: poly_line(d, np.array(run), 4.5)
    composite(m, BORDER, 0.85)
    del m

    # ---------- lagos, embalses, ibones
    fill = new_mask(); edge = new_mask()
    df, de = ImageDraw.Draw(fill), ImageDraw.Draw(edge)
    for poly in OSM["water"]:
        geoms = poly.geoms if hasattr(poly, "geoms") else [poly]
        for g in geoms:
            ext = [tuple(p) for p in np.asarray(g.exterior.coords) * sc]
            if len(ext) < 3: continue
            df.polygon(ext, fill=255)
            de.line(ext + [ext[0]], fill=255, width=max(1, int(2.6 * sc)), joint="curve")
            for h in g.interiors:
                hh = [tuple(p) for p in np.asarray(h.coords) * sc]
                if len(hh) >= 3:
                    df.polygon(hh, fill=0)
                    de.line(hh + [hh[0]], fill=255, width=max(1, int(2.6 * sc)))
    composite(fill, LAKE_FILL)
    composite(edge, LAKE_EDGE, 0.9)
    del fill, edge

    # ---------- ríos con grosor según cuenca
    m = new_mask(); d = ImageDraw.Draw(m)
    widths = {}
    for name, lines in OSM["rivers"].items():
        for ln in lines:
            c = np.asarray(ln.coords)
            if len(c) < 2: continue
            c = densify(c, 6.0)
            a = river_profile(c)
            w = river_width(a)
            ok = a >= MIN_KM2
            for i in range(len(c) - 1):
                if not (ok[i] and ok[i + 1]): continue
                ww = (w[i] + w[i + 1]) / 2 * sc
                p, q = c[i] * sc, c[i + 1] * sc
                d.line([tuple(p), tuple(q)], fill=255, width=max(1, int(round(ww))))
                r = ww / 2
                if r >= 1:
                    d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=255)
            widths.setdefault(name, []).append((c, w, a))
    if sea_mask is not None:
        sm = Image.fromarray((sea_mask * 255).astype(np.uint8)).resize((MW * K, MH * K))
        m.paste(0, (0, 0), sm)
    composite(m, RIVER)
    del m
    return widths
