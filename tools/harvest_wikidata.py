#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harvest_wikidata.py — the roster the open web actually holds.

Everyone Wikidata records as a Thai boxer (Q388513) or as competing in muay thai
(P641 = Q120931), with nationality, gender, birth year and the gym their entry names.
This is not a ranking and not a hall of fame: it is a census of who has an entry, which
is a fact about the encyclopedia, not about the sport. The gap between the two is the
point, and the pages say so.

    python3 tools/harvest_wikidata.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HARVEST, jdump  # noqa: E402

UA = "muay-thai-build/0.1 (https://wichaa.net; nan@motdang.net) python-urllib"
EP = "https://query.wikidata.org/sparql"

PEOPLE = """
SELECT ?p ?pLabel ?genderLabel ?citLabel ?dob ?dod ?sitelinks ?human ?boxer WHERE {
  { ?p wdt:P106 wd:Q388513 } UNION { ?p wdt:P641 wd:Q120931 }
  ?p wikibase:sitelinks ?sitelinks .
  BIND(EXISTS { ?p wdt:P31 wd:Q5 } AS ?human)
  BIND(EXISTS { ?p wdt:P106 wd:Q388513 } AS ?boxer)
  OPTIONAL { ?p wdt:P21 ?gender }
  OPTIONAL { ?p wdt:P27 ?cit }
  OPTIONAL { ?p wdt:P569 ?dob }
  OPTIONAL { ?p wdt:P570 ?dod }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

THAI_LABELS = """
SELECT ?p ?th WHERE {
  { ?p wdt:P106 wd:Q388513 } UNION { ?p wdt:P641 wd:Q120931 }
  ?p rdfs:label ?th FILTER(LANG(?th) = "th")
}
"""

VENUES = """
SELECT ?v ?vLabel ?coord ?inception ?cityLabel ?countryLabel ?capacity ?typeLabel WHERE {
  ?v wdt:P641 wd:Q120931 ; wdt:P625 ?coord ; wdt:P31 ?type .
  OPTIONAL { ?v wdt:P571 ?inception }
  OPTIONAL { ?v wdt:P131 ?city }
  OPTIONAL { ?v wdt:P17 ?country }
  OPTIONAL { ?v wdt:P1083 ?capacity }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""


def sparql(q: str, tries: int = 4):
    """POSTed, because a long query in a URL is a 414 waiting to happen, and retried,
    because the public endpoint answers 504 under load and then answers the same query
    in twenty seconds a minute later."""
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                EP, data=urllib.parse.urlencode({"query": q, "format": "json"}).encode(),
                headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)["results"]["bindings"]
        except Exception as e:  # noqa: BLE001
            err = e
            print(f"  {e}; retrying")
            time.sleep(10 + 10 * i)
    raise RuntimeError(f"Wikidata failed: {err}")


def val(b, k):
    return (b.get(k) or {}).get("value")


def main() -> int:
    print("people")
    rows, seen = [], {}
    for b in sparql(PEOPLE):
        qid = val(b, "p").rsplit("/", 1)[-1]
        r = seen.get(qid)
        if r is None:
            dob = val(b, "dob") or ""
            dod = val(b, "dod") or ""
            r = {"qid": qid, "name": val(b, "pLabel"), "th": None,
                 "gender": val(b, "genderLabel"), "countries": [],
                 "born": dob[:4] if dob[:1] in "12" else None,
                 "died": dod[:4] if dod[:1] in "12" else None,
                 "sitelinks": int(val(b, "sitelinks") or 0),
                 "human": val(b, "human") == "true",
                 "cohort": "boxer" if val(b, "boxer") == "true" else "trains"}
            seen[qid] = r
            rows.append(r)
        c = val(b, "citLabel")
        if c and c not in r["countries"]:
            r["countries"].append(c)
    print(f"  {len(rows)} people")
    for b in sparql(THAI_LABELS):
        r = seen.get(val(b, "p").rsplit("/", 1)[-1])
        if r and not r["th"]:
            r["th"] = val(b, "th")
    print(f"  {sum(1 for r in rows if r['th'])} with a Thai label")

    print("venues")
    venues = []
    vseen = set()
    for b in sparql(VENUES):
        qid = val(b, "v").rsplit("/", 1)[-1]
        if qid in vseen:
            continue
        vseen.add(qid)
        lat = lon = None
        c = val(b, "coord")
        if c and c.startswith("Point("):
            lon, lat = (float(x) for x in c[6:-1].split())
        inc = val(b, "inception") or ""
        venues.append({"qid": qid, "name": val(b, "vLabel"), "kind": val(b, "typeLabel"),
                       "lat": lat, "lon": lon, "opened": inc[:4] if inc[:1] in "12" else None,
                       "city": val(b, "cityLabel"), "country": val(b, "countryLabel"),
                       "capacity": val(b, "capacity")})
    print(f"  {len(venues)} venues")

    # Two cohorts, and the difference is the whole caution. `boxer` is occupation Thai
    # boxer — someone the encyclopedia says fights for a living. `trains` is only the
    # sport property, which Wikidata also carries on actors, a wrestler or two and, at the
    # top of the list by article count, Batman. Every figure the site prints is the boxer
    # cohort; the other is printed once, as the reason.
    core = [r for r in rows if r["cohort"] == "boxer" and r["human"]]
    by_country, by_decade, by_gender = {}, {}, {}
    for r in core:
        for c in (r["countries"] or ["unstated"]):
            by_country[c] = by_country.get(c, 0) + 1
        d = f"{r['born'][:3]}0s" if r["born"] else "unstated"
        by_decade[d] = by_decade.get(d, 0) + 1
        by_gender[r["gender"] or "unstated"] = by_gender.get(r["gender"] or "unstated", 0) + 1

    rows.sort(key=lambda r: (-r["sitelinks"], r["name"] or ""))
    jdump({"fetched": time.strftime("%Y-%m-%d %H:%M"),
           "source": "Wikidata Query Service",
           "licence": "CC0 1.0",
           "queries": {"people": PEOPLE.strip(), "venues": VENUES.strip()},
           "note": "Everyone with occupation Thai boxer (Q388513) or sport muay thai "
                   "(Q120931). Who has an entry is decided by who writes encyclopedias, "
                   "not by who fought: a Thai fighter with three hundred fights and no "
                   "English article is absent here and present in the sport.",
           "count": len(core), "all_rows": len(rows),
           "cohorts": {"occupation Thai boxer": len(core),
                       "sport muay thai only": len(rows) - len(core)},
           "loudest_outside_the_cohort": [r["name"] for r in rows
                                          if r["cohort"] != "boxer" or not r["human"]][:8],
           "by_country": dict(sorted(by_country.items(), key=lambda kv: -kv[1])),
           "by_decade": dict(sorted(by_decade.items())),
           "by_gender": dict(sorted(by_gender.items(), key=lambda kv: -kv[1])),
           "with_thai_label": sum(1 for r in core if r["th"]),
           "people": rows, "venues": sorted(venues, key=lambda v: v["opened"] or "9999")},
          HARVEST / "wikidata.json", indent=0)
    print(f"  countries: {list(by_country.items())[:8]}")
    print(f"  gender: {by_gender}")
    print(f"  decades: {by_decade}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
