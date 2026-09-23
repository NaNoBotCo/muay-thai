#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""site.py — build/api → build/site. A static, bilingual, offline-capable site.

Every reader-facing page exists twice: English at its path, Thai at /th/<same path>. The
two are the same build function called with a different language, so a page cannot exist
in one language and silently not the other; where a record has no Thai text the Thai page
says so rather than showing machine translation.

    python3 tools/site.py
    SITE_URL=https://example.org python3 tools/site.py
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleet  # noqa: E402
from common import BUILD, ROOT, TIER_LABEL, TYPES, jload  # noqa: E402
from css import CSS  # noqa: E402

API = BUILD / "api"
SITE = BUILD / "site"
SITE_URL = os.environ.get("SITE_URL", "https://nanobotco.github.io/muay-thai").rstrip("/")
# The same site is published twice: the GitHub Pages copy, which is what the repo builds
# by default, and https://motdang.net/muay-thai — hyphenated, because motdang.net already
# has a /muaythai.html of its own, the board of tonight's fights in Chiang Mai, and two
# different things one character apart is a trap for a reader and for a crawler. Two live copies of one site is duplicate
# content, so both declare the same canonical and the other copy carries rel="alternate".
# CANONICAL_URL overrides where that points; set it to SITE_URL to make a copy primary.
CANONICAL_URL = os.environ.get("CANONICAL_URL", "https://motdang.net/muay-thai").rstrip("/")
# Internal links are root-relative. The site is published under a path, and a host that
# serves /muaythai with a 200 instead of redirecting to /muaythai/ makes the browser
# resolve "./images/x.jpg" against the site root. BASE_PATH comes from SITE_URL and can be
# overridden for a local preview served at the root.
BASE_PATH = os.environ.get("BASE_PATH")
if BASE_PATH is None:
    _p = urllib.parse.urlparse(SITE_URL).path.strip("/")
    BASE_PATH = f"/{_p}/" if _p else "/"
if not BASE_PATH.endswith("/"):
    BASE_PATH += "/"

SELF = "muay-thai"
LANGS = ("en", "th")
NAME = {"en": "Muay Thai", "th": "มวยไทย"}
AUTHOR = {"@type": "Person", "name": "NaN", "url": "https://wichaa.net"}
# The studio byline and its schema.org form come off the roster, so one edit in
# index/data/fleet.json reaches every site that installs it.
MAKER = fleet.maker_ld(fleet.load(ROOT / "data" / "fleet.json"))
DATA_LICENSE = "https://creativecommons.org/licenses/by/4.0/"


def E(x) -> str:
    return html.escape("" if x is None else str(x))


def T(d: dict, key: str, lang: str, fallback=True):
    """A field in the requested language. `names.th` / `text_th` hold the Thai."""
    if lang == "th":
        if key.startswith("text."):
            v = (d.get("text_th") or {}).get(key[5:])
        elif key.startswith("names."):
            v = (d.get("names") or {}).get(key[6:] + "_th") or (
                (d.get("names") or {}).get("th") if key == "names.name" else None)
        else:
            v = d.get(key + "_th")
        if v:
            return v
        if not fallback:
            return None
    if key.startswith("text."):
        return (d.get("text") or {}).get(key[5:])
    if key.startswith("names."):
        return (d.get("names") or {}).get(key[6:])
    return d.get(key)


# ---------------------------------------------------------------- data, loaded once
V = jload(API / "vocab.json")
TYPE_INFO = {e["key"]: e for e in V["types"]["entries"]}
FACETS = V["facets"]["facets"]
REGIONS = {e["key"]: e for e in V["regions"]["entries"]}
TAGS = V["tags"]["tags"]
PATH_OF = {t: TYPE_INFO[t]["path"] for t in TYPE_INFO}
NODES = jload(API / "nodes.json")["nodes"]
BY_ID = {r["id"]: r for r in NODES}
SOURCES = {s["id"]: s for s in jload(API / "sources.json")["sources"]}
COV = jload(API / "coverage.json")
CUR = jload(API / "curriculum.json")
RAW_CUR = jload(API / "curriculum-raw.json")
GYMS = jload(API / "gyms.json")
ROSTER = jload(API / "roster.json")
FLEET = fleet.load(ROOT / "data" / "fleet.json")

TAG = {"en": f"The eight limbs, the thirty named techniques, and {GYMS['count']} places to "
             f"train on the map",
       "th": f"อาวุธทั้งแปด สามสิบท่าที่มีชื่อ และ {GYMS['count']} แห่งบนแผนที่ที่ฝึกได้"}

DIR_OF = {"weapon": "limbs", "move": "names", "style": "schools", "ritual": "ceremony",
          "music": "band", "bout": "fights", "person": "people", "venue": "stadiums",
          "gym": "gyms", "drill": "training", "rule": "rules", "kit": "kit",
          "story": "history", "place": "places", "org": "bodies", "issue": "questions",
          "term": "words", "art": "works"}

UI = {
 "en": {"home": "Muay Thai", "limbs": "Eight limbs", "names": "The names", "schools": "Schools",
        "ceremony": "Ceremony", "watch": "Watching", "train": "Training",
        "history": "History", "gyms": "Gyms",
        "people": "People", "numbers": "Numbers", "words": "Words",
        "all": "Everything", "about": "How this was made",
        "kin": "Connected to", "said_here": "Named here by", "sources": "Sources",
        "prov": "Where each claim comes from", "back": "Back",
        "what": "What it is", "story": "The long version", "how": "How", "today": "Now",
        "notes": "Notes", "share": "Share", "copy": "Copy link", "print": "Print",
        "no_th": "This section has not been written in Thai yet. The English is below.",
        "unverified": "Parts of this record are marked as needing verification.",
        "more": "More", "measured": "Counted for this site", "th_name": "In Thai",
        "gloss": "What the name says", "refers": "What it points at", "n": "No.",
        "set": "List", "does": "What it does"},
 "th": {"home": "มวยไทย", "limbs": "อาวุธแปด", "names": "ชื่อท่า", "schools": "สายมวย",
        "ceremony": "พิธีกรรม", "watch": "การดู", "train": "การฝึก",
        "history": "ประวัติ", "gyms": "ยิมและค่าย",
        "people": "บุคคล", "numbers": "ตัวเลข", "words": "คำศัพท์",
        "all": "ทั้งหมด", "about": "ทำขึ้นอย่างไร",
        "kin": "เกี่ยวข้องกับ", "said_here": "ถูกอ้างถึงโดย", "sources": "แหล่งอ้างอิง",
        "prov": "แต่ละข้อความมาจากไหน", "back": "ย้อนกลับ",
        "what": "คืออะไร", "story": "ฉบับยาว", "how": "วิธี", "today": "ตอนนี้",
        "notes": "หมายเหตุ", "share": "แบ่งปัน", "copy": "คัดลอกลิงก์", "print": "พิมพ์",
        "no_th": "ส่วนนี้ยังไม่ได้เขียนเป็นภาษาไทย ด้านล่างเป็นภาษาอังกฤษ",
        "unverified": "บางส่วนของบันทึกนี้ยังต้องการการตรวจสอบ",
        "more": "เพิ่มเติม", "measured": "นับขึ้นเพื่อเว็บนี้", "th_name": "ภาษาไทย",
        "gloss": "ชื่อนี้แปลว่า", "refers": "ชี้ไปที่อะไร", "n": "ท่าที่",
        "set": "ชุด", "does": "ทำอะไร"},
}

NAV = [("", "home"), ("limbs/", "limbs"), ("names/", "names"), ("schools/", "schools"),
       ("ceremony/", "ceremony"), ("watch/", "watch"), ("training/", "train"),
       ("history/", "history"), ("gyms/", "gyms"), ("people/", "people"),
       ("numbers/", "numbers"), ("words/", "words")]


def rel(depth: int = 0) -> str:
    """The site root, as a root-relative path. `depth` is ignored and kept so the call
    sites read the same; see BASE_PATH above for why this is not "../" * depth."""
    return BASE_PATH


def lroot(lang: str) -> str:
    return f"{BASE_PATH}th/" if lang == "th" else BASE_PATH


def url_of(r: dict, lang="en") -> str:
    return f"{PATH_OF[r['type']]}/{r['id']}/"


def page(title, body, depth, lang, desc="", jsonld=None, head="", cur="", path="", card=""):
    """`depth` is the page's depth below its LANGUAGE root, which is what the body's own
    links are built against. A Thai page sits one level deeper than that below the site
    root, so assets and the language switch need the site root."""
    rin = BASE_PATH + ("th/" if lang == "th" else "")
    r = BASE_PATH
    ui = UI[lang]
    en_url = f"{BASE_PATH}{path}"
    th_url = f"{BASE_PATH}th/{path}"
    bilingual = path != "api/"
    og_title = title.split(" — ")[0] if " — " in title else title
    og_desc = desc or TAG[lang]
    if og_desc.strip() == og_title.strip():
        og_desc = TAG[lang]
    og_url = f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}{path}"
    card_url = f"{CANONICAL_URL}/cards/{card or 'index'}.jpg"
    card_meta = (f'<meta property="og:image" content="{E(card_url)}">'
                 f'<meta property="og:image:secure_url" content="{E(card_url)}">'
                 f'<meta property="og:image:type" content="image/jpeg">'
                 f'<meta property="og:image:width" content="1200">'
                 f'<meta property="og:image:height" content="630">'
                 f'<meta property="og:image:alt" content="{E(og_title)}">'
                 f'<meta name="twitter:image" content="{E(card_url)}">')
    CURATTR = ' aria-current="page"'
    nav = "".join(f'<a href="{rin}{p}"{CURATTR if k == cur else ""}>{E(ui[k])}</a>'
                  for p, k in NAV)
    ld = json.dumps(jsonld or [], ensure_ascii=False)
    THATTR = ' aria-current="true"'
    thsw = (f'<a href="{th_url}"{THATTR if lang == "th" else ""} '
            f'hreflang="th">ไทย</a>') if bilingual else ""
    return f"""<!doctype html>
<html lang="{lang}"{' class="th"' if lang == 'th' else ''}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(CANONICAL_URL)}/{"th/" if lang == "th" else ""}{E(path)}">
<link rel="alternate" href="{E(SITE_URL)}/{E(path)}">
<link rel="alternate" hreflang="en" href="{SITE_URL}/{E(path)}">
<link rel="alternate" hreflang="th" href="{SITE_URL}/th/{E(path)}">
<link rel="alternate" hreflang="x-default" href="{SITE_URL}/{E(path)}">
<meta property="og:title" content="{E(og_title)}">
<meta property="og:description" content="{E(og_desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{E(og_url)}">
<meta property="og:site_name" content="{E(NAME[lang])}">
<meta property="og:locale" content="{'th_TH' if lang == 'th' else 'en_GB'}">
<meta name="twitter:card" content="summary_large_image">
{card_meta}
<link rel="icon" href="{r}icon.svg" type="image/svg+xml">
<link rel="manifest" href="{r}manifest.webmanifest">
<link rel="alternate" type="application/atom+xml" href="{r}feed.xml">
<style>{CSS}</style>{head}
<script type="application/ld+json">{ld}</script>
<script defer src="{r}copy.js"></script>
</head>
<body>
<a class="sr" href="#main">Skip to content</a>
<header class="top"><div class="in">
<a class="brand" href="{rin}">Muay <b>Thai</b></a>
<nav>{nav}</nav>
<span class="langsw">
<a href="{en_url}"{THATTR if lang == 'en' else ''} hreflang="en">EN</a>
{thsw}
</span>
</div></header>
<main id="main">
{body}
</main>
<footer class="bot"><div class="in">
<p><b>{E(NAME[lang])}</b> — {E(TAG[lang])}</p>
<p>{'Records CC BY 4.0. Gyms and stadiums © OpenStreetMap contributors, ODbL 1.0. The roster from Wikidata, CC0. Country outlines from Natural Earth, public domain. Corpus text and pictures from Wikipedia and Wikimedia Commons, licensed per file.' if lang == 'en' else 'บันทึกเผยแพร่ภายใต้ CC BY 4.0 ยิมและสนาม © ผู้ร่วมสร้าง OpenStreetMap ภายใต้ ODbL 1.0 รายชื่อบุคคลจากวิกิสนเทศ ภายใต้ CC0 เส้นขอบประเทศจาก Natural Earth สาธารณสมบัติ เนื้อหาและภาพจากวิกิพีเดียและวิกิมีเดียคอมมอนส์ ตามสัญญาอนุญาตของแต่ละไฟล์'}</p>
{fleet.maker_html(roster=FLEET, lang=lang)}
<p><a href="{rin}about/">{E(ui['about'])}</a> · <a href="{r}api/">API</a> · <a href="{rin}all/">{E(ui['all'])}</a> · <a href="{r}llms.txt">llms.txt</a></p>
{fleet.row_html(SELF, label=("More from the same publisher" if lang == "en" else "เว็บอื่นของผู้จัดทำ"), roster=FLEET)}
{fleet.support_html(self_id="muay-thai", roster=FLEET)}
</div></footer>
</body></html>
"""


