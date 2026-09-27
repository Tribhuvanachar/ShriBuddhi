#!/usr/bin/env python3
"""A verse text printed with a commentary, both closing on ॥ N ॥.

The commonest shape in this corpus. Rukmiṇīśa Vijaya, the Pāṣaṇḍakhaṇḍana and
the Uṣāharaṇa are all printed this way, and each needed the same three
readings, so they are made once here.

    <verse, one or two pādas, closing ॥ N ॥>
    <commentary, opening by quoting the verse's first word, closing ॥ N ॥>

THE MARKER DOES NOT SAY WHICH A BLOCK IS, because the verse and its gloss both
close on the same number. Three rules settle it, and each was arrived at by
being wrong first:

  1. THE VERSE IS THE FIRST VERSE-SHAPED CLOSER on its number. Not simply the
     first -- page 15 of the Pāṣaṇḍakhaṇḍana puts 794 characters of gloss
     ahead of the verse, and taking the first filed the real verse as
     commentary. Not the shortest either -- verse 24 there is 85 characters
     and its gloss tail is 46. That needs TWO PASSES, because the block that
     settles a number may not have arrived yet.

  2. WHERE NO CLOSER IS VERSE-SHAPED, the verse lost its own marker and its
     lines are in the run that accumulated above the gloss.

  3. A LINE WAITING FOR ITS MARKER IS ONE PĀDA. Admitting anything up to the
     closer's limit swept half-titles and gloss continuations into verses.

A number far below the running maximum is a quotation, not a restart -- see
staged.is_quotation.
"""

from __future__ import annotations

import collections
import re
import pathlib
import sys
from typing import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import staged as S  # noqa: E402


