#!/usr/bin/env python3
"""validate.py — every record must pass before anything is built.

Checks, in order:
  1. schema/node.schema.json (structure, enums, patterns)
  2. id == filename; type == folder; ids unique across all types
  3. kin targets and confusable_with targets exist
  4. every source id exists in data/sources/sources.json (record, etymology, provenance)
  5. region keys — WARN only (open list); facet values — WARN only (open list)
  6. every image licence is on the free-to-use allowlist and its file exists
  7. provenance.fields paths point at real fields
  8. banned words in reader-facing text (fleet rule) — ERROR

Exit 1 on any error. Warnings never fail the build; they are printed.

    python3 tools/validate.py            # all records
    python3 tools/validate.py --strict   # warnings fail too
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import IMAGES, SCHEMA, jload, load_nodes, load_sources, load_vocab, validate_record  # noqa: E402

# Free-to-use licences. "No known copyright restrictions" is the Flickr Commons and
# Library of Congress rights statement: the holding institution has found no copyright
# and asks only that the item be credited. It is the same status under which the LoC
# material already reaches this project through Wikimedia Commons, so an item that
# carries it ON ITS OWN PAGE (per item, never per collection) is accepted here too.
FREE_LICENSES = re.compile(
    r"^(CC0(\s*1\.0)?|Public domain|PD(-[A-Za-z0-9-]+)?|CC[- ]BY(-SA)?(\s*[1-4]\.[0-9])?|FAL(\s*1\.[0-9])?"
    r"|No known copyright restrictions|NoC-US|United States Government Work)$", re.I)
# Words that never appear in reader-facing copy on any of Nan's sites, and the
# adjudicating words this subject attracts. Donuts run on argument: cake against raised,
# hand-cut against frozen shell, the chain against the counter down the block, and whether
# the egg rolls belong. Report the argument; never join it. "Not a real donut" is a thing
# people say, and it goes in quotation marks attributed to whoever said it, or it stays out.
DRAFT = bool(os.environ.get("BUILD_DRAFT"))
# Words that never appear in reader-facing copy on any of Nan's sites, plus the ones this
# subject attracts. A road trip through other people's homes runs on adjudication —
# whose village is "real", which rider is "proper", what is "unspoiled". REPORT the
# argument, name who is making it, JOIN none of them. A quotation in quotation marks is
# exempt, so quote and attribute rather than assert.   <!-- stylecheck: allow -->
#
# On `hill tribe`: it is the Thai state's own English term, so it appears here inside
# quotation marks and attributed. Outside a quotation, name the people.
# `ladyboy` is in the list for the same reason and with the same exception: the English
# Wikipedia article on Parinya Charoenphol uses it as a gloss on kathoey, quoted.
BANNED = re.compile(
    r"\b(authentic(ity|ally)?|inauthentic|unspoil\w+|untouched|exotic|primitive|backward"
    r"|tourist(s|y)?|touristy|hidden gems?|off the beaten (track|path)|must[- ]see|must[- ]do"
    r"|bucket[- ]list|real fighters?|true warriors?|the real thing|honest(ly|y)?"
    r"|purist|warrior spirit|ancient secrets?|hill ?tribes?|ladyboys?|sacrile\w+"
    r"|breathtaking|stunning|deadly art|lethal art|killing art"
    r"|hidden treasures?|best[- ]kept secret)\b", re.I)


def _get(rec: dict, dotted: str):
    """Dotted path with optional list indices: text.story, kin[3].as, images[0].license."""
    node = rec
    for part in dotted.split("."):
        m = re.match(r"^([A-Za-z_]+)(?:\[(\d+)\])?$", part)
        if not m:
            return None
        key, idx = m.group(1), m.group(2)
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return None
        if idx is not None:
            if isinstance(node, list) and int(idx) < len(node):
                node = node[int(idx)]
            else:
                return None
    return node


def text_fields(rec: dict):
    for k, v in (rec.get("text") or {}).items():
        yield f"text.{k}", v
    for i, k in enumerate(rec.get("kin") or []):
        yield f"kin[{i}].as", k.get("as", "")
    for i, c in enumerate(rec.get("confusable_with") or []):
        yield f"confusable_with[{i}].tell", c.get("tell", "")
    e = rec.get("etymology") or {}
    for k in ("root", "note"):
        if e.get(k):
            yield f"etymology.{k}", e[k]
    for i, sec in enumerate(rec.get("sections") or []):
        yield f"sections[{i}].h", sec.get("h", "")
        yield f"sections[{i}].text", sec.get("text", "")
    for k in ("what", "does", "gloss", "note"):
        v = (rec.get("move") or {}).get(k)
        if v:
            yield f"move.{k}", v
    for k in ("why", "result", "disputed"):
        v = (rec.get("bout") or {}).get(k)
        if v:
            yield f"bout.{k}", v
    for k in ("nights_note", "ticket_note"):
        v = (rec.get("venue") or {}).get(k)
        if v:
            yield f"venue.{k}", v


def validate_all(strict=False, quiet=False) -> int:
    schema = jload(SCHEMA)
    recs = load_nodes()
    sources = load_sources()
    regions = {e["key"] for e in load_vocab("regions").get("entries", [])}
    facets = load_vocab("facets").get("facets", {})
    tagkeys = set(load_vocab("tags").get("tags", {}))
    recog = {e["key"] for e in load_vocab("recognizers").get("entries", [])}
    ids: dict[str, str] = {}
    errors: list[str] = []
    warns: list[str] = []
    for r in recs:
        tag = f"{r.get('type','?')}/{r.get('id','?')}"
        if r.get("id") in ids:
            errors.append(f"{tag}: duplicate id (also {ids[r['id']]})")
        ids[r.get("id", "")] = tag
    for r in recs:
        tag = f"{r['type']}/{r['id']}" if "type" in r and "id" in r else r["_path"]
        for e in validate_record(r, schema):
            errors.append(f"{tag}: {e}")
        if Path(r["_path"]).stem != r.get("id"):
            errors.append(f"{tag}: filename {Path(r['_path']).name} != id")
        if r.get("type") != r["_dir_type"]:
            errors.append(f"{tag}: type {r.get('type')!r} but the file sits in data/nodes/{r['_dir_type']}/")
        for k in r.get("kin", []):
            if k["to"] not in ids:
                # BUILD_DRAFT=1: an unwritten kin target is a warning, so the site can be
                # built while records are still being written. Never set it for a publish.
                (warns if DRAFT else errors).append(f"{tag}: kin target {k['to']} not found")
            if k["to"] == r.get("id"):
                errors.append(f"{tag}: kin points at itself")
        for c in r.get("confusable_with", []):
            if c["id"] not in ids:
                (warns if DRAFT else errors).append(f"{tag}: confusable_with {c['id']} not found")
        for s in r.get("sources", []):
            if s not in sources:
                errors.append(f"{tag}: source {s} not in sources.json")
        prov = r.get("provenance", {})
        for where, p in [("default", prov.get("default", {}))] + list(prov.get("fields", {}).items()):
            if p.get("source") and p["source"] not in sources:
                errors.append(f"{tag}: provenance {where} cites {p['source']} which is not in sources.json")
            if p.get("tier") == "cited" and not p.get("source") and not r.get("sources"):
                warns.append(f"{tag}: provenance {where} is 'cited' but names no source")
        et = r.get("etymology") or {}
        if et.get("source") and et["source"] not in sources:
            errors.append(f"{tag}: etymology cites {et['source']} which is not in sources.json")
        if r.get("type") == "term" and not et.get("root"):
            warns.append(f"{tag}: a word with no etymology.root")
        for reg in r.get("region", []):
            if reg not in regions:
                warns.append(f"{tag}: region {reg} not in regions.json (open list — add it there)")
        for fk, fv in (r.get("facets") or {}).items():
            spec = facets.get(fk)
            if not spec:
                warns.append(f"{tag}: facet {fk} not in facets.json (open list — add it there)")
                continue
            if r["type"] not in spec["types"]:
                warns.append(f"{tag}: facet {fk} is not listed for type {r['type']}")
            vals = fv if isinstance(fv, list) else [fv]
            for v in vals:
                if spec["values"] and v not in spec["values"]:
                    warns.append(f"{tag}: facet {fk}={v!r} not among known values")
        hrs = {}
        if hrs:
            if hrs.get("source") and hrs["source"] not in sources:
                errors.append(f"{tag}: hours.source {hrs['source']} not in sources.json")
            both = set(hrs.get("open", [])) & set(hrs.get("closed", []))
            if both:
                errors.append(f"{tag}: hours lists {sorted(both)} as both open and closed")
            if not hrs.get("open") and not hrs.get("closed"):
                warns.append(f"{tag}: hours names no day either way")
        for i, tg in enumerate(r.get("tags", [])):
            if tg not in tagkeys:
                warns.append(f"{tag}: tags[{i}] {tg!r} not in tags.json (open list)")
        for i, im in enumerate(r.get("images", [])):
            if not FREE_LICENSES.match(im["license"].strip()):
                errors.append(f"{tag}: images[{i}] licence {im['license']!r} is not on the free-to-use allowlist")
            if not (IMAGES / im["file"]).exists():
                warns.append(f"{tag}: images[{i}] file missing: {im['file']}")
        for path in prov.get("fields", {}):
            if _get(r, path) is None:
                warns.append(f"{tag}: provenance.fields.{path} names a field the record does not have")
        for fname, txt in text_fields(r):
            # the proper noun is exempt: an organization is named what it is named
            clean = txt or ""
            # a proper noun is exempt: a business or a book is named what it is named,
            # and a quotation keeps its speaker's words — put those in quotation marks.
            clean = re.sub(r'[\u201c"][^\u201d"]{0,240}[\u201d"]', "X", clean)
            for noun in ():
                clean = clean.replace(noun, "X")
            m = BANNED.search(clean)
            if m:
                errors.append(f"{tag}: {fname} uses the banned word {m.group(0)!r}")
        if r.get("type") in ("place", "event") and not r.get("geo"):
            warns.append(f"{tag}: no geo (map will not show it)")
        if not r.get("sources") and prov.get("default", {}).get("tier") in ("cited", "harvested"):
            warns.append(f"{tag}: tier {prov['default']['tier']} but sources is empty")
    errors += check_images(recs)
    if not quiet:
        for w in warns:
            print("warn ", w)
        for e in errors:
            print("ERROR", e)
        print(f"{len(recs)} records · {len(errors)} errors · {len(warns)} warnings")
    if errors or (strict and warns):
        return 1
    return 0


# ---------------------------------------------------------------- image sanity
# A Commons search for a fighter's ring name returns whatever carries those letters. The
# check is crude on purpose: flag a caption that is about a subject this site is not
# about, unless the caption also names something this site is about.
OFF_SUBJECT = re.compile(
    r"\b(a3\d\d|a380|boeing|airbus|aircraft|airline|airplane|paintshop|fuselage|"
    r"locomotive|railway|rolling stock|football|basketball|volleyball|cricket|"
    r"motherboard|postage stamp|banknote|coat of arms|logo)\b", re.I)
ON_SUBJECT = re.compile(
    r"\b(muay|muaythai|thai|thailand|boxing|boxer|kickbox\w*|lethwei|khmer|"
    r"bangkok|lumpinee|lumpini|rajadamnern|ratchadamnoen|chaiya|korat|lopburi|"
    r"uttaradit|chiang\s?mai|samut|ayutthaya|isan|"
    r"ring|clinch|kick|elbow|knee|teep|mongkhon|prajiat|wai\s?khru|ram\s?muay|"
    r"ramakien|ramayana|hanuman|erawan|yant\w*|wat|krabi)\b", re.I)


# Blood and open wounds do not go up without being asked about first (client, 2026-09-19).
# A record that carries an approved one sets x_blood_ok true, and the approval is a
# conversation, not a flag somebody set to get past this.
BLOODY = re.compile(r"\b(blood|bloody|bleeding|wound|wounded|infect\w+|pus|scab|gore|"
                    r"gory|laceration|stitches|surgery|injur\w+)\b", re.I)


def check_images(nodes: list) -> list:
    """Flag a picture whose caption is about something the record is not about."""
    bad = []
    for n in nodes:
        for im in (n.get("images") or []):
            alt = im.get("alt") or ""
            hay = " ".join([alt, im.get("title") or "", im.get("credit") or "",
                            im.get("file") or ""])
            if BLOODY.search(hay) and not n.get("x_blood_ok"):
                bad.append(f"{n['type']}/{n['id']}: images[{i}] reads as blood or an open "
                           f"wound — ask before publishing it ({im.get('file')})")
            if OFF_SUBJECT.search(alt + " " + (im.get("file") or "")) and not ON_SUBJECT.search(alt):
                bad.append(f"{n['type']}/{n['id']}: picture is off-subject — {alt[:70]!r} "
                           f"({im.get('file','')[:60]})")
    return bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    sys.exit(validate_all(ap.parse_args().strict))