def marks(text: str) -> str:
    t = E(text)
    t = re.sub(r"\*(Inference|Tradition holds|Tradition|อนุมาน|ตามธรรมเนียม)\s*—\*",
               lambda m: f'<mark class="inf">{m.group(1)} —</mark>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    return t


def prose(text: str) -> str:
    if not text:
        return ""
    out, bullets = [], []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("- "):
            items = "".join(f"<li>{marks(li[2:])}</li>" for li in para.split("\n")
                            if li.strip().startswith("- "))
            out.append(f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{marks(para)}</p>")
    return "".join(out)


ICONS = {
 "facebook": "M17 2h-3a5 5 0 0 0-5 5v3H6v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z",
 "line": "M12 3C6.5 3 2 6.6 2 11c0 3.9 3.5 7.2 8.2 7.9.3.07.8.2.9.5.1.3.07.7.03 1l-.14.9c-.04.3-.2 1 .9.55 1.1-.45 6-3.5 8.2-6C21.4 14.2 22 12.7 22 11c0-4.4-4.5-8-10-8z",
 "whatsapp": "M20 12a8 8 0 0 1-11.9 7L4 20l1-4.1A8 8 0 1 1 20 12z",
 "x": "M3 3l7.5 9.5L3.5 21h2l6-6.8L17 21h4l-7.9-10L20.5 3h-2l-5.6 6.4L8 3z",
 "reddit": "M22 12a2 2 0 0 0-3.4-1.4A11 11 0 0 0 13 9l.9-3.4 2.6.6a1.6 1.6 0 1 0 .2-1.4l-3.4-.8-1.3 4.9A11 11 0 0 0 5.4 10.6 2 2 0 1 0 3.6 14 4 4 0 0 0 3.5 15c0 3 3.8 5.5 8.5 5.5s8.5-2.5 8.5-5.5a4 4 0 0 0-.1-1A2 2 0 0 0 22 12z",
 "mail": "M3 6h18v12H3zM3 6l9 7 9-7",
 "link": "M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1",
 "print": "M7 8V3h10v5M7 18H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2M7 14h10v7H7z",
}


def _icon(name: str) -> str:
    d = ICONS.get(name, "")
    fill = "none" if name in ("mail", "link", "print", "whatsapp") else "currentColor"
    return (f'<svg viewBox="0 0 24 24" width="19" height="19" aria-hidden="true" '
            f'fill="{fill}" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round"><path d="{d}"/></svg>')


def share_row(url: str, title: str, lang: str, blurb: str = "") -> str:
    ui = UI[lang]
    en = lang == "en"
    q = urllib.parse.quote
    share_text = f"{title} — {blurb}" if blurb else title
    links = [
        ("facebook", "Facebook", f"https://www.facebook.com/sharer/sharer.php?u={q(url)}"),
        ("line", "LINE", f"https://social-plugins.line.me/lineit/share?url={q(url)}"),
        ("whatsapp", "WhatsApp", f"https://api.whatsapp.com/send?text={q(share_text + ' ' + url)}"),
        ("x", "X", f"https://twitter.com/intent/tweet?text={q(share_text)}&url={q(url)}"),
        ("reddit", "Reddit", f"https://reddit.com/submit?url={q(url)}&title={q(title)}"),
        ("mail", "Email", f"mailto:?subject={q(title)}&body={q(share_text + chr(10) + chr(10) + url)}"),
    ]
    btns = "".join(
        f'<a class="sh sh-{k}" href="{E(href)}" rel="noopener" target="_blank" '
        f'data-share="{E(k)}">{_icon(k)}<span>{E(label)}</span></a>'
        for k, label, href in links)
    head = "Send this to whoever you train with" if en else "ส่งให้คนที่ซ้อมด้วยกัน"
    sub = "It opens the same in Thai." if en else "เปิดเป็นภาษาอังกฤษได้เหมือนกัน"
    return (f'<aside class="sharebar"><div class="shhead"><b>{E(head)}</b>'
            f'<span class="mute small">{E(sub)}</span></div>'
            f'<div class="shrow">{btns}'
            f'<button type="button" class="sh sh-link" data-copy="{E(url)}">'
            f'{_icon("link")}<span>{E(ui["copy"])}</span></button>'
            f'<button type="button" class="sh sh-print" onclick="window.print()">'
            f'{_icon("print")}<span>{E(ui["print"])}</span></button>'
            f'<button type="button" class="sh sh-native" hidden data-native="{E(url)}" '
            f'data-title="{E(title)}">{_icon("link")}<span>'
            f'{E("Share…" if en else "แชร์…")}</span></button></div></aside>'
            '<script>document.addEventListener("DOMContentLoaded",function(){'
            'var n=document.querySelector(".sh-native");'
            'if(n&&navigator.share){n.hidden=false;n.addEventListener("click",function(){'
            'navigator.share({title:n.dataset.title,url:n.dataset.native}).catch(function(){})})}});'
            "</script>")


# ---------------------------------------------------------------- small parts
def tier_chip(p: dict, lang="en") -> str:
    t = (p or {}).get("tier", "")
    return f'<span class="tier {E(t)}">{E(t)}</span>' if t else ""


def src_link(sid: str, lang="en") -> str:
    s = SOURCES.get(sid)
    if not s:
        return E(sid)
    t = E(s.get("title") or sid)
    pub = E(s.get("publisher") or "")
    if s.get("url"):
        return f'<a href="{E(s["url"])}" rel="noopener">{t}</a>{" — " + pub if pub else ""}'
    return f"{t} — {pub}"


def prov_block(r: dict, lang: str) -> str:
    ui = UI[lang]
    pv = r.get("provenance") or {}
    rows = [("<em>default</em>", pv.get("default") or {})]
    rows += [(E(k), v) for k, v in (pv.get("fields") or {}).items()]
    body = "".join(
        f"<tr><td>{k}</td><td>{tier_chip(v, lang)}</td>"
        f"<td>{src_link(v.get('source'), lang) if v.get('source') else ''}</td>"
        f"<td class='small mute'>{E(v.get('note') or '')}</td></tr>" for k, v in rows)
    srcs = "".join(f"<li>{src_link(s, lang)}</li>" for s in r.get("sources", []))
    return (f'<details><summary>{E(ui["prov"])}</summary>'
            f'<div class="scroll"><table><thead><tr><th>Field</th><th>Tier</th><th>Source</th>'
            f'<th>Note</th></tr></thead><tbody>{body}</tbody></table></div>'
            f'<h3>{E(ui["sources"])}</h3><ul class="small">{srcs}</ul>'
            f'<p class="small mute">' +
            " · ".join(f"<b>{E(k)}</b> {E(v)}" for k, v in TIER_LABEL.items()) +
            "</p></details>")


def clip(t: str, n: int) -> str:
    t = (t or "").strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def credit(im: dict, short=False) -> str:
    """Licence, author and a link to the Commons page, beside the picture. Share-alike is
    complied with rather than avoided, so the terms travel with the file."""
    who = E(im.get("author") or "unknown")
    lic = E(im.get("license") or "")
    page_url = im.get("page_url") or ""
    lic_html = (f'<a href="{E(im["license_url"])}" rel="license noopener">{lic}</a>'
                if im.get("license_url") else lic)
    src = f'<a href="{E(page_url)}" rel="noopener">Commons</a>' if page_url else ""
    note = E(im.get("credit") or "") if im.get("source") == "own" else ""
    parts = [who, note, lic_html] if note else [who, lic_html]
    if not short and src:
        parts.append(src)
    return " · ".join(x for x in parts if x)



def shot_link(href: str, src: str, label: str, im: dict = None) -> str:
    """A picture that leads somewhere, in four layers: the photograph as a background, a
    scrim under the words, a spacer that gives the box its height, and the text over both.
    The whole box is the link, so the picture is not a decoration beside one."""
    cred = f'<span class="cred">{credit(im, short=True)}</span>' if im else ""
    return (f'<figure class="thumb"><h3><a class="shot" href="{E(href)}">'
            f'<span class="bg" style="background-image:url({E(src)})"></span>'
            f'<span class="scrim"></span><span class="sp"></span>'
            f'<span class="tx">{E(label)}</span></a></h3>{cred}</figure>')


def img_url(im: dict, thumb=False) -> str:
    f = im["file"]
    if thumb:
        f = f.rsplit(".", 1)[0] + ".thumb.jpg"
    return f"{rel()}images/{f}"


def pictures(n: dict) -> list:
    return [i for i in (n.get("images") or []) if i.get("file")]


def hero_shot(n: dict) -> str:
    ims = pictures(n)
    if not ims:
        return ""
    im = next((i for i in ims if i.get("primary")), ims[0])
    return (f'<div class="hero-shot"><img src="{E(img_url(im))}" alt="{E(im.get("alt") or "")}" '
            f'loading="lazy" decoding="async">'
            f'<span class="cap">{credit(im, short=True)}</span></div>')


def shot_strip(ims: list) -> str:
    if not ims:
        return ""
    out = ['<div class="strip">']
    for im in ims:
        out.append(f'<figure><img src="{E(img_url(im, thumb=True))}" '
                   f'alt="{E(im.get("alt") or "")}" loading="lazy" decoding="async">'
                   f'<figcaption>{credit(im, short=True)}</figcaption></figure>')
    out.append("</div>")
    return "".join(out)


def node_card(n: dict, lang: str, n_label=None) -> str:
    r = lroot(lang)
    name = T(n, "names.name", lang)
    th = n["names"].get("th")
    what = T(n, "text.what", lang) or ""
    mv = n.get("move") or {}
    meta = []
    if mv.get("refers"):
        meta.append(f'<span class="tag ref-{E(mv["refers"])}">{E(mv["refers"])}</span>')
    for t in (n.get("tags") or [])[:2]:
        meta.append(f'<span class="tag">{E(t)}</span>')
    ims = pictures(n)
    thumb = ""
    if ims:
        im = next((i for i in ims if i.get("primary")), ims[0])
        thumb = shot_link(f"{r}{url_of(n)}", img_url(im, thumb=True), name, im)
    num = f'<span class="n">{n_label}</span>' if n_label else ""
    thai = f'<p class="th">{E(th)}</p>' if th and lang == "en" else ""
    head = "" if thumb else f'<h3><a href="{r}{url_of(n)}">{E(name)}</a></h3>'
    return (f'<article class="card">{num}{thumb}{head}{thai}'
            f'<p>{E(clip(what, 150))}</p>'
            f'<div class="tags">{"".join(meta)}</div></article>')


# ---------------------------------------------------------------- parallax bands
# Hand-picked backgrounds. A Commons search returns a lot that is true and useless, so a
# picture that gets to be a full-width band is named here rather than taken from whatever
# sorts first. Each entry is (record id, filename fragment); the fragment picks one file.
BANDS = {
    "ring":      ("rajadamnern", "rajinfront"),
    "crowd":     ("betting", ""),
    "kick":      ("eight-limbs", "muay-thai-high-kick"),
    "jump":      ("eight-limbs", "round-jump-kick"),
    "statues":   ("wat-bang-kung-statues", "11"),
    "statues2":  ("wat-bang-kung-statues", "thai-boxing-sculptures"),
    "ram":       ("wai-kru-ram-muay", "ram-muay"),
    "waikru":    ("wai-kru-ram-muay", "wai-kru-muay-thai"),
    "clinch":    ("clinch", ""),
    "lowkick":   ("shin", "muay-thai-low-kick"),
    "stadium":   ("lumpinee", "bangkok-lumpinee-boxing-stadium-3"),
    "training":  ("first-session", "016"),
    "pads":      ("pads", ""),
    "women":     ("women-in-the-ring", "womens-muay-thai"),
    "kids":      ("child-boxing", "muay-thai-thai-boxing-kids"),
    "manuscript": ("ramakien-in-the-ring", ""),
    "rope":      ("kaad-chuek", ""),
    "band":      ("sarama", ""),
    "boran":     ("muay-boran", "krabi-krabong-thai"),
    "lamai":     ("chiangmai", ""),
    "gyms":      ("the-gym-map", ""),
    "yant":      ("sak-yant", "own-04"),
    "yant2":     ("gao-yod", "own-01"),
    "watbangphra": ("wat-bang-phra", ""),
    "lanna":     ("lanna", ""),
    "mangrai":   ("mangrai-law", ""),
    "jerng":     ("fon-jerng", ""),
}


def band_image(key: str):
    rid, frag = BANDS.get(key, (None, None))
    n = BY_ID.get(rid or "")
    ims = pictures(n) if n else []
    if not ims:
        return None
    if frag:
        for im in ims:
            if frag in im["file"]:
                return im
    return next((i for i in ims if i.get("primary")), ims[0])


def band(key: str, kicker: str, head: str, line: str = "", lang: str = "en",
         big: str = "", big_label: str = "", href: str = "", cta: str = "",
         cls: str = "") -> str:
    """One full-bleed parallax band. Returns "" when the picture is missing, so a band
    never ships as an empty black strip."""
    im = band_image(key)
    if not im:
        return ""
    inner = [f'<span class="kicker">{E(kicker)}</span>']
    if big:
        inner.append(f'<p class="big">{E(big)}'
                     f'{f"<small>{E(big_label)}</small>" if big_label else ""}</p>')
    if head:
        inner.append(f"<h2>{E(head)}</h2>")
    if line:
        inner.append(f"<p>{E(line)}</p>")
    if href and cta:
        inner.append(f'<a class="btn" href="{E(href)}">{E(cta)}</a>')
    return (f'<section class="band {cls}" style="background-image:url({E(img_url(im))})">'
            f'<div class="in">{"".join(inner)}</div>'
            f'<span class="cred">{credit(im, short=True)}</span></section>')


def slab(cells) -> str:
    return '<div class="slab">' + "".join(
        f"<div><b>{E(v)}</b><span>{E(l)}</span></div>" for v, l in cells) + "</div>"


def by_type(t: str) -> list:
    return [n for n in NODES if n["type"] == t]


def grid(nodes, lang, numbered=False) -> str:
    return '<div class="grid">' + "".join(
        node_card(n, lang, str(i + 1) if numbered else None) for i, n in enumerate(nodes)
    ) + "</div>"


# ---------------------------------------------------------------- front page
def front(lang: str) -> str:
    ui = UI[lang]
    r = lroot(lang)
    en = lang == "en"
    c = CUR
    b = []
    b.append(f'<h1>{E("Muay Thai" if en else "มวยไทย")}</h1>')
    b.append(f'<p class="lede">{E(TAG[lang])}</p>')
    b.append(slab([
        ("8", "limbs" if en else "อาวุธ"),
        (str(c["n"]), "named techniques" if en else "ท่าที่มีชื่อ"),
        (str(c["myth"]), "out of the epic" if en else "มาจากวรรณคดี"),
        (f'{GYMS["count"]:,}', "gyms mapped" if en else "ยิมบนแผนที่"),
        (str(GYMS["countries"]), "countries" if en else "ประเทศ"),
        (f'{ROSTER["count"]:,}', "fighters on record" if en else "นักมวยในบันทึก"),
    ]))
    b.append(band("kick",
                  "Two fists, two elbows, two knees, two shins" if en else "หมัดสอง ศอกสอง เข่าสอง แข้งสอง",
                  "Eight limbs, and the count is the argument" if en else "แปดอาวุธ และการนับคือข้อโต้แย้ง",
                  ("Boxing has two. Kickboxing has four. Making the elbow and the knee legal "
                   "changes every distance in the fight." if en else
                   "มวยสากลมีสอง คิกบ็อกซิ่งมีสี่ การทำให้ศอกและเข่าถูกกติกาเปลี่ยนทุกระยะในการชก"),
                  lang=lang, href=f"{r}limbs/", cta=("The eight" if en else "ทั้งแปด")))

    b.append(f'<h2>{E("Start here" if en else "เริ่มที่นี่")}</h2>')
    starters = [x for x in ("eight-limbs", "four-styles-of-fighter", "scoring",
                            "why-foreigners-lose-decisions", "first-session", "fight-night",
                            "sak-yant", "mangrai-law")
                if x in BY_ID]
    b.append(grid([BY_ID[x] for x in starters], lang))

    b.append(band("statues",
                  "The finding" if en else "ข้อค้นพบ",
                  (f"{c['picture']} of the {c['n']} names are a picture, not an instruction"
                   if en else f"{c['picture']} ใน {c['n']} ชื่อคือภาพ ไม่ใช่คำสั่ง"),
                  ("A crocodile's tail. A bird leaving its nest. Hanuman handing over a ring. "
                   "Only one of the thirty describes the movement, and it does that in Sanskrit."
                   if en else
                   "หางจระเข้ นกออกจากรัง หนุมานถวายแหวน "
                   "มีเพียงท่าเดียวในสามสิบท่าที่บอกการเคลื่อนไหว และมันบอกเป็นภาษาสันสกฤต"),
                  lang=lang, big=str(c["myth"]),
                  big_label=("named for the Ramakien" if en else "ตั้งชื่อตามรามเกียรติ์"),
                  href=f"{r}names/", cta=("All thirty" if en else "ครบสามสิบ")))

    b.append(f'<h2>{E("What this holds" if en else "เว็บนี้มีอะไร")}</h2>')
    cards = []
    for t in TYPES:
        rows = by_type(t)
        if not rows:
            continue
        ti = TYPE_INFO[t]
        cards.append(
            f'<article class="card"><h3><a href="{r}{DIR_OF[t]}/">'
            f'{E(ti["th"] if lang == "th" else ti["name"])}</a> '
            f'<span class="n">{len(rows)}</span></h3>'
            f'<p>{E(ti["th_blurb"] if lang == "th" else ti["blurb"])}</p></article>')
    b.append('<div class="grid">' + "".join(cards) + "</div>")

    b.append(band("gyms",
                  "Counted for this site" if en else "นับขึ้นเพื่อเว็บนี้",
                  (f"{GYMS['count']} places to train, in {GYMS['countries']} countries"
                   if en else f"{GYMS['count']} แห่งที่ฝึกได้ ใน {GYMS['countries']} ประเทศ"),
                  (f"The sport's own OpenStreetMap tag found {GYMS['by_how']['tag only'] + GYMS['by_how']['both']} "
                   f"of them. The other {GYMS['by_how']['name only']} are there because a gym put the "
                   f"word in its own name." if en else
                   f"แท็ก OpenStreetMap ของกีฬานี้เองหาเจอ {GYMS['by_how']['tag only'] + GYMS['by_how']['both']} แห่ง "
                   f"อีก {GYMS['by_how']['name only']} แห่งอยู่ตรงนั้นเพราะยิมใส่คำนั้นไว้ในชื่อตัวเอง"),
                  lang=lang, href=f"{r}gyms/", cta=("The map" if en else "ดูแผนที่")))

    b.append(f'<h2>{E("Open questions" if en else "ข้อถกเถียง")}</h2>')
    b.append(grid(by_type("issue"), lang))

    b.append(band("jerng",
                  "Where it starts" if en else "เริ่มที่ไหน",
                  "Not in Ayutthaya. In Lanna, as a dance." if en else "ไม่ใช่ที่อยุธยา แต่ในล้านนา ในรูปการฟ้อน",
                  ("The Thai-language history begins the craft with jerng, the northern "
                   "martial dance, and the oldest written muay is in a Lanna law of 1296, "
                   "filed under quarrels." if en else
                   "ประวัติศาสตร์ฉบับภาษาไทยเริ่มวิชานี้จากเจิง การฟ้อนเชิงต่อสู้ของภาคเหนือ "
                   "และคำว่ามวยที่เก่าที่สุดในเอกสารอยู่ในกฎหมายล้านนา พ.ศ. 1839 ในหมวดการวิวาท"),
                  lang=lang, big="1296", big_label=("the first written muay" if en else "มวยคำแรกในเอกสาร"),
                  href=f"{r}history/", cta=("History and geography" if en else "ประวัติและภูมิศาสตร์")))

    b.append(band("ram",
                  "Before the bell" if en else "ก่อนระฆัง",
                  "Four minutes of not fighting" if en else "สี่นาทีที่ไม่ได้ชก",
                  ("The headband belongs to the gym, the dance belongs to the fighter, and the "
                   "band has already started." if en else
                   "มงคลเป็นของค่าย การรำเป็นของนักมวย และวงดนตรีเริ่มไปแล้ว"),
                  lang=lang, href=f"{r}ceremony/", cta=("The ceremony" if en else "พิธีกรรม")))

    b.append(share_row(f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}", NAME[lang], lang,
                       TAG[lang]))
    return "".join(b)


# ---------------------------------------------------------------- the names
def refers_label(k: str, lang: str) -> str:
    en = {"myth": "Out of the epic", "beast": "An animal", "people": "A person",
          "thing": "An object or a chore", "plain": "The movement itself"}
    th = {"myth": "จากวรรณคดี", "beast": "สัตว์", "people": "คน",
          "thing": "สิ่งของหรืองานบ้าน", "plain": "ตัวการเคลื่อนไหวเอง"}
    return (en if lang == "en" else th).get(k, k)


def name_table(rows: list, lang: str, show_n=True) -> str:
    ui = UI[lang]
    head = (f"<tr>{'<th>' + E(ui['n']) + '</th>' if show_n else ''}"
            f"<th>{E(ui['th_name'])}</th><th>RTGS</th><th>{E(ui['gloss'])}</th>"
            f"<th>{E(ui['refers'])}</th></tr>")
    body = []
    for row in rows:
        rid = next((n["id"] for n in NODES
                    if (n.get("move") or {}).get("th") == row["th"]), None)
        name = E(row["gloss"])
        if rid:
            name = f'<a href="{lroot(lang)}{PATH_OF["move"]}/{rid}/">{name}</a>'
        body.append(
            f"<tr>{'<td>' + str(row.get('n') or '') + '</td>' if show_n else ''}"
            f'<td class="th">{E(row["th"])}</td><td class="mono">{E(row["rtgs"])}</td>'
            f"<td>{name}</td>"
            f'<td><span class="tag ref-{E(row["refers"])}">{E(refers_label(row["refers"], lang))}</span>'
            f'{" " + E(row["figure"]) if row.get("figure") else ""}</td></tr>')
    return (f'<div class="scroll"><table class="names"><thead>{head}</thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def names_page(lang: str) -> str:
    ui = UI[lang]
    en = lang == "en"
    r = lroot(lang)
    c = CUR
    b = [f'<h1>{E("The thirty names" if en else "สามสิบชื่อ")}</h1>',
         f'<p class="lede">{E("Fifteen mother techniques and fifteen that come after. Twenty-nine of the thirty are named after something you can picture." if en else "แม่ไม้สิบห้า และลูกไม้อีกสิบห้า ยี่สิบเก้าในสามสิบตั้งชื่อตามสิ่งที่นึกภาพได้")}</p>']
    b.append(slab([(str(c["n"]), "names" if en else "ชื่อ"),
                   (str(c["picture"]), "are a picture" if en else "เป็นภาพ"),
                   (str(c["myth"]), "from the epic" if en else "จากวรรณคดี"),
                   (str(c["by_class"].get("beast", 0)), "an animal" if en else "สัตว์"),
                   (str(c["by_class"].get("people", 0)), "a person" if en else "คน"),
                   (str(c["plain"]), "the movement" if en else "การเคลื่อนไหว")]))
    b.append('<div class="note"><p>' + (
        "The Thai names and the descriptions beside them are lifted off the Thai Wikipedia "
        "article at revision " + str(RAW_CUR.get("revision", "")) + ", which cites the Thai "
        "Encyclopedia for Youth. The English gloss and the classification in the last column "
        "are this project's reading, marked as inference wherever they appear. The table is "
        "printed in full so a reader who would classify a row differently is looking at the "
        "same row." if en else
        "ชื่อภาษาไทยและคำอธิบายข้าง ๆ ดึงมาจากบทความวิกิพีเดียภาษาไทยที่รุ่นแก้ไข " +
        str(RAW_CUR.get("revision", "")) + " ซึ่งอ้างสารานุกรมไทยสำหรับเยาวชนฯ "
        "ส่วนคำแปลภาษาอังกฤษและการจัดประเภทในคอลัมน์สุดท้ายเป็นการอ่านของโครงการนี้ "
        "และระบุว่าเป็นการอนุมานทุกที่ที่ปรากฏ ตารางพิมพ์ไว้ครบ "
        "เพื่อให้ผู้อ่านที่จะจัดประเภทต่างออกไปได้มองแถวเดียวกัน") + "</p></div>")

    b.append(band("manuscript",
                  "Where the names come from" if en else "ชื่อมาจากไหน",
                  "A war epic, painted on a wall" if en else "มหากาพย์สงคราม เขียนไว้บนผนัง",
                  ("Rama, Hanuman, Thotsakan, Erawan, the nagas. The Ramakien was the state's "
                   "own narrative property, and the curriculum is built out of it."
                   if en else
                   "พระราม หนุมาน ทศกัณฐ์ เอราวัณ นาค "
                   "รามเกียรติ์เป็นทรัพย์สินทางเรื่องเล่าของรัฐเอง และหลักสูตรถูกสร้างขึ้นจากมัน"),
                  lang=lang, big=str(c["myth"]), big_label=("of thirty" if en else "ในสามสิบ"),
                  href=f"{r}{PATH_OF['art']}/ramakien-in-the-ring/",
                  cta=("The epic in the ring" if en else "วรรณคดีในสังเวียน")))

    b.append(f'<h2>{E("แม่ไม้ — the fifteen" if en else "แม่ไม้ สิบห้าท่า")}</h2>')
    b.append(name_table(c["mae_mai"], lang))
    b.append(f'<h2>{E("ลูกไม้ — the fifteen that come after" if en else "ลูกไม้ สิบห้าท่าที่ตามมา")}</h2>')
    b.append(name_table(c["luk_mai"], lang))

    b.append(f'<h2>{E("The schools name their own" if en else "แต่ละสายมีชื่อของตัวเอง")}</h2>')
    for key, rec_id, label_en, label_th in (
            ("korat", "korat", "Korat — five teaching techniques and twenty-one older ones",
             "โคราช แม่ไม้ครูห้าท่า และท่าโบราณยี่สิบเอ็ดท่า"),
            ("chaiya", "chaiya", "Chaiya — seven", "ไชยา เจ็ดท่า"),
            ("lopburi", "lopburi", "Lopburi — six, and five of them are out of the epic",
             "ลพบุรี หกท่า และห้าท่ามาจากวรรณคดี")):
        sc = c["schools"][key]
        link = f'<a href="{r}{PATH_OF["style"]}/{rec_id}/">' if rec_id in BY_ID else ""
        b.append(f'<h3>{link}{E(label_en if en else label_th)}{"</a>" if link else ""}</h3>')
        b.append(name_table(sc["rows"], lang, show_n=False))
    b.append(f'<p class="mute">' + E(
        "Thasao's list is recorded as twelve upper and twelve lower techniques with no names "
        "attached. That is what the source carries." if en else
        "รายการของท่าเสาบันทึกไว้ว่ามีแม่ไม้บนสิบสองและแม่ไม้ล่างสิบสอง โดยไม่มีชื่อ "
        "นั่นคือสิ่งที่แหล่งอ้างอิงถือไว้") + "</p>")

    b.append(f'<h2>{E("Written up" if en else "ที่เขียนไว้")}</h2>')
    b.append(grid(by_type("move"), lang))
    b.append(share_row(f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}names/",
                       "The thirty names" if en else "สามสิบชื่อ", lang))
    return "".join(b)


# ---------------------------------------------------------------- gyms
def inline_svg(name: str) -> str:
    """The drawn map, inlined rather than linked. An <img> pointing at an SVG is an
    isolated document: it inherits none of the page's CSS, so a map linked that way keeps
    its own palette while the page around it follows the reader's theme. Inlined, the
    shapes take their colours from the stylesheet like everything else. The file itself
    stays on disk, self-contained, for anyone who wants it on its own."""
    f = SITE / name
    if not f.exists():
        return ""
    svg = f.read_text(encoding="utf-8")
    svg = re.sub(r"<style>.*?</style>", "", svg, flags=re.S)
    return svg.replace("<svg ", '<svg class="mapsvg" ', 1)


def web(tags: dict):
    """The website tag as a usable URL, or None. OpenStreetMap carries these as people
    typed them: no scheme, two URLs in one value separated by a semicolon, a bare domain.
    Take the first, give it a scheme, and drop anything that is not a host."""
    raw = (tags.get("website") or tags.get("contact:website") or "").strip()
    if not raw:
        return None
    raw = re.split(r"[;,\s]+", raw)[0]
    if raw.startswith("//"):
        raw = "https:" + raw
    elif not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    host = urllib.parse.urlparse(raw).netloc
    return raw if "." in host and " " not in host else None


def country_roster(lang: str) -> str:
    """Harvested rows, grouped by country and then by subregion. A name-dump reads as
    empty; the grouping is the directory."""
    en = lang == "en"
    rows = GYMS["rows"]
    by_c = {}
    for row in rows:
        by_c.setdefault(row["country_name"] or ("unplaced" if en else "ไม่ทราบประเทศ"),
                        []).append(row)
    out = []
    for cname, rs in sorted(by_c.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        rs.sort(key=lambda x: (x["tags"].get("addr:city") or "", x["tags"].get("name") or ""))
        items = []
        for x in rs:
            nm = x["tags"].get("name") or x["tags"].get("name:en") or ("unnamed" if en else "ไม่มีชื่อ")
            city = x["tags"].get("addr:city") or ""
            site = web(x["tags"])
            kind = x["kind"]
            osm = f'https://www.openstreetmap.org/{"node" if x["osm"][0] == "n" else "way" if x["osm"][0] == "w" else "relation"}/{x["osm"][1:]}'
            link = f'<a href="{E(site)}" rel="noopener nofollow">{E(nm)}</a>' if site else E(nm)
            items.append(f'<li><span class="tag k-{E(kind)}">{E(kind)}</span> {link}'
                         f'{" · " + E(city) if city else ""} '
                         f'<a class="osm" href="{E(osm)}" rel="noopener">OSM</a></li>')
        out.append(f'<details{" open" if len(rs) >= 20 else ""}><summary>{E(cname)} '
                   f'<span class="n">{len(rs)}</span></summary>'
                   f'<ul class="roster">{"".join(items)}</ul></details>')
    return "".join(out)


def gyms_page(lang: str) -> str:
    en = lang == "en"
    r = lroot(lang)
    g = GYMS
    b = [f'<h1>{E("Every gym on the map" if en else "ทุกยิมบนแผนที่")}</h1>',
         f'<p class="lede">' + E(
             f"{g['count']} places in {g['countries']} countries, as OpenStreetMap held them "
             f"on {g['fetched'][:10]}. Volunteer data, unchecked by this project."
             if en else
             f"{g['count']} แห่งใน {g['countries']} ประเทศ ตามที่ OpenStreetMap ถือไว้เมื่อ "
             f"{g['fetched'][:10]} เป็นข้อมูลอาสาสมัคร โครงการนี้ไม่ได้ตรวจสอบ") + "</p>"]
    b.append(slab([(f'{g["count"]:,}', "rows" if en else "แถว"),
                   (str(g["countries"]), "countries" if en else "ประเทศ"),
                   (str(g["thailand"]), "in Thailand" if en else "ในไทย"),
                   (str(g["abroad"]), "abroad" if en else "ต่างประเทศ"),
                   (str(g["stadiums"]), "stadiums" if en else "สนาม"),
                   (str(g["with_website"]), "with a website" if en else "มีเว็บไซต์")]))
    legend = ('<ul class="legend"><li><i class="sw c"></i>' +
              E("none on the map" if en else "ไม่มีบนแผนที่") +
              '</li><li><i class="sw a"></i>1</li><li><i class="sw b"></i>2–3</li>'
              '<li><i class="sw c2"></i>4–8</li><li><i class="sw d"></i>9–25</li>'
              '<li><i class="sw e"></i>26+</li><li><i class="sw dotsw"></i>' +
              E("one row" if en else "หนึ่งแถว") + "</li></ul>")
    b.append('<figure class="map">' + inline_svg("world.svg") + legend
             + '<figcaption>' + E(
                 "Equal Earth projection, because the subject is how many of a thing are "
                 "where. Shading is the count per country; each dot is one row. "
                 "© OpenStreetMap contributors, ODbL. Outlines: Natural Earth."
                 if en else
                 "ใช้แผนที่แบบ Equal Earth เพราะเรื่องที่ดูคือมีของอยู่ที่ไหนกี่แห่ง "
                 "สีเข้มคือจำนวนต่อประเทศ จุดหนึ่งคือหนึ่งแถว "
                 "© ผู้ร่วมสร้าง OpenStreetMap ภายใต้ ODbL เส้นขอบ: Natural Earth") +
             "</figcaption></figure>")

    b.append('<div class="note"><p>' + (
        f"<b>The floor is well below this.</b> The English Wikipedia article records more than "
        f"<b>3,800 muay thai gyms overseas in 2020</b>. This map has {g['abroad']} outside "
        f"Thailand. What follows is a census of OpenStreetMap, not of the sport."
        if en else
        f"<b>พื้นอยู่ต่ำกว่านี้มาก</b> บทความวิกิพีเดียภาษาอังกฤษบันทึกว่ามี"
        f"<b>ยิมมวยไทยในต่างประเทศมากกว่า 3,800 แห่งในปี 2563</b> "
        f"แผนที่นี้มี {g['abroad']} แห่งนอกประเทศไทย "
        f"สิ่งที่ตามมาคือสำมะโนของ OpenStreetMap ไม่ใช่ของกีฬานี้") + "</p></div>")

    b.append(f'<h2>{E("Two ways of asking" if en else "ถามสองวิธี")}</h2>')
    b.append(slab([(str(g["by_how"]["tag only"]), "found by tag only" if en else "เจอจากแท็กอย่างเดียว"),
                   (str(g["by_how"]["name only"]), "by name only" if en else "จากชื่ออย่างเดียว"),
                   (str(g["by_how"]["both"]), "by both" if en else "เจอทั้งสองทาง")]))
    b.append("<p>" + E(
        "One query asked OpenStreetMap for the tag the sport has — sport=muay_thai and its "
        "spellings. One asked for the name, in every script the sport is written in. The "
        "tag missed almost half of what is there." if en else
        "คำสั่งหนึ่งถาม OpenStreetMap ด้วยแท็กของกีฬานี้ คือ sport=muay_thai และการสะกดแบบอื่น "
        "อีกคำสั่งถามด้วยชื่อ ในทุกระบบเขียนที่กีฬานี้ถูกเขียน แท็กพลาดไปเกือบครึ่งของที่มีอยู่") + "</p>")
    dropped = "".join(f"<tr><td>{E(k)}</td><td class='num'>{v}</td></tr>"
                      for k, v in g["dropped"].items())
    b.append(f'<details><summary>' + E("What was thrown out, and why" if en else "อะไรถูกคัดออก และเพราะอะไร")
             + f'</summary><p>' + E(
                 "Thai is written without spaces, so มวย (boxing) matches inside หมวย — Muay, "
                 "a nickname — and inside มวยผม, a bun of hair. In Latin script muay matches "
                 "inside Turkish muayene, a medical or vehicle inspection. Matching at word "
                 "level and requiring a facility tag clears both."
                 if en else
                 "ภาษาไทยเขียนติดกัน คำว่า มวย จึงไปตรงกับข้างใน หมวย ซึ่งเป็นชื่อเล่น "
                 "และข้างใน มวยผม ส่วนอักษรละติน muay ไปตรงกับข้างในคำตุรกี muayene "
                 "ที่แปลว่าการตรวจโรคหรือตรวจสภาพรถ การจับคู่ระดับคำและการบังคับให้มีแท็กสถานที่แก้ได้ทั้งสองอย่าง")
             + f'</p><div class="scroll"><table><thead><tr><th>Reason</th><th>Rows</th></tr>'
               f'</thead><tbody>{dropped}</tbody></table></div></details>')

    b.append(f'<h2>{E("Thailand" if en else "ประเทศไทย")}</h2>')
    b.append('<figure class="map">' + inline_svg("thailand.svg")
             + '<figcaption>© OpenStreetMap contributors, ODbL. '
             + E("Outlines: Natural Earth." if en else "เส้นขอบ: Natural Earth")
             + '</figcaption></figure>')

    b.append(f'<h2>{E("By country" if en else "ตามประเทศ")}</h2>')
    b.append('<div class="roster-wrap">' + country_roster(lang) + "</div>")
    b.append(f'<h2>{E("Written up" if en else "ที่เขียนไว้")}</h2>')
    b.append(grid(by_type("gym") + by_type("venue"), lang))
    b.append(share_row(f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}gyms/",
                       "Every gym on the map" if en else "ทุกยิมบนแผนที่", lang,
                       f"{g['count']} in {g['countries']} countries"))
    return "".join(b)


# ---------------------------------------------------------------- people
def people_page(lang: str) -> str:
    en = lang == "en"
    ro = ROSTER
    b = [f'<h1>{E("People" if en else "บุคคล")}</h1>',
         f'<p class="lede">' + E(
             "Written up here, and then a census of everyone the open record holds."
             if en else "ที่เขียนไว้ตรงนี้ แล้วตามด้วยสำมะโนของทุกคนที่บันทึกเปิดถือไว้") + "</p>"]
    b.append(grid(by_type("person"), lang))

    b.append(f'<h2>{E("Who the record remembers" if en else "ใครที่บันทึกจำไว้")}</h2>')
    b.append(slab([(f'{ro["count"]:,}', "on record" if en else "ในบันทึก"),
                   (str(ro["thai"]), "Thai" if en else "คนไทย"),
                   (str(ro["thai_women"]), "Thai women" if en else "ผู้หญิงไทย"),
                   (str(ro["women"]), "women in all" if en else "ผู้หญิงทั้งหมด"),
                   (str(ro["with_thai_label"]), "with a Thai name" if en else "มีชื่อภาษาไทย")]))
    b.append('<div class="note"><p>' + (
        "This counts entries in Wikidata, not fighters. Sorted by how many Wikipedias hold "
        "an entry, the top of the list is Shaquille O'Neal — and in the wider cohort, "
        "Batman. So nothing here is a ranking. The shape is still worth having: it is a "
        "measurement of who gets written about."
        if en else
        "นี่คือการนับรายการในวิกิสนเทศ ไม่ใช่การนับนักมวย "
        "เมื่อเรียงตามจำนวนวิกิพีเดียที่มีบทความ ยอดของรายการคือชาคีลล์ โอนีล "
        "และในกลุ่มที่กว้างกว่านั้นคือแบทแมน ตรงนี้จึงไม่มีอะไรเป็นการจัดอันดับ "
        "แต่รูปร่างของมันยังมีค่า มันคือการวัดว่าใครได้ถูกเขียนถึง") + "</p></div>")

    top = [(k, v) for k, v in ro["by_country"].items() if k != "unstated"][:16]
    mx = max(v for _, v in top) if top else 1
    bars = "".join(
        f'<tr><td>{E(k)}</td><td class="bar"><span style="width:{v / mx * 100:.1f}%"></span></td>'
        f'<td class="num">{v}</td></tr>' for k, v in top)
    b.append(f'<h3>{E("By country" if en else "ตามประเทศ")}</h3>'
             f'<div class="scroll"><table class="chart"><tbody>{bars}</tbody></table></div>')

    dec = [(k, v) for k, v in sorted(ro["by_decade"].items()) if k != "unstated" and k >= "1900s"]
    mx2 = max(v for _, v in dec) if dec else 1
    bars2 = "".join(
        f'<tr><td>{E(k)}</td><td class="bar"><span style="width:{v / mx2 * 100:.1f}%"></span></td>'
        f'<td class="num">{v}</td></tr>' for k, v in dec)
    b.append(f'<h3>{E("By decade of birth" if en else "ตามทศวรรษเกิด")}</h3>'
             f'<div class="scroll"><table class="chart"><tbody>{bars2}</tbody></table></div>')

    gen = "".join(f'<tr><td>{E(k)}</td><td class="num">{v}</td></tr>'
                  for k, v in ro["by_gender"].items())
    b.append(f'<h3>{E("By gender, as Wikidata records it" if en else "ตามเพศ ตามที่วิกิสนเทศบันทึก")}</h3>'
             f'<div class="scroll"><table><tbody>{gen}</tbody></table></div>')
    b.append("<p>" + E(
        f"Of the {ro['thai']} Thai entries, {ro['thai_women']} are women. Thailand's women's "
        f"cards are full and its gyms are full; this is a measurement of who gets written up."
        if en else
        f"ในรายการคนไทย {ro['thai']} คน เป็นผู้หญิง {ro['thai_women']} คน "
        f"รายการมวยหญิงของไทยเต็มและยิมก็เต็ม นี่คือการวัดว่าใครได้ถูกเขียนถึง") + "</p>")

    b.append(share_row(f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}people/",
                       "People" if en else "บุคคล", lang))
    return "".join(b)


