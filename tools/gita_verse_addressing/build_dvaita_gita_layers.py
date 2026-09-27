#!/usr/bin/env python3
"""Stitch the corpus's verse-keyed Dvaita Gītā commentaries onto DvaitaVedantaIn.

WHAT WAS MISSING. `data/itihasa/bhagavad_gita` carries the Gītā verse by verse
with 22 commentators hanging off each śloka. Nine of those are Dvaita-tradition
works that DvaitaVedantaIn's own gītā tree does NOT have, so a reader opening
श्रीमद्भगवद्गीताभाष्यम् there could not reach them at all. They could not simply
be advertised as layers either: they are addressed adhyāya.śloka, and
DvaitaVedantaIn's spine knew only the importer's `SM26:N` counter (measured: 0
of 700 joined). tools/gita_verse_addressing/add_verse_refs.py gave that spine
verse addresses; this tool writes the layers that use them.

ONE OF THE NINE IS NOT A DUPLICATE OF WHAT IS THERE, despite the name.
DvaitaVedantaIn's `tika_bhashya` is not Madhva's bhāṣya: every one of its units
is the bhāṣya CONCATENATED with all its ṭīkās ("भाष्यम् / प्रमेयदीपिका /
भावप्रदीपिका / …"), the source's all-layers-on-one-page view filed as a single
layer — which is why it runs to 2.4 MB and why its 694 units collapse onto only
362 verses. The bare bhāṣya, one unit per verse, was genuinely absent.
`tika_prameyadipika` is likewise partial (365 units, 202 KB) against the
verse-keyed copy's 700 units and 453 KB.

DERIVED, NOT COPIED BY HAND. Everything here is generated from the verse tree
and nothing else, so the two locations cannot silently drift:
tests/test_dvaita_gita_layers.py regenerates and compares.

ADHYĀYA 1 LANDS NOWHERE, and that is the edition, not a bug: DvaitaVedanta.in
carries Madhva's first-adhyāya bhāṣya as one summary unit rather than verse by
verse, so the spine has no unit for 1.1–1.47. Those units are counted and
reported as unplaceable rather than forced onto a neighbouring verse.

Usage: python3 tools/gita_verse_addressing/build_dvaita_gita_layers.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSE_TREE = Path("data/itihasa/bhagavad_gita")
TARGET = Path("data/darshana/vedanta/dvaita/DvaitaVedantaIn/gita_prasthana"
              "/gita_bhashya")
SPINE = TARGET / "mula" / "data.json"

# commentator-as-recorded-in-the-verse-tree -> the layer it becomes here.
# `folder` must start with tika_ (tools/build_layer_manifest.py discovers
# layers by that prefix and js/layer-stitch.js keys the commentary tab off the
# name with the prefix stripped). `label` is the tab label and is the work's
# own traditional title -- never an edition or a site name, which would be
# published provenance (CLAUDE.md).
ROSTER = [
    # (commentator in verse tree, folder, label, author, field)
    ("Sri Madhavacharya",
     "tika_gitabhashya", "गीताभाष्यम्",
     "श्रीमदानन्दतीर्थभगवत्पादाचार्यः", "sanskrit_text"),
    # A SECOND witness of the Prameyadipika, not a replacement for the
    # tika_prameyadipika already here and not the "complete" text either:
    # measured by verse, the existing copy has 24 verses this one lacks and
    # this one has 60 the existing lacks (356 shared). Labelled as the variant
    # recension it is, because calling it सम्पूर्णा would claim a completeness
    # neither copy has.
    ("Sri Jayatritha",
     "tika_prameyadipika_antara", "प्रमेयदीपिका (पाठान्तरम्)",
     "श्रीजयतीर्थः", "sanskrit_text"),
    ("Śrī Rāghavendra Tīrtha (Gītāsārasaṅgraha)",
     "tika_gitasarasangraha", "गीतासारसङ्ग्रहः",
     "श्रीराघवेन्द्रतीर्थः", "sanskrit_text"),
    ("Śrī Rāghavendra Yati (Gītānvayaprakāśikā)",
     "tika_gitanvayaprakashika", "गीतान्वयप्रकाशिका",
     "श्रीराघवेन्द्रयतिः", "sanskrit_text"),
    ("Śrī Vidyādhirāja Tīrtha (Gītāvivṛti)",
     "tika_gitavivrti", "गीताविवृतिः",
     "श्रीविद्याधिराजतीर्थः", "sanskrit_text"),
    ("Śrī Vādirāja Tīrtha (Gītālakṣālaṅkāra)",
     "tika_gitalakshalankara", "गीतालक्षालङ्कारः",
     "श्रीवादिराजतीर्थः", "sanskrit_text"),
    ("Pāṅgarī Śrīnivāsācārya (Trividhārthavivṛti)",
     "tika_trividharthavivrti", "त्रिविधार्थविवृतिः",
     "पाङ्गरी श्रीनिवासाचार्यः", "sanskrit_text"),
    ("Dr. Giridhar Boray (English, after Rāghavendra Tīrtha's Gītāvivṛti)",
     "tika_anuvada_gitavivrti", "Gītāvivṛti (English)",
     "Dr. Giridhar Boray", "text"),
    ("Prof. Gururao V. Nadgouda & Smt. Indira Nadgouda (English)",
     "tika_anuvada_english", "English translation",
     "Prof. Gururao V. Nadgouda & Smt. Indira Nadgouda", "text"),
]


# The source of the verse-keyed bhāṣyas records a verse the commentator PASSED
# OVER with a sentence saying so ("।।2.1।।Sri Madhvacharya did not comment on
# this sloka. The commentary starts from 2.11."). That is a note about the
# edition, not commentary, and 479 of them were about to ship as if Madhva and
# Jayatīrtha had written them -- caught by reading the rendered page, not the
# data. A verse the commentator skipped should show nothing under his tab.
# Anchored and length-bounded so it can only ever match a unit that is WHOLLY
# such a notice, never a real commentary that happens to discuss one.
VERSE_MARKER = re.compile(r"^\s*।।\s*[\d.]+\s*।।\s*")
SKIPPED_NOTICE = re.compile(
    r"^.{0,80}?did not comment on this [sś]h?loka\b.{0,80}$", re.I | re.S)


def is_skipped_notice(text: str) -> bool:
    return bool(SKIPPED_NOTICE.match(VERSE_MARKER.sub("", text).strip()))


def spine_refs() -> set[str]:
    with SPINE.open(encoding="utf-8") as f:
        data = json.load(f)
    return {r for it in data["items"] for r in (it.get("verse_refs") or [])}


def read_verse_tree() -> dict[str, dict[str, str]]:
    """{commentator: {"2.47": text}} over all eighteen adhyāyas."""
    out: dict[str, dict[str, str]] = {}
    for n in range(1, 19):
        path = VERSE_TREE / f"adhyaya_{n:02d}" / "data.json"
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        for item in data["items"]:
            for shloka in item.get("shlokas") or []:
                ref = f"{n}.{shloka.get('number')}"
                for b in shloka.get("bhashya") or []:
                    text = (b.get("text") or "").strip()
                    if not text or is_skipped_notice(text):
                        continue
                    # One commentator can contribute more than once to a verse
                    # (a translation plus its note); keep both, in file order.
                    per = out.setdefault(b.get("commentator") or "", {})
                    per[ref] = per[ref] + "\n\n" + text if ref in per else text
    return out


def build_layer(label, author, field, texts, refs) -> tuple[str, int, int]:
    """Serialise one layer file; return (text, placed, unplaceable)."""
    lines = [json.dumps({"schema": "grantha_tika_text",
                         "default_author": author},
                        ensure_ascii=False, separators=(",", ":"))[:-1] +
             ',"items":[']
    placed = unplaceable = 0
    body = []
    for ref in sorted(texts, key=lambda r: tuple(int(x) for x in r.split("."))):
        if ref not in refs:
            unplaceable += 1
            continue
        placed += 1
        body.append(json.dumps(
            {"id": f"{label}:{ref}", "ref": ref, "tika_title": label,
             field: texts[ref]},
            ensure_ascii=False, separators=(",", ":")))
    lines.append(",\n".join(body))
    lines.append("]}")
    return lines[0] + "\n" + lines[1] + "\n" + lines[2] + "\n", placed, unplaceable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="compare against what is committed; write nothing")
    args = ap.parse_args()

    refs = spine_refs()
    if not refs:
        print("spine carries no verse_refs -- run add_verse_refs.py first",
              file=sys.stderr)
        return 1
    tree = read_verse_tree()
    print(f"spine: {len(refs)} verse addresses")

    stale = []
    for commentator, folder, label, author, field in ROSTER:
        texts = tree.get(commentator)
        if not texts:
            print(f"  MISSING from verse tree: {commentator}", file=sys.stderr)
            return 1
        text, placed, unplaceable = build_layer(label, author, field, texts, refs)
        out = TARGET / folder / "data.json"
        current = out.read_text(encoding="utf-8") if out.is_file() else None
        print(f"  {folder:<30} {placed:>4} placed  {unplaceable:>3} unplaceable"
              f"  {len(text)//1024:>5} KB")
        if current == text:
            continue
        stale.append(folder)
        if not args.check:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
    if args.check:
        if stale:
            print("stale: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("all layers match the verse tree")
    else:
        print(f"wrote {len(stale)} layer(s)" if stale else "no change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
