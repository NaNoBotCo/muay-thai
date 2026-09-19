#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_geo.py — the world's borders, once, so a harvested row can be told which country
it is in without asking a geocoder six hundred times.

Natural Earth admin-0 countries at 1:50m, public domain. Rings are kept as they arrive and
simplified only in the drawing code; the lookup in geo.py walks them directly.

    python3 tools/fetch_geo.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GEO, jdump  # noqa: E402

UA = "muay-thai-build/0.1 (https://wichaa.net; nan@motdang.net) python-urllib"
URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
       "geojson/ne_50m_admin_0_countries.geojson")


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        g = json.load(r)
    out = []
    for f in g["features"]:
        p = f["properties"]
        iso = p.get("ISO_A2_EH") or p.get("ISO_A2") or ""
        if iso in ("-99", ""):
            iso = p.get("ADM0_A3", "")[:2]
        rings = []
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            for ring in poly:
                rings.append([[round(c[0], 4), round(c[1], 4)] for c in ring])
        out.append({"iso": iso, "name": p.get("NAME_EN") or p.get("NAME"),
                    "region": p.get("REGION_UN"), "sub": p.get("SUBREGION"),
                    "continent": p.get("CONTINENT"), "rings": rings})
    jdump({"fetched": time.strftime("%Y-%m-%d"), "source": URL,
           "licence": "Natural Earth, public domain",
           "note": "admin-0 countries at 1:50m; a point within a few kilometres of a border "
                   "can fall on the wrong side, and islands smaller than the generalisation "
                   "are not in the file at all.",
           "countries": out}, GEO / "countries.json", indent=0)
    print(f"{len(out)} countries, {sum(len(c['rings']) for c in out)} rings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
