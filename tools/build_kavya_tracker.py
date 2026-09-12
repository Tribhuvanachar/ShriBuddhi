#!/usr/bin/env python3
"""
build_kavya_tracker.py — what kavya we hold, what we do not, and how far in.

The question this answers is the project lead's: how many kavyas are there in
all, how many are finished, which are part-done and to what extent, and what is
still only a name on a list. It answers it from three places that each know
part of it and none of which agrees with the others on its own:

  dge/data/**                        what is published on the site right now
  the Kavya corpus (kavya-dist)      what the importer built, off-site
  tools/kavya/config/works.json      what the importer was asked for, and the
                                     recorded reason where it could not
  tools/kavya/config/tracker_wanted.json
                                     the Madhva-lineage kavyas that no importer
                                     has a source for -- the Vijaya kavyas above
                                     all -- with the dictated title kept beside
                                     the reading

A work counts as COMPLETE only when it has mula AND, where the tradition has
one, a commentary. That distinction is the point of the tracker: Raghavendra
Vijaya has all ten sargas of its mula published and every single shloka carries
an empty `commentaries` block, so by verse count it looks finished and by what
a reader needs it is half done.

    python3 tools/build_kavya_tracker.py
    python3 tools/build_kavya_tracker.py --corpus <a kavya-dist checkout>

Writes admin/config/kavya-status.json (machine) and dge/KAVYA_TRACKER.md (human).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_URL = ("https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala"
              "@kavya-dist/kavya_alankara/_index.json")

# A layer id that is a commentary rather than the text or an aid to reading it.
AIDS = {"mula", "padaccheda", "anvaya", "chandas", "saaramsha"}


def count_on_disk(path):
    """Verses and commentary coverage in one grantha, in either shape.

    dge/data holds both: the itihasa_purana_text shape this project writes now
    ({items: [{shlokas: [...]}]}), and the older stotra shape the Vijaya kavyas
    are in ({shlokas: {"1": {sa, commentaries}}}). Counting only the first would
    report Sumadhva Vijaya and Raghavendra Vijaya as empty, which is how they
    came to look absent in an earlier pass.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return 0, 0
    verses = commented = 0
    if isinstance(d.get("items"), list):
        for it in d["items"]:
            for sh in it.get("shlokas", []) or []:
                verses += 1
                if sh.get("bhashya") or sh.get("artha"):
                    commented += 1
    elif isinstance(d.get("shlokas"), dict):
        for sh in d["shlokas"].values():
            if not isinstance(sh, dict):
                continue
            verses += 1
            if sh.get("commentaries"):
                commented += 1
    return verses, commented


def on_disk(data_root):
    """Every kavya-family work published from dge/data, with its layers."""
    out = {}
    for path in sorted(glob.glob(os.path.join(data_root, "kavya_alankara", "*"))):
        if not os.path.isdir(path):
            continue
        wid = os.path.basename(path)
        verses = commented = 0
        layers = []
        for f in sorted(glob.glob(os.path.join(path, "*", "data.json"))):
            v, c = count_on_disk(f)
            verses += v
            commented += c
            layers.append(os.path.basename(os.path.dirname(f)))
        out[wid] = {"verses": verses, "commented": commented, "layers": layers}
    return out


def corpus(source):
    """The built Kavya corpus: local checkout, or the published index."""
    try:
        if source and os.path.exists(source):
            with open(os.path.join(source, "_index.json"), encoding="utf-8") as fh:
                idx = json.load(fh)
        else:
            with urllib.request.urlopen(source or CORPUS_URL, timeout=120) as r:
                idx = json.load(r)
    except Exception as exc:                                   # noqa: BLE001
        print("  ! no corpus index (%s); reporting from disk only" % exc,
              file=sys.stderr)
        return {}
    out = {}
    for w in idx.get("works", []):
        layers = w.get("layers", [])
        out[w["id"]] = {
            "name_sa": w.get("name_sa", ""), "name_iast": w.get("name_iast", ""),
            "author": w.get("author", ""), "genre": (w.get("genre_path") or [None, None])[1],
            "layers": [l["id"] for l in layers],
            "verses": max([l.get("counts", {}).get("shlokas", 0) for l in layers] or [0]),
            "commentary_layers": [l["id"] for l in layers
                                  if l.get("layer_kind") in ("tika", "tippani")],
        }
    return out


