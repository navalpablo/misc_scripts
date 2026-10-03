#!/usr/bin/env bash
# 05b · Datos de relevancia desde Wikidata (CC0), vía el servidor SPARQL QLever.
#   municipios (población, nº de Wikipedias, nombres es/ca/eu/fr), comunidad autónoma,
#   monumentos y valles del área del mapa. Los usa 09_select_labels.py.
set -euo pipefail
cd "$(dirname "$0")"
EP=https://qlever.dev/api/wikidata
for q in munis_qlever regions pois valleys heritage; do
  out=wikidata/${q%_qlever}.json
  curl -sf -L --max-time 280 -A "pirineo-map/1.0" -H "Accept: application/sparql-results+json" \
       --data-urlencode "query@wikidata/q_$q.rq" "$EP" -o "$out"
  echo "  $out"
done
python3 - <<'PY'
import json
d = json.load(open("wikidata/munis.json"))["results"]["bindings"]
rows = []
for x in d:
    g = lambda k: x.get(k, {}).get("value")
    rows.append(dict(q=g("item").split("/")[-1], lon=float(g("lon")), lat=float(g("lat")), pop=float(g("pop")),
                     sl=int(g("sitelinks") or 0), es=g("les"), ca=g("lca"), eu=g("leu"), fr=g("lfr")))
json.dump(rows, open("wikidata/munis_rows.json", "w"), ensure_ascii=False)
print("  municipios:", len(rows))
PY
