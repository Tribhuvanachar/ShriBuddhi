#!/usr/bin/env python3
"""Bring the sūtrapāṭha into line with ashtadhyayi.com, and keep it there.

WHY THIS EXISTS. Our sutrapatha/data.json records its own provenance as "sutra
text extracted from commentary dictionary keys" -- we never held a sutrapatha,
we held the sutra-shaped keys of a commentary index. Every defect follows from
that: 1.1.17 merges उञः and ऊँ into one record, so the numbering runs one behind
for the rest of the pada; 48 records carry the printed edition's line-break
hyphens; 45 carry zero-width joiners; 21 sutras are missing, nearly all of them
the last of a pada, including 8.4.68 -- the final sutra of the Ashtadhyayi.

tools/realign_sutra_enrichment.py already found this and patched around it,
moving each gloss back onto the sutra it belongs to BY TEXT. That fixed what the
reader sees. It could not fix the numbering, so anything resolving a citation by
ID -- the reference linker, intellisense, backlinks -- still lands on the wrong
sutra past each pada's first merge.

Taking the upstream file whole fixes both at once, because the enrichment we
carry came from there in the first place. It also retires the realignment, since
upstream's own cross-references are consistent with its own numbering.

ATTRIBUTION. ashtadhyayi.com's README: "You are free to use this data in your own
projects provided that appropriate credits are mentioned wherever applicable."
This tool writes that credit into the file it produces, and the site carries it
in the footer. Not a courtesy -- the condition of use. The project has been here
before: the English gloss layer from this same source was removed from published
data in Aug 2026 for being shown without attribution.

NOT AN AUTOMATIC MERGE. Upstream is a living file that scholars correct through
the website's own edit button. --check reports what changed and writes nothing;
--apply is a deliberate act. Run --check periodically and read it.

  python3 tools/sync_ashtadhyayi.py --check
  python3 tools/sync_ashtadhyayi.py --apply
  python3 tools/sync_ashtadhyayi.py --check --source local/copy.txt
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(REPO, "data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json")
UPSTREAM = "https://raw.githubusercontent.com/ashtadhyayi-com/data/master/sutraani/data.txt"

CREDIT = ("Sūtra text, padaccheda, anvaya, anuvṛtti, adhikāra and sūtra type from "
          "ashtadhyayi.com (github.com/ashtadhyayi-com/data, sutraani/data.txt), "
          "used with credit per that project's terms. Its sūtrapāṭha is corrected "
          "continuously by scholars through the site's own edit button, which is "
          "why it is the reference rather than a one-time import.")

#: AD is adhikāra, a governing rule -- not atideśa. Our table had both codes
#: pointing at atideśa, so every adhikāra sūtra was mislabelled to the reader.
TYPE_LABELS = {
    "S":  ("Definition (saṃjñā)", "संज्ञा"),
    "P":  ("Meta-rule (paribhāṣā)", "परिभाषा"),
    "V":  ("Operational rule (vidhi)", "विधि"),
    "AT": ("Extension (atideśa)", "अतिदेश"),
    "AD": ("Governing rule (adhikāra)", "अधिकार"),
}


def sid(code: str) -> str:
    """11003 -> 1.1.3. Upstream packs adhyaya, pada and a 3-digit number."""
    code = str(code).strip()
    return "%s.%s.%d" % (code[0], code[1], int(code[2:]))


def fetch(source: str | None) -> list:
    if source:
        raw = open(source, encoding="utf-8").read()
    else:
        with urllib.request.urlopen(UPSTREAM, timeout=120) as r:
            raw = r.read().decode("utf-8")
    return json.loads(raw)["data"]


def build_item(x: dict) -> dict:
    a, p, n = x["a"], x["p"], x["n"]
    ref = "%s.%s.%s" % (a, p, n)
    item = {
        "id": ref,
        "reference": ref,
        "sanskrit_text": unicodedata.normalize("NFC", x["s"].strip()),
        "tags": ["ashtadhyayi", "sutra", "adhyaya_%s" % a],
    }
    pc = [w.split("$")[0].strip() for w in (x.get("pc") or "").split("##") if w.strip()]
    if pc:
        item["padaccheda"] = pc
    ss = (x.get("ss") or "").strip()
    if ss:
        item["anvaya"] = ss
    an = []
    for part in (x.get("an") or "").split("##"):
        part = part.strip()
        if not part or "$" not in part:
            continue
        word, _, src = part.partition("$")
        src = src.strip("$")
        if word.strip() and src.isdigit():
            an.append({"word": word.strip(), "from": sid(src)})
    if an:
        item["anuvritti"] = an
    ad = (x.get("ad") or "").strip()
    if ad:
        bits = ad.split("$")
        if len(bits) >= 4 and all(b.strip().isdigit() for b in bits[1:4]):
            item["adhikara"] = bits[0].strip()
            item["adhikara_refs"] = [[bits[0].strip(),
                                      "%s.%s.%s" % (bits[1], bits[2], bits[3])]]
        else:
            item["adhikara"] = ad
    code = (x.get("type") or "").split("$")[0].strip()
    if code in TYPE_LABELS:
        label, dev = TYPE_LABELS[code]
        item["sutra_type"] = {"code": code, "label": label, "label_dev": dev}
    return item


def diff(old_items: list, new_items: list) -> dict:
    o = {x.get("id"): x for x in old_items}
    n = {x.get("id"): x for x in new_items}
    nfc = lambda s: unicodedata.normalize("NFC", (s or "").strip())
    changed = [k for k in sorted(set(o) & set(n))
               if nfc(o[k].get("sanskrit_text")) != nfc(n[k].get("sanskrit_text"))]
    return {"added": sorted(set(n) - set(o)), "removed": sorted(set(o) - set(n)),
            "text_changed": changed, "total_old": len(o), "total_new": len(n)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the result (default: report only)")
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if anything differs")
    ap.add_argument("--source", default="", help="a local copy of data.txt instead of the network")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args(argv)

    try:
        up = fetch(a.source or None)
    except Exception as e:                                   # noqa: BLE001
        print(f"could not read upstream: {e}", file=sys.stderr)
        return 2

    doc = json.load(open(TARGET, encoding="utf-8"))
    new_items = [build_item(x) for x in up]
    new_items.sort(key=lambda i: [int(p) for p in i["id"].split(".")])
    d = diff(doc.get("items") or [], new_items)

    print(f"upstream {d['total_new']} sutras, ours {d['total_old']}")
    print(f"  added        : {len(d['added'])}")
    print(f"  removed      : {len(d['removed'])}")
    print(f"  text changed : {len(d['text_changed'])}")
    for k in d["text_changed"][:a.limit]:
        old = next(x for x in doc["items"] if x.get("id") == k)
        new = next(x for x in new_items if x["id"] == k)
        print(f"    {k}\n      ours: {old.get('sanskrit_text')}\n      new : {new['sanskrit_text']}")
    if len(d["text_changed"]) > a.limit:
        print(f"    … and {len(d['text_changed']) - a.limit} more")
    if d["added"]:
        print("  added ids    : " + ", ".join(d["added"][:40]))

    if not a.apply:
        nothing = not (d["added"] or d["removed"] or d["text_changed"])
        print("\nnothing written" + ("" if nothing else " -- pass --apply"))
        return 1 if (a.check and not nothing) else 0

    doc["items"] = new_items
    doc["count"] = len(new_items)
    doc["source"] = CREDIT
    doc.pop("enrichment", None)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import format_data_json
    text = format_data_json.canonical(doc) or json.dumps(doc, ensure_ascii=False,
                                                         separators=(",", ":"))
    with open(TARGET, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"\nwrote {os.path.relpath(TARGET, REPO)} -- {len(new_items)} sutras")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