# ---------------------------------------------------------------- assembled pages
def assembled(lang: str, title_en, title_th, lede_en, lede_th, lead_ids, types, bandkey,
              band_args, path, cur) -> str:
    en = lang == "en"
    b = [f"<h1>{E(title_en if en else title_th)}</h1>",
         f'<p class="lede">{E(lede_en if en else lede_th)}</p>']
    leads = [BY_ID[i] for i in lead_ids if i in BY_ID]
    if leads:
        lead = leads[0]
        b.append(hero_shot(lead))
        for key in ("what", "story", "how"):
            txt = T(lead, f"text.{key}", lang, fallback=False) or (lead.get("text") or {}).get(key)
            if txt:
                b.append(prose(txt))
        b.append(f'<p><a class="btn" href="{lroot(lang)}{url_of(lead)}">'
                 f'{E(("Full record" if en else "บันทึกเต็ม") + " — " + (T(lead, "names.name", lang) or ""))}</a></p>')
    if bandkey:
        b.append(band(bandkey, *band_args[0:3], lang=lang, **band_args[3]))
    for t in types:
        rows = [n for n in by_type(t) if n["id"] not in lead_ids[:1]]
        if not rows:
            continue
        ti = TYPE_INFO[t]
        b.append(f'<h2>{E(ti["th"] if lang == "th" else ti["name"])}</h2>')
        b.append(f'<p class="mute">{E(ti["th_blurb"] if lang == "th" else ti["blurb"])}</p>')
        b.append(grid(rows, lang))
    b.append(share_row(f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}{path}",
                       title_en if en else title_th, lang))
    return "".join(b)


