#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harvest_osm.py — every gym, camp and stadium OpenStreetMap knows about, worldwide.

Two queries, unioned, because they disagree and the disagreement is the finding:

  by tag    sport=muay_thai and its spellings. The tag exists; almost nobody uses it.
  by name   any object whose name carries muay / มวย / ムエタイ / 무에타이 / муай / 泰拳
            / thaiboxen / thai box. A gym says what it is in its name long before a
            mapper reaches for the right key.

A harvest file is never a record. It carries the query, the endpoint, the fetch time and
the licence, so an absence reads as "not in OSM on that date" rather than "not there"
([[absence is not evidence of absence]]). Country comes from point-in-polygon against
data/geo/countries.json, not from a geocoder.

    python3 tools/harvest_osm.py --gyms
    python3 tools/harvest_osm.py --gyms --cached     # re-bucket without refetching
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HARVEST, jdump, jload  # noqa: E402
from geo import country_of, load_countries  # noqa: E402

UA = "muay-thai-build/0.1 (https://wichaa.net; nan@motdang.net) python-urllib"
ENDPOINTS = ["https://overpass-api.de/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter",
             "https://overpass.private.coffee/api/interpreter"]
RAW = HARVEST / "_raw"

# The name test, in the scripts the sport is actually written in. `thai.?box` catches
# Thaiboxen, Thai Boxing and thai-box; the Thai word มวย on its own means boxing, so a
# Thai row matching only มวย is kept but marked, because it may be a western-boxing gym.
NAME_RE = r"muay|มวย|ムエタイ|무에타이|муай|泰拳|thai.?box|boxe.?thai"
SPORT_RE = r"muay_?thai|thai_?boxing"

KEEP = ("name", "name:en", "name:th", "int_name", "alt_name", "sport", "leisure", "amenity",
        "shop", "club", "building", "operator", "brand", "website", "contact:website",
        "phone", "contact:phone", "contact:instagram", "contact:facebook", "opening_hours",
        "addr:city", "addr:country", "addr:province", "addr:state", "addr:street",
        "wikidata", "wikipedia", "description", "fee", "female", "male", "tourism")


