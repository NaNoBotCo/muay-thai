#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ingest_own.py — pictures of ours, into the records.

Reads whatever is sitting in the drop folder, converts HEIC to JPEG, resizes, and attaches
each one to a record with its credit and licence. Files are taken in filename order and
assigned to records in the order given by --to; a file whose name starts with a record id
goes to that record regardless.

    python3 tools/ingest_own.py --list
    python3 tools/ingest_own.py --to sak-yant kho-ham gao-yod --apply

Default drop folder: ~/Desktop/FIELD DROP/sak yant
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import IMAGES, NODES, TYPES, jdump, jload  # noqa: E402

DROP = Path.home() / "Desktop" / "FIELD DROP" / "sak yant"
CREDIT = "Taken at Sak Yant Chiang Mai, used with permission"
AUTHOR = "NaN"
LICENSE = "CC BY 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
EXT = {".heic", ".HEIC", ".jpg", ".JPG", ".jpeg", ".JPEG", ".png", ".PNG"}


def find_record(rid: str):
    for t in TYPES:
        p = NODES / t / f"{rid}.json"
        if p.exists():
            return p
    return None


def upright(path: Path):
    """Apply the EXIF orientation and drop the tag. A phone writes the picture sideways
    and a rotation flag beside it; sips carries the flag through and the browser then
    shows the sideways version, so the rotation is baked in here instead."""
    try:
        from PIL import Image, ImageOps
        with Image.open(path) as im:
            fixed = ImageOps.exif_transpose(im)
            if fixed is not im or im.getexif().get(274, 1) != 1:
                fixed.convert("RGB").save(path, "JPEG", quality=84, optimize=True)
    except Exception as e:  # noqa: BLE001
        print(f"  ! orientation {path.name}: {e}")


def to_jpeg(src: Path, dst: Path, px: int = 1400) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82",
                        "-Z", str(px), str(src), "--out", str(dst)],
                       capture_output=True)
    if r.returncode == 0 and dst.exists():
        upright(dst)
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", default=str(DROP))
    ap.add_argument("--to", nargs="*", default=["sak-yant"])
    ap.add_argument("--alt", default="")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    drop = Path(a.drop)
    files = sorted([p for p in drop.glob("*") if p.suffix in EXT])
    if a.list or not files:
        print(f"{len(files)} file(s) in {drop}")
        for p in files:
            print("  ", p.name)
        if not files:
            print("  (drop the pictures in there, then run again with --apply)")
        return 0

    assigned: dict[str, list[Path]] = {rid: [] for rid in a.to}
    spare = []
    for p in files:
        stem = p.stem.lower()
        hit = next((rid for rid in a.to if stem.startswith(rid)), None)
        (assigned[hit] if hit else spare).append(p)
    # anything unlabelled goes round the list in turn
    for i, p in enumerate(spare):
        assigned[a.to[i % len(a.to)]].append(p)

    for rid, ps in assigned.items():
        if not ps:
            continue
        rec_path = find_record(rid)
        if not rec_path:
            print(f"  ! no record {rid}")
            continue
        rec = jload(rec_path)
        ims = [im for im in (rec.get("images") or [])]
        have = {im["file"] for im in ims}
        for n, p in enumerate(ps):
            out_rel = f"{rid}/{rid}-own-{n + 1:02d}.jpg"
            out = IMAGES / out_rel
            if out_rel in have:
                continue
            if not a.apply:
                print(f"  would add {p.name} -> {out_rel}")
                continue
            if p.suffix.lower() in (".jpg", ".jpeg") and p.stat().st_size < 900_000:
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, out)
                upright(out)
            elif not to_jpeg(p, out):
                print(f"  ! could not convert {p.name}")
                continue
            sha = hashlib.sha256(out.read_bytes()).hexdigest()
            ims.append({"file": out_rel, "source": "own", "license": LICENSE,
                        "license_url": LICENSE_URL, "author": AUTHOR, "credit": CREDIT,
                        "alt": a.alt or f"Sak yant being done at Sak Yant Chiang Mai.",
                        "primary": not ims, "sha256": sha})
            print(f"  + {p.name} -> {out_rel}")
        if a.apply:
            rec["images"] = ims
            jdump(rec, rec_path)
    if not a.apply:
        print("\ndry run — add --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
