#!/usr/bin/env python3
"""Turn the segmented Saṅgraha Rāmāyaṇam into its shelf files.

सङ्ग्रहरामायणम् of Nārāyaṇa Paṇḍitācārya, with Viśvapati Tīrtha's
Bhāvārthadīpikā and Bannañje Govindācārya's Saṅgrahacandrikā.

    data/Tattvavada/Itara/Kavya/sangraha_ramayana/<kanda>_sarga_NN/data.json

Beside the Sumadhva Vijaya and the Maṇimañjarī, which are the same hand.
One file per sarga, 64 of them across the seven kāṇḍas.

THE SAṄGRAHACANDRIKĀ IS MODERN, AND THAT IS SAID RATHER THAN ACTED ON. It
is Bannañje Govindācārya's own, first published in this 2015 edition, so
it is in copyright in a way the mūla and the Bhāvārthadīpikā are not. It
lands and goes live in ShriBuddhi like the rest; whether it reaches a
reader is recorded in js/core.js and is the lead's decision.

VERSES ARE KEYED BY POSITION, and the number the page printed is kept
beside each. See the segmenter: read straight off the page those numbers
give 144 duplicates and 1,587 gaps.
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ocr_common"))
import shelf_writer as W                                        # noqa: E402


def _load(name: str, path: pathlib.Path):
    """Under a name of its own -- every segmenter here is ``segment.py``."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


seg = _load("sangraha_ramayana_segment", HERE / "segment.py")

TARGET = pathlib.Path("data/Tattvavada/Itara/Kavya/sangraha_ramayana")
WORK = "Sangraha Ramayanam"
AUTHOR = "Narayana Panditacharya"

COMMENTARIES = {
    "bhavarthadipika": "भावार्थदीपिका — श्रीविश्वपतितीर्थः",
    "sangrahacandrika": "सङ्ग्रहचन्द्रिका — बन्नञ्जे गोविन्दाचार्यः",
}

#: Nothing. The Saṅgrahacandrikā is modern -- Bannañje Govindācārya's own,
#: first published in this 2015 edition -- and this file gated it on that
#: reasoning. That was the wrong call to make here: what reaches a reader
#: is recorded in js/core.js DGE_COPYRIGHT_GATED_COMMENTARY_KEYS and is the
#: lead's decision, not an importer's. The work lands, it goes live in
#: ShriBuddhi, and the copyright question is raised rather than settled.
GATED: set[str] = set()

SOURCE = {
    "edition": "सङ्ग्रहरामायणम् — with the Bhāvārthadīpikā of Śrī Viśvapati "
               "Tīrtha and the Saṅgrahacandrikā of Bannañje Govindācārya, "
               "critically edited by Dr Bannañje Govindācārya",
    "extent": "All seven kāṇḍas, 64 sargas, as the edition's own sarga "
              "colophons divide it",
    "ocr": "Sarvam Document AI, 1,525 pages across two volumes, with a "
           "Google Vision pass; segmented by tools/sangraha_ramayana/segment.py",
}

ORDINAL = {s: t for s, _, t in ((k[1], k[0], k[2]) for k in seg.KANDAS)}
MIN_CHARS = 12


def build(units: list[dict]) -> dict:
    files: dict[str, dict] = {}
    for u in units:
        if not (u["kanda"] and u["sarga"]):
            continue
        name = f"{u['kanda']}_sarga_{int(u['sarga']):02d}"
        f = files.setdefault(name, {"units": [], "kanda": u["kanda"],
                                    "sarga": int(u["sarga"])})
        f["units"].append(u)

    out = {}
    for name, f in files.items():
        shlokas = {}
        for u in f["units"]:
            entry = {"sa": u["verse"]}
            if u.get("printed"):
                entry["unit_title"] = str(u["printed"])
            com = {k: " ".join(v.split()) for k, v in u["layers"].items()
                   if k in COMMENTARIES and len(v.strip()) >= MIN_CHARS}
            if com:
                entry["commentaries"] = com
            shlokas[str(u["number"])] = entry
        title = ORDINAL.get(f["kanda"], f["kanda"])
        out[name] = {
            "metadata": {
                "title": f"{WORK} — {title} सर्गः {f['sarga']}",
                "author": AUTHOR,
                "stotraCode": name,
                "totalShlokas": len(shlokas),
                "sargaName": f"{title} सर्गः {f['sarga']}",
                "lacunae": [],
                "availableCommentaries": dict(COMMENTARIES),
                "source": SOURCE,
            },
            "shlokas": shlokas,
        }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    files = build(seg.segment())
    import collections
    per = collections.Counter()
    verses = 0
    for name, payload in files.items():
        verses += len(payload["shlokas"])
        for v in payload["shlokas"].values():
            per.update((v.get("commentaries") or {}).keys())
    print(f"{len(files)} sargas, {verses} verses")
    for key, label in COMMENTARIES.items():
        tag = "   [gated to an admin]" if key in GATED else ""
        print(f"   {per[key]:>5}   {label}{tag}")

    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    print(f"\nwrote {W.write(files, TARGET)} file(s) to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
