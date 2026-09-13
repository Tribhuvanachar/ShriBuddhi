#!/usr/bin/env python3
"""
build_jayanthi_tika.py — fold the Kannada edition of the Jayantī Nirṇaya into
the EXISTING grantha as a selectable commentary (ṭīkā) layer.

The Kannada edition (Śrīpādarāja Maṭha, Muḷabāgilu; anvaya-artha and nine
tātparya sections of Śrī Agrahāra Nārāyaṇa Tantri) was first imported as a
parallel `mula_kannada/` folder. The project lead's decision: it belongs on the
existing Jayantī Nirṇaya — which already carries the Devanāgarī mūla and the
Jayatīrtha ṭīkā slot — *as a commentary*, not as a second mūla. So this script
re-keys its content onto the mūla's own item ids so dge/js/layer-stitch.js can
pair them and the reader can switch the layer on per verse.

Recension mapping (verified by comparing first lines of both editions):
  mūla JN_C01_V01..V09  1:1  Kannada JN_001..JN_009
  mūla JN_C01_V10, V11   <-  Kannada JN_010_011  (one joint anvaya for 10-11)
  mūla JN_C01_V12        <-  Kannada JN_012
  mūla JN_C01_V13, V14   <-  Kannada JN_013_014  (joint anvaya for 13-14)
  mūla JN_C01_V15, V16   <-  Kannada JN_015_017  (joint anvaya for 15-17)
Where one Kannada block serves several mūla verses the full anvaya is attached
to the FIRST verse of the range (printed editions gloss such pairs jointly) and
the later verse(s) get a short pointer, so the layer has no silent gaps.

Material with no mūla counterpart is preserved rather than dropped:
  - the invocation  -> a labelled preamble on the first verse
  - 9 tātparya sections + colophon -> a labelled appendix on the last verse
The Devanāgarī mūla stops at 16 verses; this edition carries a 17th
(धर्मायेति ततः स्वस्थो …) inside its 15-17 block. That is recorded as a note on
the last verse rather than silently merged.

Reads only committed data. No API calls, no cost.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
G = os.path.join(ROOT, "dge/data/darshana/vedanta/dvaita/SarvaMula/"
                       "achara_and_ancillary_granthas/jayanti_nirnaya")
SRC = os.path.join(ROOT, "tools/jayanthi/jayanthi_kannada_parsed.json")
MULA = os.path.join(G, "mula/data.json")
OUT_DIR = os.path.join(G, "tika_kannada")
OUT = os.path.join(OUT_DIR, "data.json")

TIKA_TITLE = "ಕನ್ನಡ ಅನ್ವಯಾರ್ಥ — ಶ್ರೀ ಅಗ್ರಹಾರ ನಾರಾಯಣ ತಂತ್ರಿ"

# mula id -> (kannada source id, role)  role: 'full' | 'ref'
MAP = {}
for i in range(1, 10):
    MAP["JN_C01_V%02d" % i] = ("JN_%03d" % i, "full")
MAP["JN_C01_V10"] = ("JN_010_011", "full")
MAP["JN_C01_V11"] = ("JN_010_011", "ref")
MAP["JN_C01_V12"] = ("JN_012", "full")
MAP["JN_C01_V13"] = ("JN_013_014", "full")
MAP["JN_C01_V14"] = ("JN_013_014", "ref")
MAP["JN_C01_V15"] = ("JN_015_017", "full")
MAP["JN_C01_V16"] = ("JN_015_017", "ref")

RANGE_LABEL = {"JN_010_011": "೧೦–೧೧", "JN_013_014": "೧೩–೧೪", "JN_015_017": "೧೫–೧೭"}


def block(title, body):
    return "【%s】\n%s" % (title, body.strip())


def main():
    src = json.load(open(SRC, encoding="utf-8"))
    mula = json.load(open(MULA, encoding="utf-8"))
    by_id = {it["id"]: it for it in src["items"]}
    mula_ids = [it["id"] for it in mula["items"]]

    inv = by_id.get("JN_INV")
    col = by_id.get("JN_COL")
    tat = [it for it in src["items"] if it["id"].startswith("JN_T")]

    items = []
    for mid in mula_ids:
        if mid not in MAP:
            continue
        kid, role = MAP[mid]
        k = by_id[kid]
        anvaya = (k.get("commentaries") or {}).get("kannada_anvaya", "").strip()
        verse = (k.get("sanskrit_text") or "").strip()
        parts = []

        # preamble: the edition's invocation, on the very first verse
        if mid == "JN_C01_V01" and inv:
            parts.append(block("ಮಂಗಳಾಚರಣೆ (Invocation)",
                               (inv.get("sanskrit_text") or "").strip()))

        if role == "full":
            lbl = RANGE_LABEL.get(kid)
            head = ("ಶ್ಲೋಕ %s — ಕನ್ನಡ ಪಾಠ" % lbl) if lbl else "ಕನ್ನಡ ಪಾಠ"
            parts.append(block(head, verse))
            parts.append(block("ಅನ್ವಯಾರ್ಥ", anvaya))
        else:
            lbl = RANGE_LABEL.get(kid, "")
            parts.append(block(
                "ಅನ್ವಯಾರ್ಥ",
                "ಈ ಶ್ಲೋಕದ ಅನ್ವಯಾರ್ಥವು ಶ್ಲೋಕ %s ರೊಂದಿಗೆ ಒಟ್ಟಿಗೆ ಕೊಟ್ಟಿದೆ "
                "(ಮೇಲಿನ ಶ್ಲೋಕವನ್ನು ನೋಡಿ).\n"
                "— The Kannada edition glosses verses %s jointly; see the "
                "commentary on the first verse of that range." % (lbl, lbl)))

        # appendix: the nine tātparya sections + colophon, on the last verse
        if mid == mula_ids[-1]:
            if tat:
                body = "\n\n".join(
                    "◆ %s\n%s" % (t.get("reference", "").strip(),
                                  (t.get("sanskrit_text") or "").strip())
                    for t in tat)
                parts.append(block("ತಾತ್ಪರ್ಯ (Tātparya — %d sections)" % len(tat), body))
            if col:
                parts.append(block("ಸಮಾಪ್ತಿ (Colophon)",
                                   (col.get("sanskrit_text") or "").strip()))
            parts.append(block(
                "ಪಾಠಭೇದ (Recension note)",
                "ಈ ಕನ್ನಡ ಆವೃತ್ತಿಯು ೧೫–೧೭ ಸಂಖ್ಯೆಯ ಶ್ಲೋಕಗಳನ್ನು ಒಟ್ಟಿಗೆ ಕೊಡುತ್ತದೆ; "
                "ಅದರಲ್ಲಿ ೧೭ನೆಯ ಶ್ಲೋಕವು (ಧರ್ಮಾಯೇತಿ ತತಃ ಸ್ವಸ್ಥೋ …) ಈ ಮೂಲಪಾಠದಲ್ಲಿ "
                "ಪ್ರತ್ಯೇಕವಾಗಿ ಇಲ್ಲ.\n"
                "— This Kannada edition carries a 17th verse inside its 15-17 "
                "block which the Devanagari mula recension here does not list "
                "separately."))

        items.append({
            "id": mid,
            "reference": k.get("reference", ""),
            "sanskrit_text": "\n\n".join(parts),
            "tika_title": TIKA_TITLE,
            "unit_title": "",
            "artha": "",
            "section": "",
            "breadcrumb": ["ಜಯಂತೀ ನಿರ್ಣಯ", "ಕನ್ನಡ ಅನ್ವಯಾರ್ಥ"],
            "tags": ["kannada", "anvaya", "tika"],
            "notes": "",
            "references": [],
            "source": "",
            "audio": [],
        })

    out = {
        "schema": "grantha_tika_text",
        "default_author": "ಶ್ರೀ ಅಗ್ರಹಾರ ನಾರಾಯಣ ತಂತ್ರಿ",
        "tika_title": TIKA_TITLE,
        "source": src.get("source", ""),
        "source_note": src.get("source_note", ""),
        "publisher": src.get("publisher", ""),
        "items": items,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    covered = sum(1 for it in items if "【ಅನ್ವಯಾರ್ಥ】" in it["sanskrit_text"])
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    print("  items: %d (mula verses: %d)" % (len(items), len(mula_ids)))
    print("  with anvaya block: %d" % covered)
    print("  tatparya sections carried: %d ; colophon: %s ; invocation: %s"
          % (len(tat), bool(col), bool(inv)))


if __name__ == "__main__":
    main()
