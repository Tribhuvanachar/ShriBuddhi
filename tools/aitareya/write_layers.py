#!/usr/bin/env python3
"""
write_layers.py -- turn segmented Aitareya blocks into shelf `items`.

tools/aitareya/segment.py addresses each stretch of staged OCR to an
(āraṇyaka, adhyāya, khaṇḍa). This is the step after: it writes those
blocks into the shape the shelf actually reads --

    {"schema": "grantha_tika_text", "default_author": ..., "items": [...]}

each item carrying id, reference, section, unit_title, sanskrit_text,
breadcrumb, tika_title and layer, exactly as the four existing Aitareya
layers do.

`unit_title` is not invented. It is the mūla's opening words for that
khaṇḍa, and it is read from the shelf's own tika_bhashya item at the same
address -- so a new layer's units line up with the units already there,
which is what makes them stack in the reader rather than sit beside each
other unrelated. A block addressed to a khaṇḍa the shelf does not have is
reported and skipped, never given a made-up title.

One item per (address, layer): the volume's blocks for a khaṇḍa are
joined in page order. That matches the granularity the shelf already
uses -- tika_bhashya and tika_bhavapradipa are keyed at khaṇḍa level.

PROOFREADING GATE. The pipeline is: OCR -> Gemini proofread -> place ->
test -> merge. Raw OCR must not reach the corpus: the Maṇimañjarī case
showed what it hides (Sarvam read a Devanāgarī line as Kannada and a
306-verse work landed as 305, silently). So --write refuses unless the
staged file records a proofread pass, and --allow-unproofread is the
explicit, deliberate override.

  python3 tools/aitareya/write_layers.py                    # report
  python3 tools/aitareya/write_layers.py --write            # needs proofread
  python3 tools/aitareya/write_layers.py --write --allow-unproofread
"""
from __future__ import annotations

import argparse
import json
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGED = ROOT / "data/ocr_staging/aitareya"
TARGET = ROOT / ("data/darshana/vedanta/dvaita/DvaitaVedantaIn/"
                 "upanishad_prasthana/aitareyopanishad_bhashya")
REF_LAYER = TARGET / "tika_bhashya/data.json"

SCHEMA = "grantha_tika_text"

# Layer directory -> (display name used in `layer`/`tika_title`, author).
LAYER_META = {
    "tika_bhavapradipa": ("भावप्रदीप", "भगवन्तरायकृतः"),
    "tika_bhashyartha_ratnamala": ("भाष्यार्थरत्नमाला", "भाष्यार्थरत्नमालाकारः"),
    "tika_khandartha": ("खण्डार्थः", "खण्डार्थकारः"),
    "tika_upanishat": ("उपनिषत्", ""),
    "tika_bhashya": ("भाष्यम्", "आनन्दतीर्थभगवत्पादाचार्यः"),
}

# Layers already on the shelf. Writing over one replaces a text a reader
# can see today, so it needs saying out loud rather than happening.
EXISTING = {"mula", "tika_bhashya", "tika_upanishat", "tika_bhavapradipa"}

ADHYAYA_NUM = {"प्रथमोऽध्यायः": 1, "द्वितीयोऽध्यायः": 2, "तृतीयोऽध्यायः": 3,
               "चतुर्थोऽध्यायः": 4, "पञ्चमोऽध्यायः": 5, "षष्ठोऽध्यायः": 6,
               "सप्तमोऽध्यायः": 7, "अष्टमोऽध्यायः": 8}
KHANDA_NUM = {"प्रथम: खण्ड:": 1, "द्वितीय: खण्ड:": 2, "तृतीय: खण्ड:": 3,
              "चतुर्थ: खण्ड:": 4, "पञ्चम: खण्ड:": 5, "षष्ट: खण्ड:": 6,
              "सप्तम: खण्ड:": 7, "अष्टम: खण्ड:": 8}
ARANYAKA_NAME = {2: "द्वितीयारण्यके", 3: "तृतीयारण्यके"}


def shelf_units() -> dict[tuple, dict]:
    """(āraṇyaka, adhyāya, khaṇḍa) -> the shelf's own unit for it."""
    out: dict[tuple, dict] = {}
    for x in json.loads(REF_LAYER.read_text())["items"]:
        parts = x["reference"].split(" > ")
        if len(parts) < 7:
            continue
        addr = tuple(parts[3:6])
        out.setdefault(addr, {"unit_title": x.get("unit_title") or parts[6],
                              "breadcrumb_head": parts[:3]})
    return out


def address_of(block: dict) -> tuple | None:
    """A block's (āraṇyaka, adhyāya, khaṇḍa) as shelf names.

    ratnamala's blocks carry the names directly, from matching the shelf.
    bhagavantaraya's carry the numbers its running head prints, which are
    mapped here -- that mapping is the whole reason its coordinate is
    usable: the running head states the same address the shelf uses.
    """
    if block.get("adhyaya_name"):
        return (block["aranyaka_name"], block["adhyaya_name"], block["khanda_name"])
    a, ad, kh = block.get("aranyaka"), block.get("adhyaya"), block.get("khanda")
    if not (a and ad and kh):
        return None
    ar = ARANYAKA_NAME.get(a)
    adn = next((k for k, v in ADHYAYA_NUM.items() if v == ad), None)
    khn = next((k for k, v in KHANDA_NUM.items() if v == kh), None)
    return (ar, adn, khn) if ar and adn and khn else None