def limbs_page(lang):
    return assembled(
        lang, "The eight limbs", "อาวุธทั้งแปด",
        "Two fists, two elbows, two knees, two shins — and what each one is worth.",
        "หมัดสอง ศอกสอง เข่าสอง แข้งสอง และแต่ละอย่างมีค่าเท่าไร",
        ["eight-limbs"], ["weapon"], "clinch",
        ("The part that is not kickboxing" if lang == "en" else "ส่วนที่ไม่ใช่คิกบ็อกซิ่ง",
         "Nobody pulls them apart" if lang == "en" else "ไม่มีใครแยกสองคนออกจากกัน",
         ("Legal knees make the clinch worth having; an unbroken clinch gives the fight a "
          "wrestling phase; a wrestling phase is where the fifth round is decided."
          if lang == "en" else
          "เข่าที่ถูกกติกาทำให้วงในคุ้มที่จะเข้า วงในที่ไม่ถูกแยกทำให้ไฟต์มีช่วงปล้ำ "
          "และช่วงปล้ำคือที่ที่ยกห้าถูกตัดสิน"), {}),
        "limbs/", "limbs")


def schools_page(lang):
    return assembled(
        lang, "The schools", "สายมวย",
        "Heavy fists Korat, clever Lopburi, good form Chaiya, faster than Thasao — and where that rhyme came from.",
        "หมัดหนักโคราช ฉลาดลพบุรี ท่าดีไชยา ไวกว่าท่าเสา และคำกล่าวนี้มาจากไหน",
        ["four-lines"], ["style", "place"], "boran",
        ("Muay boran" if lang == "en" else "มวยโบราณ",
         "The old name is younger than the new one" if lang == "en" else "ชื่อเก่าอายุน้อยกว่าชื่อใหม่",
         ("*Muay boran* was coined to describe what came before, after *muay thai* had been "
          "introduced to distinguish the Siamese art from international boxing."
          if lang == "en" else
          "คำว่ามวยโบราณถูกบัญญัติขึ้นเพื่อเรียกสิ่งที่มาก่อน "
          "หลังจากคำว่ามวยไทยถูกใช้เพื่อแยกศิลปะของสยามออกจากมวยสากล"), {}),
        "schools/", "schools")


