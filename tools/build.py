#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build.py — records + harvests → build/api.

Everything the site prints is computed here and written as JSON, so the API a reader or a
bot can fetch is the same data the pages are made from. Each figure is computed once, and
the pages read it rather than restating it.

    python3 tools/build.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BUILD, TYPES, jdump, jload, load_harvest, load_nodes,  # noqa: E402
                    load_sources, load_vocab)

API = BUILD / "api"


def curriculum(vocab_mm: dict) -> dict:
    """The thirty named techniques, and what the names point at.

    The Thai names and descriptions are harvested; the gloss and the classification are
    this project's, and the page prints the table so a reader can disagree with a row.
    """
    canon = vocab_mm["canonical"]
    by_class = Counter(r["refers"] for r in canon)
    schools = {k: vocab_mm[k] for k in ("korat", "chaiya", "lopburi")}
    school_counts = {k: dict(Counter(r["refers"] for r in v)) for k, v in schools.items()}
    figures = Counter(r["figure"] for r in canon if r["figure"])
    return {
        "n": len(canon),
        "mae_mai": vocab_mm["mae_mai"], "luk_mai": vocab_mm["luk_mai"],
        "by_class": dict(by_class),
        "picture": sum(v for k, v in by_class.items() if k != "plain"),
        "plain": by_class.get("plain", 0),
        "myth": by_class.get("myth", 0),
        "classes": vocab_mm["classes"],
        "schools": {k: {"rows": schools[k], "by_class": school_counts[k], "n": len(schools[k])}
                    for k in schools},
        "figures": figures.most_common(),
        "note": vocab_mm["note"],
    }


def gyms(h: dict) -> dict:
    if not h:
        return {}
    rows = h["rows"]
    by_country = h["by_country"]
    th = [r for r in rows if r["country"] == "TH"]
    abroad = [r for r in rows if r["country"] != "TH"]
    by_sub = Counter(r["sub"] or "unplaced" for r in rows)
    return {
        "count": h["count"], "fetched": h["fetched"], "licence": h["licence"],
        "attribution": h["attribution"], "note": h["note"], "queries": h["queries"],
        "dropped": h["dropped"],
        "countries": len(by_country), "by_country": by_country, "by_kind": h["by_kind"],
        "by_how": h["by_how"], "by_subregion": dict(by_sub.most_common()),
        "named": h["named"], "with_website": h["with_website"],
        "thailand": len(th), "abroad": len(abroad),
        "stadiums": sum(1 for r in rows if r["kind"] == "stadium"),
        "camps": sum(1 for r in rows if r["kind"] == "camp"),
        "rows": rows,
    }


def roster(h: dict) -> dict:
    if not h:
        return {}
    core = [r for r in h["people"] if r["cohort"] == "boxer" and r["human"]]
    thai = [r for r in core if "Thailand" in (r["countries"] or [])]
    return {
        "count": h["count"], "fetched": h["fetched"], "licence": h["licence"],
        "note": h["note"], "cohorts": h["cohorts"],
        "outside": h["loudest_outside_the_cohort"],
        "by_country": h["by_country"], "by_decade": h["by_decade"], "by_gender": h["by_gender"],
        "with_thai_label": h["with_thai_label"],
        "thai": len(thai),
        "thai_women": sum(1 for r in thai if r["gender"] == "female"),
        "women": h["by_gender"].get("female", 0),
        "venues": h["venues"],
        "people": core,
    }


def main() -> int:
    recs = load_nodes()
    sources = load_sources()
    vocab = {n: load_vocab(n) for n in ("types", "regions", "facets", "tags")}
    mm = load_vocab("maemai")
    g = gyms(load_harvest("osm-gyms"))
    wd = roster(load_harvest("wikidata"))
    cur = curriculum(mm)
    raw_mm = load_harvest("maemai") or {}

    by_id = {r["id"]: r for r in recs}
    for r in recs:
        r.pop("_path", None)
        r.pop("_dir_type", None)

    back = {}
    for r in recs:
        for k in r.get("kin", []):
            back.setdefault(k["to"], []).append({"from": r["id"], "type": r["type"],
                                                 "name": r["names"]["name"], "as": k["as"]})
    for r in recs:
        r["kin_in"] = back.get(r["id"], [])

    cov = {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "records": len(recs),
        "by_type": {t: sum(1 for r in recs if r["type"] == t) for t in TYPES},
        "kin_edges": sum(len(r.get("kin", [])) for r in recs),
        "sources": len(sources),
        "needs_verification": sum(1 for r in recs if r.get("needs_verification")),
        "bilingual": sum(1 for r in recs if r.get("text_th")),
        "th_fields": sum(len(r.get("text_th") or {}) for r in recs),
        "images": sum(len(r.get("images") or []) for r in recs),
        "records_with_images": sum(1 for r in recs if r.get("images")),
        "techniques": cur["n"],
        "gyms": g.get("count", 0),
        "gym_countries": g.get("countries", 0),
        "roster": wd.get("count", 0),
        "tiers": {},
    }
    for r in recs:
        t = (r.get("provenance", {}).get("default") or {}).get("tier", "?")
        cov["tiers"][t] = cov["tiers"].get(t, 0) + 1

    API.mkdir(parents=True, exist_ok=True)
    jdump({"count": len(recs), "nodes": recs}, API / "nodes.json")
    jdump(cur, API / "curriculum.json")
    jdump(raw_mm, API / "curriculum-raw.json", indent=0)
    jdump(g, API / "gyms.json", indent=0)
    jdump(wd, API / "roster.json", indent=0)
    jdump({"sources": list(sources.values())}, API / "sources.json")
    jdump(vocab, API / "vocab.json")
    jdump(cov, API / "coverage.json")
    for t in TYPES:
        rows = [r for r in recs if r["type"] == t]
        jdump({"type": t, "count": len(rows), "nodes": rows}, API / f"{t}.json")
        for r in rows:
            jdump(r, API / t / f"{r['id']}.json")

    print(f"build: {len(recs)} records · {cov['kin_edges']} kin · {len(sources)} sources · "
          f"{cov['th_fields']} Thai fields · {cov['images']} images")
    print(f"       curriculum: {cur['n']} named, {cur['picture']} a picture, "
          f"{cur['myth']} out of the epic")
    print(f"       gyms: {g.get('count')} in {g.get('countries')} countries "
          f"({g.get('thailand')} Thai, {g.get('abroad')} abroad)")
    print(f"       roster: {wd.get('count')} people, {wd.get('thai')} Thai, "
          f"{wd.get('thai_women')} Thai women")
    print(f"       tiers: {cov['tiers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
