#!/usr/bin/env python3
"""cards.py — a share card per page, 1200×630.

A link with no picture shares as a grey box with a line of text under it, and
`twitter:card: summary_large_image` with no image attached is worse than declaring
nothing. This draws one card for every page that has something to show: the page's own
photograph, a scrim heavy enough to read type over, the headline, and one number where
there is a number worth leading with.

Cards are only redrawn when missing, so a rebuild is cheap. Pass --force to redo them.

    python3 tools/cards.py
    python3 tools/cards.py --force --only numbers
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, IMAGES, jload  # noqa: E402

W, H = 1200, 630
FONTS = Path("/System/Library/Fonts/Supplemental")
DISPLAY = FONTS / "Arial Black.ttf"
BODY = FONTS / "Arial Bold.ttf"
THAI = FONTS / "Ayuthaya.ttf"
HOT = (255, 59, 47)
CREAM = (250, 245, 236)


def _font(path: Path, size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _is_thai(s: str) -> bool:
    return any("฀" <= c <= "๿" for c in s or "")


def _fit(draw, text, font_path, size, max_w, max_lines=3):
    """Shrink until the headline fits in `max_lines`, then wrap it."""
    from PIL import ImageFont
    while size > 26:
        f = _font(font_path, size)
        avg = max(1, draw.textlength("MMMMMMMMMM", font=f) / 10)
        per = max(8, int(max_w / avg))
        lines = textwrap.wrap(text, per) or [text]
        if len(lines) <= max_lines and all(draw.textlength(l, font=f) <= max_w for l in lines):
            return f, lines
        size -= 4
    f = _font(font_path, size)
    return f, textwrap.wrap(text, 24)[:max_lines] or [text]


def draw_card(out: Path, headline: str, kicker: str = "", big: str = "", big_label: str = "",
              photo: Path | None = None, credit: str = ""):
    from PIL import Image, ImageDraw, ImageFilter
    base = Image.new("RGB", (W, H), (18, 16, 13))
    if photo and photo.exists():
        try:
            im = Image.open(photo).convert("RGB")
            # cover
            r = max(W / im.width, H / im.height)
            im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
            base.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
        except Exception:  # noqa: BLE001
            pass
    # scrim: dark at the left and the bottom, where the type goes
    scrim = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(scrim)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(245 - 120 * min(1.0, x / (W * 0.9))))
    bottom = Image.new("L", (W, H), 0)
    bd = ImageDraw.Draw(bottom)
    for y in range(H):
        bd.line([(0, y), (W, y)], fill=int(60 + 190 * max(0.0, (y - H * 0.35) / (H * 0.65))))
    scrim = Image.blend(scrim, bottom, 0.5).filter(ImageFilter.GaussianBlur(2))
    base = Image.composite(Image.new("RGB", (W, H), (10, 8, 5)), base, scrim)

    d = ImageDraw.Draw(base)
    pad = 62
    y = pad
    if kicker:
        kf = _font(THAI if _is_thai(kicker) else BODY, 26)
        d.text((pad, y), kicker.upper() if not _is_thai(kicker) else kicker, font=kf, fill=HOT)
        y += 46
    if big:
        bf = _font(DISPLAY, 148)
        # measure rather than assume: Arial Black's box is taller than its size and the
        # label was landing inside the digits' descender
        bbox = d.textbbox((pad, y), big, font=bf)
        d.text((pad, y), big, font=bf, fill=(255, 255, 255))
        y = bbox[3] + 10
        if big_label:
            lf = _font(THAI if _is_thai(big_label) else BODY, 27)
            d.text((pad, y), big_label, font=lf, fill=HOT)
            y += 46
    y += 12
    hf, lines = _fit(d, headline, THAI if _is_thai(headline) else DISPLAY,
                     74 if not big else 50, W - pad * 2, 3 if not big else 2)
    for line in lines:
        d.text((pad, y), line, font=hf, fill=(255, 255, 255))
        y += int(hf.size * 1.12)
    # the mark
    mf = _font(DISPLAY, 28)
    label = "MUAY "
    d.text((pad, H - pad - 26), label, font=mf, fill=CREAM)
    d.text((pad + d.textlength(label, font=mf), H - pad - 26), "THAI", font=mf, fill=HOT)
    if credit:
        cf = _font(BODY, 17)
        t = credit[:74]
        d.text((W - pad - d.textlength(t, font=cf), H - pad - 20), t, font=cf, fill=(190, 178, 162))
    d.rectangle([0, 0, W - 1, H - 1], outline=(255, 255, 255), width=6)
    out.parent.mkdir(parents=True, exist_ok=True)
    # JPEG, not PNG: these are photographs with type over them, and as PNG the same 78
    # cards came to 79 MB against about 9 as JPEG. Every platform that reads og:image
    # takes JPEG.
    base.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    return out


def photo_for(node: dict):
    for im in (node.get("images") or []):
        if im.get("primary"):
            return IMAGES / im["file"], f'{im.get("author", "")} · {im.get("license", "")}'
    for im in (node.get("images") or []):
        return IMAGES / im["file"], f'{im.get("author", "")} · {im.get("license", "")}'
    return None, ""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args()
    site = BUILD / "site"
    nodes = jload(BUILD / "api" / "nodes.json")["nodes"]
    by_id = {n["id"]: n for n in nodes}
    cur = jload(BUILD / "api" / "curriculum.json")
    gy = jload(BUILD / "api" / "gyms.json")
    ro = jload(BUILD / "api" / "roster.json")

    # A share card is a brag, not a footnote. Lead with the number people came for.
    PAGES = [
        ("index", "Two fists, two elbows, two knees, two shins", "Muay Thai",
         "8", "limbs, and the count is the argument", "eight-limbs"),
        ("names", "Every one of them is named after a picture", "The thirty names",
         str(cur["myth"]), "of thirty come out of the Ramakien", "wat-bang-kung-statues"),
        ("gyms", "Where the sport landed, counted off the map", "Gyms",
         f'{gy["count"]:,}', f'places to train in {gy["countries"]} countries', "the-gym-map"),
        ("people", "Who the record remembers, and who it does not", "People",
         f'{ro["count"]:,}', "on record · 248 Thai · five Thai women", "the-roster"),
        ("limbs", "The elbow and the knee are legal, and that changes every distance",
         "The eight limbs", "", "", "clinch"),
        ("schools", "Heavy fists Korat, clever Lopburi, good form Chaiya", "The schools",
         "4", "lines, named at a royal funeral in 1910", "four-lines"),
        ("ceremony", "One practice, four surfaces", "Ceremony", "", "", "sak-yant"),
        ("watch", "You scored round one. Nobody else did.", "Watching a fight",
         "", "", "scoring"),
        ("training", "The shin hurts before the lungs do", "Training", "", "", "first-session"),
        ("history", "The oldest written muay is a Lanna law about quarrels", "History",
         "1296", "Mangrai law, on palm leaf", "mangrai-law"),
        ("numbers", "Counted, not repeated", "Numbers", "", "", "the-gym-map"),
        ("words", "What the corner is shouting", "Words", "", "", "clinch"),
    ]
    n = 0
    for slug, head, kicker, big, big_label, photo_id in PAGES:
        if a.only and a.only != slug:
            continue
        out = site / "cards" / f"{slug}.jpg"
        if out.exists() and not a.force:
            continue
        node = by_id.get(photo_id)
        p, credit = photo_for(node) if node else (None, "")
        draw_card(out, head, kicker, big, big_label, p, credit)
        n += 1
        print(f"  cards/{slug}.jpg")
    # one per record that has a photograph
    for node in nodes:
        out = site / "cards" / f"{node['type']}-{node['id']}.jpg"
        if out.exists() and not a.force:
            continue
        if a.only and a.only != node["id"]:
            continue
        p, credit = photo_for(node)
        if not p:
            continue
        mv = node.get("move") or {}
        big = str(mv["n"]) if mv.get("n") else ""
        label = ("of the fifteen" if mv.get("set") == "mae-mai"
                 else "of the second fifteen" if mv.get("set") == "luk-mai" else "")
        draw_card(out, node["names"]["name"], node["names"].get("th") or node["type"],
                  big, label, p, credit)
        n += 1
    print(f"cards: {n} drawn")
