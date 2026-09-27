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
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGED = ROOT / "data/ocr_staging/aitareya"
TARGET = ROOT / ("data/darshana/vedanta/dvaita/DvaitaVedantaIn/"
                 "upanishad_prasthana/aitareyopanishad_bhashya")
REF_LAYER = TARGET / "mula/data.json"

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
# Both spellings of each khaṇḍa occur and they are the SAME khaṇḍa. The shelf
# writes the seventh as सप्त: खण्ड: and the ṭippaṇī's running head as
# सप्तम: खण्ड:; matching on the string dropped 23 blocks that had a home all
# along. Addresses are therefore compared as NUMBERS, never as names -- see
# shelf_units() and address_of() -- so a further spelling costs one line here
# instead of silently losing a khaṇḍa.
KHANDA_NUM = {"प्रथम: खण्ड:": 1, "द्वितीय: खण्ड:": 2, "तृतीय: खण्ड:": 3,
              "चतुर्थ: खण्ड:": 4, "पञ्चम: खण्ड:": 5,
              "षष्ट: खण्ड:": 6, "षष्ठ: खण्ड:": 6,
              "सप्त: खण्ड:": 7, "सप्तम: खण्ड:": 7,
              "अष्टम: खण्ड:": 8}
ARANYAKA_NUM = {"द्वितीयारण्यके": 2, "तृतीयारण्यके": 3}
ARANYAKA_NAME = {2: "द्वितीयारण्यके", 3: "तृतीयारण्यके"}


def shelf_units() -> dict[tuple, dict]:
    """(āraṇyaka, adhyāya, khaṇḍa) AS NUMBERS -> the shelf's own unit for it.

    Keyed numerically so a difference of spelling between the shelf and a
    ṭippaṇī's running head cannot hide a khaṇḍa, and the names the shelf uses
    travel in the value so the emitted breadcrumb still reads as the shelf
    writes it.

    THE REFERENCE LAYER IS THE MŪLA. It used to be tika_bhashya, which is a
    commentary and carries 31 of the mūla's 38 khaṇḍas -- so seven khaṇḍas that
    exist in the text had no address, and every block addressed to one was
    counted "not on shelf" and dropped. That silently cost 153 blocks, among
    them the WHOLE of Viśveśvara Tīrtha's ṭīkā (298 blocks, 453,151 characters),
    which looked like a deliberate hold rather than a bug. The mūla is what
    defines where a commentary can attach; a commentary is not.
    """
    out: dict[tuple, dict] = {}
    for x in json.loads(REF_LAYER.read_text())["items"]:
        parts = x["reference"].split(" > ")
        if len(parts) < 7:
            continue
        names = tuple(parts[3:6])
        addr = (ARANYAKA_NUM.get(names[0]), ADHYAYA_NUM.get(names[1]),
                KHANDA_NUM.get(names[2]))
        if None in addr:
            continue
        out.setdefault(addr, {"unit_title": x.get("unit_title") or parts[6],
                              "breadcrumb_head": parts[:3], "names": names})
    return out


def address_of(block: dict) -> tuple | None:
    """A block's (āraṇyaka, adhyāya, khaṇḍa) as shelf names.

    ratnamala's blocks carry the names directly, from matching the shelf.
    bhagavantaraya's carry the numbers its running head prints, which are
    mapped here -- that mapping is the whole reason its coordinate is
    usable: the running head states the same address the shelf uses.
    """
    if block.get("adhyaya_name"):
        addr = (ARANYAKA_NUM.get(block["aranyaka_name"]),
                ADHYAYA_NUM.get(block["adhyaya_name"]),
                KHANDA_NUM.get(block["khanda_name"]))
        return None if None in addr else addr
    a, ad, kh = block.get("aranyaka"), block.get("adhyaya"), block.get("khanda")
    if not (a and ad and kh):
        return None
    # The NUMBERS must be ones the edition actually uses. Returning a triple
    # for adhyāya 99 would hand a nonsense address to the shelf lookup, which
    # would then count it "not on shelf" -- indistinguishable from a khaṇḍa
    # the volume genuinely does not cover.
    if a not in ARANYAKA_NAME or ad not in ADHYAYA_NUM.values() \
            or kh not in KHANDA_NUM.values():
        return None
    return (a, ad, kh)


