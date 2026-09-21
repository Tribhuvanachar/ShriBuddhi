#!/usr/bin/env python3
"""
build_manimanjari.py -- land the staged Maṇimañjarī into the Kāvya shelf.

Source: the three pre-split layers on origin/ocr-staging/manimanjari
(mula, tika_sanskrit, tika_kannada), read straight off the remote-tracking
ref. Nothing is fetched and no branch is touched.

Target: data/Tattvavada/Itara/Kavya/manimanjari/sarga_N/data.json, in the
{metadata, shlokas} shape sumadhva_vijaya already uses on that shelf -- the
same author, Narayana Panditacarya, which is what settles the placement.

Two defects in the staged split are repaired here, both verified against the
page images of the source scan rather than inferred:

  1. tika_kannada has one block with no verse number, labelled sarga 4, on
     PDF page 173 -- which falls in the gap between Kannada sarga 3 (ends
     p172) and sarga 4 (begins p174). Its text glosses mula 3.31 word for
     word, matching the Sanskrit tika on 3.31 phrase for phrase. It is
     3.31, and is relabelled as such. That alone brings sarga 3 from 30 to
     its canonical 31 and leaves sarga 4 at a complete 1..39.

  2. mula 4.30 is absent -- sarga 4 runs 1..39 with a hole at 30, while the
     Sanskrit tika carries all 39 and its 4.30 opens with the pratika
     "नीलामिति", so the verse certainly exists. The page image of PDF p190
     shows it printed in Devanagari between 4.29 and the Kannada gloss;
     Sarvam misread that line as Kannada, which is why the splitter dropped
     it. Vision read it correctly but for "पुत्र" where the page prints
     "पुत्रीं" -- the reading the tika's own gloss ("पुत्री नीलां") and the
     anustubh metre both require. The text below is what the page prints.

Every repair is recorded in the emitted unit's "provenance" so a reader or a
later editor can see that it did not come from the OCR of that line.

The build refuses to write unless all three layers land on the canonical
sarga counts with no gaps -- it will not invent or drop a verse silently.

  python3 tools/build_manimanjari.py            # validate and report
  python3 tools/build_manimanjari.py --write    # write the shelf + library
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANCH = "origin/ocr-staging/manimanjari"
STAGED = "data/ocr_staging/manimanjari/layers/%s.json"
OUT = ROOT / "data/Tattvavada/Itara/Kavya/manimanjari"
LIBRARY = ROOT / "data/library.json"

# Settled in docs/OCR_PENDING.md §4 against the printed colophons, sarga 6
# read off the scan directly after the two engines disagreed 52 / 51.
CANONICAL = {1: 31, 2: 32, 3: 31, 4: 39, 5: 51, 6: 52, 7: 29, 8: 41}

LAYERS = ("mula", "tika_sanskrit", "tika_kannada")

COMMENTARIES = {
    "sanskrit_tika": "संस्कृतटीका — रायपल्य राघवेन्द्राचार्यः",
    "kannada_tika": "ಕನ್ನಡ ಟೀಕಾ — ರಾಯಪಲ್ಯ ರಾಘವೇಂದ್ರಾಚಾರ್ಯ",
}
LAYER_TO_KEY = {"tika_sanskrit": "sanskrit_tika", "tika_kannada": "kannada_tika"}

# Read off the page image of PDF p190 (dpi 170). See the module docstring.
MULA_4_30 = (
    "नीलां नग्नजितःपुत्रीं मित्रविन्दां पितृष्वसुः ।\n"
    "भद्राञ्च कैकयसुतां लक्षणां स्वां च सोऽवहत् ॥ ३० ॥"
)
MULA_4_30_PROV = {
    "recovered": True,
    "why": "absent from the staged split: Sarvam read this Devanagari line as "
           "Kannada, so the mula splitter never saw it",
    "read_from": "page image of PDF p190 of the source scan, rendered at 170 dpi",
    "corroborated_by": [
        "the Sanskrit tika's own pratika for 4.30, नीलामिति",
        "Vision OCR of the same page, which differs only in reading पुत्र for पुत्रीं",
        "the anustubh metre, which requires the long form",
    ],
}
KAN_3_31_PROV = {
    "relabelled": True,
    "why": "staged as sarga 4 with no verse number, on PDF p173 -- between "
           "Kannada sarga 3 (ends p172) and sarga 4 (begins p174)",
    "read_from": "its own text, which glosses mula 3.31 word for word",
}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True, check=True).stdout


def load_layers() -> dict[str, list[dict]]:
    out = {}
    for name in LAYERS:
        out[name] = json.loads(git("cat-file", "-p", f"{BRANCH}:{STAGED % name}"))["blocks"]
    return out


def repair(layers: dict[str, list[dict]]) -> list[str]:
    """Applies the two documented repairs. Returns what it did, and raises if
    the defect it expects is not the defect it finds -- a staged file that has
    been re-split since must not be silently patched on stale assumptions."""
    log = []

    kan = layers["tika_kannada"]
    orphans = [b for b in kan if b.get("verse") is None]
    if len(orphans) != 1:
        raise SystemExit(f"expected exactly 1 unnumbered Kannada block, found {len(orphans)}")
    o = orphans[0]
    if o.get("sarga") != 4 or o.get("page") != 173:
        raise SystemExit(f"unnumbered Kannada block is not the known one: {o.get('sarga')}/{o.get('page')}")
    if any(b for b in kan if b.get("sarga") == 3 and b.get("verse") == 31):
        raise SystemExit("Kannada sarga 3 already has a verse 31 -- refusing to add a second")
    o["sarga"], o["verse"] = 3, 31
    o["id"] = "s3_v31"
    o["provenance"] = KAN_3_31_PROV
    log.append("tika_kannada: unnumbered p173 block relabelled 4.? -> 3.31")

    mula = layers["mula"]
    if any(b for b in mula if b.get("sarga") == 4 and b.get("verse") == 30):
        raise SystemExit("mula 4.30 is present -- the staged split has changed; re-check before writing")
    mula.append({
        "id": "s4_v30", "type": "mula", "sarga": 4, "verse": 30,
        "page": 190, "pages": [190], "text": MULA_4_30,
        "ocr_confidence": None, "provenance": MULA_4_30_PROV,
    })
    log.append("mula: 4.30 restored from the page image")
    return log


def validate(layers: dict[str, list[dict]]) -> None:
    bad = []
    for name, blocks in layers.items():
        for sarga, want in CANONICAL.items():
            vs = sorted(b["verse"] for b in blocks if b.get("sarga") == sarga)
            if len(vs) != want or vs != list(range(1, want + 1)):
                missing = [n for n in range(1, want + 1) if n not in vs]
                dup = sorted({n for n in vs if vs.count(n) > 1})
                bad.append(f"  {name} sarga {sarga}: have {len(vs)}, want {want}"
                           f"{', missing ' + str(missing) if missing else ''}"
                           f"{', duplicated ' + str(dup) if dup else ''}")
    if bad:
        raise SystemExit("refusing to write -- layers do not match the canonical counts:\n"
                         + "\n".join(bad))


def build(layers: dict[str, list[dict]]) -> dict[int, dict]:
    idx = {name: {(b["sarga"], b["verse"]): b for b in blocks}
           for name, blocks in layers.items()}
    out = {}
    for sarga, total in CANONICAL.items():
        shlokas = {}
        for v in range(1, total + 1):
            m = idx["mula"][(sarga, v)]
            unit = {"sa": m["text"], "commentaries": {}}
            if m.get("provenance"):
                unit["provenance"] = m["provenance"]
            for layer, key in LAYER_TO_KEY.items():
                b = idx[layer].get((sarga, v))
                if b and (b.get("text") or "").strip():
                    unit["commentaries"][key] = b["text"]
                    if b.get("provenance"):
                        unit.setdefault("commentaryProvenance", {})[key] = b["provenance"]
            shlokas[str(v)] = unit
        out[sarga] = {
            "metadata": {
                "title": f"Maṇimañjarī सर्गः {sarga}",
                "author": "Narayana Panditacharya",
                "stotraCode": f"sarga_{sarga}",
                "totalShlokas": total,
                "availableCommentaries": dict(COMMENTARIES),
                "source": {
                    "edition": "Maṇimañjarī of Śrī Nārāyaṇa Paṇḍitācārya, with the "
                               "Sanskrit and Kannada commentaries of Śrī Rāyapalya "
                               "Rāghavendrācārya",
                    "publisher": "Sri Trilokyacharya Sevaka Vrinda, Madhva Mandiram, "
                                 "Bangalore 560019",
                    "edition_year": 2003,
                    "ocr": "Sarvam Document AI, split by tools/split_manimanjari_layers.py",
                },
            },
            "shlokas": shlokas,
        }
    return out


def write_library(sargas: list[int]) -> int:
    """Appends the new granthas without reformatting the rest of the file.

    data/library.json is ~32,000 lines. Round-tripping it through json.dump
    rewrites every line -- different indent, different key order -- and buries
    an 8-line addition in a 16,000-line diff that no one can review. So the
    entries are written with the file's own indent and key order, and the
    file is re-read afterwards to prove it is still valid JSON with exactly
    the expected number of granthas.
    """
    raw = LIBRARY.read_text()
    doc = json.loads(raw)
    have = {g.get("path") for g in doc["granthas"]}
    want = [s for s in sargas
            if f"data/Tattvavada/Itara/Kavya/manimanjari/sarga_{s}/data.json" not in have]
    if not want:
        return 0

    blocks = []
    for s in want:
        blocks.append(
            "    {\n"
            f'      "path": "data/Tattvavada/Itara/Kavya/manimanjari/sarga_{s}/data.json",\n'
            '      "populated": true,\n'
            f'      "title": "Maṇimañjarī सर्गः {s}"\n'
            "    }")

    # Splice in before the closing bracket of the granthas array, which is the
    # last "\n  ]" in the file -- located by structure rather than by rewriting.
    marker = "\n  ]"
    cut = raw.rindex(marker)
    merged = raw[:cut] + ",\n" + ",\n".join(blocks) + raw[cut:]

    check = json.loads(merged)
    if len(check["granthas"]) != len(doc["granthas"]) + len(want):
        raise SystemExit("splice produced the wrong grantha count -- not writing")
    LIBRARY.write_text(merged)
    return len(want)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    layers = load_layers()
    for line in repair(layers):
        print("repair:", line)
    validate(layers)
    print("all three layers match the canonical sarga counts "
          f"({sum(CANONICAL.values())} verses across {len(CANONICAL)} sargas)")

    built = build(layers)
    total_comm = sum(len(u["commentaries"]) for s in built.values() for u in s["shlokas"].values())
    print(f"built {len(built)} sargas, {sum(len(s['shlokas']) for s in built.values())} verses, "
          f"{total_comm} commentary units")

    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0

    for sarga, data in built.items():
        d = OUT / f"sarga_{sarga}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}/sarga_1..{len(built)}/data.json")
    print(f"added {write_library(sorted(built))} entries to data/library.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
