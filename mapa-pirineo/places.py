"""
Toponimia del mapa. Coordenadas WGS84 (lon, lat) de fuentes públicas;
las cimas se recolocan después sobre el máximo local real del DEM.
pos: lado del rótulo respecto al punto: r, l, t, b, tr, tl, br, bl
"""

# nombre, altitud oficial (m), lon, lat, pos
PEAKS = [
    ("Aneto",              3404,  0.6567, 42.6311, "b"),
    ("Posets",             3375,  0.4361, 42.6547, "l"),
    ("Monte Perdido",      3355,  0.0347, 42.6750, "b"),
    ("Vignemale",          3298, -0.1469, 42.7731, "r"),
    ("Balaitús",           3144, -0.2928, 42.8389, "t"),
    ("Pica d'Estats",      3143,  1.3972, 42.6667, "t"),
    ("Comapedrosa",        2942,  1.4469, 42.5839, "l"),
    ("Cotiella",           2912,  0.3192, 42.5156, "b"),
    ("Puigmal",            2910,  2.1167, 42.3833, "b"),
    ("Collarada",          2886, -0.4797, 42.7183, "r"),
    ("Midi d'Ossau",       2884, -0.4381, 42.8433, "l"),
    ("Pic du Midi de Bigorre", 2877, 0.1411, 42.9364, "t"),
    ("Mont Valier",        2838,  1.0858, 42.7975, "t"),
    ("Canigó",             2784,  2.4567, 42.5192, "t"),
    ("Bisaurín",           2670, -0.6447, 42.7952, "l"),
    ("Pedraforca",         2506,  1.7031, 42.2394, "b"),
    ("Anie",               2504, -0.7225, 42.9489, "t"),
    ("Guara",              2077, -0.2286, 42.2869, "b"),
    ("Orhi",               2017, -1.0050, 42.9897, "t"),
    ("Oroel",              1769, -0.5108, 42.5197, "b"),
    ("Larrun",              905, -1.6356, 43.3089, "b"),
]

# nombre, lon, lat, pos, rango (1 ciudad, 2 villa)
TOWNS = [
    ("Pamplona · Iruña",     -1.6458, 42.8125, "b", 1),
    ("Huesca",               -0.4083, 42.1361, "r", 1),
    ("Pau",                  -0.3708, 43.2951, "t", 1),
    ("Tarbes",                0.0781, 43.2328, "r", 1),
    ("Perpinyà · Perpignan",  2.8956, 42.6986, "t", 1),
    ("Baiona · Bayonne",     -1.4748, 43.4929, "r", 1),
    ("Donostia",             -1.9812, 43.3183, "b", 1),
    ("Andorra la Vella",      1.5218, 42.5063, "b", 2),
    ("Lourdes",              -0.0458, 43.0947, "r", 2),
    ("Foix",                  1.6075, 42.9653, "r", 2),
    ("Saint-Gaudens",         0.7233, 43.1081, "r", 2),
    ("Oloron",               -0.6067, 43.1942, "r", 2),
    ("Donibane Garazi",      -1.2378, 43.1631, "r", 2),
    ("Puigcerdà",             1.9283, 42.4317, "b", 2),
    ("La Seu d'Urgell",       1.4561, 42.3586, "b", 2),
    ("Sabiñánigo",           -0.3644, 42.5186, "r", 2),
    ("Aínsa",                 0.1394, 42.4186, "b", 2),
    ("Benasque",              0.5236, 42.6047, "l", 2),
    ("Vielha",                0.7956, 42.7017, "r", 2),
    ("Figueres",              2.9614, 42.2667, "b", 2),
    ("Tremp",                 0.8947, 42.1667, "r", 2),
    ("Ripoll",                2.1903, 42.2014, "r", 2),
    ("Canfranc",             -0.5253, 42.7144, "l", 2),
    ("Jaca",                 -0.5494, 42.5700, "t", 2),
]

# rótulos de área: texto, lon, lat, estilo
AREAS = [
    ("FRANCIA",            0.30, 43.36, "country"),
    ("ESPAÑA",            -0.95, 42.25, "country"),
    ("ANDORRA",            1.56, 42.62, "small_country"),
    ("Canal de Berdún",   -0.86, 42.615, "valley"),
    ("Valle de Tena",     -0.30, 42.735, "valley"),
    ("Val d'Aran",         0.84, 42.775, "valley"),
    ("Ordesa",             0.01, 42.625, "valley"),
    ("Cerdanya",           1.98, 42.48, "valley"),
    ("Golfo de Bizkaia",  -1.78, 43.50, "sea"),
]

# Ríos: rótulo, patrón del nombre OSM (regex), lon, lat del punto donde centrar el rótulo, tamaño
RIVERS = [
    ("Aragón",             r"^Río Aragón$",          -0.80, 42.590, 1),
    ("Aragón Subordán",    r"Subordán",              -0.735, 42.69, 2),
    ("Gállego",            r"Gállego",               -0.40, 42.36, 1),
    ("Ara",                r"^(Río )?Ara$",          -0.02, 42.555, 2),
    ("Cinca",              r"^Río Cinca$",            0.17, 42.27, 1),
    ("Ésera",              r"sera$",                  0.47, 42.47, 2),
    ("Noguera Ribagorzana", r"Ribagor",               0.72, 42.33, 2),
    ("Noguera Pallaresa",  r"Noguera Pallaresa$",     1.06, 42.42, 2),
    ("Segre",              r"^el Segre$",             1.66, 42.40, 1),
    ("Ter",                r"^Riu Ter$",              2.28, 42.17, 1),
    ("Têt",                r"^La Têt$",               2.55, 42.62, 1),
    ("Tech",               r"^Le Tech$",              2.70, 42.47, 2),
    ("Aude",               r"^L'Aude$",               2.22, 42.92, 1),
    ("Ariège",             r"^L'Ariège$",             1.62, 43.08, 1),
    ("Garonne",            r"^La Garonne$",           0.95, 43.12, 1),
    ("Adour",              r"^L'Adour$",              0.10, 43.26, 1),
    ("Gave de Pau",        r"^Le Gave de Pau$",      -0.18, 43.17, 1),
    ("Gave d'Oloron",      r"^Le Gave d'Oloron$",    -0.80, 43.30, 1),
    ("Nive",               r"^La Nive$",             -1.35, 43.28, 2),
    ("Bidasoa",            r"Bidasoa",               -1.68, 43.20, 2),
    ("Arga",               r"^Arga$",                -1.72, 42.62, 1),
    ("Irati",              r"^Irati$",               -1.30, 42.76, 2),
]
