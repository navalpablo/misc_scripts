"""
04b · Espacios naturales protegidos desde OpenStreetMap (capa «park» de las teselas OpenMapTiles).

Une las piezas de cada espacio que vienen cortadas por las teselas (zoom 11) y guarda el
contorno en coordenadas de píxel del mapa a resolución completa, solo para los espacios
listados en places.PARKS (parques nacionales, parques naturales y regionales).

Salida: work/parks.pkl  {nombre OSM: (Multi)Polygon}
"""
import glob, math, pickle, re
import numpy as np
import rasterio
import mapbox_vector_tile as mvt
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import unary_union
from places import PARKS

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


pats = [(p[1], re.compile(p[1])) for p in PARKS]
pieces = {}
for p in sorted(glob.glob("tiles/11_*.pbf")):
    z, x, y = map(int, re.findall(r"\d+", p.split("/")[-1]))
    d = mvt.decode(open(p, "rb").read())
    for f in d.get("park", {}).get("features", []):
        name = f["properties"].get("name") or ""
        key = next((k for k, rx in pats if rx.search(name)), None)
        if key is None:
            continue
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
        for poly in polys:
            rings = [tile_to_px(z, x, y, r) for r in poly]
            if len(rings[0]) >= 3:
                pieces.setdefault(key, []).append(Polygon(rings[0], rings[1:]).buffer(0))

parks = {}
for key, ps in pieces.items():
    # las piezas de teselas vecinas se tocan: un pequeño cierre morfológico borra las costuras
    u = unary_union([q.buffer(3) for q in ps]).buffer(-3).simplify(1.5)
    parks[key] = u
    print(f"  {key[:60]:60s} {u.area * (src.transform.a / 1000) ** 2:8.0f} km²")
missing = [p[1] for p in PARKS if p[1] not in parks]
if missing:
    print("  sin geometría:", missing)
pickle.dump(parks, open("work/parks.pkl", "wb"))