def ceremony_page(lang):
    return assembled(
        lang, "The ceremony", "พิธีกรรม",
        "The headband, the armbands, the dance, and the four instruments playing under all of it.",
        "มงคล ประเจียด การรำ และเครื่องดนตรีสี่ชิ้นที่บรรเลงอยู่ข้างใต้ทั้งหมดนั้น",
        ["wai-kru-ram-muay"], ["ritual", "music"], "yant",
        ("Sak yant" if lang == "en" else "สักยันต์",
         "One practice, four surfaces" if lang == "en" else "แนวปฏิบัติเดียว สี่พื้นผิว",
         ("Yant on skin, yant on the cloth at the arm, yant rolled in metal at the waist, "
          "yant braided into the cord on the head. A fighter walking to the ring is usually "
          "wearing three of the four."
          if lang == "en" else
          "ยันต์บนผิว ยันต์บนผ้าที่แขน ยันต์ม้วนในโลหะที่เอว ยันต์ถักอยู่ในวงด้ายบนหัว "
          "นักมวยที่เดินไปเวทีมักสวมอยู่สามในสี่อย่าง"), {}),
        "ceremony/", "ceremony")


def watch_page(lang):
    return assembled(
        lang, "Watching a fight", "การดูมวย",
        "Five rounds, three judges, and almost none of it scored the way you expect.",
        "ห้ายก กรรมการสามคน และแทบไม่มีอะไรให้คะแนนอย่างที่คุณคิด",
        ["scoring"], ["rule", "bout"], "crowd",
        ("The floor" if lang == "en" else "วงพนัน",
         "The noise is money" if lang == "en" else "เสียงนั้นคือเงิน",
         ("An estimated 40 billion baht a year moves through the betting, in play, by hand "
          "signal, re-priced between rounds."
          if lang == "en" else
          "ประมาณสี่หมื่นล้านบาทต่อปีหมุนอยู่ในวงพนัน เล่นสด ใช้สัญญาณมือ และตั้งราคาใหม่ระหว่างยก"), {}),
        "watch/", "watch")


