"""
04 · Hidrografía y red viaria desde OpenStreetMap + área de cuenca desde el DEM.

  - Teselas vectoriales OpenMapTiles de OpenFreeMap (datos © OpenStreetMap), zoom 11.
  - Ríos (class=river) con su nombre, láminas de agua (lagos, embalses, ibones),
    autopistas/autovías, nacionales/primarias, frontera internacional.
  - Área de cuenca drenada (pysheds sobre el DEM a ~108 m) para dar a cada tramo
    de río un grosor creciente aguas abajo.

Salida: work/osm.pkl  (geometrías en coordenadas de píxel del mapa a resolución completa)
"""
import glob, math, pickle, re
import numpy as np
if not hasattr(np, "in1d"): np.in1d = np.isin   # pysheds con numpy 2.x
import rasterio
from rasterio.enums import Resampling
import mapbox_vector_tile as mvt
from pyproj import Transformer
from shapely.geometry import shape, LineString, MultiLineString, Polygon, MultiPolygon
from shapely.ops import linemerge, unary_union

src = rasterio.open("work/dem_lcc.tif")
T = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
inv = ~src.transform

def tile_to_px(z, x, y, coords, extent=4096):
    """coords en espacio de tesela (origen abajo-izquierda en mapbox_vector_tile) -> píxel del mapa."""
    a = np.asarray(coords, float)
    n = 2 ** z
    gx = (x + a[:, 0] / extent) / n
    gy = (y + 1 - a[:, 1] / extent) / n
    lon = gx * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * gy))))
    X, Y = T.transform(lon, lat)
    c, r = inv * (X, Y)
    return np.column_stack([c, r])

def lines_of(geom):
    t = geom["type"]
    if t == "LineString": return [geom["coordinates"]]
    if t == "MultiLineString": return geom["coordinates"]
    return []

def polys_of(geom):
    t = geom["type"]
    if t == "Polygon": return [geom["coordinates"]]
    if t == "MultiPolygon": return geom["coordinates"]
    return []

rivers, roads, border, water = {}, {"major": [], "primary": [], "secondary": []}, [], []
for p in sorted(glob.glob("tiles/11_*.pbf")):
    z, x, y = map(int, re.findall(r"\d+", p.split("/")[-1]))
    d = mvt.decode(open(p, "rb").read())
    for f in d.get("waterway", {}).get("features", []):
        pr = f["properties"]
        if pr.get("class") != "river" or pr.get("brunnel") == "tunnel":
            continue
        name = pr.get("name:es") if False else pr.get("name") or ""
        for ln in lines_of(f["geometry"]):
            rivers.setdefault(name, []).append(LineString(tile_to_px(z, x, y, ln)))
    for f in d.get("transportation", {}).get("features", []):
        pr = f["properties"]; cl = pr.get("class")
        if pr.get("brunnel") == "tunnel":
            continue
        key = ("major" if cl in ("motorway", "trunk") else "primary" if cl == "primary"
               else "secondary" if cl == "secondary" else None)
        if key:
            for ln in lines_of(f["geometry"]):
                roads[key].append(LineString(tile_to_px(z, x, y, ln)))
    for f in d.get("boundary", {}).get("features", []):
        pr = f["properties"]
        if pr.get("admin_level") == 2 and not pr.get("maritime"):
            for ln in lines_of(f["geometry"]):
                border.append(LineString(tile_to_px(z, x, y, ln)))
    for f in d.get("water", {}).get("features", []):
        pr = f["properties"]
        if pr.get("class") in ("lake", "river") and not pr.get("intermittent"):
            for poly in polys_of(f["geometry"]):
                rings = [tile_to_px(z, x, y, r) for r in poly]
                water.append(Polygon(rings[0], rings[1:]).buffer(0))

def merged(ls):
    u = unary_union(ls)
    if u.geom_type == "LineString":
        return [u]
    m = linemerge(u)
    return list(m.geoms) if hasattr(m, "geoms") else [m]

rivers = {k: merged(v) for k, v in rivers.items()}
roads = {k: merged(v) for k, v in roads.items()}
border = merged(border)
water = [w for w in (unary_union(water).geoms if hasattr(unary_union(water), "geoms") else [unary_union(water)])]
water = [w for w in water if w.area > 30]      # > ~2 ha
print("ríos:", len(rivers), "tramos:", sum(len(v) for v in rivers.values()))
print("carreteras:", {k: len(v) for k, v in roads.items()}, "frontera:", len(border), "agua:", len(water))

Q = 4
pickle.dump(dict(rivers=rivers, roads=roads, border=border, water=water, Q=Q),
            open("work/osm.pkl", "wb"))

# ---------- área de cuenca (km²) con pysheds a 1/4 de resolución
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
Q = 4
with rasterio.open("work/dem_lcc.tif") as s:
    dem = s.read(1, out_shape=(s.height // Q, s.width // Q), resampling=Resampling.average)
    tr = s.transform * s.transform.scale(s.width / dem.shape[1], s.height / dem.shape[0])
dem[dem < -9000] = 0
dem = np.where(dem <= 0, -50, dem).astype(np.float64)   # el mar como sumidero
import pyproj
vf = ViewFinder(affine=tr, shape=dem.shape, crs=pyproj.Proj(src.crs.to_proj4()), nodata=-9999.0)
r = Raster(dem, viewfinder=vf)
grid = Grid(viewfinder=vf)
r = grid.fill_pits(r); r = grid.fill_depressions(r); r = grid.resolve_flats(r)
fdir = grid.flowdir(r)
acc = np.asarray(grid.accumulation(fdir), np.float32)
cell_km2 = (src.transform.a * Q) ** 2 / 1e6
acc_km2 = acc * cell_km2
# máximo local en 3x3 para que los ríos OSM (no exactamente sobre el talweg del DEM) lo capten
from scipy import ndimage as nd
acc_km2 = nd.maximum_filter(acc_km2, 5)
np.save("work/acc_km2_q4.npy", acc_km2)
print("cuenca máx km²:", acc_km2.max())