def classify(entry):
    """complete / mula_only / partial / sourced_not_imported / no_source / wanted."""
    if entry["verses"] == 0:
        return "wanted" if entry["wanted"] else (
            "no_source" if entry["register"] else "sourced_not_imported")
    if entry["commentary_expected"] and not entry["commentary"]:
        return "mula_only"
    if entry["commentary"]:
        return "complete"
    return "complete" if not entry["commentary_expected"] else "mula_only"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=os.path.join(REPO, "dge", "data"))
    ap.add_argument("--corpus", default="", help="a kavya-dist checkout, or a URL")
    ap.add_argument("--out-json", default=os.path.join(REPO, "admin", "config", "kavya-status.json"))
    ap.add_argument("--out-md", default=os.path.join(REPO, "dge", "KAVYA_TRACKER.md"))
    args = ap.parse_args()

    works = {w["id"]: w for w in json.load(
        open(os.path.join(REPO, "tools", "kavya", "config", "works.json"),
             encoding="utf-8"))["works"]}
    wanted = {w["id"]: w for w in json.load(
        open(os.path.join(REPO, "tools", "kavya", "config", "tracker_wanted.json"),
             encoding="utf-8"))["works"]}
    disk = on_disk(args.data_root)
    built = corpus(args.corpus)

    rows = {}
    for wid in set(works) | set(wanted) | set(disk) | set(built):
        w = works.get(wid, {})
        want = wanted.get(wid, {})
        b = built.get(wid, {})
        d = disk.get(wid, {})
        commentary = list(b.get("commentary_layers") or [])
        if d.get("commented"):
            commentary = commentary or ["(commentary in the published grantha)"]
        # A kavya is expected to have a commentary unless something says
        # otherwise. The first cut of this defaulted the other way -- expect one
        # only where one already exists -- and reported 43 of 69 works complete,
        # which is the tracker telling the project lead what he already has
        # rather than what is missing. Naishadhiyacarita without its Jivatu is
        # not a finished work; it is a mula waiting for a tika.
        expected = want.get("commentary_expected")
        if expected is None:
            expected = True
        rows[wid] = {
            "id": wid,
            "name_sa": w.get("name_sa") or b.get("name_sa") or want.get("name_sa") or "",
            "name_iast": w.get("name_iast") or b.get("name_iast") or want.get("name_iast") or "",
            "author": w.get("author") or b.get("author") or want.get("author") or "",
            "kind": want.get("kind") or (w.get("genre_path") or [None, None, "kavya"])[-1],
            "verses": max(b.get("verses", 0), d.get("verses", 0)),
            "published_verses": d.get("verses", 0),
            "corpus_verses": b.get("verses", 0),
            "layers": sorted(set(list(b.get("layers") or []) + list(d.get("layers") or []))),
            "commentary": commentary,
            "commentary_expected": bool(expected),
            "register": (w.get("register") or {}).get("status", ""),
            "wanted": bool(want),
            "dictated": want.get("dictated", ""),
            "confidence": want.get("confidence", ""),
            "note": want.get("note", ""),
        }
        rows[wid]["status"] = classify(rows[wid])

    order = ["complete", "mula_only", "partial", "sourced_not_imported", "no_source", "wanted"]
    by = {s: [r for r in rows.values() if r["status"] == s] for s in order}
    total = len(rows)
    verses = sum(r["verses"] for r in rows.values())
    ready = len(by["complete"])
    summary = {
        "works_total": total,
        "verses_held": verses,
        "complete": ready,
        "mula_only": len(by["mula_only"]),
        "no_source": len(by["no_source"]),
        "wanted": len(by["wanted"]),
        "percent_complete": round(100.0 * ready / max(1, total), 1),
        "percent_with_text": round(100.0 * sum(1 for r in rows.values() if r["verses"]) / max(1, total), 1),
    }

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as fh:
        json.dump({"_readme": "Generated by tools/build_kavya_tracker.py. Do not hand-edit.",
                   "summary": summary, "works": rows}, fh, ensure_ascii=False, indent=1)

    L = ["# Kāvya tracker", "",
         "_Generated by `tools/build_kavya_tracker.py`. Do not hand-edit — rerun it._", "",
         "| | |", "|---|---|",
         f"| Works tracked | **{total}** |",
         f"| Verses held | **{verses:,}** |",
         f"| Complete (mūla + commentary where one is expected) | **{ready}** ({summary['percent_complete']}%) |",
         f"| Mūla only, commentary pending | **{len(by['mula_only'])}** |",
         f"| Declared but no usable source | **{len(by['no_source'])}** |",
         f"| Named, nothing yet | **{len(by['wanted'])}** |", ""]
    titles = {
        "complete": "Complete",
        "mula_only": "Mūla only — the commentary is what is missing",
        "partial": "Partial",
        "sourced_not_imported": "Has a source, not yet in the corpus",
        "no_source": "No usable source found",
        "wanted": "Named, nothing yet",
    }
    for s in order:
        if not by[s]:
            continue
        L += [f"## {titles[s]} ({len(by[s])})", ""]
        L += ["| Work | Author | Verses | Layers | Note |", "|---|---|---:|---|---|"]
        for r in sorted(by[s], key=lambda x: -x["verses"]):
            name = r["name_sa"] or r["name_iast"] or r["id"]
            if r["name_iast"] and r["name_sa"]:
                name = f"{r['name_sa']} · {r['name_iast']}"
            note = r["note"] or r["register"]
            if r["confidence"] and r["confidence"] != "high":
                note = f"**reading {r['confidence']}-confidence** (dictated “{r['dictated']}”) — {note}"
            L.append(f"| {name} | {r['author'] or '—'} | {r['verses'] or '—'} | "
                     f"{', '.join(r['layers']) or '—'} | {note[:240]} |")
        L.append("")
    with open(args.out_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
