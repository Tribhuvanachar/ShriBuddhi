#!/usr/bin/env python3
"""Segment the staged Vaidika Svara Prakaraṇam into addressed sūtras.

ವೈದಿಕ ಸ್ವರ ಪ್ರಕರಣಮ್ { ಶೌನಕೀಯಂ, ಪಾಣಿನೀಯಂ ಚ }, edited and translated by Vidvān
Kadri Prabhākara Aḍiga, Śrī Tattvasaṃśodhana Saṃsat, Palimāru Maṭha, Udupi,
2011. 108 pages of Sarvam Document AI covering 5-112 with no gaps, and a full
Google Vision pass over 1-112.

THIS IS A KANNADA BOOK -- 80,617 Kannada characters against 597 Devanāgarī --
about Vedic accent. The sūtras it expounds are Sanskrit, printed in Kannada
script, each followed by a Kannada ಅರ್ಥ (gloss). Sarvam was called with
`language: sa-IN` on it and handled it anyway.

WHAT THE EDITION GIVES US, counted across all 108 pages rather than read off
one:

  * TWO PARTS, each announced by a headline of its own:
    ॥ ಅಥ ಶೌನಕೋಕ್ತಮ್-ಋಗ್ವೇದೀಯ-ಸ್ವರಪ್ರಕರಣಮ್ ॥ (p17, from the Ṛk Prātiśākhya) and
    ಅಥ ಪಾಣಿನೀಯ ಸಾಧಾರಣಸ್ವರ-ಪ್ರಕ್ರಿಯಾ (p64).
  * The SŪTRA NUMBER as ಸೂತ್ರ-N, which numbers what FOLLOWS it -- the opposite
    of the bare ॥ N ॥ in the two Kāvya works, which numbers what precedes.
  * ಅರ್ಥ :- opens the Kannada gloss on the sūtra just given.
  * A TABLE OF CONTENTS on pages 8-12, ಅಥ ವಿಷಯಾನುಕ್ರಮಣಿಕಾ, which lists every
    sūtra WITH ITS TOPIC. That is the book supplying a heading for each unit,
    so none has to be invented, and it is an independent count to check the
    body against.

  * What it does NOT give is one numbering. The Śaunakīya part restarts at 1
    in each of its three sections; the Pāṇinīya part runs 1..46 straight
    through, across its own ಅಧ್ಯಾಯ headings. So the section is found by where
    the numbering RESTARTS, not by the headings -- which is also why an
    earlier pass that reset on every ಅಧ್ಯಾಯ heading reported adhyāya 2 as
    "3 sūtras, 4..6, gaps 1,2,3".

  * NUMBERS IN PARENTHESES BELONG TO ANOTHER TEXT. `(ಫಿಟ್ ಸೂತ್ರ-೮೫)` and
    `(ಫಿಟ್ ಸೂತ್ರ-ಪಾದ-೪-ಸೂತ್ರ-೮೭)` cite the Phiṭ Sūtras. Counting those as this
    book's own turned the Pāṇinīya part into "1..87 with 58 gaps". But the
    guard has to be the PARENTHESES and not the word ಫಿಟ್: p98 reads
    `( ಫಿಟ್ ಸೂತ್ರ ) ಸೂತ್ರ - ೪೧,` -- a citation with no number, then this book's
    own sūtra 41 outside it. Excluding on the word alone lost that one sūtra,
    and a single missing sūtra is exactly the Maṇimañjarī signature.

    python3 tools/vaidika_svara/segment.py --staged-dir <dir>
    python3 tools/vaidika_svara/segment.py --staged-dir <dir> --json report.json
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

KN_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")
BLOCK = re.compile(r'<(\w+)[^>]*data-layout="([^"]+)"[^>]*>(.*?)</\1>', re.S)
SKIP_LAYOUTS = ("page-number", "footer", "image")

SUTRA = re.compile(r"ಸೂತ್ರ\s*[-–—:]?\s*([೦-೯0-9]+)")
# A heading that starts a new division of the book. It ENDS the sūtra being
# accumulated: without it the last sūtra of a section simply ran on to the next
# marker, so 0.34 swallowed the six pages of ಉಪಕ್ರಮ- that follow it (7,247
# characters) and 3.46 swallowed ಭಾಗ-೩ and the back matter (11,418).
DIVISION = re.compile(r"^(ಅಧ್ಯಾಯ|ಭಾಗ|ಪ್ರಕರಣ|ಉಪಕ್ರಮ|ಅಥ\s)")
# The gloss opener. ಸೂತ್ರಾರ್ಥ is the same thing under a fuller name, used once
# -- on sūtra 1, which is the first unit a reader sees, so its exposition sat
# in the sūtra slot on the opening screen.
#
# It has to be spelt out as its own alternative rather than as (?:ಸೂತ್ರ)?ಅರ್ಥ:
# the two words are joined by sandhi, so ಸೂತ್ರ + ಅರ್ಥ is written ಸೂತ್ರಾರ್ಥ, with
# the ಅ absorbed into the vowel sign on ರ. There is no literal ಅ to match --
# the same trap as the pratīka in Rukmiṇīśa Vijaya, where नेमुस्ताम् + इति
# prints नेमुस्तामिति with no इति in the string.
# Longest alternative first, so ಸೂತ್ರಾರ್ಥ cannot match as bare ಅರ್ಥ.
ARTHA = re.compile(r"(?:ಸೂತ್ರಾರ್ಥ|ಅರ್ಥ)\s*[:：]\s*[-–—]?")
PART_SAUNAKIYA = "ಶೌನಕೋಕ್ತಮ್"
PART_PANINIYA = "ಪಾಣಿನೀಯ ಸಾಧಾರಣಸ್ವರ"
PARTS = {
    "saunakiya": "ಅಥ ಶೌನಕೋಕ್ತಮ್-ಋಗ್ವೇದೀಯ-ಸ್ವರಪ್ರಕರಣಮ್",
    "paniniya": "ಅಥ ಪಾಣಿನೀಯ ಸಾಧಾರಣಸ್ವರ-ಪ್ರಕ್ರಿಯಾ",
}
# The body begins after the front matter and the table of contents.
FIRST_BODY_PAGE = 13
TOC_PAGES = range(8, 13)


def untag(html: str) -> str:
    """HTML to text, keeping <br> as the line break it stands for."""
    return re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>", "\n", html)).strip()


def flat(text: str) -> str:
    return " ".join(text.split())


def load_pages(staged_dir: str) -> dict[int, str]:
    """Every Sarvam page that came back. The Vision pass is a different shape
    (plain `text`, no `ok`) and is read by vision_pages()."""
    pages: dict[int, str] = {}
    for path in sorted(glob.glob(os.path.join(staged_dir, "*.json"))):
        if "vision" in os.path.basename(path):
            continue
        try:
            doc = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        for page in doc.get("pages") or []:
            html = page.get("html") or page.get("text") or ""
            if page.get("ok") and html.strip():
                pages.setdefault(page["page"], html)
    return pages


def vision_pages(staged_dir: str) -> dict[int, str]:
    """The Vision pass, for checking a reading the Sarvam output makes doubtful."""
    out: dict[int, str] = {}
    for path in sorted(glob.glob(os.path.join(staged_dir, "*vision*.json"))):
        try:
            doc = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        for page in doc.get("pages") or []:
            if (page.get("text") or "").strip():
                out.setdefault(page["page"], page["text"])
    return out


def paren_spans(text: str) -> list[tuple[int, int]]:
    """The (…) ranges in a string, so a number inside one can be left alone."""
    out, start = [], None
    for i, ch in enumerate(text):
        if ch in "(（":
            start = i
        elif ch in ")）" and start is not None:
            out.append((start, i))
            start = None
    return out


def sutra_marks(text: str) -> list[tuple[int, int, int]]:
    """This book's own ಸೂತ್ರ-N markers as (start, end, number).

    A marker inside parentheses cites another text -- the Phiṭ Sūtras -- and is
    not this book's numbering. See the docstring: the parentheses are the test,
    not the word ಫಿಟ್.
    """
    spans = paren_spans(text)
    out = []
    for m in SUTRA.finditer(text):
        if any(a < m.start() < b for a, b in spans):
            continue
        out.append((m.start(), m.end(), int(m.group(1).translate(KN_DIGITS))))
    return out


def read_blocks(pages: dict[int, str], first_page: int = FIRST_BODY_PAGE) -> list[dict]:
    """The body as one ordered stream of text blocks, each carrying its part."""
    stream: list[dict] = []
    part = None
    for page in sorted(pages):
        if page < first_page:
            continue
        for m in BLOCK.finditer(pages[page]):
            kind, body = m.group(2), untag(m.group(3))
            if kind in SKIP_LAYOUTS or not body:
                continue
            one = flat(body)
            if len(one) < 70 and PART_SAUNAKIYA in one:
                part = "saunakiya"
                continue
            if len(one) < 70 and PART_PANINIYA in one:
                part = "paniniya"
                continue
            if "Archiver" in one and len(one) < 30:     # scan watermark
                continue
            stream.append({"page": page, "kind": kind, "text": one, "part": part})
    return stream


def read_toc(pages: dict[int, str]) -> dict[tuple[int, int], str]:
    """Each sūtra's own topic, from ಅಥ ವಿಷಯಾನುಕ್ರಮಣಿಕಾ on pages 8-12.

    Keyed the same way the body is -- (section index, sūtra number) -- by
    applying the same restart rule to the table of contents, because the
    numbering restarts there too. So a heading never has to be invented, and
    the count is an independent check on the body.

    The entries run together in one block: `ಸೂತ್ರ-೧-<topic> ಸೂತ್ರ-೨-<topic>`,
    so each title is the text between one marker and the next.
    """
    out: dict[tuple[int, int], str] = {}
    section, last = 0, None
    for page in sorted(p for p in pages if p in TOC_PAGES):
        for m in BLOCK.finditer(pages[page]):
            kind, body = m.group(2), untag(m.group(3))
            if kind in SKIP_LAYOUTS or not body:
                continue
            one = flat(body)
            marks = sutra_marks(one)
            for i, (_, end, n) in enumerate(marks):
                stop = marks[i + 1][0] if i + 1 < len(marks) else len(one)
                title = one[end:stop].strip(" ,.:;।॥-–—")
                if last is not None and n < last:
                    section += 1
                last = n
                if 4 <= len(title) <= 160:
                    out.setdefault((section, n), title)
    return out


def align_toc(toc: dict, body: dict) -> dict[int, int]:
    """Map each table-of-contents section onto the body section it lists.

    They cannot be paired by position: the table of contents has three sections
    and the body four, because the book's own contents page OMITS the six-sūtra
    ಅಥ ಸಮಾಸಸ್ವರ ವಿಷಯಃ section. Paired by index, every title from there on lands
    on the wrong sūtra -- which is worse than no title, because a wrong heading
    reads as correct.

    So they are paired by containment, in reading order, and only when exactly
    one such pairing exists. Otherwise no titles are attached at all.
    """
    toc_secs: dict[int, set] = collections.defaultdict(set)
    for sec, n in toc:
        toc_secs[sec].add(n)
    body_secs: dict[int, set] = collections.defaultdict(set)
    for sec, n in body:
        body_secs[sec].add(n)
    tk, bk = sorted(toc_secs), sorted(body_secs)

    def search(i: int, j: int) -> list[list[tuple[int, int]]]:
        if i == len(tk):
            return [[]]
        found = []
        for jj in range(j, len(bk)):
            if toc_secs[tk[i]] <= body_secs[bk[jj]]:
                for rest in search(i + 1, jj + 1):
                    found.append([(tk[i], bk[jj])] + rest)
            if len(found) > 1:
                break
        return found

    matches = search(0, 0)
    return dict(matches[0]) if len(matches) == 1 else {}


def segment(pages: dict[int, str]) -> dict:
    """Address every sūtra, with the text that belongs to it.

    A ಸೂತ್ರ-N marker numbers what FOLLOWS it, so a unit runs from one marker to
    the next. Where the marker sits mid-block -- most of them do -- the block is
    cut at it, the same problem the two Kāvya works had and the same answer.
    """
    stream = read_blocks(pages)
    toc = read_toc(pages)

    # Flatten to (page, part, text) pieces cut at every marker.
    pieces: list[dict] = []
    for b in stream:
        marks = sutra_marks(b["text"])
        if not marks:
            division = (b["kind"] in ("headline", "section-title")
                        and len(b["text"]) < 80
                        and bool(DIVISION.match(b["text"])))
            pieces.append({**b, "num": None, "division": division})
            continue
        if marks[0][0] > 0:
            head = b["text"][:marks[0][0]].strip()
            if head:
                pieces.append({**b, "text": head, "num": None, "division": False})
        for i, (_, end, n) in enumerate(marks):
            stop = marks[i + 1][0] if i + 1 < len(marks) else len(b["text"])
            pieces.append({**b, "text": b["text"][end:stop].strip(" ,.:;-–—"),
                           "num": n, "division": False})

    # Group into sections by where the numbering RESTARTS, not by the headings.
    units: dict[tuple[int, int], dict] = {}
    order: list[tuple[int, int]] = []
    section, last, cur = 0, None, None
    unattached: list[dict] = []
    last_heading = ""
    passages: list[dict] = []
    passage = None
    for p in pieces:
        if p["num"] is None:
            if p.get("division"):
                last_heading = p["text"]
                # This sūtra ends here, and the heading OPENS a passage: the
                # prose between one division and the next sūtra is the book's
                # own -- ಉಪಕ್ರಮ- runs six pages and ಭಾಗ-೩ thirteen, 17,242
                # characters between them. Dropping it would lose a fifth of
                # the Kannada in the book without leaving a trace.
                cur = None
                passage = {"heading": p["text"], "page": p["page"],
                           "part": p["part"], "parts": []}
                passages.append(passage)
            elif cur is not None:
                cur["parts"].append(p["text"])
            elif passage is not None:
                passage["parts"].append(p["text"])
            else:
                unattached.append(p)
            continue
        passage = None
        if last is not None and p["num"] < last:
            section += 1
        last = p["num"]
        key = (section, p["num"])
        if key in units:                      # a number repeated inside a run
            cur = units[key]
            cur["parts"].append(p["text"])
            continue
        cur = {"section": section, "sutra": p["num"], "page": p["page"],
               "part": p["part"], "parts": [p["text"]], "title": "",
               "heading": last_heading}
        last_heading = ""       # a heading names the sūtra it precedes, once
        units[key] = cur
        order.append(key)

    for ps in passages:
        ps["text"] = "\n".join(x for x in ps["parts"] if x).strip()
        del ps["parts"]
    # A heading with nothing under it is a heading, not a passage.
    passages[:] = [ps for ps in passages if len(ps["text"]) >= 200]

    # Titles, once the two sectionings have been matched to each other.
    mapping = align_toc(toc, units)
    for (tsec, n), title in toc.items():
        bsec = mapping.get(tsec)
        if bsec is not None and (bsec, n) in units:
            units[(bsec, n)]["title"] = title

    for u in units.values():
        whole = "\n".join(x for x in u["parts"] if x).strip()
        m = ARTHA.search(whole)
        # The sūtra, then its Kannada gloss. Where the edition marks the gloss
        # with ಅರ್ಥ :- the two are kept apart; where it does not, the whole
        # unit stands as the text rather than being guessed into halves.
        u["sa"] = whole[:m.start()].strip() if m else whole
        u["artha"] = whole[m.end():].strip() if m else ""
        u["text"] = whole
        del u["parts"]

    sections = []
    for s in sorted({k[0] for k in units}):
        got = sorted(n for sec, n in units if sec == s)
        high = max(got)
        any_u = units[(s, got[0])]
        sections.append({
            "section": s, "part": any_u["part"], "found": len(got),
            # A section without a heading of its own is named by its part.
            "heading": any_u.get("heading") or PARTS.get(any_u["part"], ""),
            "highest": high,
            "pages": [min(units[(s, n)]["page"] for n in got),
                      max(units[(s, n)]["page"] for n in got)],
            "missing": [i for i in range(1, high + 1) if i not in set(got)],
        })
    return {
        "pages": len(pages),
        "page_range": [min(pages), max(pages)] if pages else [],
        "page_gaps": [n for n in range(min(pages), max(pages) + 1)
                      if n not in pages] if pages else [],
        "passages": passages,
        "passage_chars": sum(len(x["text"]) for x in passages),
        "unattached_blocks": len(unattached),
        "unattached_chars": sum(len(x["text"]) for x in unattached),
        "toc_entries": len(toc),
        "toc_sections_matched": len(align_toc(toc, units)),
        "sections": sections,
        "sutras_found": sum(s["found"] for s in sections),
        "sutras_missing": sum(len(s["missing"]) for s in sections),
        "with_title": sum(1 for u in units.values() if u["title"]),
        "with_artha": sum(1 for u in units.values() if u["artha"]),
        "units": units,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir", required=True)
    ap.add_argument("--json", help="write the full report here")
    args = ap.parse_args(argv)

    pages = load_pages(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    rep = segment(pages)
    print(f"pages {rep['pages']} ({rep['page_range'][0]}-{rep['page_range'][1]}), "
          f"gaps {len(rep['page_gaps'])}")
    print(f"table of contents: {rep['toc_entries']} sūtra topics\n")
    for s in rep["sections"]:
        flag = "" if not s["missing"] else f"  MISSING {s['missing'][:8]}"
        print(f"  section {s['section']}  {s['part'] or '?':<10} "
              f"pages {s['pages'][0]:>3}-{s['pages'][1]:<3} "
              f"{s['found']:>3} sūtras, 1..{s['highest']}{flag}")
    print(f"\n{rep['sutras_found']} sūtras addressed, {rep['sutras_missing']} missing")
    print(f"   {rep['with_title']} carry a topic from the table of contents, "
          f"{rep['with_artha']} carry a marked ಅರ್ಥ gloss")
    print(f"\n{len(rep['passages'])} prose passages between the sūtras, "
          f"{rep['passage_chars']:,} characters")
    for ps in rep["passages"]:
        print(f"   p{ps['page']:<4} {len(ps['text']):>6} ch  {ps['heading'][:56]}")
    print(f"unattached after all that: {rep['unattached_blocks']} blocks, "
          f"{rep['unattached_chars']:,} chars")
    if args.json:
        out = dict(rep)
        out["units"] = [v for _, v in sorted(rep["units"].items())]
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print("report written to", args.json)
    return 0 if rep["sutras_missing"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
