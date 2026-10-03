"""
09 · Selección homogénea de rótulos por relevancia, con el mismo criterio en todo el mapa.

Fuentes:
  - Municipios, monumentos y valles: Wikidata (consultas en wikidata/*.rq, servidor QLever).
  - Cimas: capa mountain_peak de OpenStreetMap (teselas OpenFreeMap) + DEM Copernicus.

Criterios (iguales en España, Andorra y Francia):
  - Municipio: relevancia = log10(población) + 0.06·(nº de Wikipedias − línea base del país;
    los bots crean un artículo por municipio, así que solo cuenta el exceso).
  - Monumento o lugar de patrimonio cultural (castillo, monasterio, iglesia, cueva con arte,
    yacimiento, puente…, con protección patrimonial en Wikidata): nº de Wikipedias + 10 si es
    Patrimonio Mundial ≥ 6, fuera de los núcleos ya rotulados.
  - Valle: elemento «valle» de Wikidata con ≥ 4 Wikipedias.
  - Cima: cumbre con nombre que es el punto más alto del relieve en 8 km a la redonda.
Selección voraz por relevancia con una distancia mínima entre elementos del mismo tipo,
empezando por los elegidos a mano en places.py. Así la densidad sale pareja: donde hay
mucho donde elegir entra lo más relevante; donde hay poco, lo más relevante del lugar.

Salida: work/auto_labels.json
"""
import json, glob, math, os, re
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform as tx
from scipy import ndimage as nd
import mapbox_vector_tile as mvt
from places import TOWNS, POIS, POIS_WD, PEAKS, VALLEYS, AREAS

D_TOWN, D_POI, D_VALLEY, D_PEAK = 12e3, 9e3, 15e3, 16e3      # metros
MIN_POP, MIN_POI_SL, MIN_VALLEY_SL = 150, 5, 4

src = rasterio.open("work/dem_lcc.tif")
inv = ~src.transform
H, W = src.height, src.width
sea4 = np.load("work/mask_sea_f4.npy")

def proj(lon, lat):
    X, Y = tx("EPSG:4326", src.crs, list(np.atleast_1d(lon)), list(np.atleast_1d(lat)))
    return np.array(X), np.array(Y)

def inside(lon, lat, margin_px=60):
    X, Y = proj(lon, lat)
    c, r = inv * (X[0], Y[0])
    return (margin_px < c < W - margin_px and margin_px < r < H - margin_px
            and not sea4[int(r / 4), int(c / 4)])

def greedy(cands, seeds, D, key):
    """cands: dicts con lon/lat; seeds: [(X, Y)] ya ocupados. Devuelve los elegidos."""
    sel = list(seeds); out = []
    for r in sorted(cands, key=key):
        X, Y = proj(r["lon"], r["lat"]); X, Y = X[0], Y[0]
        if all(math.hypot(X - a, Y - b) >= D for a, b in sel):
            sel.append((X, Y)); out.append(r)
    return out

def xy_list(items):
    if not items: return []
    X, Y = proj([i[0] for i in items], [i[1] for i in items])
    return list(zip(X, Y))

def far_from(points, lon, lat, d):
    X, Y = proj(lon, lat)
    return all(math.hypot(X[0] - a, Y[0] - b) >= d for a, b in points)

def cap(s):
    return s[:1].upper() + s[1:] if s else s

# ---------------------------------------------------------------- municipios
rows = json.load(open("wikidata/munis_rows.json"))
reg = {}
for x in json.load(open("wikidata/regions.json"))["results"]["bindings"]:
    reg.setdefault(x["item"]["value"].split("/")[-1], set()).add(x["reg"]["value"].split("/")[-1])

def region(q):
    R = reg.get(q, set())
    if "Q228" in R: return "AD"
    if "Q5705" in R: return "CAT"
    if "Q95010" in R: return "GIP"
    if "Q4018" in R: return "NAV"
    if R: return "ES"
    return "FR"