def training_page(lang):
    return assembled(
        lang, "Training", "การฝึก",
        "Two sessions a day, in the order they happen, and what to ask before paying for a month.",
        "วันละสองรอบ เรียงตามลำดับจริง และควรถามอะไรก่อนจ่ายค่าเดือน",
        ["first-session"], ["drill", "kit"], "training",
        ("Two hours" if lang == "en" else "สองชั่วโมง",
         "The shin hurts before the lungs do" if lang == "en" else "แข้งเจ็บก่อนปอด",
         ("A shin that has never hit anything bruises on a pad on day one, and the bruise is "
          "on the bone." if lang == "en" else
          "แข้งที่ไม่เคยกระแทกอะไรจะช้ำจากเป้าตั้งแต่วันแรก และรอยช้ำนั้นอยู่บนกระดูก"), {}),
        "training/", "train")


def history_page(lang):
    return assembled(
        lang, "History and geography", "ประวัติและภูมิศาสตร์",
        "A palm-leaf law of 1296, a dance in Lanna, boxers in an order of battle, and the "
        "reign that turned all of it into a national sport.",
        "กฎหมายใบลาน พ.ศ. 1839 การฟ้อนในล้านนา นักมวยในลำดับการรบ "
        "และรัชกาลที่เปลี่ยนทั้งหมดนั้นให้เป็นกีฬาของชาติ",
        ["mangrai-law"], ["story", "place"], "lanna",
        ("Where it starts" if lang == "en" else "เริ่มที่ไหน",
         "Not in Ayutthaya" if lang == "en" else "ไม่ใช่ที่อยุธยา",
         ("The Thai-language history of the sport begins it with jerng, the Lanna martial "
          "dance — and the oldest written muay is in a northern law code about quarrels."
          if lang == "en" else
          "ประวัติศาสตร์มวยไทยฉบับภาษาไทยเริ่มเรื่องด้วยเจิง การฟ้อนเชิงต่อสู้ของล้านนา "
          "และคำว่ามวยที่เก่าที่สุดในเอกสารอยู่ในกฎหมายทางเหนือว่าด้วยการวิวาท"), {}),
        "history/", "history")


def words_page(lang):
    return assembled(
        lang, "Words", "คำศัพท์",
        "What the corner is shouting, and where the words come from.",
        "มุมกำลังตะโกนอะไร และคำเหล่านั้นมาจากไหน",
        [], ["term"], "",
        (None, None, None, {}), "words/", "words")


# ---------------------------------------------------------------- numbers
def numbers_page(lang: str) -> str:
    en = lang == "en"
    r = lroot(lang)
    c, g, ro = CUR, GYMS, ROSTER
    b = [f'<h1>{E("Numbers" if en else "ตัวเลข")}</h1>',
         f'<p class="lede">' + E(
             "Everything on this site that was counted rather than repeated, with the method "
             "beside it." if en else
             "ทุกอย่างบนเว็บนี้ที่ถูกนับ ไม่ใช่เล่าต่อ พร้อมวิธีการอยู่ข้าง ๆ") + "</p>"]

    def block(head, cells, note):
        return (f"<h2>{E(head)}</h2>" + slab(cells) + f'<p class="mute">{E(note)}</p>')

    b.append(block(
        "The curriculum" if en else "หลักสูตร",
        [(str(c["n"]), "named techniques" if en else "ท่าที่มีชื่อ"),
         (str(c["picture"]), "are a picture" if en else "เป็นภาพ"),
         (str(c["myth"]), "from the epic" if en else "จากวรรณคดี"),
         (str(c["plain"]), "describe the movement" if en else "บอกการเคลื่อนไหว")],
        ("Counted off the two lists of fifteen on the Thai Wikipedia article at revision "
         f"{RAW_CUR.get('revision', '')}. The classification is this project's."
         if en else
         "นับจากรายการสิบห้าสองชุดในบทความวิกิพีเดียภาษาไทยที่รุ่นแก้ไข "
         f"{RAW_CUR.get('revision', '')} การจัดประเภทเป็นของโครงการนี้")))
    b.append(block(
        "Places to train" if en else "แห่งที่ฝึกได้",
        [(f'{g["count"]:,}', "rows" if en else "แถว"),
         (str(g["countries"]), "countries" if en else "ประเทศ"),
         (str(g["by_how"]["name only"]), "found by name only" if en else "เจอจากชื่ออย่างเดียว"),
         (str(sum(g["dropped"].values())), "dropped" if en else "คัดออก")],
        ("Two Overpass queries over OpenStreetMap, unioned and de-duplicated; country by "
         "point-in-polygon against Natural Earth at 1:50m. A published figure puts overseas "
         "gyms above 3,800, so this is a floor."
         if en else
         "คำสั่ง Overpass สองชุดบน OpenStreetMap รวมและตัดซ้ำ "
         "ประเทศได้จากการทดสอบจุดในรูปหลายเหลี่ยมกับ Natural Earth มาตราส่วน 1:50m "
         "ตัวเลขที่เผยแพร่ระบุว่ายิมในต่างประเทศมีเกิน 3,800 แห่ง ตัวเลขนี้จึงเป็นพื้น")))
    b.append(block(
        "The roster" if en else "รายชื่อ",
        [(f'{ro["count"]:,}', "on record" if en else "ในบันทึก"),
         (str(ro["thai"]), "Thai" if en else "คนไทย"),
         (str(ro["women"]), "women" if en else "ผู้หญิง"),
         (str(ro["thai_women"]), "Thai women" if en else "ผู้หญิงไทย")],
        ("Wikidata, occupation Thai boxer, humans only. Not a ranking: the cohort includes "
         "actors, and the wider one includes Batman." if en else
         "วิกิสนเทศ อาชีพนักมวยไทย เฉพาะมนุษย์ ไม่ใช่การจัดอันดับ "
         "กลุ่มนี้มีนักแสดงรวมอยู่ และกลุ่มที่กว้างกว่ามีแบทแมน")))
    b.append(block(
        "This site" if en else "เว็บนี้",
        [(str(COV["records"]), "records" if en else "บันทึก"),
         (str(COV["kin_edges"]), "links between them" if en else "เส้นเชื่อม"),
         (str(COV["sources"]), "sources" if en else "แหล่งอ้างอิง"),
         (str(COV["th_fields"]), "Thai fields" if en else "ช่องภาษาไทย"),
         (str(COV["images"]), "pictures" if en else "ภาพ"),
         (str(COV["needs_verification"]), "flagged for checking" if en else "ติดธงให้ตรวจ")],
        ("Every figure on this page is computed at build time from the files in the repo. "
         "None is typed in." if en else
         "ตัวเลขทุกตัวบนหน้านี้คำนวณตอนสร้างเว็บจากไฟล์ในคลัง ไม่มีตัวไหนพิมพ์ใส่เอง")))

    tiers = "".join(f'<tr><td>{E(k)}</td><td class="num">{v}</td>'
                    f'<td class="small mute">{E(TIER_LABEL.get(k, ""))}</td></tr>'
                    for k, v in sorted(COV["tiers"].items(), key=lambda kv: -kv[1]))
    b.append(f'<h2>{E("How the claims are held" if en else "ข้อความถูกถือไว้อย่างไร")}</h2>'
             f'<div class="scroll"><table><tbody>{tiers}</tbody></table></div>')
    b.append(f'<p><a class="btn" href="{r}{PATH_OF["story"]}/what-we-did-not-do/">'
             f'{E("What this site does not have" if en else "สิ่งที่เว็บนี้ไม่มี")}</a></p>')
    b.append(share_row(f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}numbers/",
                       "Numbers" if en else "ตัวเลข", lang))
    return "".join(b)


# ---------------------------------------------------------------- node page
def node_page(n: dict, lang: str) -> str:
    ui = UI[lang]
    r = lroot(lang)
    ti = TYPE_INFO[n["type"]]
    name = T(n, "names.name", lang)
    kind = ti["th"] if lang == "th" else ti["one"]
    said = T(n, "names.said", lang)
    url = f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}{url_of(n)}"
    b = [f'<h1><span class="kind">{E(kind)}</span>{E(name)}</h1>']
    nm = n["names"]
    if lang == "en" and nm.get("th"):
        b.append(f'<p class="said th">{E(nm["th"])}'
                 f'{" · " + E(nm["rtgs"]) if nm.get("rtgs") else ""}</p>')
    if said:
        b.append(f'<p class="said">{E(said)}</p>')
    if n.get("needs_verification"):
        b.append(f'<div class="warn">{E(ui["unverified"])}</div>')
    ims = pictures(n)
    if ims:
        b.append(hero_shot(n))

    mv = n.get("move") or {}
    if mv:
        cells = []
        if mv.get("n"):
            cells.append((str(mv["n"]), ui["n"]))
        if mv.get("set"):
            cells.append((FACETS["set"]["values"].get(mv["set"], mv["set"]).split(" — ")[0], ui["set"]))
        cells.append((refers_label(mv.get("refers", ""), lang), ui["refers"]))
        b.append(slab(cells))
        rows = [f'<tr><th>{E(ui["th_name"])}</th><td class="th">{E(mv.get("th", ""))}</td></tr>',
                f'<tr><th>RTGS</th><td class="mono">{E(mv.get("rtgs", ""))}</td></tr>',
                f'<tr><th>{E(ui["gloss"])}</th><td>{E(mv.get("gloss", ""))}</td></tr>']
        if mv.get("figure"):
            rows.append(f'<tr><th>{E(ui["refers"])}</th><td>{E(mv["figure"])}</td></tr>')
        does = (mv.get("does_th") if lang == "th" else None) or mv.get("does")
        if does:
            rows.append(f'<tr><th>{E(ui["does"])}</th><td>{E(does)}</td></tr>')
        b.append(f'<div class="scroll"><table class="kv"><tbody>{"".join(rows)}</tbody></table></div>')

    bt = n.get("bout") or {}
    if bt:
        cells = [(bt.get("date", ""), "date" if lang == "en" else "วันที่")]
        if bt.get("city"):
            cells.append((bt["city"], "where" if lang == "en" else "ที่ไหน"))
        if bt.get("result"):
            cells.append((bt["result"], "result" if lang == "en" else "ผล"))
        b.append(slab(cells))
        if bt.get("rules"):
            b.append(f'<p class="mute">{E(bt["rules"])}</p>')

    vn = n.get("venue") or {}
    if vn:
        cells = []
        if vn.get("opened"):
            cells.append((vn["opened"], "opened" if lang == "en" else "เปิด"))
        if vn.get("city"):
            cells.append((vn["city"], "city" if lang == "en" else "เมือง"))
        if vn.get("ticket_thb"):
            cells.append((str(vn["ticket_thb"]), "ticket" if lang == "en" else "บัตร"))
        if cells:
            b.append(slab(cells))
        if vn.get("nights_note"):
            b.append(f'<div class="warn">{E(vn["nights_note"])}</div>')

    se = n.get("session") or {}
    if se:
        b.append(slab([(se.get("minutes", ""), "minutes" if lang == "en" else "นาที"),
                       (se.get("when", ""), "when" if lang == "en" else "เมื่อไร"),
                       (se.get("hurts", ""), "what hurts" if lang == "en" else "อะไรเจ็บ")]))

    if n.get("geo"):
        g = n["geo"]
        b.append(f'<p class="mute mono">{g["lat"]:.4f}, {g["lon"]:.4f} · '
                 f'<a href="https://www.openstreetmap.org/?mlat={g["lat"]}&mlon={g["lon"]}#map=15/'
                 f'{g["lat"]}/{g["lon"]}" rel="noopener">OpenStreetMap</a></p>')

    for key, label in (("what", ui["what"]), ("story", ui["story"]), ("how", ui["how"]),
                       ("today", ui["today"]), ("notes", ui["notes"])):
        txt = T(n, f"text.{key}", lang, fallback=False)
        miss = False
        if txt is None:
            txt = (n.get("text") or {}).get(key)
            miss = lang == "th" and bool(txt)
        if not txt:
            continue
        b.append(f"<h2>{E(label)}</h2>")
        if miss:
            b.append(f'<div class="warn">{E(ui["no_th"])}</div>')
        b.append(prose(txt))

    ety = n.get("etymology") or {}
    if ety.get("root"):
        b.append(f'<h2>{E("Root" if lang == "en" else "รากศัพท์")}</h2>'
                 f'<p class="root">{E(ety["root"])}</p>')
        if ety.get("first_attested"):
            b.append(f'<p class="mute">{E("First attested" if lang == "en" else "หลักฐานแรกสุด")}'
                     f': {E(ety["first_attested"])}</p>')
        if ety.get("note"):
            b.append(f'<p class="mute">{E(ety["note"])}</p>')

    if len(ims) > 1:
        b.append(shot_strip([i for i in ims if not i.get("primary")]))

    kin = [k for k in (n.get("kin") or []) if k["to"] in BY_ID]
    if kin:
        b.append(f'<h2>{E(ui["kin"])}</h2><ul class="kin">')
        for k in kin:
            t = BY_ID[k["to"]]
            b.append(f'<li><a href="{r}{url_of(t)}">{E(T(t, "names.name", lang))}</a> '
                     f'<span class="mute">{E(k["as"])}</span></li>')
        b.append("</ul>")
    kin_in = [k for k in (n.get("kin_in") or []) if k["from"] in BY_ID]
    if kin_in:
        b.append(f'<h2>{E(ui["said_here"])}</h2><ul class="kin">')
        for k in kin_in:
            t = BY_ID[k["from"]]
            b.append(f'<li><a href="{r}{url_of(t)}">{E(T(t, "names.name", lang))}</a> '
                     f'<span class="mute">{E(k["as"])}</span></li>')
        b.append("</ul>")

    if n.get("links"):
        b.append("<ul class=\"kin\">" + "".join(
            f'<li><a href="{E(l["url"])}" rel="noopener">{E(l.get("label") or l["url"])}</a></li>'
            for l in n["links"]) + "</ul>")

    b.append(prov_block(n, lang))
    b.append(f'<p class="mute small"><a href="{rel()}api/{n["type"]}/{n["id"]}.json">'
             f'{E("This record as JSON" if lang == "en" else "บันทึกนี้ในรูป JSON")}</a></p>')
    b.append(share_row(url, name, lang, T(n, "names.said", lang) or ""))
    return "".join(b)