def segment(pages: dict[int, str],
            section_of: Callable[[str, str], int | None] | None = None,
            *,
            max_verse: int = 200,
            min_verse: int = 25,
            max_pending_line: int = 90,
            max_pending_lines: int = 3,
            max_pending_chars: int = 260,
            drop_line: re.Pattern | None = None,
            skip_layouts: tuple[str, ...] = S.FURNITURE + ("footnote",),
            start_at: Callable[[str], bool] | None = None,
            ) -> dict:
    """Address every verse of a verse-plus-commentary text.

    `section_of(kind, text)` returns the sarga/adhyāya a block announces, or
    None. `drop_line` marks lines that belong to no verse (titles, colophons).
    `start_at(text)` marks where the work itself begins, so front matter is not
    swept into verse 1.
    """
    stream = S.read_stream(pages, skip=skip_layouts)
    if start_at is not None:
        i = next((i for i, b in enumerate(stream) if start_at(b["text"])), 0)
        stream = stream[i:]

    stats: collections.Counter = collections.Counter()
    slots: dict[tuple[int, int], list[dict]] = collections.defaultdict(list)
    loose: dict[tuple[int, int], list[dict]] = collections.defaultdict(list)
    # A work whose numbering runs straight through has one section, and
    # section_of is left out: the Bṛhatīsahasram numbers 1 to 1139 across
    # प्राग्भागः, three तृचाशीति sections and उत्तरभागः without restarting.
    section = None if section_of else 1
    running_max = 0
    pending: list[dict] = []

    for b in stream:
        s = section_of(b["kind"], b["text"]) if section_of else None
        if s is not None:
            if s != section:
                section, running_max, pending = s, 0, []
            continue
        if b["kind"] == "header" or section is None:
            continue
        n = S.closing_number(b["text"])
        if n is None:
            if (len(b["text"]) <= max_pending_line
                    and not (drop_line and drop_line.search(b["text"]))):
                pending.append(b)
                while (len(pending) > max_pending_lines
                       or sum(len(x["text"]) for x in pending) > max_pending_chars):
                    pending.pop(0)
            else:
                if running_max:
                    loose[(section, running_max)].append(b)
                pending = []
            continue
        if n < 1 or S.is_quotation(n, running_max):
            stats["quotations"] += 1
            if running_max:
                loose[(section, running_max)].append(b)
            continue
        slots[(section, n)].append({**b, "run": [x["text"] for x in pending]})
        pending = []
        # ONLY A VERSE-SHAPED BLOCK MOVES THE RUNNING MAXIMUM. A commentary
        # block on Uṣāharaṇa 7.57 closes with ॥ ७१ ॥ -- 627 characters of gloss
        # and a misread number -- and letting that advance the maximum made
        # every real verse from 58 to 70 look like a quotation. Thirteen
        # verses vanished on one bad digit, and nothing downstream would have
        # shown it: the sarga simply had a hole in the middle.
        if min_verse <= len(b["text"]) <= max_verse:
            running_max = max(running_max, n)

    units: dict[tuple[int, int], dict] = {}
    comments: dict[tuple[int, int], list[str]] = collections.defaultdict(list)
    for key, blocks in slots.items():
        # A BARE ॥ N ॥ BLOCK IS NOT A VERSE. Without a floor, 78 of the
        # Uṣāharaṇa's addresses came out as five characters -- the marker and
        # nothing else -- which is the failure that took Rukmiṇīśa Vijaya off
        # the shelf, arriving by a different road.
        verse = next((b for b in blocks
                      if min_verse <= len(b["text"]) <= max_verse), None)
        if verse is not None:
            units[key] = {"section": key[0], "verse": key[1],
                          "page": verse["page"],
                          "text": "\n".join(verse["run"] + [verse["text"]])}
            stats["by_marker"] += 1
        else:
            run = next((b["run"] for b in blocks if b["run"]), [])
            if run and 30 <= sum(len(x) for x in run) <= max_pending_chars:
                units[key] = {"section": key[0], "verse": key[1],
                              "page": blocks[0]["page"], "text": "\n".join(run)}
                stats["from_the_run_above_its_gloss"] += 1
            else:
                stats["no_verse_shaped_block"] += 1
        for b in blocks:
            if b is not verse:
                comments[key].append(b["text"])
        for b in loose.get(key, []):
            comments[key].append(b["text"])

    for key, parts in comments.items():
        if key in units:
            body = "\n".join(parts).strip()
            if body:
                units[key]["commentary"] = body

    per: dict[int, list[int]] = collections.defaultdict(list)
    for (s, n) in units:
        per[s].append(n)
    sections = []
    for s in sorted(per):
        got = sorted(per[s])
        hi = max(got)
        sections.append({"section": s, "found": len(got), "highest": hi,
                         "missing": [i for i in range(1, hi + 1)
                                     if i not in set(got)]})
    return {
        **S.page_report(pages),
        "stats": dict(stats),
        "sections": sections,
        "verses_found": sum(x["found"] for x in sections),
        "verses_missing": sum(len(x["missing"]) for x in sections),
        "with_commentary": sum(1 for v in units.values() if v.get("commentary")),
        "units": units,
    }


def quality(units: dict, low: int = 30, high: int = 400) -> dict:
    """The measurement that matters: what stands under the addresses.

    Rukmiṇīśa Vijaya was landed on its counts at 71% plausible -- 287 of its
    verses were nothing but a verse number -- and only a screenshot showed it.
    """
    lens = sorted(len(v["text"]) for v in units.values())
    comms = [v["commentary"] for v in units.values() if v.get("commentary")]
    n = len(units) or 1
    return {
        "units": len(units),
        "empty": sum(1 for x in lens if x < 10),
        "short": sum(1 for x in lens if 10 <= x < low),
        "plausible": sum(1 for x in lens if low <= x <= high),
        "long": sum(1 for x in lens if x > high),
        "plausible_pct": round(100 * sum(1 for x in lens if low <= x <= high) / n),
        "len_min": lens[0] if lens else 0,
        "len_median": lens[len(lens) // 2] if lens else 0,
        "len_max": lens[-1] if lens else 0,
        "duplicate_text": len(units) - len({v["text"] for v in units.values()}),
        "duplicate_commentary": len(comms) - len(set(comms)),
        "commentary_equals_verse": sum(
            1 for v in units.values()
            if v.get("commentary", "").strip() == v["text"].strip()),
    }