def town_name(r):
    g = r["region"]
    if g in ("AD", "CAT"):
        n = r["ca"] or r["es"]
    elif g == "GIP":
        n = r["eu"] or r["es"]
    elif g == "NAV":
        n = r["es"] or r["eu"]
        if "/" in n:
            n = " · ".join(p.strip() for p in n.split("/"))
        elif r["eu"] and r["eu"] != n and r["lat"] > 42.75:
            n = f"{n} · {r['eu']}"
    elif g == "ES":
        n = r["es"] or r["ca"]
        if "/" in n: n = n.split("/")[0].strip()
    else:
        n = r["fr"] or r["es"]
    return cap(n)

for r in rows:
    r["region"] = region(r["q"])
    base = 36 if r["region"] == "FR" else 39
    r["score"] = math.log10(max(r["pop"], 1)) + 0.06 * (r["sl"] - base)
    r["name"] = town_name(r) if (r["es"] or r["fr"] or r["ca"]) else None

town_seed = xy_list([(t[1], t[2]) for t in TOWNS])
cand = [r for r in rows if r["pop"] >= MIN_POP and r["name"] and inside(r["lon"], r["lat"])
        and far_from(town_seed, r["lon"], r["lat"], 3000)]
towns = greedy(cand, town_seed, D_TOWN, key=lambda r: -r["score"])
print("municipios añadidos:", len(towns))
all_town_xy = town_seed + xy_list([(t["lon"], t["lat"]) for t in towns])

def nearest_region(lon, lat):
    best = min(rows, key=lambda r: (r["lon"] - lon) ** 2 + ((r["lat"] - lat) * 1.35) ** 2)
    return best["region"]

def local_label(x, g):
    lab = {"es": x.get("les"), "ca": x.get("lca"), "fr": x.get("lfr"), "eu": x.get("leu")}
    if g in ("CAT", "AD"): order = ["ca", "es", "fr"]
    elif g == "FR": order = ["fr", "es", "ca"]
    else: order = ["es", "ca", "fr"]
    for k in order:
        if lab[k]: return cap(lab[k])
    return None

def wd_rows(path):
    out = []
    for x in json.load(open(path))["results"]["bindings"]:
        g = {k: v["value"] for k, v in x.items()}
        out.append(dict(q=g["item"].split("/")[-1], lon=float(g["lon"]), lat=float(g["lat"]),
                        sl=int(g.get("sitelinks", 0)), les=g.get("les"), lca=g.get("lca"),
                        lfr=g.get("lfr"), leu=g.get("leu"), type=g.get("type", "").split("/")[-1]))
    return out

# ---------------------------------------------------------------- monumentos y patrimonio
# Dos consultas de Wikidata: tipos de monumento (pois.json) y todo lo que tiene una protección
# patrimonial (P1435: BIC, monument historique, BCIN, Patrimonio Mundial…; heritage.json).
# Se queda lo que por su nombre es un monumento visitable (castillo, monasterio, iglesia, cueva,
# yacimiento, puente…) y se ordena por nº de Wikipedias, con +10 si es Patrimonio Mundial.
POI_TYPES = {"Q23413", "Q44613", "Q160742", "Q2977", "Q57821", "Q839954", "Q16560", "Q817056", "Q1785071"}
POI_WORDS = re.compile(
    r"\b(castillo|castell|ch[aâ]teau|castro|monasterio|monestir|monast[eè]re|abad[ií]a|abbaye|abbatiale|abadia|"
    r"catedral|cath[ée]drale|colegiata|col·legiata|coll[ée]giale|bas[ií]lica|basilique|iglesia|esgl[ée]sia|[ée]glise|"
    r"ermita|chapelle|capilla|santuario|santuari|sanctuaire|cueva|cuevas|cova|grotte|grottes|gruta|fuerte|fort|"
    r"forteresse|fortaleza|palacio|palau|palais|puente|pont|torre|tour|oppidum|ciudad|ciutat|yacimiento|jaciment|"
    r"dolmen|priorat|prieur[ée]|priorato|claustro|clo[îi]tre|muralla|ruinas|ru[ïi]nes|villa|termas|thermes|cit[ée])\b", re.I)