# ---------------------------------------------------------------- type index
def type_index(t: str, lang: str) -> str:
    ti = TYPE_INFO[t]
    en = lang == "en"
    rows = by_type(t)
    b = [f'<h1>{E(ti["th"] if lang == "th" else ti["name"])}</h1>',
         f'<p class="lede">{E(ti["th_blurb"] if lang == "th" else ti["blurb"])}</p>']
    facet = (ti.get("group_by") or "").replace("facets.", "")
    spec = FACETS.get(facet)
    if spec and spec.get("values"):
        groups = {}
        for n in rows:
            v = (n.get("facets") or {}).get(facet) or "_"
            groups.setdefault(v, []).append(n)
        order = list(spec["values"]) + ["_"]
        for v in order:
            if v not in groups:
                continue
            label = spec["values"].get(v, "Everything else" if en else "อื่น ๆ")
            b.append(f'<h2>{E(label)}</h2>')
            b.append(grid(groups[v], lang))
    else:
        b.append(grid(rows, lang))
    b.append(share_row(f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}{DIR_OF[t]}/",
                       ti["th"] if lang == "th" else ti["name"], lang))
    return "".join(b)


def all_page(lang: str) -> str:
    en = lang == "en"
    r = lroot(lang)
    b = [f'<h1>{E("Everything" if en else "ทั้งหมด")}</h1>',
         f'<p class="lede">{COV["records"]} '
         f'{E("records, by type" if en else "บันทึก จัดตามประเภท")}</p>']
    for t in TYPES:
        rows = by_type(t)
        if not rows:
            continue
        ti = TYPE_INFO[t]
        b.append(f'<h2><a href="{r}{DIR_OF[t]}/">{E(ti["th"] if lang == "th" else ti["name"])}</a> '
                 f'<span class="n">{len(rows)}</span></h2><ul class="cols">')
        for n in sorted(rows, key=lambda x: (T(x, "names.name", lang) or "")):
            th = n["names"].get("th")
            thai = f' <span class="th mute">{E(th)}</span>' if th and lang == "en" else ""
            b.append(f'<li><a href="{r}{url_of(n)}">{E(T(n, "names.name", lang))}</a>{thai}</li>')
        b.append("</ul>")
    return "".join(b)


def about(lang: str) -> str:
    en = lang == "en"
    b = [f'<h1>{E("How this was made" if en else "ทำขึ้นอย่างไร")}</h1>']
    if en:
        b.append(prose(
            f"A static site built from {COV['records']} records in a public repository. Every "
            f"figure printed anywhere on it is computed at build time from those files and "
            f"from four harvests, so a number on a page and a number in the API cannot drift "
            f"apart.\n\n"
            f"**The harvests.** OpenStreetMap by Overpass, for {GYMS['count']} gyms, camps and "
            f"stadiums in {GYMS['countries']} countries. Wikidata, for {ROSTER['count']} people "
            f"recorded as Thai boxers. Thai Wikipedia at a named revision, for the thirty "
            f"technique names and the four regional lists. Wikimedia Commons, for "
            f"{COV['images']} pictures, each with its author and licence printed beside it.\n\n"
            f"**Tiers.** Every claim carries one: *cited* names a source, *harvested* came out "
            f"of an open dataset with its licence, *tradition* is general knowledge of the "
            f"practice and is hedged, *inference* is this project's own reasoning from the "
            f"above, and *field* means someone stood there. The record page for anything you "
            f"doubt has the table at the bottom.\n\n"
            f"**Both languages, or neither.** Each page is one build function called twice. "
            f"Where a record has no Thai text the Thai page says so and shows the English "
            f"rather than machine-translating in silence. {COV['th_fields']} fields are "
            f"written in Thai.\n\n"
            f"**What it does not have** is on its own page, linked from the numbers.\n\n"
            f"**Who made it.** hongdam.net, a bilingual web studio in Chiang Rai. The "
            f"enriched, graphical sites in this family are all built there."))
    else:
        b.append(prose(
            f"เว็บสถิตที่สร้างจากบันทึก {COV['records']} ชิ้นในคลังสาธารณะ "
            f"ตัวเลขทุกตัวที่พิมพ์ที่ไหนก็ตามบนเว็บนี้คำนวณตอนสร้างจากไฟล์เหล่านั้นและจากการเก็บข้อมูลสี่ชุด "
            f"ตัวเลขบนหน้าเว็บกับตัวเลขใน API จึงเคลื่อนออกจากกันไม่ได้\n\n"
            f"**การเก็บข้อมูล** OpenStreetMap ผ่าน Overpass ได้ยิม ค่าย และสนาม {GYMS['count']} แห่ง "
            f"ใน {GYMS['countries']} ประเทศ วิกิสนเทศ ได้คน {ROSTER['count']} คนที่บันทึกว่าเป็นนักมวยไทย "
            f"วิกิพีเดียภาษาไทยที่รุ่นแก้ไขซึ่งระบุไว้ ได้ชื่อท่าสามสิบท่าและรายการท้องถิ่นสี่สาย "
            f"และวิกิมีเดียคอมมอนส์ ได้ภาพ {COV['images']} ภาพ แต่ละภาพพิมพ์ชื่อผู้ถ่ายและสัญญาอนุญาตไว้ข้าง ๆ\n\n"
            f"**ชั้นของข้อความ** ทุกข้อความมีชั้นกำกับ *cited* ระบุแหล่ง *harvested* มาจากชุดข้อมูลเปิดพร้อมสัญญาอนุญาต "
            f"*tradition* คือความรู้ทั่วไปของแนวปฏิบัติและมีการกันไว้ *inference* คือการให้เหตุผลของโครงการนี้เอง "
            f"และ *field* คือมีคนไปยืนอยู่ตรงนั้น หน้าบันทึกของสิ่งที่คุณสงสัยมีตารางอยู่ด้านล่าง\n\n"
            f"**สองภาษา หรือไม่มีเลย** แต่ละหน้าคือฟังก์ชันเดียวที่ถูกเรียกสองครั้ง "
            f"ที่ใดบันทึกไม่มีข้อความภาษาไทย หน้าไทยจะบอกไว้และแสดงภาษาอังกฤษ แทนการแปลด้วยเครื่องเงียบ ๆ "
            f"มีช่องที่เขียนเป็นภาษาไทย {COV['th_fields']} ช่อง\n\n"
            f"**สิ่งที่เว็บนี้ไม่มี** อยู่ในหน้าของตัวเอง ลิงก์จากหน้าตัวเลข\n\n"
            f"**ใครทำ** hongdam.net สตูดิโอเว็บสองภาษาในเชียงราย "
            f"เว็บชุดนี้ที่เนื้อหาแน่นและมีภาพประกอบมาก สร้างที่นั่นทั้งหมด"))
    b.append(f'<p class="mute small">{E("Built" if en else "สร้างเมื่อ")} {E(COV["built"])} · '
             f'<a href="{rel()}api/">API</a> · '
             f'<a href="https://github.com/NaNoBotCo/muay-thai" rel="noopener">GitHub</a></p>')
    return "".join(b)


# ---------------------------------------------------------------- machine files
def icon_svg() -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<rect width="64" height="64" rx="10" fill="#17110c"/>'
            '<g stroke="#e0322b" stroke-width="7" stroke-linecap="round">'
            '<path d="M14 18h36"/><path d="M14 32h36"/><path d="M14 46h36"/></g>'
            '<circle cx="32" cy="32" r="6" fill="#f0a500"/></svg>')


def manifest() -> str:
    return json.dumps({"name": NAME["en"], "short_name": "Muay Thai",
                       "start_url": BASE_PATH, "display": "standalone",
                       "background_color": "#fdfbf4", "theme_color": "#17110c",
                       "icons": [{"src": f"{BASE_PATH}icon.svg", "sizes": "any",
                                  "type": "image/svg+xml"}]}, ensure_ascii=False, indent=1)


def all_paths() -> list:
    paths = [""] + [p for p, _ in NAV[1:]] + ["all/", "about/"]
    paths += [f"{DIR_OF[t]}/" for t in TYPES if by_type(t)]
    paths += [url_of(n) for n in NODES]
    return sorted(set(paths))


def robots() -> str:
    lines = ["User-agent: *", "Allow: /", "", f"Sitemap: {SITE_URL}/sitemap.xml"]
    lines.append(fleet.robots_lines(SELF, roster=FLEET))
    return "\n".join(lines) + "\n"


def sitemap() -> str:
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
           'xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for p in all_paths():
        for lang in LANGS:
            loc = f"{SITE_URL}/{'th/' if lang == 'th' else ''}{p}"
            alts = "".join(
                f'<xhtml:link rel="alternate" hreflang="{l}" '
                f'href="{SITE_URL}/{"th/" if l == "th" else ""}{p}"/>' for l in LANGS)
            out.append(f"<url><loc>{E(loc)}</loc>{alts}"
                       f"<lastmod>{COV['built'][:10]}</lastmod></url>")
    out.append("</urlset>")
    return "\n".join(out)


def feed() -> str:
    items = sorted(NODES, key=lambda n: n.get("updated", ""), reverse=True)[:40]
    ent = "".join(
        f"<entry><title>{E(n['names']['name'])}</title>"
        f"<link href=\"{SITE_URL}/{url_of(n)}\"/>"
        f"<id>{SITE_URL}/{url_of(n)}</id>"
        f"<updated>{n.get('updated', COV['built'][:10])}T00:00:00Z</updated>"
        f"<summary>{E(clip((n.get('text') or {}).get('what', ''), 300))}</summary></entry>"
        for n in items)
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            f"<title>{E(NAME['en'])}</title><link href=\"{SITE_URL}/\"/>"
            f"<id>{SITE_URL}/</id><updated>{COV['built'][:10]}T00:00:00Z</updated>"
            f"{ent}</feed>")


