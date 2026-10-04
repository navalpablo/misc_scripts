"""
04c · Túneles de carretera desde OpenStreetMap (capa «transportation», brunnel=tunnel).

04_osm_hydro_roads.py deja fuera los túneles, así que las carreteras se cortan en Somport,
Monrepós, Bielsa, Vielha, el Cadí… Aquí se guardan aparte para dibujarlos como trazo discontinuo
(versión alternativa de la lámina).

Salida: work/tunnels.pkl  {"major": [LineString], "primary": [...], "secondary": [...]}
"""
import glob, math, pickle, re
import numpy as np
import rasterio
import mapbox_vector_tile as mvt
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.ops import linemerge, unary_union

src = rasterio.open("work/dem_lcc.tif")
T = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
inv = ~src.transform


def tile_to_px(z, x, y, coords, extent=4096):
    a = np.asarray(coords, float)
    n = 2 ** z
    gx = (x + a[:, 0] / extent) / n
    gy = (y + 1 - a[:, 1] / extent) / n
    lon = gx * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * gy))))
    X, Y = T.transform(lon, lat)
    c, r = inv * (X, Y)
    return np.column_stack([c, r])


tun = {"major": [], "primary": [], "secondary": []}
for p in sorted(glob.glob("tiles/11_*.pbf")):
    z, x, y = map(int, re.findall(r"\d+", p.split("/")[-1]))
    d = mvt.decode(open(p, "rb").read())
    for f in d.get("transportation", {}).get("features", []):
        pr = f["properties"]; cl = pr.get("class")
        if pr.get("brunnel") != "tunnel":
            continue
        key = ("major" if cl in ("motorway", "trunk") else "primary" if cl == "primary"
               else "secondary" if cl == "secondary" else None)
        if not key:
            continue
        g = f["geometry"]
        lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []
        for ln in lines:
            if len(ln) >= 2:
                tun[key].append(LineString(tile_to_px(z, x, y, ln)))


def merged(ls):
    if not ls:
        return []
    u = unary_union(ls)
    if u.geom_type == "LineString":
        return [u]
    m = linemerge(u)
    return list(m.geoms) if hasattr(m, "geoms") else [m]


tun = {k: merged(v) for k, v in tun.items()}
print("túneles:", {k: (len(v), round(sum(l.length for l in v) * src.transform.a / 1000, 1)) for k, v in tun.items()},
      "(nº, km)")
pickle.dump(tun, open("work/tunnels.pkl", "wb"))
