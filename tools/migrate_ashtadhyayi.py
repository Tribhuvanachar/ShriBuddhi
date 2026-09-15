#!/usr/bin/env python3
"""Replace the Aṣṭādhyāyī corpus with the set from ashtadhyayi.com, in one act.

THE PROBLEM THIS ENDS. Our Ashtadhyayi was assembled from three sources that
number the sutras differently: the sutrapatha from "commentary dictionary keys"
(3,962), the commentaries from StarDict builds, the enrichment from
ashtadhyayi.com (3,983). They were joined by POSITION, so every one of them
disagreed with the others somewhere. 1.1.17 merges उञः and ऊँ into one record
and the numbering runs one behind for the rest of the pada;
realign_sutra_enrichment.py existed only to paper over that; and syncing the
sutrapatha alone moved eight commentaries a sutra off their own text.

Those are not separate bugs. They are one bug -- the inconsistency lives BETWEEN
the files -- so it cannot be fixed a file at a time.

WHY TAKING THE SET WHOLE FIXES IT. Upstream keys the sutrapatha and every
commentary by the same code: 11001 is 1.1.1 in all eighteen files. The join is
the primary key. There is no alignment step, no text matching, nothing to
realign, and no way for the layers to drift apart, because they never came apart.

ATOMIC. Either the whole Ashtadhyayi is consistent afterwards or nothing moved.
Every layer is built in memory and validated against the sutrapatha before a
single file is written -- a half-migrated corpus reaching a reader is exactly
what went wrong the last time.

WHAT IS DELIBERATELY LEFT OUT. sutrartha_english. The English gloss from this
same file was removed from published data on 23 Aug 2026 -- shown to readers
with no attribution, held on an informal e-mail permission. Upstream's README
now grants use on credit, which probably settles it, but reversing that decision
is the project lead's to make, not this script's. vasu_english IS included: S.
C. Vasu's 1891 translation is public domain and already published here.

  python3 tools/migrate_ashtadhyayi.py --source path/to/ashtadhyayi-com/data
  python3 tools/migrate_ashtadhyayi.py --source … --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(REPO, "data/vedanga/vyakarana/ashtadhyayi")

CREDIT = ("ashtadhyayi.com (github.com/ashtadhyayi-com/data, sutraani/), used with "
          "credit per that project's terms. Its text is corrected continuously by "
          "scholars through the site's own edit button, which is why it is the "
          "reference rather than a one-time import.")

#: upstream file -> (our folder, title, devanagari title, author)
#: Folder names keep our existing ones where a layer already exists, so nothing
#: downstream has to learn a new path for a text it already had.
LAYERS = [
    ("kashika",               "kashika",               "Kāśikā-vṛtti",            "काशिकावृत्तिः",            "Vāmana–Jayāditya"),
    ("nyaas",                 "nyasa",                 "Nyāsa (Kāśikāvivaraṇapañjikā)", "न्यासः",             "Jinendrabuddhi"),
    ("padamanjari",           "padamanjari",           "Padamañjarī",             "पदमञ्जरी",                 "Haradatta Miśra"),
    ("kaumudi",               "siddhanta_kaumudi",     "Siddhānta-Kaumudī",       "सिद्धान्तकौमुदी",          "Bhaṭṭoji Dīkṣita"),
    ("balamanorama",          "balamanorama",          "Bālamanoramā",            "बालमनोरमा",                "Vāsudeva Dīkṣita"),
    ("tattvabodhini",         "tattvabodhini",         "Tattvabodhinī",           "तत्त्वबोधिनी",             "Jñānendra Sarasvatī"),
    ("bhashya",               "mahabhashya_patanjali", "Mahābhāṣya",              "महाभाष्यम्",               "Patañjali"),
    ("laghukaumudi",          "laghu_kaumudi",         "Laghu-Siddhānta-Kaumudī", "लघुसिद्धान्तकौमुदी",       "Varadarāja"),
    ("praudhamanorama",       "praudha_manorama",      "Prauḍhamanoramā",         "प्रौढमनोरमा",              "Bhaṭṭoji Dīkṣita"),
    ("laghushabdendushekhar", "laghu_shabdendushekhara", "Laghuśabdenduśekhara",  "लघुशब्देन्दुशेखरः",        "Nāgeśa Bhaṭṭa"),
    ("prakriyasarvasvam",     "prakriya_sarvasvam",    "Prakriyāsarvasvam",       "प्रक्रियासर्वस्वम्",       "Nārāyaṇa Bhaṭṭa"),
    ("sudha",                 "sudha",                 "Sudhā",                   "सुधा",                     ""),
    ("sarala",                "sarala",                "Saralā",                  "सरला",                     ""),
    ("sutrartha",             "sutrartha",             "Sūtrārtha (Sanskrit gloss)", "सूत्रार्थः",            ""),
    ("vasu_english",          "vasu",                  "S. C. Vasu — translation & notes", "",                "Śrīśa Chandra Vasu"),
    ("vasu_english_summary",  "vasu_summary",          "S. C. Vasu — summary",    "",                         "Śrīśa Chandra Vasu"),
]
EXCLUDED = {"sutrartha_english": "removed from published data 23 Aug 2026 over attribution; the lead's call to revisit"}

TYPE_LABELS = {
    "S":  ("Definition (saṃjñā)", "संज्ञा"),
    "P":  ("Meta-rule (paribhāṣā)", "परिभाषा"),
    "V":  ("Operational rule (vidhi)", "विधि"),
    "AT": ("Extension (atideśa)", "अतिदेश"),
    "AD": ("Governing rule (adhikāra)", "अधिकार"),
}


def sid(code: str) -> str:
    code = str(code).strip()
    return "%s.%s.%d" % (code[0], code[1], int(code[2:]))


def load(src: str, name: str):
    with open(os.path.join(src, "sutraani", name + ".txt"), encoding="utf-8") as fh:
        d = json.load(fh)
    return d


def build_sutrapatha(raw: list) -> dict:
    items = []
    for x in raw:
        ref = "%s.%s.%s" % (x["a"], x["p"], x["n"])
        it = {"id": ref, "reference": ref, "sanskrit_text": x["s"].strip(),
              "tags": ["ashtadhyayi", "sutra", "adhyaya_%s" % x["a"]]}
        pc = [w.split("$")[0].strip() for w in (x.get("pc") or "").split("##") if w.strip()]
        if pc:
            it["padaccheda"] = pc
        if (x.get("ss") or "").strip():
            it["anvaya"] = x["ss"].strip()
        an = []
        for part in (x.get("an") or "").split("##"):
            w, _, s = part.strip().partition("$")
            s = s.strip("$")
            if w.strip() and s.isdigit():
                an.append({"word": w.strip(), "from": sid(s)})
        if an:
            it["anuvritti"] = an
        ad = (x.get("ad") or "").strip()
        if ad:
            b = ad.split("$")
            if len(b) >= 4 and all(q.strip().isdigit() for q in b[1:4]):
                it["adhikara"] = b[0].strip()
                it["adhikara_refs"] = [[b[0].strip(), "%s.%s.%s" % (b[1], b[2], b[3])]]
            else:
                it["adhikara"] = ad
        code = (x.get("type") or "").split("$")[0].strip()
        if code in TYPE_LABELS:
            lab, dev = TYPE_LABELS[code]
            it["sutra_type"] = {"code": code, "label": lab, "label_dev": dev}
        items.append(it)
    items.sort(key=lambda i: [int(p) for p in i["id"].split(".")])
    return {"schema": "grantha_mula_text", "default_author": "Maharshi Pāṇini",
            "title": "Aṣṭādhyāyī", "title_devanagari": "अष्टाध्यायी",
            "source": CREDIT, "count": len(items), "items": items}


def text_of(v) -> str:
    """A layer's entry is a string, or an object of named parts (sūtrārtha's
    sa/sd). Joined rather than picked, so nothing upstream holds is dropped."""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        return "\n\n".join(str(v[k]).strip() for k in v if str(v.get(k) or "").strip())
    return str(v or "").strip()


def build_layer(raw: dict, folder: str, title: str, dev: str, author: str,
                valid: set) -> tuple[dict, list]:
    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
        raw = raw["data"]
    items, orphans = [], []
    for code in sorted(raw, key=lambda c: (len(c), c)):
        body = text_of(raw[code])
        if not body:
            continue
        if not (code.isdigit() and len(code) >= 3):
            orphans.append(code); continue
        ref = sid(code)
        if ref not in valid:
            orphans.append(code); continue
        items.append({
            "id": ref, "reference": ref, "sanskrit_text": body,
            "references": [{"target": "vedanga/vyakarana/ashtadhyayi/sutrapatha",
                            "unit_id": ref, "note": "comments_on"}],
            "tags": ["ashtadhyayi", folder, "adhyaya_%s" % ref.split(".")[0]],
            "tika_title": title,
        })
    items.sort(key=lambda i: [int(p) for p in i["id"].split(".")])
    doc = {"schema": "grantha_tika_text", "title": title, "source": CREDIT,
           "count": len(items), "items": items}
    if dev:
        doc["title_devanagari"] = dev
    if author:
        doc["default_author"] = author
    return doc, orphans


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="a clone of ashtadhyayi-com/data")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    sutra_raw = load(a.source, "data")["data"]
    sp = build_sutrapatha(sutra_raw)
    valid = {i["id"] for i in sp["items"]}
    print("sutrapatha: %d sutras" % len(valid))

    built, all_orphans = {}, {}
    for up, folder, title, dev, author in LAYERS:
        try:
            raw = load(a.source, up)
        except FileNotFoundError:
            print("  MISSING upstream file: %s" % up, file=sys.stderr)
            return 2
        doc, orph = build_layer(raw, folder, title, dev, author, valid)
        built[folder] = doc
        if orph:
            all_orphans[folder] = orph
        print("  %-24s -> %-24s %5d entries%s"
              % (up, folder, doc["count"], ("  (%d unkeyed)" % len(orph)) if orph else ""))

    # Validate before writing anything: every id must exist in the sutrapatha.
    bad = [(f, i["id"]) for f, d in built.items() for i in d["items"] if i["id"] not in valid]
    if bad:
        print("REFUSING: %d entries point at a sutra that does not exist" % len(bad), file=sys.stderr)
        return 2
    print("\nall %d entries across %d layers resolve to a sutra"
          % (sum(d["count"] for d in built.values()), len(built)))
    for k, v in EXCLUDED.items():
        print("excluded: %s -- %s" % (k, v))
    for f, o in all_orphans.items():
        print("unkeyed in %s: %s" % (f, ", ".join(o[:8])))

    if not a.apply:
        print("\nnothing written -- pass --apply")
        return 0

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import format_data_json

    def write(folder, doc):
        d = os.path.join(BASE, folder)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "data.json")
        text = format_data_json.canonical(doc) or json.dumps(doc, ensure_ascii=False,
                                                             separators=(",", ":"))
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    write("sutrapatha", sp)
    for folder, doc in built.items():
        write(folder, doc)
    print("\nwrote sutrapatha + %d layers" % len(built))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