FRONT_MATTER = (0, 0, 0)


def FRONT_MATTER_UNIT(shelf: dict) -> dict:
    """The volume's own opening -- maṅgalācaraṇam and the history of the
    Upaniṣad -- which belongs to the work rather than to any khaṇḍa. It borrows
    the shelf's breadcrumb head so it reads as part of the same text."""
    head = next(iter(shelf.values()))["breadcrumb_head"] if shelf else []
    return {"unit_title": "मङ्गलाचरणम् — उपनिषद इतिहासश्च",
            "breadcrumb_head": head,
            "names": ("ग्रन्थारम्भः", "", "")}


def _devanagari(s: str) -> str:
    return re.sub(r"[^\u0900-\u097F]", "", s or "")


def anchor_unaddressed(blocks: list[dict], shelf: dict) -> dict:
    """Give an address to the blocks that open a volume, before its running
    head starts printing one.

    ratnamala's first 25 blocks carry no coordinate at all: they are the first
    seventeen pages, printed before the section labels its segmenter reads
    begin. They are not a decision about what belongs on the shelf -- they are
    the commentary on Āraṇyaka 2.1.1 and 2.1.2, plus the volume's own front
    matter.

    Placed the way the rest of this pipeline places things: on an anchor the
    EDITION supplies, not on a guess. Three of the blocks quote a shelf unit's
    opening words, and a gloss runs from the block that quotes until the next
    one does, so each anchor carries its continuation blocks with it. The
    result is checked for the two things that would make it wrong -- the
    anchors must appear in shelf order and each run must be contiguous -- and
    the whole pass is abandoned if either fails, because a wrong address is
    worse than none: a hole is visible and a wrong address is not.

    Blocks before the FIRST anchor are the volume's front matter -- the
    maṅgalācaraṇam and the history of the Upaniṣad -- which belong to the work
    and not to any khaṇḍa. They get FRONT_MATTER, which sorts before khaṇḍa 1.
    """
    titles = [(a, _devanagari(u["unit_title"])) for a, u in shelf.items()]
    out: dict[int, tuple] = {}
    current = None
    anchors: list[tuple] = []
    for i, b in enumerate(blocks):
        text = _devanagari(b.get("text_proofread") or b.get("text") or "")
        hits = sorted({a for a, t in titles if len(t) >= 12 and t[:12] in text})
        if len(hits) == 1 and hits[0] != current:
            current = hits[0]
            anchors.append(current)
        out[i] = current or FRONT_MATTER
    if anchors != sorted(anchors):
        return {}                       # anchors out of order: do not guess
    seen: list[tuple] = []
    for i in sorted(out):               # each address must be one unbroken run
        if not seen or seen[-1] != out[i]:
            if out[i] in seen:
                return {}
            seen.append(out[i])
    return out


