#!/usr/bin/env python3
"""library_census.py -- what the library actually contains, counted honestly.

"1,306 works" was a misleading thing to say, and this exists so it is not
said again. 1,306 is the number of POPULATED ENTRIES in data/library.json,
and an entry is a single data.json -- which is usually one LAYER of a work,
not a work. The Brahmasutra bhashya alone is 23 of those entries.

It also separates what we OCRed ourselves from a scan, which can be checked
against a source PDF, from what arrived as text from somewhere else, which
cannot -- there is no PDF to check it against, and the right check for those
is structural and visual only.

Three schemas are in use for units and all three are legitimate:

    items            a list, the common case
    shlokas          a DICT keyed by number, the older Kavya format
    grantha_layer_v2_index   a sharded index whose `parts` hold the units

A census that knows only the first reports the other two as empty, which is
how this file came to be written: the first pass called 36 granthas empty
and every one of them was fine.

    python3 tools/library_census.py --out admin/config/library_census.json
"""
import argparse, collections, json, os, sys

UNIT_KEYS = ("items", "shlokas", "units", "verses", "entries")
LAYER_PREFIXES = ("tika", "bhashya", "vyakhyana", "tippani", "commentary",
                  "upodghata", "anuvyakhyana", "parishishta")


def unit_count(d):
    """How many units, and which schema said so."""
    for k in UNIT_KEYS:
        v = d.get(k)
        if isinstance(v, (list, dict)) and len(v):
            return len(v), k + ("[dict]" if isinstance(v, dict) else "")
    if d.get("schema") == "grantha_layer_v2_index" and d.get("units_total"):
        return int(d["units_total"]), "grantha_layer_v2_index"
    m = d.get("metadata") or {}
    if m.get("totalShlokas"):
        return int(m["totalShlokas"]), "metadata.totalShlokas"
    return 0, None


def is_layer(name):
    return name == "mula" or any(name.startswith(p) for p in LAYER_PREFIXES)


def census(root="."):
    lib = json.load(open(os.path.join(root, "data", "library.json"), encoding="utf-8"))
    entries = [x for x in lib.get("granthas", []) if x.get("populated")]

    schemas, shelves = collections.Counter(), collections.Counter()
    works = collections.defaultdict(list)
    total_units, empty = 0, []

    for x in entries:
        p = os.path.join(root, x["path"])
        slug = x["path"].replace("data/", "", 1).replace("/data.json", "")
        parts = slug.split("/")
        shelves[parts[0]] += 1
        works["/".join(parts[:-1]) if is_layer(parts[-1]) else slug].append(slug)
        if not os.path.isfile(p):
            empty.append({"slug": slug, "why": "file missing"})
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:                              # noqa: BLE001
            empty.append({"slug": slug, "why": "unparseable: %s" % str(e)[:60]})
            continue
        n, k = unit_count(d)
        if n:
            schemas[k] += 1
            total_units += n
        else:
            empty.append({"slug": slug, "why": "no units; keys=%s"
                          % ",".join(list(d.keys())[:5])})

    # What we OCRed ourselves, and what can therefore be checked against a scan.
    rec_path = os.path.join(root, "admin", "config", "ocr_receipts.json")
    src_path = os.path.join(root, "admin", "config", "ocr_sources.json")
    staged = json.load(open(rec_path, encoding="utf-8"))["works"] if os.path.isfile(rec_path) else {}
    sources = (json.load(open(src_path, encoding="utf-8")).get("works", {})
               if os.path.isfile(src_path) else {})
    with_pdf = [k for k in sources if not k.startswith("_")]

    return {
        "_readme": [
            "1,306 is POPULATED ENTRIES, not works: an entry is one data.json,",
            "which is usually one layer. 'works' below counts a mula and its",
            "tikas once. 'ocr' counts what we scanned ourselves; everything",
            "else arrived as text and has no PDF to be checked against.",
        ],
        "entries_populated": len(entries),
        "works": len(works),
        "works_multi_layer": sum(1 for v in works.values() if len(v) > 1),
        "units_total": total_units,
        "unit_schemas": dict(schemas),
        "entries_without_units": empty,
        "by_shelf": dict(shelves.most_common()),
        "ocr": {
            "staging_branches": len(staged),
            "branches_with_a_source_pdf": len(with_pdf),
            "harikathamrtasara_branches": len([k for k in with_pdf if k.startswith("hks__")]),
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    c = census(args.root)
    print("populated entries in library.json : %s" % f'{c["entries_populated"]:,}')
    print("  distinct works (layers folded)  : %s  (%d carry several layers)"
          % (f'{c["works"]:,}', c["works_multi_layer"]))
    print("  units across all of them        : %s" % f'{c["units_total"]:,}')
    print("  entries carrying nothing        : %d" % len(c["entries_without_units"]))
    print("\nunit schemas in use:")
    for k, v in sorted(c["unit_schemas"].items(), key=lambda kv: -kv[1]):
        print("   %-26s %5d entries" % (k, v))
    print("\nOCRed by us from a scan:")
    o = c["ocr"]
    print("   %3d staging branches (one per PDF or volume)" % o["staging_branches"])
    print("   %3d have a source PDF recorded, of which %d are the Harikathamrtasara"
          % (o["branches_with_a_source_pdf"], o["harikathamrtasara_branches"]))
    print("\nby shelf:")
    for k, v in list(c["by_shelf"].items())[:14]:
        print("   %-34s %5d" % (k, v))
    if args.out:
        with open(os.path.join(args.root, args.out), "w", encoding="utf-8") as fh:
            json.dump(c, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
