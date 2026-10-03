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
ROAD_MAJOR = (166, 76, 54)
ROAD_PRIMARY = (150, 98, 74)
ROAD_SECONDARY = (150, 112, 92)
BORDER = (104, 58, 98)

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


NATURE = (58, 112, 62)          # contorno de espacios protegidos
NATURE_BAND = (96, 156, 84)     # cinta interior
# tipo: (ancho de la cinta interior, opacidad de la cinta, grosor de línea, trazo discontinuo)
PARK_STYLE = {1: (40, 0.42, 3.4, None), 2: (26, 0.32, 2.6, None), 3: (20, 0.26, 2.4, (26, 14))}


def draw_parks(canvas, OX, OY, F, MW, MH, parks, kinds, sea_mask=None):
    """Espacios protegidos: cinta verde difuminada por dentro del contorno + línea fina.
    parks: {clave: (Multi)Polygon en px de resolución completa}; kinds: {clave: 1|2|3}."""
    S = 1 / F
    K = 2
    land = None
    if sea_mask is not None:
        land = Image.fromarray(((~sea_mask) * 255).astype(np.uint8)).resize((MW, MH))
    for kind in (3, 2, 1):
        keys = [k for k in parks if kinds.get(k) == kind]
        if not keys:
            continue
        bw, bop, lw, dash = PARK_STYLE[kind]
        fill = Image.new("L", (MW, MH), 0); edge = Image.new("L", (MW, MH), 0)
        line = Image.new("L", (MW * K, MH * K), 0)
        df, de, dl = ImageDraw.Draw(fill), ImageDraw.Draw(edge), ImageDraw.Draw(line)
        for k in keys:
            g = parks[k]
            for poly in (g.geoms if hasattr(g, "geoms") else [g]):
                rings = [np.asarray(poly.exterior.coords)] + [np.asarray(h.coords) for h in poly.interiors]
                for i, ring in enumerate(rings):
                    pts = [tuple(p) for p in ring * S]
                    if len(pts) < 3:
                        continue
                    df.polygon(pts, fill=255 if i == 0 else 0)
                    de.line(pts + [pts[0]], fill=255, width=max(1, int(round(2 * bw * S))), joint="curve")
                    c = densify(ring, 2.0)
                    if dash is None:
                        dl.line([tuple(p) for p in c * S * K], fill=255, width=max(1, int(round(lw * S * K))),
                                joint="curve")
                    else:
                        seg = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
                        on = (seg % sum(dash)) < dash[0]
                        run = []
                        for p, o in zip(c, on):
                            if o:
                                run.append(tuple(p * S * K))
                            elif run:
                                if len(run) > 1:
                                    dl.line(run, fill=255, width=max(1, int(round(lw * S * K))))
                                run = []
                        if len(run) > 1:
                            dl.line(run, fill=255, width=max(1, int(round(lw * S * K))))
        # cinta: el contorno grueso difuminado, solo por dentro del espacio y sobre tierra
        band = edge.filter(ImageFilter.GaussianBlur(max(1, bw * S * 0.45)))
        band = Image.fromarray((np.asarray(band, np.uint16) * np.asarray(fill, np.uint16) // 255).astype(np.uint8))
        lin = line.resize((MW, MH), Image.BOX)
        if land is not None:
            band = Image.fromarray((np.asarray(band, np.uint16) * np.asarray(land, np.uint16) // 255).astype(np.uint8))
            lin = Image.fromarray((np.asarray(lin, np.uint16) * np.asarray(land, np.uint16) // 255).astype(np.uint8))
        canvas.paste(Image.new("RGB", (MW, MH), NATURE_BAND), (OX, OY), band.point(lambda v: int(v * bop)))
        canvas.paste(Image.new("RGB", (MW, MH), NATURE), (OX, OY), lin.point(lambda v: int(v * 0.85)))
        del fill, edge, line, band, lin


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
    for key, col, w, op in (("secondary", ROAD_SECONDARY, 2.0, 0.40),
                            ("primary", ROAD_PRIMARY, 3.0, 0.68),
                            ("major", ROAD_MAJOR, 4.4, 0.80)):
        m = new_mask(); d = ImageDraw.Draw(m)
        for ln in OSM["roads"][key]:
            poly_line(d, np.asarray(ln.coords), w)
        composite(m, col, op)
        del m

    # ---------- frontera: cinta suave + línea de trazo y punto
    m = new_mask(); d = ImageDraw.Draw(m)
    for ln in OSM["border"]:
        poly_line(d, np.asarray(ln.coords), 42)
    composite(m, BORDER, 0.24, blur=max(1, 7 * S))
    m = new_mask(); d = ImageDraw.Draw(m)
    pattern = [(46, True), (16, False), (9, True), (16, False)]   # trazo, hueco, punto, hueco
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
                if len(run) > 1: poly_line(d, np.array(run), 6.5)
                run = []
        if len(run) > 1: poly_line(d, np.array(run), 6.5)
    composite(m, BORDER, 0.95)
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
    # máscara de embalses y lagos (a 1x) para que los ríos no se dibujen por dentro;
    # se erosiona ~6 px para que el río llegue hasta la orilla y para ignorar riberas estrechas
    water1x = np.asarray(fill.resize((MW, MH), Image.BOX)) > 127
    water1x = nd.binary_erosion(water1x, iterations=max(1, int(round(6 * S))))
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
    m1 = np.asarray(m.resize((MW, MH), Image.BOX)).copy()
    del m
    m1[water1x] = 0                                   # dentro de embalses y lagos se ve el agua, no el río
    del water1x
    canvas.paste(Image.new("RGB", (MW, MH), RIVER), (OX, OY), Image.fromarray(m1))
    del m1
    return widths
