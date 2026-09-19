#!/usr/bin/env python3
"""fetch_wiki.py — the drafting corpus: Wikipedia articles as plain text, one per file.

Pulls the English article and, where it exists, the Thai one, so a bilingual record can
cite both. Each file carries its URL, its revision id and the fetch date at the top.
Wikipedia is CC BY-SA 4.0. The corpus is a working input: .gitignore excludes it and
publish.sh does not copy it into docs/.

    python3 tools/fetch_wiki.py                 # into data/corpus/
    python3 tools/fetch_wiki.py --out /tmp/x    # somewhere else
    python3 tools/fetch_wiki.py --list          # print the article list and stop
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, jdump, slugify  # noqa: E402

UA = "muay-thai-build/0.1 (https://wichaa.net; nan@motdang.net) python-urllib"

EN = """
Muay Thai
Muay boran
Muay Chaiya
Muay Lao
Lethwei
Kun Khmer
Tomoi
Bokator
Krabi–krabong
Nai Khanom Tom
Wai khru ram muay
Mongkhon
Sak Yant
Thai amulet
Ramakien
Hanuman
Erawan
Ayutthaya Kingdom
Naresuan
Sanphet VIII
Rattanakosin Kingdom
Lumpinee Boxing Stadium
Rajadamnern Stadium
ONE Championship
Kickboxing
K-1
Glory (kickboxing)
Boxing
Weight class
Clinch fighting
Roundhouse kick
Elbow (strike)
Knee (strike)
Shin
Muay Thai in popular culture
Ong-Bak: Muay Thai Warrior
Tony Jaa
Buakaw Banchamek
Samart Payakaroon
Dieselnoi Chor Thanasukarn
Apidej Sit Hirun
Saenchai
Rodtang Jitmuangnon
Superlek Kiatmoo9
Nong-O Hama
Stamp Fairtex
Somrak Khamsing
Yodsanklai Fairtex
Petchboonchu F.A. Group
Sagat Petchyindee
Changpuek Kiatsongrit
Ramon Dekkers
Toshio Fujiwara
John Wayne Parr
Liam Harrison
Anissa Meksen
Sports Authority of Thailand
International Federation of Muaythai Associations
World Muaythai Council
Gambling in Thailand
Thai language
Royal Thai General System of Transcription
Thai numerals
Bangkok
Chiang Mai
Isan
Surin province
Buriram province
Chaiya District
Nakhon Ratchasima
Lopburi
Uttaradit
Thailand
Sport in Thailand
Songkran
Thai people
Thai folklore
Piphat
Pi (instrument)
Ching (instrument)
Klong khaek
Muay Thai at the Southeast Asian Games
Muay at the 2023 Southeast Asian Games
World Games
Mixed martial arts
Sanda (sport)
Savate
Burmese–Siamese wars
Konbaung dynasty
Yangon
Child labour
Traumatic brain injury
Chronic traumatic encephalopathy
""".strip().splitlines()

TH = """
มวยไทย
มวยโบราณ
มวยไชยา
มวยโคราช
มวยลพบุรี
มวยท่าเสา
แม่ไม้มวยไทย
นายขนมต้ม
ไหว้ครู
กระบี่กระบอง
สนามมวยเวทีลุมพินี
เวทีมวยราชดำเนิน
รามเกียรติ์
หนุมาน
ช้างเอราวัณ
บัวขาว บัญชาเมฆ
สามารถ พยัคฆ์อรุณ
แสนชัย ส.คิงส์สตาร์
รถถัง จิตรเมืองนนท์
สมรักษ์ คำสิงห์
ดีเซลน้อย ช.ธนสุกาญจน์
ปี่ชวา
กลองแขก
ฉิ่ง
สักยันต์
อาณาจักรอยุธยา
สมเด็จพระนเรศวรมหาราช
สมเด็จพระเจ้าเสือ
จังหวัดสุรินทร์
อำเภอไชยา
จังหวัดนครราชสีมา
จังหวัดลพบุรี
จังหวัดอุตรดิตถ์
มวยสากล
""".strip().splitlines()


def fetch(title: str, lang: str) -> dict | None:
    api = f"https://{lang}.wikipedia.org/w/api.php"
    q = {"action": "query", "format": "json", "prop": "extracts|info", "explaintext": 1,
         "redirects": 1, "inprop": "url", "titles": title}
    req = urllib.request.Request(api + "?" + urllib.parse.urlencode(q), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
    except Exception as e:  # noqa: BLE001
        print(f"  ! {title}: {e}")
        return None
    for p in d.get("query", {}).get("pages", {}).values():
        if "missing" in p or not p.get("extract"):
            return None
        return {"title": p["title"], "url": p.get("fullurl", ""), "rev": p.get("lastrevid"),
                "lang": lang, "text": p["extract"]}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "corpus"))
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        print("\n".join(EN + TH))
        return 0
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    index, missing = [], []
    for lang, titles in (("en", EN), ("th", TH)):
        for t in titles:
            t = t.strip()
            if not t:
                continue
            d = fetch(t, lang)
            if not d:
                missing.append(f"{lang}:{t}")
                print(f"  MISSING {lang}:{t}")
                continue
            slug = slugify(d["title"]) or re.sub(r"\W+", "-", d["title"])[:60]
            name = f"{'wp' if lang == 'en' else 'th'}-{slug}.txt"
            (out / name).write_text(
                f"# {d['title']}\n# {d['url']}\n# revision {d['rev']}\n# fetched {today}\n"
                f"# Wikipedia, CC BY-SA 4.0\n\n{d['text']}\n", encoding="utf-8")
            index.append({"id": f"s:{'wp' if lang == 'en' else 'thwp'}-{slug}", "kind": "web",
                          "title": d["title"], "publisher": f"Wikipedia ({lang})", "url": d["url"],
                          "accessed": today, "file": name, "words": len(d["text"].split())})
            print(f"  {name}  {len(d['text'].split())} words")
            time.sleep(0.4)
    jdump({"fetched": today, "licence": "CC BY-SA 4.0", "articles": index, "missing": missing},
          out / "_index.json")
    print(f"\n{len(index)} articles into {out}; {len(missing)} missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
