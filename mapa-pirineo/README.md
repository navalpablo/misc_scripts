# Pirineos — mapa de relieve para imprimir (150 cm)

Lámina decorativa de los Pirineos, del golfo de Bizkaia al cabo de Creus, pensada para
imprimir a **150 × 70 cm** (mapa de 140 cm a ~301 ppp, escala 1:320.000) y enmarcar.

![vista previa](preview.jpg)

**Todo se calcula a partir de datos cartográficos reales, sin generación de imágenes por IA:**

| Elemento | Fuente |
|---|---|
| Relieve sombreado, tintas hipsométricas, nieve en cotas altas | Copernicus DEM GLO-30 (30 m) — © DLR e.V. 2010–2014, © Airbus Defence and Space GmbH 2014–2018, programa Copernicus (UE/ESA) |
| Grosor de los ríos (crece aguas abajo) | Área de cuenca calculada sobre el mismo DEM (`pysheds`) |
| Ríos, lagos, embalses, ibones, carreteras, frontera | © colaboradores de OpenStreetMap (ODbL), vía teselas OpenMapTiles de OpenFreeMap |
| Cimas | Coordenadas públicas, recolocadas sobre el máximo real del DEM; altitudes oficiales |
| Tipografías | Cormorant Garamond, EB Garamond, Josefin Sans (SIL OFL) |

## Cómo se genera

```bash
pip install -r requirements.txt
./run_all.sh            # lámina completa: output/pirineo_150cm.{tif,png}
F=4 ./run_all.sh        # vista previa rápida a 1/4 de resolución (work/compose_f4.png)
```

| Paso | Script | Qué hace |
|---|---|---|
| 0 | `00_download.sh` | Descarga los tiles del DEM (~650 MB), las teselas OSM (~30 MB) y las fuentes |
| 1 | `01_prepare_dem.py` | Mosaico y reproyección a cónica conforme de Lambert centrada en 0°43′ E (27 m/píxel) |
| 2 | `02_render_relief.py` | Sombreado multidireccional (luz del NO), oclusión de valles, tintas por cota, sombras frías, perspectiva aérea, mar con líneas de agua |
| 3 | `04_osm_hydro_roads.py` | Extrae ríos/agua/carreteras/frontera de OSM y calcula el área de cuenca |
| 4 | `03_compose.py` | Lámina final: ríos y carreteras (`linework.py`), rótulos de cimas, poblaciones y ríos, gratícula, cartela, leyenda y créditos |

Toponimia y posiciones de rótulos en `places.py` (fácil de editar: añadir un pico, mover un nombre, etc.).

## Imprimir

- Archivo: `output/pirineo_150cm.tif` (17.731 × 8.286 px, 301 ppp, RGB).
- Papel mate o *fine art* (algodón / Hahnemühle Photo Rag o similar); evitar brillo.
- Marco fino de madera natural o negro; el propio diseño ya incluye margen de paspartú.
