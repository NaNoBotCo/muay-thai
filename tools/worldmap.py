#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""worldmap.py — two maps, drawn as plain SVG from the harvest and from Natural Earth.

  world.svg      Equal Earth, countries shaded by how many places to train the map holds,
                 with a dot on each one. Equal Earth because the subject is how many of a
                 thing are where, and an equal-area projection is the only kind that does
                 not lie about that.
  thailand.svg   the same rows, at the scale of the country they come from.

Written into build/site/ so the pages reference a file rather than inlining ten thousand
path elements into every page that wants the picture.

    python3 tools/worldmap.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, GEO, jload  # noqa: E402
from geo import equal_earth  # noqa: E402

SITE = BUILD / "site"
# An <img> pointing at an SVG is an isolated document: it inherits nothing from the page,
# so a CSS variable defined on the page resolves to the fallback here and the sea comes out
# white on a dark page. The stylesheet below is therefore self-contained, dark mode
# included, and asks the viewer's own preference rather than the page's.
STYLE = (
    "<style>"
    ".sea{fill:#fdfbf4}.c{fill:#efe8d8;stroke:#d9cdb4;stroke-width:.5}"
    ".a{fill:#f6d8c8}.b{fill:#efb191}.c2{fill:#e2825a}.d{fill:#c8522c}.e{fill:#8f2a10}"
    ".th{fill:#f6d8c8}"
    ".dot{fill:#17110c;fill-opacity:.85;stroke:#fff;stroke-width:.5}"
    "@media (prefers-color-scheme:dark){"
    ".sea{fill:#1c1813}.c{fill:#2e2720;stroke:#453a2c}"
    ".a{fill:#5e3a2a}.b{fill:#84492f}.c2{fill:#a85a34}.d{fill:#cf7141}.e{fill:#f0a06a}"
    ".th{fill:#5e3a2a}"
    ".dot{fill:#ffc23d;fill-opacity:.9;stroke:#12100d;stroke-width:.5}}"
    "</style>")


BANDS = [(1, "a"), (3, "b"), (8, "c"), (25, "d"), (10 ** 9, "e")]


def band_of(n: int) -> str:
    for lim, cls in BANDS:
        if n <= lim:
            return cls
    return "e"


def keep(ring, min_span=0.6):
    """Drop a ring smaller than the line width it would be drawn with. At 1100 px the
    whole world is 360 degrees wide, so half a degree is under two pixels."""
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (max(lons) - min(lons)) > min_span or (max(lats) - min(lats)) > min_span


def simplify(ring, tol=0.7):
    """Keep a point only when it has moved `tol` degrees from the last one kept. Crude,
    and the right kind of crude for a map whose subject is which country, not which bay."""
    out = [ring[0]]
    for pt in ring[1:]:
        if abs(pt[0] - out[-1][0]) > tol or abs(pt[1] - out[-1][1]) > tol:
            out.append(pt)
    if len(out) < 3:
        return ring[::max(1, len(ring) // 8)]
    return out


def world_svg(counts: dict, rows: list, w=1100) -> str:
    g = jload(GEO / "countries.json")
    pts = [equal_earth(lon, lat) for lon in (-180, 180) for lat in (-90, 90)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    h = int(w * (y1 - y0) / (x1 - x0))

    def P(lon, lat):
        x, y = equal_earth(lon, lat)
        return ((x - x0) / (x1 - x0) * w, h - (y - y0) / (y1 - y0) * h)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
           f'role="img" aria-label="Places to train muay thai, by country, on an Equal Earth projection">',
           STYLE,
           f'<rect class="sea" width="{w}" height="{h}"/>']
    for c in g["countries"]:
        n = counts.get(c["name"], 0)
        cls = {"a": "a", "b": "b", "c": "c2", "d": "d", "e": "e"}[band_of(n)] if n else ""
        for ring in c["rings"]:
            if len(ring) < 4 or not keep(ring):
                continue
            ring = simplify(ring)
            d = "M" + "L".join(f"{P(p[0], p[1])[0]:.0f} {P(p[0], p[1])[1]:.0f}" for p in ring) + "Z"
            out.append(f'<path class="c {cls}" d="{d}"/>')
    for r in rows:
        x, y = P(r["lon"], r["lat"])
        out.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="2.6"/>')
    out.append("</svg>")
    return "".join(out)


def thailand_svg(rows: list, w=560) -> str:
    g = jload(GEO / "countries.json")
    box = (5.5, 97.2, 20.6, 105.8)          # S, W, N, E
    h = int(w * (box[2] - box[0]) / ((box[3] - box[1]) * 0.95))

    def P(lon, lat):
        return ((lon - box[1]) / (box[3] - box[1]) * w,
                h - (lat - box[0]) / (box[2] - box[0]) * h)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" '
           f'aria-label="Places to train muay thai in Thailand, from OpenStreetMap">',
           STYLE, f'<rect class="sea" width="{w}" height="{h}"/>']
    for c in g["countries"]:
        for ring in c["rings"]:
            lons = [p[0] for p in ring]
            lats = [p[1] for p in ring]
            if max(lons) < box[1] or min(lons) > box[3] or max(lats) < box[0] or min(lats) > box[2]:
                continue
            ring = simplify(ring, 0.03)
            d = "M" + "L".join(f"{P(p[0], p[1])[0]:.0f} {P(p[0], p[1])[1]:.0f}" for p in ring) + "Z"
            out.append(f'<path class="c {"th" if c["iso"] == "TH" else ""}" d="{d}"/>')
    for r in rows:
        if not (box[0] <= r["lat"] <= box[2] and box[1] <= r["lon"] <= box[3]):
            continue
        x, y = P(r["lon"], r["lat"])
        out.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="3"/>')
    out.append("</svg>")
    return "".join(out)


def main() -> int:
    gy = jload(BUILD / "api" / "gyms.json")
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "world.svg").write_text(world_svg(gy["by_country"], gy["rows"]), encoding="utf-8")
    (SITE / "thailand.svg").write_text(thailand_svg(gy["rows"]), encoding="utf-8")
    print(f"maps: world.svg {(SITE / 'world.svg').stat().st_size // 1024} KB · "
          f"thailand.svg {(SITE / 'thailand.svg').stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