POI_SKIP = re.compile(r"estaci[óo]n|estaci[óo]|\bgare\b|museo|mus[ée]e|museu|teatro|th[ée][âa]tre|parlament|"
                      r"ayuntamiento|consistorial|h[ôo]tel de ville|mairie|escuela|[ée]cole|colegio|cementerio|"
                      r"cimeti[èe]re|monument aux morts|orgue|[óo]rgano|retablo|retable|\bcruz\b|\bcroix\b|\bcreu\b|"
                      r"calvaire|fuente|fontaine|mercado|march[ée]|lavoir|lavadero|observatori|horno|four|forn|"
                      r"tren|train|canal|parque|parc|valle|vall\b|zona|camino|chemin|sender|ruta|russe|^h[ôo]tel |forau|\bfoz\b|gorges|cirque", re.I)

def poi_ok(p):
    labs = [p.get(k) for k in ("les", "lca", "lfr", "leu") if p.get(k)]
    return any(POI_WORDS.search(l) for l in labs) and not any(POI_SKIP.search(l) for l in labs)

seen_q = set(); pois_raw = []
for p in wd_rows("wikidata/pois.json"):
    labs = [p.get(k) for k in ("les", "lca", "lfr", "leu") if p.get(k)]
    if p["type"] in POI_TYPES and not any(POI_SKIP.search(l) for l in labs):
        p["unesco"] = 0; seen_q.add(p["q"]); pois_raw.append(p)
if os.path.exists("wikidata/heritage.json"):
    for x in json.load(open("wikidata/heritage.json"))["results"]["bindings"]:
        g = {k: v["value"] for k, v in x.items()}
        q = g["item"].split("/")[-1]
        if q in seen_q: continue
        p = dict(q=q, lon=float(g["lon"]), lat=float(g["lat"]), sl=int(g.get("sitelinks", 0)),
                 les=g.get("les"), lca=g.get("lca"), lfr=g.get("lfr"), leu=g.get("leu"),
                 type=g.get("type", "").split("/")[-1], unesco=int(g.get("unesco", 0)))
        if poi_ok(p):
            seen_q.add(q); pois_raw.append(p)
for p in pois_raw:
    p["score"] = p["sl"] + 10 * p.get("unesco", 0)
pois_raw = [p for p in pois_raw if p["score"] >= MIN_POI_SL and inside(p["lon"], p["lat"])]
poi_seed = xy_list([(p[1], p[2]) for p in POIS + POIS_WD])
# fuera de los núcleos rotulados (los muy relevantes pueden quedar a 1,4 km de su centro)
pois_raw = [p for p in pois_raw if far_from(all_town_xy, p["lon"], p["lat"], 1400 if p["score"] >= 11 else 2500)
            and far_from(poi_seed, p["lon"], p["lat"], 4000)]
pois = greedy(pois_raw, poi_seed, D_POI, key=lambda p: -p["score"])
def short_poi(n):
    """Acorta nombres largos: «Cathédrale Notre-Dame-de-… de Lescar» -> «Cathédrale de Lescar»."""
    m = re.match(r"^(Cathédrale|Catedral|Catedral de [^ ]+|Abbaye|Monastère)\b.* (de |d')([A-ZÀ-Ý][^ ]*(?: [^ ]+)?)$", n)
    if m and len(n) > 28:
        return f"{m.group(1).split(' ')[0]} {m.group(2)}{m.group(3)}"
    n = re.sub(r" et d'.*$", "", n)                       # «Grottes d'Isturitz et d'Oxocelhaya»
    n = re.sub(r"^(Église|Iglesia|Església) (Saint|Sainte|San|Santa|Sant)", r"\2", n)
    n = re.sub(r"\s*\(.*\)$", "", n)
    return n
RENAME = {"Iglesia de El Salvador": "El Salvador de Agüero"}      # nombres genéricos de Wikidata
for p in pois:
    p["name"] = local_label(p, nearest_region(p["lon"], p["lat"]))
    if p["name"]: p["name"] = RENAME.get(short_poi(p["name"]), short_poi(p["name"]))
pois = [p for p in pois if p["name"] and len(p["name"]) <= 34]
print("monumentos añadidos:", len(pois), [(p["name"], p["score"]) for p in pois])