def build(volume: str, blocks: list[dict], shelf: dict) -> tuple[dict, dict]:
    by_layer: dict[str, dict[tuple, list]] = defaultdict(lambda: defaultdict(list))
    stats = {"placed": 0, "no_address": 0, "address_not_on_shelf": 0, "empty": 0,
             "anchored": 0, "front_matter": 0, "proofread_text": 0, "raw_text": 0}
    srcs: dict[tuple, list] = {}
    # Blocks the running head never gave a coordinate to, anchored on the mūla
    # the edition itself quotes. Empty when that could not be done safely.
    unaddressed = [b for b in blocks if address_of(b) is None]
    anchored = anchor_unaddressed(unaddressed, shelf) if unaddressed else {}
    anchored_by_id = {id(b): anchored[i] for i, b in enumerate(unaddressed)
                      if i in anchored}
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
            addr = anchored_by_id.get(id(b))
            if addr is None:
                stats["no_address"] += 1
                continue
            stats["front_matter" if addr == FRONT_MATTER else "anchored"] += 1
        if addr not in shelf and addr != FRONT_MATTER:
            stats["address_not_on_shelf"] += 1
            continue
        by_layer[b["layer"]][addr].append((b.get("page") or 0, text))
        srcs.setdefault(addr, []).append(bool(proofed))
        stats["placed"] += 1

    files: dict[str, dict] = {}
    for layer, addrs in by_layer.items():
        name, author = LAYER_META.get(layer, (layer, ""))
        items = []
        ordered = sorted(addrs)          # addresses are numeric triples
        for n, addr in enumerate(ordered, 1):
            unit = shelf.get(addr) or FRONT_MATTER_UNIT(shelf)
            title = unit["unit_title"]
            body = "\n".join(t for _, t in sorted(addrs[addr]))
            # The SHELF's own spelling of the address, not the ṭippaṇī's, so a
            # commentary's breadcrumb reads exactly as the mūla's does beside it.
            names = [x for x in unit["names"] if x]
            crumb = unit["breadcrumb_head"] + names + [title]
            items.append(OrderedDict([
                ("id", f"AIT_{layer}_{n:04d}"),
                ("reference", " > ".join(crumb)),
                ("section", names[2] if len(names) > 2 else names[0]),
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


def _canonical(payload: dict) -> str | None:
    """format_data_json's serialisation, or None if it declines this shape."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "format_data_json", Path(__file__).resolve().parents[1] / "format_data_json.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.canonical(payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-unproofread", action="store_true")
    ap.add_argument("--volumes", default="bhagavantaraya,ratnamala")
    args = ap.parse_args()

    shelf = shelf_units()
    print(f"shelf addresses available: {len(shelf)}\n")
    pending_write = []
    stats_of: dict[str, dict] = {}

    for vol in args.volumes.split(","):
        src = STAGED / f"{vol}_segmented.json"
        if not src.exists():
            print(f"== {vol}: no staged file at {src.relative_to(ROOT)} -- run segment.py --write first\n")
            continue
        doc = json.loads(src.read_text())
        files, stats = build(vol, doc["blocks"], shelf)
        # DERIVED, not declared. This used to read doc["proofread"], a
        # file-level flag that nothing in the pipeline ever writes -- not
        # proofread.py, not land_proofread.py -- so the gate read False for
        # three volumes that were 100% proofread and would have read True for
        # a file where somebody had simply set the key. build() already
        # counts, per block, whether the text it took came from
        # text_proofread or fell back to raw OCR. That count is the thing the
        # gate is actually about.
        proofread = stats["raw_text"] == 0 and stats["proofread_text"] > 0
        print(f"== {vol}   proofread: {proofread}")
        print(f"   blocks    : {stats}")
        for layer, payload in sorted(files.items()):
            n = len(payload["items"])
            chars = sum(len(i["sanskrit_text"]) for i in payload["items"])
            flag = "  [REPLACES an existing layer]" if layer in EXISTING else "  [new layer]"
            print(f"   {layer:<30} {n:>3} items  {chars:>8,} chars{flag}")
        print()
        stats_of[vol] = stats
        pending_write.append((vol, proofread, files))

    if not args.write:
        print("(dry run -- pass --write to emit)")
        return 0

    wrote = 0
    for vol, proofread, files in pending_write:
        if not proofread and not args.allow_unproofread:
            print(f"refusing to write {vol}: {stats_of[vol]['raw_text']} block(s) "
                  f"would land as raw OCR.\nThe pipeline is OCR -> proofread -> place -> "
                  f"test -> merge, and raw OCR hides exactly the kind of fault "
                  f"that cost\nManimanjari a verse. Pass --allow-unproofread to "
                  f"override deliberately.")
            continue
        for layer, payload in files.items():
            d = TARGET / layer
            d.mkdir(parents=True, exist_ok=True)
            # CANONICAL SHAPE, not json.dumps'. The corpus has one agreed
            # serialisation and tests/test_content_editing_tools.py asserts
            # every data.json is in it. Writing indent=1 by hand put all six
            # Aitareya layers out of shape the moment they landed, exactly as
            # the Manimanjari splice had done five days earlier. Formatting
            # the corpus is format_data_json's job; do not reimplement it.
            text = _canonical(payload) or (
                json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
            (d / "data.json").write_text(text, encoding="utf-8")
            wrote += 1
        print(f"wrote {len(files)} layers for {vol}")
    return 0 if wrote or not args.write else 1


if __name__ == "__main__":
    raise SystemExit(main())
