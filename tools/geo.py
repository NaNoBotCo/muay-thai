#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""geo.py — where a point is, and how to draw it.

`country_of` answers which country a harvested row sits in, by ray casting against
data/geo/countries.json (Natural Earth 1:50m, public domain). Bounding boxes are tested
first so a gym in Bangkok does not walk the coastline of Canada.

The map drawing lives here too: one equal-area world projection and one Thailand frame,
both writing plain SVG with no library and no tile server.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GEO, jload  # noqa: E402

_C = None


def load_countries():
    """[(iso, name, region, sub, bbox, ring)] — one entry per ring, biggest first."""
    global _C
    if _C is not None:
        return _C
    p = GEO / "countries.json"
    if not p.exists():
        _C = []
        return _C
    out = []
    for c in jload(p)["countries"]:
        for ring in c["rings"]:
            xs = [pt[0] for pt in ring]
            ys = [pt[1] for pt in ring]
            out.append((c["iso"], c["name"], c.get("region"), c.get("sub"),
                        (min(xs), min(ys), max(xs), max(ys)), ring))
    # smallest rings first: Singapore sits inside no one, but Vatican sits inside Italy
    out.sort(key=lambda e: (e[4][2] - e[4][0]) * (e[4][3] - e[4][1]))
    _C = out
    return _C


def _inside(lon: float, lat: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if x > lon:
                inside = not inside
    return inside


def country_of(lat: float, lon: float, snap_km: float = 30.0):
    """(iso, name, un_region, subregion) or four Nones.

    Containment first. When nothing contains the point, the nearest ring within
    `snap_km` wins: at 1:50m the coastline is generalised inland, so a gym on Manhattan,
    in Hong Kong or on any reclaimed waterfront falls outside every polygon and would
    otherwise be counted in no country at all. The snap is a deliberate widening of the
    coast, not a guess about which country a point is near — 30 km is narrower than the
    distance between two countries anywhere the rings are this coarse.
    """
    for iso, name, region, sub, (x0, y0, x1, y1), ring in load_countries():
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        if _inside(lon, lat, ring):
            return iso, name, region, sub
    best, bd = None, snap_km
    pad = snap_km / 90.0
    for iso, name, region, sub, (x0, y0, x1, y1), ring in load_countries():
        if not (x0 - pad <= lon <= x1 + pad and y0 - pad <= lat <= y1 + pad):
            continue
        for px, py in ring:
            if abs(px - lon) > pad or abs(py - lat) > pad:
                continue
            d = haversine((lat, lon), (py, px))
            if d < bd:
                best, bd = (iso, name, region, sub), d
    return best or (None, None, None, None)


# ------------------------------------------------------------------ projections
def equal_earth(lon: float, lat: float):
    """Equal Earth (Šavrič, Patterson & Jenny 2018). Areas are true, which is the whole
    point when the map's subject is how many of a thing are where."""
    A = (1.340264, -0.081106, 0.000893, 0.003796)
    t = math.asin(math.sqrt(3) / 2 * math.sin(math.radians(lat)))
    t2 = t * t
    t6 = t2 * t2 * t2
    x = (math.radians(lon) * math.cos(t)
         / (math.sqrt(3) / 2 * (A[0] + 3 * A[1] * t2 + t6 * (7 * A[2] + 9 * A[3] * t2))))
    y = t * (A[0] + A[1] * t2 + t6 * (A[2] + A[3] * t2))
    return x, y


def merc(lon: float, lat: float):
    lat = max(-85.0, min(85.0, lat))
    return (math.radians(lon),
            math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def haversine(a, b) -> float:
    R = 6371.0088
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))
