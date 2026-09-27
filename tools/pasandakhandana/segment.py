#!/usr/bin/env python3
"""Segment the staged Pāṣaṇḍakhaṇḍanam into addressed verses.

पाषण्डखण्डनम् of Śrī Vādirāja Tīrtha with the vyākhyā of Śrī Surottama Tīrtha.
50 pages of Sarvam Document AI covering 4-53 with no gaps, and a Google Vision
pass over 1-53.

WHAT THE EDITION GIVES US, counted across all 50 pages:

  * ONE CONTINUOUS RUN of verse numbers, 1 to 129, with no gaps at all.
  * THE VERSE AND ITS COMMENTARY BOTH CLOSE WITH ॥ N ॥, the verse first. So
    the marker alone does not say which a block is -- exactly as in Rukmiṇīśa
    Vijaya -- and the FIRST block to close on a number is the verse.
  * NO LAYOUT TAG SEPARATES THEM. Almost everything is data-layout="paragraph";
    the 26 section-title blocks are scattered and mean nothing here. (In the
    Veṅkaṭeśa Māhātmya that same tag marks the commentary heading. Which book
    is which has to be counted, not assumed.)
  * The commentary QUOTES earlier verses: 13 again on p37 and 17 on p39, in a
    run that has reached 92 and 96 and goes on rising. A number far below the
    running maximum is a quotation, not a restart.

    python3 tools/pasandakhandana/segment.py --staged-dir <dir>
"""

from __future__ import annotations

import argparse
import collections
import re
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ocr_common"))
import staged as S  # noqa: E402

# A verse is printed a line or two at a time. Anything longer that carries no
# marker is the commentary running on, and must not be swept into the verse.
MAX_VERSE_LINE = 130
# A verse is at most a few lines. Without a bound the run before a marker
# swallowed whatever preceded it -- verse 1 came out carrying the half-title,
# the publisher's imprint and the maṅgala, 354 characters of front matter.
MAX_VERSE_LINES = 3
MAX_VERSE_CHARS = 200
# A verse LINE waiting for its marker is one pāda: measured across the book
# they run 32 to 49 characters. Admitting anything up to MAX_VERSE_LINE let in
# the 76-character half-title and 104 characters of gloss continuation, which
# came out inside verses 1 and 2.
MAX_PENDING_LINE = 60
# Title and colophon lines, which belong to no verse.
TITLE_LINE = re.compile(r"विरचित|सव्याख्यम्|व्याख्या\s*॥|श्रीहयग्रीवाय")
# The work's own opening. Everything before it is the volume's front matter --
# हृदयवाणी, the imprint, the series note -- and belongs to no verse.
OPENING = re.compile(r"अथ\s+श्रीमद्वादिराज.*?पाषण्डखण्डनम्|अथ\s+पाषण्डखण्डनं")


def segment(pages: dict[int, str]) -> dict:
    """Address every verse, with its vyākhyā.

    Two passes, because one is not enough. Several blocks close on the same
    number -- p15 has three on ॥ २६ ॥: 794 characters of gloss, then the
    84-character verse, then 437 more of gloss -- so which block is the verse
    cannot be decided as each arrives. Taking the FIRST closer made the 794
    the verse and filed the real one as commentary; taking the SHORTEST would
    break verse 24, whose verse is 85 characters and whose gloss tail is 46.

    It is the first VERSE-SHAPED closer: first in the edition's order, short
    enough to be two pādas. Everything else on that number is the gloss.
    """
    stream = S.read_stream(pages, skip=S.FURNITURE + ("footnote",))
    start = next((i for i, b in enumerate(stream) if OPENING.search(b["text"])), 0)
    front_matter = stream[:start]
    stream = stream[start:]

    stats = collections.Counter()
    slots: dict[int, list[dict]] = collections.defaultdict(list)
    loose: dict[int, list[dict]] = collections.defaultdict(list)
    pending: list[dict] = []
    running_max = 0

    for b in stream:
        n = S.closing_number(b["text"])
        if n is None:
            if (len(b["text"]) <= MAX_PENDING_LINE
                    and not TITLE_LINE.search(b["text"])):
                pending.append(b)
                while (len(pending) > MAX_VERSE_LINES
                       or sum(len(x["text"]) for x in pending) > MAX_VERSE_CHARS):
                    pending.pop(0)
            else:
                if running_max:
                    loose[running_max].append(b)
                pending = []
            continue
        if n < 1 or S.is_quotation(n, running_max):
            stats["quotations"] += 1
            if running_max:
                loose[running_max].append(b)
            continue
        b = {**b, "run": [x["text"] for x in pending]}
        pending = []
        slots[n].append(b)
        running_max = max(running_max, n)

    verses: dict[int, dict] = {}
    comments: dict[int, list[str]] = collections.defaultdict(list)
    for n, blocks in slots.items():
        verse = next((b for b in blocks if len(b["text"]) <= MAX_VERSE_LINE), None)
        if verse is not None:
            verses[n] = {"verse": n, "page": verse["page"],
                         "text": "\n".join(verse["run"] + [verse["text"]])}
            stats["verses"] += 1
        else:
            # No block on this number is verse-shaped, so the verse lost its
            # own marker. Its lines are still there, in the run that had
            # accumulated before the gloss closed: 93 is
            # स्वयं सञ्चरतो वायोः… with only the gloss carrying ॥ ९३ ॥.
            run = next((b["run"] for b in blocks if b["run"]), [])
            if run and 30 <= sum(len(x) for x in run) <= MAX_VERSE_CHARS:
                verses[n] = {"verse": n, "page": blocks[0]["page"],
                             "text": "\n".join(run)}
                stats["verse_from_the_run_above_its_gloss"] += 1
            else:
                stats["no_verse_shaped_block"] += 1
        for b in blocks:
            if b is not verse:
                comments[n].append(b["text"])
                stats["commentary_blocks"] += 1
        for b in loose.get(n, []):
            comments[n].append(b["text"])

    for n, parts in comments.items():
        if n in verses:
            verses[n]["commentary"] = "\n".join(parts).strip()

    got = sorted(verses)
    high = max(got) if got else 0
    return {
        **S.page_report(pages),
        "verses_found": len(got),
        "highest": high,
        "missing": [i for i in range(1, high + 1) if i not in verses],
        "with_commentary": sum(1 for v in verses.values() if v.get("commentary")),
        "front_matter_blocks": len(front_matter),
        "stats": dict(stats),
        "verses": verses,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir", required=True)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    pages = S.load_sarvam(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    rep = segment(pages)
    print(f"pages {rep['pages']} ({rep['page_range'][0]}-{rep['page_range'][1]}), "
          f"gaps {len(rep['page_gaps'])}")
    print(f"{rep['verses_found']} verses, highest {rep['highest']}, "
          f"missing {len(rep['missing'])} {rep['missing'][:10]}")
    print(f"   {rep['with_commentary']} carry the vyākhyā;  {rep['stats']}")
    if args.json:
        out = dict(rep)
        out["verses"] = [v for _, v in sorted(rep["verses"].items())]
        json.dump(out, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("report written to", args.json)
    return 0 if not rep["missing"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