def llms_txt() -> str:
    lines = [f"# {NAME['en']}", "", f"> {TAG['en']}", "",
             "Made by hongdam.net, a bilingual web studio in Chiang Rai.", "",
             f"{COV['records']} records, bilingual English and Thai, every claim tiered and "
             f"sourced. Built {COV['built']}.", "",
             "## Findings",
             f"- The thirty named techniques of the muay thai curriculum: {CUR['picture']} of "
             f"{CUR['n']} are named after a picture rather than a movement, and {CUR['myth']} "
             f"name a figure from the Ramakien or its Hindu antecedents. Counted off Thai "
             f"Wikipedia at revision {RAW_CUR.get('revision', '')}; the classification is this "
             f"project's and the full table is printed at /names/.",
             f"- OpenStreetMap holds {GYMS['count']} places to train muay thai in "
             f"{GYMS['countries']} countries. {GYMS['by_how']['name only']} of them were found "
             f"only by name: the sport's own tag, sport=muay_thai, is used fewer than fifty "
             f"times worldwide. A published figure puts overseas gyms above 3,800, so the map "
             f"is a floor.",
             f"- Wikidata records {ROSTER['count']} people as Thai boxers. {ROSTER['thai']} are "
             f"Thai and {ROSTER['thai_women']} of those are women. That is a measurement of "
             f"who gets written about, not of who fights.",
             "",
             "## Pages"]
    for p, k in NAV:
        lines.append(f"- [{UI['en'][k]}]({SITE_URL}/{p})")
    lines += [f"- [Everything]({SITE_URL}/all/)", f"- [How this was made]({SITE_URL}/about/)",
              f"- [API]({SITE_URL}/api/)", "", "## Data",
              f"- [nodes.json]({SITE_URL}/api/nodes.json) — every record",
              f"- [curriculum.json]({SITE_URL}/api/curriculum.json) — the thirty names",
              f"- [gyms.json]({SITE_URL}/api/gyms.json) — the harvest, with its queries",
              f"- [roster.json]({SITE_URL}/api/roster.json) — the Wikidata census",
              f"- [nodes.jsonl]({SITE_URL}/nodes.jsonl) · [nodes.csv]({SITE_URL}/nodes.csv)",
              "", "## Licence",
              "Records CC BY 4.0. Harvested rows keep their own licences: OpenStreetMap ODbL "
              "1.0, Wikidata CC0, Wikipedia CC BY-SA 4.0, Commons per file.", ""]
    lines.append(fleet.llms_section(SELF, roster=FLEET))
    return "\n".join(lines) + "\n"


def llms_full() -> str:
    out = [llms_txt(), "", "# Records", ""]
    for n in NODES:
        out.append(f"## {n['names']['name']} ({n['type']}/{n['id']})")
        if n["names"].get("th"):
            out.append(f"Thai: {n['names']['th']}")
        for k, v in (n.get("text") or {}).items():
            out.append(f"### {k}\n{v}")
        out.append(f"Sources: {', '.join(n.get('sources', []))}")
        out.append("")
    return "\n".join(out)


def humans_txt() -> str:
    lines = ["/* TEAM */", "Built by: NaN", "Site: https://wichaa.net",
             "Studio: hongdam.net — Chiang Rai", "",
             "/* THANKS */",
             "OpenStreetMap contributors · Wikidata · Wikipedia (English and Thai) · "
             "Wikimedia Commons photographers · Natural Earth", "",
             "/* SITE */", f"Records: {COV['records']}", f"Built: {COV['built']}",
             "Standards: HTML5, CSS, no framework, no tracker, no web font", ""]
    lines.append(fleet.readme_lines(SELF, roster=FLEET))
    return "\n".join(lines) + "\n"


def ai_txt() -> str:
    return ("# Reuse\n"
            "Records on this site are CC BY 4.0: reuse them with attribution to "
            f"{SITE_URL} .\n"
            "Harvested rows keep their own licences — OpenStreetMap ODbL 1.0, Wikidata CC0, "
            "Wikipedia CC BY-SA 4.0, pictures per file. The machine-readable form is at "
            f"{SITE_URL}/api/ .\n")


def api_index() -> str:
    files = [("nodes.json", "every record, with its kin resolved both ways"),
             ("curriculum.json", "the thirty named techniques and what the names point at"),
             ("curriculum-raw.json", "the same names as harvested, with the revision id"),
             ("gyms.json", "the OpenStreetMap harvest, with the queries that made it"),
             ("roster.json", "the Wikidata census of people recorded as Thai boxers"),
             ("sources.json", "every source by id"), ("vocab.json", "types, regions, facets, tags"),
             ("coverage.json", "what this build contains")]
    files += [(f"{t}.json", f"records of type {t}") for t in TYPES if by_type(t)]
    # root-relative, because a host that serves /api with a 200 instead of redirecting to
    # /api/ resolves "nodes.json" against the site root and 404s every one of these.
    rows = "".join(f'<tr><td><a href="{rel()}api/{f}">{f}</a></td><td>{E(d)}</td></tr>'
                   for f, d in files)
    return (f"<h1>API</h1><p class=\"lede\">Plain JSON, same origin, no key. "
            f"Records CC BY 4.0; harvested rows keep their own licences.</p>"
            f'<div class="scroll"><table><tbody>{rows}</tbody></table></div>'
            f'<p><a href="{rel()}nodes.jsonl">nodes.jsonl</a> · '
            f'<a href="{rel()}nodes.csv">nodes.csv</a></p>')


COPY_JS = """document.addEventListener("click",function(e){
var b=e.target.closest("[data-copy]");if(!b)return;
navigator.clipboard.writeText(b.dataset.copy).then(function(){
var s=b.querySelector("span");if(!s)return;var t=s.textContent;s.textContent="Copied";
setTimeout(function(){s.textContent=t},1600)})});
(function(){var h=document.querySelector("header.top");if(!h)return;
var b=document.body,last=window.pageYOffset,hh=h.offsetHeight;
addEventListener("resize",function(){hh=h.offsetHeight},{passive:true});
addEventListener("scroll",function(){var y=window.pageYOffset,d=y-last;
if(y<=hh||d<-4){b.classList.remove("nav-away")}
else if(d>4){b.classList.add("nav-away")}
if(Math.abs(d)>1)last=y},{passive:true});
addEventListener("focusin",function(e){if(h.contains(e.target))
b.classList.remove("nav-away")});})();"""


# ---------------------------------------------------------------- main
def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    if SITE.exists():
        for child in SITE.iterdir():
            if child.name in ("world.svg", "thailand.svg"):
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    SITE.mkdir(parents=True, exist_ok=True)

    pages = 0
    for lang in LANGS:
        base = SITE / ("th" if lang == "th" else "")
        ui = UI[lang]
        ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": NAME[lang],
               "url": f"{CANONICAL_URL}/", "inLanguage": lang, "author": AUTHOR,
               "license": DATA_LICENSE},
              fleet.publisher_ld(roster=FLEET),
              {"@context": "https://schema.org", "@type": "WebPage",
               "creator": MAKER, "inLanguage": lang}]
        specials = [
            ("", front, ui["home"], f"{NAME[lang]} — {TAG[lang]}", "home", "index"),
            ("limbs/", limbs_page, ui["limbs"], None, "limbs", "limbs"),
            ("names/", names_page, ui["names"], None, "names", "names"),
            ("schools/", schools_page, ui["schools"], None, "schools", "schools"),
            ("ceremony/", ceremony_page, ui["ceremony"], None, "ceremony", "ceremony"),
            ("watch/", watch_page, ui["watch"], None, "watch", "watch"),
            ("training/", training_page, ui["train"], None, "train", "training"),
            ("history/", history_page, ui["history"], None, "history", "history"),
            ("gyms/", gyms_page, ui["gyms"], None, "gyms", "gyms"),
            ("people/", people_page, ui["people"], None, "people", "people"),
            ("numbers/", numbers_page, ui["numbers"], None, "numbers", "numbers"),
            ("words/", words_page, ui["words"], None, "words", "words"),
            ("all/", all_page, ui["all"], None, "", "index"),
            ("about/", about, ui["about"], None, "", "index"),
        ]
        for path, fn, label, title, cur, card in specials:
            body = fn(lang)
            t = title or f"{label} — {NAME[lang]}"
            desc = TAG[lang] if path == "" else f"{label} — {NAME[lang]}"
            write(base / path / "index.html",
                  page(t, body, 0 if path == "" else 1, lang, desc=desc, jsonld=ld,
                       cur=cur, path=path, card=card))
            pages += 1
        special_paths = {x[0] for x in specials}
        for t in TYPES:
            # A type whose directory is one of the assembled sections above is reached
            # through that section, which already lists it. Writing the plain index here
            # would overwrite the section with a bare grid.
            if not by_type(t) or f"{DIR_OF[t]}/" in special_paths:
                continue
            ti = TYPE_INFO[t]
            label = ti["th"] if lang == "th" else ti["name"]
            write(base / DIR_OF[t] / "index.html",
                  page(f"{label} — {NAME[lang]}", type_index(t, lang), 1, lang,
                       desc=ti["th_blurb"] if lang == "th" else ti["blurb"],
                       jsonld=ld, path=f"{DIR_OF[t]}/", card=DIR_OF[t]
                       if (SITE / "cards" / f"{DIR_OF[t]}.jpg").exists() else "index"))
            pages += 1
        for n in NODES:
            name = T(n, "names.name", lang)
            desc = clip(T(n, "text.what", lang) or "", 180)
            nld = [{"@context": "https://schema.org", "@type": "Article",
                    "headline": name, "inLanguage": lang,
                    "url": f"{CANONICAL_URL}/{'th/' if lang == 'th' else ''}{url_of(n)}",
                    "author": AUTHOR, "creator": MAKER, "license": DATA_LICENSE,
                    "dateModified": n.get("updated", "")}]
            write(base / url_of(n) / "index.html",
                  page(f"{name} — {NAME[lang]}", node_page(n, lang), 2, lang, desc=desc,
                       jsonld=nld, cur="", path=url_of(n),
                       card=f'{n["type"]}-{n["id"]}'))
            pages += 1

    # machine files, once
    write(SITE / "api" / "index.html",
          page("API — Muay Thai", api_index(), 1, "en", desc="Plain JSON, same origin, no key.",
               path="api/"))
    pages += 1
    shutil.copytree(API, SITE / "api", dirs_exist_ok=True)
    if (ROOT / "data" / "images").exists():
        shutil.copytree(ROOT / "data" / "images", SITE / "images", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("_triage", "*.json"))
    write(SITE / "robots.txt", robots())
    write(SITE / "sitemap.xml", sitemap())
    write(SITE / "feed.xml", feed())
    write(SITE / "icon.svg", icon_svg())
    write(SITE / "manifest.webmanifest", manifest())
    write(SITE / "copy.js", COPY_JS)
    write(SITE / "llms.txt", llms_txt())
    write(SITE / "llms-full.txt", llms_full())
    write(SITE / "humans.txt", humans_txt())
    write(SITE / "ai.txt", ai_txt())
    write(SITE / "nodes.jsonl",
          "\n".join(json.dumps(n, ensure_ascii=False) for n in NODES) + "\n")
    cols = ["id", "type", "name", "th", "region", "confidence", "updated", "sources"]
    rows = [",".join(cols)]
    for n in NODES:
        vals = [n["id"], n["type"], n["names"]["name"], n["names"].get("th", ""),
                " ".join(n.get("region", [])), n.get("confidence", ""), n.get("updated", ""),
                " ".join(n.get("sources", []))]
        rows.append(",".join('"' + str(v).replace('"', '""') + '"' for v in vals))
    write(SITE / "nodes.csv", "\n".join(rows) + "\n")
    fleet.decorate(SITE, SELF, roster=FLEET)
    write(SITE / ".basepath", BASE_PATH)   # what links.py resolves against

    print(f"site: {pages} pages ({pages // 2} per language) into {SITE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