def build(volume: str, blocks: list[dict], shelf: dict) -> tuple[dict, dict]:
    by_layer: dict[str, dict[tuple, list]] = defaultdict(lambda: defaultdict(list))
    stats = {"placed": 0, "no_address": 0, "address_not_on_shelf": 0, "empty": 0,
             "proofread_text": 0, "raw_text": 0}
    srcs: dict[tuple, list] = {}
    for b in blocks:
        # The proofread text is the point of proofreading. An earlier version
        # of this read b["text"] unconditionally, which would have paid for a
        # Gemini pass over 1,406 blocks, written the result to disk, and then
        # shelved the raw OCR anyway -- a failure that costs money and leaves
        # no trace, since the output would look perfectly well-formed.
        proofed = (b.get("text_proofread") or "").strip()
        text = proofed or (b.get("text") or "").strip()
        stats["proofread_text" if proofed else "raw_text"] += 1
        if not text:
            stats["empty"] += 1
            continue
        addr = address_of(b)
        if addr is None:
            stats["no_address"] += 1
            continue
        if addr not in shelf:
            stats["address_not_on_shelf"] += 1
            continue
        by_layer[b["layer"]][addr].append((b.get("page") or 0, text))
        srcs.setdefault(addr, []).append(bool(proofed))
        stats["placed"] += 1

    files: dict[str, dict] = {}
    for layer, addrs in by_layer.items():
        name, author = LAYER_META.get(layer, (layer, ""))
        items = []
        ordered = sorted(addrs, key=lambda a: (ARANYAKA_NAME and
                                               [k for k, v in ARANYAKA_NAME.items() if v == a[0]][0],
                                               ADHYAYA_NUM.get(a[1], 99),
                                               KHANDA_NUM.get(a[2], 99)))
        for n, addr in enumerate(ordered, 1):
            unit = shelf[addr]
            title = unit["unit_title"]
            body = "\n".join(t for _, t in sorted(addrs[addr]))
            crumb = unit["breadcrumb_head"] + [addr[0], addr[1], addr[2], title]
            items.append(OrderedDict([
                ("id", f"AIT_{layer}_{n:04d}"),
                ("reference", " > ".join(crumb)),
                ("section", addr[2]),
                ("unit_title", title),
                ("sanskrit_text", body),
                ("artha", ""), ("notes", ""), ("tags", []),
                ("references", []), ("audio", []),
                ("breadcrumb", crumb),
                ("tika_title", name),
                ("layer", name),
                ("provenance", {
                    "from": f"data/ocr_staging/aitareya/{volume}_segmented.json",
                    "how": "OCR, segmented by tools/aitareya/segment.py, "
                           "addressed against this shelf's tika_bhashya",
                    "text": ("Gemini-proofread" if all(
                        srcs[addr]) else "raw OCR, NOT proofread"),
                }),
            ]))
        files[layer] = {"schema": SCHEMA, "default_author": author, "items": items}
    return files, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-unproofread", action="store_true")
    ap.add_argument("--volumes", default="bhagavantaraya,ratnamala")
    args = ap.parse_args()

    shelf = shelf_units()
    print(f"shelf addresses available: {len(shelf)}\n")
    pending_write = []

    for vol in args.volumes.split(","):
        src = STAGED / f"{vol}_segmented.json"
        if not src.exists():
            print(f"== {vol}: no staged file at {src.relative_to(ROOT)} -- run segment.py --write first\n")
            continue
        doc = json.loads(src.read_text())
        proofread = bool(doc.get("proofread"))
        files, stats = build(vol, doc["blocks"], shelf)
        print(f"== {vol}   proofread: {proofread}")
        print(f"   blocks    : {stats}")
        for layer, payload in sorted(files.items()):
            n = len(payload["items"])
            chars = sum(len(i["sanskrit_text"]) for i in payload["items"])
            flag = "  [REPLACES an existing layer]" if layer in EXISTING else "  [new layer]"
            print(f"   {layer:<30} {n:>3} items  {chars:>8,} chars{flag}")
        print()
        pending_write.append((vol, proofread, files))

    if not args.write:
        print("(dry run -- pass --write to emit)")
        return 0

    wrote = 0
    for vol, proofread, files in pending_write:
        if not proofread and not args.allow_unproofread:
            print(f"refusing to write {vol}: the staged file records no Gemini "
                  f"proofread pass.\nThe pipeline is OCR -> proofread -> place -> "
                  f"test -> merge, and raw OCR hides exactly the kind of fault "
                  f"that cost\nManimanjari a verse. Pass --allow-unproofread to "
                  f"override deliberately.")
            continue
        for layer, payload in files.items():
            d = TARGET / layer
            d.mkdir(parents=True, exist_ok=True)
            (d / "data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
            wrote += 1
        print(f"wrote {len(files)} layers for {vol}")
    return 0 if wrote or not args.write else 1


if __name__ == "__main__":
    raise SystemExit(main())
