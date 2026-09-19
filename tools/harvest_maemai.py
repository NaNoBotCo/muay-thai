#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harvest_maemai.py — the named curriculum, off the page it is published on.

The plain-text extract of the Thai Wikipedia article drops the tables, and the tables are
the article: fifteen แม่ไม้ with their descriptions, fifteen ลูกไม้, and the four regional
lists. So this reads the wikitext at a named revision and pulls the names out mechanically,
rather than retyping them. What it writes is the Thai only — the transliteration, the gloss
and the classification of what each name refers to are this project's own work and live in
data/vocab/maemai.json, where they can be argued with.

    python3 tools/harvest_maemai.py
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HARVEST, jdump  # noqa: E402

UA = "muay-thai-build/0.1 (https://wichaa.net; nan@motdang.net) python-urllib"
PAGE = "แม่ไม้มวยไทย"


def wikitext(page: str):
    q = {"action": "parse", "page": page, "prop": "wikitext|revid", "format": "json",
         "formatversion": 2}
    u = f"https://th.wikipedia.org/w/api.php?{urllib.parse.urlencode(q)}"
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}),
                                timeout=90) as r:
        d = json.load(r)
    return d["parse"]["wikitext"], d["parse"]["revid"]


def strip(s: str) -> str:
    s = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = s.replace("'''", "").replace("''", "")
    return s.strip(" *\n\t")


def main() -> int:
    wt, rev = wikitext(PAGE)
    # the แม่ไม้ table: rows of | n / | '''name''' / | description
    table = wt.split("== แม่ไม้มวยไทย ==", 1)[1].split("=== แม่ไม้", 1)[0]
    mae = []
    for cell in table.split("|-"):
        lines = [strip(x) for x in cell.split("\n| ")[1:]]
        lines = [x for x in lines if x]
        if len(lines) >= 3 and lines[0].isdigit():
            mae.append({"n": int(lines[0]), "th": lines[1], "described": lines[2]})
    # the ลูกไม้ list: a bullet list inside a Div col
    luk_block = wt.split("== ลูกไม้มวยไทย ==", 1)[1].split("== สายต่าง", 1)[0]
    luk = [{"n": i + 1, "th": strip(m)}
           for i, m in enumerate(re.findall(r"^\* (.+)$", luk_block, re.M))]
    # the regional lists
    schools = {}
    sec = wt.split("== สายต่าง ๆ ==", 1)[1].split("== ในวัฒนธรรม", 1)[0]
    for line in re.findall(r"^\* (.+)$", sec, re.M):
        line = strip(line)
        name = line.split(" ", 1)[0]
        # Each school's names follow ได้แก่ or คือ, and Korat's line has two such runs:
        # five teaching techniques and then twenty-one older ones. Split on both, take
        # every run, and drop anything that is a count rather than a name.
        names = []
        for run in re.split(r"ได้แก่|คือ", line)[1:]:
            for n in re.split(r",\s*|\sกับ|\sและ", run):
                n = n.strip(" .")
                if n and not re.search(r"\d", n) and len(n) > 3:
                    names.append(n)
        schools[name] = {"line": line, "names": names}

    out = {"fetched": time.strftime("%Y-%m-%d"),
           "source": f"https://th.wikipedia.org/wiki/{urllib.parse.quote(PAGE)}",
           "revision": rev, "licence": "CC BY-SA 4.0 (Wikipedia)",
           "cites": "สารานุกรมไทยสำหรับเยาวชนฯ — the Thai Encyclopedia for Youth, which is "
                    "the article's own source for both lists of fifteen",
           "note": "Names and Thai descriptions as published. Counts are of what this one "
                   "article lists; a gym's own curriculum may name more, fewer or others.",
           "mae_mai": mae, "luk_mai": luk, "schools": schools}
    jdump(out, HARVEST / "maemai.json")
    print(f"แม่ไม้ {len(mae)} · ลูกไม้ {len(luk)} · schools {len(schools)} · rev {rev}")
    for s, v in schools.items():
        print(f"  {s}: {len(v['names'])} named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