def overpass(query: str, tries: int = 4):
    err = None
    for i in range(tries):
        ep = ENDPOINTS[i % len(ENDPOINTS)]
        t0 = time.time()
        try:
            req = urllib.request.Request(ep, data=urllib.parse.urlencode({"data": query}).encode(),
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.load(r)
            print(f"  {ep.split('/')[2]}: {len(d.get('elements', []))} elements in {time.time()-t0:.0f}s")
            return d
        except Exception as e:  # noqa: BLE001
            err = e
            print(f"  {ep.split('/')[2]}: {e} after {time.time()-t0:.0f}s; retrying")
            time.sleep(5 + 5 * i)
    raise RuntimeError(f"Overpass failed: {err}")


def centre(el: dict):
    if el.get("type") == "node":
        return el.get("lat"), el.get("lon")
    c = el.get("center") or {}
    return c.get("lat"), c.get("lon")


def fetch(cached: bool) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, q in (
        ("tag", f'[out:json][timeout:550];nwr["sport"~"{SPORT_RE}",i];out center tags;'),
        ("name", f'[out:json][timeout:550];nwr["name"~"{NAME_RE}",i];out center tags;'),
        ("altname", f'[out:json][timeout:550];nwr["alt_name"~"{NAME_RE}",i];out center tags;'),
    ):
        p = RAW / f"gyms-{key}.json"
        if cached and p.exists():
            out[key] = jload(p)
            print(f"  {key}: {len(out[key]['elements'])} from cache")
            continue
        print(f"query {key}")
        d = overpass(q)
        d["query"] = q
        jdump(d, p, indent=0)
        out[key] = d
        time.sleep(3)
    return out


# ------------------------------------------------------------------ what is a gym
# The word is not the thing, and in Thai it is not even the word. Thai is written
# without spaces, so มวย (boxing) matches inside หมวย — Muay, a common nickname — and
# inside มวยผม, a bun of hair. Twenty of the first Thai matches were noodle shops, a
# butcher, a beauty salon and two statues of the earth goddess wringing out her hair.
# So a row is kept only when a name signal and a facility tag agree.
TH_YES = ("มวยไทย", "ค่ายมวย", "เวทีมวย", "สนามมวย", "นักมวย", "ชมรมมวย", "ยิมมวย", "โรงมวย")
TH_NO = re.compile(r"[หส]มวย|มวยผม")
# Word-level, not substring, and that is not pedantry. `muay` inside a word is Turkish
# muayene (a medical or vehicle inspection) forty times over, Filipino Pamuayan,
# Indonesian Mamuaya, Spanish Muaylas. Anchoring to a word boundary removes every one of
# them and costs nothing real, because the sport's name is always its own word.
LATIN_YES = re.compile(r"\bmuay\b|\bmuaythai\b|thai.?box\w*|\bboxe.?tha\w*|"
                       r"ムエタイ|무에타이|муай|泰拳", re.I)
SPORT_YES = re.compile(r"muay_?thai|thai_?boxing", re.I)
# A place that serves food, examines patients or inspects cars is not a gym, whatever the
# letters in its name.
AMENITY_NO = {"restaurant", "cafe", "fast_food", "bar", "pub", "food_court", "ice_cream",
              "bakery", "fuel", "pharmacy", "bank", "atm", "school", "kindergarten",
              "hospital", "clinic", "doctors", "dentist", "veterinary", "place_of_worship",
              "toilets", "bus_station", "parking", "parking_space", "marketplace",
              "car_wash", "vehicle_inspection", "police", "post_office", "library"}
SHOP_NO = {"supermarket", "convenience", "variety_store", "butcher", "beverages",
           "confectionery", "seafood", "coffee", "beauty", "hairdresser", "bakery",
           "greengrocer", "alcohol", "car_repair", "motorcycle", "hardware", "electronics",
           "books", "bookmaker", "craft", "florist"}
FACILITY = {"leisure": {"sports_centre", "fitness_centre", "stadium", "pitch", "sports_hall",
                        "dojo", "club", "horse_riding"},
            "amenity": {"dojo", "gym", "training", "events_venue", "theatre"},
            "building": {"stadium", "sports_hall", "sports_centre", "yes"},
            "club": None,
            "sport": None}
SHOP_KIND = {"sports", "fitness", "martial_arts", "clothes", "trade", "outdoor"}
NOT_A_PLACE = {"highway", "railway", "public_transport", "natural", "waterway", "boundary",
               "landuse", "place", "barrier", "power", "man_made", "route"}


def names_of(tags: dict) -> str:
    return " ".join(v for k, v in tags.items()
                    if k.startswith(("name", "alt_name", "int_name", "official_name")))


def name_signal(tags: dict):
    """("strong" | "weak" | "") — strong is the sport named as its own word in any of its
    scripts; weak is the bare Thai word for boxing, which does not say which boxing."""
    nm = names_of(tags)
    if LATIN_YES.search(nm) or any(w in nm for w in TH_YES):
        return "strong"
    if "มวย" in TH_NO.sub("", nm):
        return "weak"
    return ""


def classify(tags: dict):
    """(kind, note). kind is gym / camp / stadium / shop / gym?, or "" when dropped."""
    if any(k in tags for k in NOT_A_PLACE) and not any(
            k in tags for k in ("sport", "leisure", "club", "shop", "amenity")):
        return "", "not a place"
    sport = (tags.get("sport") or "").lower()
    sport_hit = bool(SPORT_YES.search(sport))
    strength = name_signal(tags)
    if not sport_hit and not strength:
        return "", "no signal"
    if (tags.get("amenity") in AMENITY_NO or tags.get("shop") in SHOP_NO) and not sport_hit:
        return "", f"{tags.get('amenity') or tags.get('shop')}, not a gym"
    facility = any(tags.get(k) and (v is None or tags.get(k) in v) for k, v in FACILITY.items())
    nm = names_of(tags)
    low = nm.lower()
    if tags.get("shop") in SHOP_KIND and not facility:
        return "shop", "sells the kit"
    if not sport_hit and strength == "weak" and not facility:
        return "", "Thai word for boxing, nothing else"
    if not sport_hit and strength == "weak":
        return "gym?", "Thai word for boxing, sport not stated"
    if (tags.get("leisure") == "stadium" or tags.get("building") == "stadium"
            or re.search(r"\bstadium\b|\barena\b", low) or "เวทีมวย" in nm or "สนามมวย" in nm):
        return "stadium", ""
    if "ค่ายมวย" in nm or re.search(r"\bcamp\b", low):
        return "camp", ""
    # A strong name with no facility tag is a gym OSM has not finished describing, which
    # is the ordinary state of this sport in OSM and not a reason to throw the row away.
    return "gym", "" if facility else "named only; no facility tag"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gyms", action="store_true")
    ap.add_argument("--cached", action="store_true")
    a = ap.parse_args()
    if not a.gyms:
        ap.error("nothing asked for; --gyms")

    raw = fetch(a.cached)
    load_countries()
    seen, rows = {}, []
    dropped = {}
    for key, d in raw.items():
        for el in d["elements"]:
            oid = f"{el['type'][0]}{el['id']}"
            tags = el.get("tags") or {}
            lat, lon = centre(el)
            if lat is None:
                dropped["no location"] = dropped.get("no location", 0) + 1
                continue
            row = seen.get(oid)
            if row is None:
                kind, reason = classify(tags)
                if not kind:
                    dropped[reason] = dropped.get(reason, 0) + 1
                    seen[oid] = False
                    continue
                iso, cname, region, sub = country_of(lat, lon)
                row = {"osm": oid, "lat": round(lat, 6), "lon": round(lon, 6),
                       "country": iso, "country_name": cname, "region": region, "sub": sub,
                       "kind": kind, "found_by": [], "note": reason,
                       "tags": {k: v for k, v in tags.items() if k in KEEP}}
                seen[oid] = row
                rows.append(row)
            if row:
                row["found_by"].append(key)

    rows.sort(key=lambda r: (r["country_name"] or "zz", (r["tags"].get("name") or "")))
    by_country, by_kind, by_how = {}, {}, {"tag only": 0, "name only": 0, "both": 0}
    for r in rows:
        by_country[r["country_name"] or "unplaced"] = by_country.get(r["country_name"] or "unplaced", 0) + 1
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
        tag = "tag" in r["found_by"]
        nm = "name" in r["found_by"] or "altname" in r["found_by"]
        by_how["both" if (tag and nm) else "tag only" if tag else "name only"] += 1

    jdump({"fetched": time.strftime("%Y-%m-%d %H:%M"),
           "source": "OpenStreetMap via Overpass",
           "licence": "ODbL 1.0",
           "attribution": "© OpenStreetMap contributors",
           "queries": {k: v["query"] for k, v in raw.items() if "query" in v},
           "note": "Volunteer data, unchecked by this project. A gym absent here is absent "
                   "from OpenStreetMap on the fetch date, which is not the same as absent. "
                   "Country is point-in-polygon against Natural Earth 1:50m, so a row within "
                   "a few kilometres of a border may sit on the wrong side of it.",
           "count": len(rows), "dropped": dict(sorted(dropped.items(), key=lambda kv: -kv[1])),
           "by_country": dict(sorted(by_country.items(), key=lambda kv: -kv[1])),
           "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
           "by_how": by_how,
           "named": sum(1 for r in rows if r["tags"].get("name")),
           "with_website": sum(1 for r in rows if r["tags"].get("website") or r["tags"].get("contact:website")),
           "unsure": sum(1 for r in rows if r["kind"] == "gym?"),
           "rows": rows}, HARVEST / "osm-gyms.json", indent=0)
    print(f"\n{len(rows)} rows, {len(by_country)} countries")
    print("  " + ", ".join(f"{k} {v}" for k, v in list(by_country.items())[:12]))
    print(f"  how found: {by_how}")
    print(f"  kinds: {by_kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