# ---------------------------------------------------------------- valles
val_raw = [v for v in wd_rows("wikidata/valleys.json") if v["sl"] >= MIN_VALLEY_SL and inside(v["lon"], v["lat"])]
val_seed = xy_list([(v[2], v[3]) for v in VALLEYS] + [(a[1], a[2]) for a in AREAS if a[3] == "valley"])
val_raw = [v for v in val_raw if far_from(val_seed, v["lon"], v["lat"], 8000)]
valleys = greedy(val_raw, val_seed, D_VALLEY, key=lambda v: -v["sl"])
seen = set(); vv = []
for v in valleys:
    v["name"] = local_label(v, nearest_region(v["lon"], v["lat"]))
    if v["name"] and v["name"] not in seen:
        seen.add(v["name"]); vv.append(v)
valleys = vv
print("valles añadidos:", len(valleys), [v["name"] for v in valleys])

# ---------------------------------------------------------------- cimas
def tile_ll(z, x, y, c, ext=4096):
    n = 2 ** z; gx = (x + c[0] / ext) / n; gy = (y + 1 - c[1] / ext) / n
    return gx * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * gy))))
peaks_osm = {}
for p in glob.glob("tiles/11_*.pbf"):
    z, x, y = map(int, re.findall(r"\d+", p.split("/")[-1]))
    d = mvt.decode(open(p, "rb").read())
    for f in d.get("mountain_peak", {}).get("features", []):
        pr = f["properties"]
        if f["geometry"]["type"] != "Point" or not pr.get("name") or pr.get("class") not in (None, "peak", "volcano"):
            continue
        lon, lat = tile_ll(z, x, y, f["geometry"]["coordinates"])
        peaks_osm.setdefault((pr["name"], round(lon, 3), round(lat, 3)), (lon, lat, pr.get("ele")))
Q = 4
dem = src.read(1); dem[dem < -9000] = 0
dem4 = dem[:H // Q * Q, :W // Q * Q].reshape(H // Q, Q, W // Q, Q).max(axis=(1, 3)); del dem
R8 = int(8000 / (src.transform.a * Q))
yy, xx = np.mgrid[-R8:R8 + 1, -R8:R8 + 1]
dommax = nd.maximum_filter(dem4, footprint=(xx ** 2 + yy ** 2) <= R8 ** 2)
peak_cands = []
for (name, _, _), (lon, lat, ele) in peaks_osm.items():
    if not inside(lon, lat, 120): continue
    X, Y = proj(lon, lat); c, r = inv * (X[0], Y[0]); c4, r4 = int(c / Q), int(r / Q)
    w = dem4[max(0, r4 - 8):r4 + 9, max(0, c4 - 8):c4 + 9]               # ~900 m alrededor
    zloc = float(w.max())
    if zloc < 800 or zloc + 15 < dommax[r4, c4]:
        continue                                                      # no domina 8 km a la redonda
    try: e = int(round(float(ele)))
    except (TypeError, ValueError): e = int(round(zloc))
    if abs(e - zloc) > 150: e = int(round(zloc))
    peak_cands.append(dict(name=cap(name.strip()), lon=lon, lat=lat, ele=e))
peak_seed = xy_list([(p[2], p[3]) for p in PEAKS])
peak_cands = [p for p in peak_cands if far_from(peak_seed, p["lon"], p["lat"], 4000)]
peaks = greedy(peak_cands, peak_seed, D_PEAK, key=lambda p: -p["ele"])
seen = set(); peaks = [p for p in peaks if not (p["name"] in seen or seen.add(p["name"]))]
print("cimas añadidas:", len(peaks), [(p["name"], p["ele"]) for p in peaks])

json.dump(dict(
    towns=[dict(name=t["name"], lon=t["lon"], lat=t["lat"], pop=int(t["pop"]), score=round(t["score"], 2)) for t in towns],
    pois=[dict(name=p["name"], lon=p["lon"], lat=p["lat"], sl=p["sl"], score=p["score"]) for p in pois],
    valleys=[dict(name=v["name"], lon=v["lon"], lat=v["lat"], sl=v["sl"]) for v in valleys],
    peaks=peaks), open("work/auto_labels.json", "w"), ensure_ascii=False, indent=1)
