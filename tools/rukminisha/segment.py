#!/usr/bin/env python3
"""Segment the staged Rukmiṇīśa Vijaya OCR into addressed verses.

Vādirāja Tīrtha's mahākāvya, 19 sargas, printed with a Sanskrit vyākhyā.
712 pages of Sarvam Document AI output (no Vision pass exists for this work),
complete from page 19 to 712 with no gaps.

WHAT THE EDITION GIVES US, once read correctly:

  * The SARGA is a running header on (almost) every page, tagged
    data-layout="header". So a page declares its own sarga and there is no
    need to track section starts. Two spellings occur: षष्ठ सर्गः for the
    sixth, without the visarga the others carry, and one page OCR'd
    सप्तदशः as ससदशः.
  * The VERSE closes with its own ॥ N ॥ marker, in Devanāgarī or ASCII digits
    -- sometimes trailing the verse block, sometimes alone in a block of its
    own where the OCR split the line. A block holding nothing but ॥ N ॥
    numbers the block BEFORE it: 341 of those occur, 340 of them directly
    after an unnumbered text block.
  * The COMMENTARY opens with व्या and CLOSES WITH ॥ N ॥ TOO -- the same
    number the verse just carried. So ॥ N ॥ appears twice per verse, and a
    marker on its own says nothing about whether the block holding it is
    verse or gloss.

  * What it does NOT give is a layout tag separating verse from commentary.
    data-layout="section-title" looked like it did -- the first page examined
    had the verse under exactly that tag -- but there are only 78 of them in
    the whole book against ~2,480 verse markers. Sampling one page and
    generalising would have produced a 37-verse text out of 1,143.

WHY COMMENTARY IS A STATE AND NOT A TEST. An earlier version of this file
called a block commentary when it STARTED with व्या. The gloss on one verse
runs over many blocks and across page breaks, and only the first block says
व्या; every continuation was therefore eligible to be a verse, and a
continuation that happened to end with the closing ॥ N ॥ became one. Landed
on the shelf that produced 287 verses that were nothing but a verse number,
52 fragments, and prose in the mūla slot -- 71% plausible, which the
screenshot caught and the counts did not. So the commentary is tracked as a
region: व्या opens it and the closing ॥ N ॥ ends it, and nothing inside is a
candidate verse.

    python3 tools/rukminisha/segment.py --staged-dir data/ocr_staging/rukminisha_vijaya
    python3 tools/rukminisha/segment.py --staged-dir <dir> --json report.json
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

ORDINALS = {
    "प्रथमः": 1, "द्वितीयः": 2, "तृतीयः": 3, "चतुर्थः": 4, "पञ्चमः": 5,
    "षष्ठः": 6, "षष्ठ": 6, "सप्तमः": 7, "अष्टमः": 8, "नवमः": 9, "दशमः": 10,
    "एकादशः": 11, "द्वादशः": 12, "त्रयोदशः": 13, "चतुर्दशः": 14,
    "पञ्चदशः": 15, "षोडशः": 16, "सप्तदशः": 17, "ससदशः": 17,
    "अष्टादशः": 18, "एकोनविंशः": 19,
}
DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
VERSE_NUM = re.compile(r"॥\s*([0-9०-९]+)\s*॥")
# The number sometimes ends the block with only ONE danda, or none after it:
#   ...शरणं विरिञ्चम् ॥ ११
# 17 verses across the book close that way. Anchored to the end of the block
# so a number quoted mid-sentence is never taken for a verse marker.
VERSE_NUM_END = re.compile(r"॥\s*([0-9०-९]+)\s*[॥।]?\s*$")
# A block holding nothing but the marker. The OCR split the line; the number
# belongs to the block above it, not to itself. Reading it as a verse in its
# own right is what produced 287 empty verses.
BARE_NUM = re.compile(r"^\s*॥?\s*([0-9०-९]+)\s*॥?\s*$")
# The marker that CLOSES a commentary region, at the very end of the block.
CLOSE_NUM = re.compile(r"॥\s*([0-9०-९]+)\s*॥\s*$")
BLOCK = re.compile(r'<(\w+)[^>]*data-layout="([^"]+)"[^>]*>(.*?)</\1>', re.S)
TEXT_BLOCKS = ("paragraph", "section-title", "headline")


def untag(html: str) -> str:
    """HTML to text, keeping <br> as the line break it stands for."""
    return re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>", "\n", html)).strip()


def load_pages(staged_dir: str) -> dict[int, str]:
    """Every page that actually came back, across all staged files.

    A page can appear in several files -- overlapping dispatch ranges, and
    re-runs of pages an earlier batch failed on. A page whose `ok` is false
    carries no html; one that succeeded wins over one that did not, so the
    later file never erases a page the earlier one delivered.
    """
    pages: dict[int, str] = {}
    for path in sorted(glob.glob(os.path.join(staged_dir, "*.json"))):
        try:
            doc = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        for page in doc.get("pages") or []:
            html = page.get("html") or page.get("text") or ""
            if page.get("ok") and html.strip():
                pages[page["page"]] = html
    return pages


def sarga_of(text: str) -> int | None:
    if "सर्ग" not in text:
        return None
    return ORDINALS.get(text.split()[0])


def colophon_sarga(text: str) -> int | None:
    """The sarga a closing colophon names, if this block is one.

        ॥ इति श्रीमत्कविकुलतिलक...महाकाव्ये चतुर्दशः सर्गः ॥ १४ ॥

    Two things make this worth recognising. Its trailing ॥ १४ ॥ is the SARGA
    number, not a verse number, so read as a verse it invents one. And it says
    which sarga has just ended, which fixes the duplicated pages: p550 repeats
    p548, and by the time the OCR reaches it the running title has already
    moved the sarga on, so sarga 14's closing gloss ॥ ७० ॥ was landing as verse
    15.70 -- a verse 8 numbers past the end of a sarga that has 62.
    """
    if "इति" not in text or "सर्ग" not in text:
        return None
    for word, n in ORDINALS.items():
        if f"{word} सर्गः" in text or f"{word}सर्गः" in text:
            return n
    return None


def read_blocks(pages: dict[int, str]) -> list[dict]:
    """The book as one ordered stream of text blocks, each carrying its sarga.

    The sarga comes from the running header and carries forward to pages that
    have none. Commentary is marked but kept, because it is what separates one
    verse from the next and so is what makes positional recovery possible.
    """
    current = None
    stream: list[dict] = []
    unknown: collections.Counter = collections.Counter()
    for page in sorted(pages):
        for m in BLOCK.finditer(pages[page]):
            kind, body = m.group(2), untag(m.group(3))
            if kind == "header":
                s = sarga_of(body)
                if s:
                    current = s
                elif "सर्ग" in body:
                    unknown[body] += 1
                continue
            if kind not in TEXT_BLOCKS or not body:
                continue
            # A sarga title also appears as an ordinary text block, not only as
            # a tagged header. 13 pages of this scan are printed twice, two
            # leaves apart, and on the duplicate the header often fails to tag;
            # its title line then carries the sarga instead. Without this, the
            # duplicate of the sarga-2 opening was attributed to sarga 1 and
            # verse 2.1 stood at BOTH 1.1 and 2.1.
            titled = sarga_of(body) or colophon_sarga(body)
            if titled:
                current = titled
                continue
            nums = [int(r.translate(DEV_DIGITS)) for r in VERSE_NUM.findall(body)]
            tail = VERSE_NUM_END.search(body)
            if tail:
                n = int(tail.group(1).translate(DEV_DIGITS))
                if n not in nums:
                    nums.append(n)
            # There is no verse 0. Sarga 10 carries one -- the OCR read some
            # mark as ॥ ० ॥ -- and it counted as a verse while every consumer
            # that iterates 1..highest silently skipped it, so the segmenter
            # reported 1212 verses and the writer emitted 1211. An off-by-one
            # between two counts of the same text is exactly how Manimanjari
            # lost a verse, so it is refused here rather than reconciled later.
            nums = [n for n in nums if n >= 1]
            bare = BARE_NUM.match(body)
            close = CLOSE_NUM.search(body.rstrip())
            stream.append({
                "page": page, "sarga": current, "text": body, "nums": nums,
                # `opens` only says this block STARTS a gloss. Whether a block is
                # INSIDE one is a property of the region, decided in segment().
                "opens": body.startswith("व्या")
                         or bool(GLOSS_OPEN_BARE.match(body.replace("\n", " "))),
                "commentary": False,
                "bare": int(bare.group(1).translate(DEV_DIGITS)) if bare else None,
                "close": int(close.group(1).translate(DEV_DIGITS)) if close else None,
            })
    mark_regions(stream)
    return stream, unknown


def mark_regions(stream: list[dict]) -> dict:
    """Set `commentary` on every block INSIDE a gloss, not just the one that opens it.

    व्या opens a region and a trailing ॥ N ॥ closes it. Everything between is
    gloss, however it happens to start, because the commentary on one verse runs
    over many blocks and across page breaks and only the first says व्या.

    Two things can go wrong in the OCR, and both are handled rather than
    ignored, because an unclosed region would otherwise swallow every verse
    after it:

      * The closing ॥ N ॥ is lost. Then a bare ॥ N ॥ block appears further
        down -- that marker belongs to a VERSE, so the region must already have
        ended, and the block above the marker is the verse. The region is closed
        retroactively at the last block that could plausibly have ended it.
      * A new व्या arrives while a region is still open. The previous region
        simply ends there.
    """
    stats = {"opened": 0, "closed_by_marker": 0, "closed_by_bare": 0,
             "closed_by_reopen": 0, "unclosed_at_end": 0}
    open_at = None
    for i, b in enumerate(stream):
        if open_at is None:
            if b["opens"]:
                open_at, stats["opened"] = i, stats["opened"] + 1
                b["commentary"] = True
                if b["close"] is not None:      # opens and closes in one block
                    open_at = None
                    stats["closed_by_marker"] += 1
            continue
        if b["opens"]:
            # The region before this one never closed; it ended here.
            stats["closed_by_reopen"] += 1
            open_at, stats["opened"] = i, stats["opened"] + 1
            b["commentary"] = True
            if b["close"] is not None:
                open_at = None
                stats["closed_by_marker"] += 1
            continue
        if b["bare"] is not None:
            # A marker alone in a block numbers a VERSE, so the gloss is over.
            # Unmark back to the block before this one: that block is the verse.
            for j in range(open_at, i - 1):
                stream[j]["commentary"] = True
            stream[i - 1]["commentary"] = False
            open_at = None
            stats["closed_by_bare"] += 1
            continue
        b["commentary"] = True
        if b["close"] is not None:
            open_at = None
            stats["closed_by_marker"] += 1
    if open_at is not None:
        stats["unclosed_at_end"] = 1
    return stats


# व्या : <pratika>ति ।  -- the commentary opens by quoting the verse's first
# word with इति attached. The इति is SANDHI'd into the preceding syllable, so
# there is no literal इति to split on: नेमुस्ताम् + इति prints नेमुस्तामिति,
# and काचित् + इति prints काचिदिति, voicing the त्. Reversing that reliably is
# not possible, but it does not need to be -- the shared prefix is enough to
# tell two candidate blocks apart.
PRATIKA_OPEN = re.compile(r"^व्या\s*[:：]\s*([^\s।]+ति)\s*।")
# The same opener with the व्या lost by the OCR: '<pratika>ति ।' at the very
# start of a block. 9 blocks in the book look like this and all 9 are gloss --
# अथेति ।, बलस्येति ।, छत्रमिति । -- because a verse's first pada does not end
# in a danda after one word. Without this, छत्रमिति । became mūla verse 13.1.
GLOSS_OPEN_BARE = re.compile(r"^\s*[^\s।॥]+ति\s*।")
I_MATRA = "\u093F"


def pratika_stem(word: str) -> str:
    """The quoted word with its sandhi'd इति removed, as far as is safe."""
    w = word[:-2] if word.endswith("ति") else word
    return w[:-1] if w.endswith(I_MATRA) else w


def pratika_for(stream: list[dict], sarga: int, verse: int) -> str | None:
    """The stem the commentary on this verse quotes, if it named one."""
    for b in stream:
        if b["commentary"] and b["sarga"] == sarga and verse in b["nums"]:
            m = PRATIKA_OPEN.match(b["text"].replace("\n", " "))
            if m:
                return pratika_stem(m.group(1))
    return None


def gloss_regions(stream: list[dict]) -> list[tuple[int, int, int, int]]:
    """Every gloss region as (opened_at, closed_at, closing_verse_number, sarga)."""
    out, open_at = [], None
    for i, b in enumerate(stream):
        if open_at is None:
            if b["commentary"]:
                open_at = i
                if b["close"] is not None:
                    out.append((open_at, i, b["close"], b["sarga"]))
                    open_at = None
            continue
        if not b["commentary"]:
            open_at = None
            continue
        if b["close"] is not None:
            out.append((open_at, i, b["close"], b["sarga"]))
            open_at = None
    return out


def verse_run_above(stream: list[dict], start: int, sarga: int) -> list[dict]:
    """The unbroken run of verse-candidate blocks immediately above `start`."""
    run, j = [], start - 1
    while (j >= 0 and not stream[j]["commentary"] and stream[j]["sarga"] == sarga
           and stream[j]["bare"] is None and not sarga_of(stream[j]["text"])):
        run.insert(0, stream[j])
        j -= 1
    return run


def recover_by_gloss_close(stream: list[dict], verses: dict) -> int:
    """Address a verse from the number its COMMENTARY closes with.

    The gloss on verse N ends with ॥ N ॥ and is printed directly beneath the
    verse it glosses. So when the verse's own marker is lost -- which is what
    every remaining gap is -- the commentary underneath still names it, and the
    verse is the run of blocks immediately above where that gloss opened.

    This is the edition stating the address, not the segmenter inferring it, so
    it runs before the positional pass. It still refuses where the edition is
    ambiguous: the number must be closed by EXACTLY ONE gloss region in the
    sarga, and the run above must be verse-shaped (40-600 characters). A run
    that is too long is a gloss the region marker failed to open, and a run that
    is too short is a fragment; either would put wrong text on the shelf under a
    right-looking address, which is the failure that is invisible downstream.
    """
    placed = 0
    # Text already standing under another address must never be reused. Two
    # addresses holding the same verse is not a near miss -- one of them is
    # simply wrong, and nothing downstream can tell which.
    claimed = {v["text"] for v in verses.values()}
    byaddr: dict[tuple[int, int], list] = collections.defaultdict(list)
    for o, c, n, sg in gloss_regions(stream):
        if sg and n >= 1:
            byaddr[(sg, n)].append(o)
    for (sg, n), opens in byaddr.items():
        if (sg, n) in verses or len(opens) != 1:
            continue
        run = verse_run_above(stream, opens[0], sg)
        if not run:
            continue
        text = "\n".join(x["text"] for x in run)
        if not 40 <= len(text) <= 600 or text in claimed:
            continue
        verses[(sg, n)] = {"sarga": sg, "verse": n, "page": run[0]["page"],
                           "text": text, "how": "gloss-close"}
        claimed.add(text)
        placed += 1
    return placed


def recover_by_position(stream: list[dict], verses: dict) -> int:
    """Place a verse whose marker the OCR lost entirely.

    A verse block sits between the commentary on the verse before it and the
    commentary on the one after. So an UNNUMBERED, non-commentary block lying
    between numbered verse N-1 and numbered verse N+1, with no other candidate
    competing for the slot, is verse N.

    Deliberately conservative: it refuses when more than one unnumbered block
    occupies the gap, because then it cannot tell which is the verse and which
    is a stray line, a heading or a page artefact. Guessing there would put
    invented addressing on the shelf, which is the one outcome worse than a
    gap.
    """
    placed = 0
    # Same rule as the gloss-close pass: never stand text under a second
    # address. Without this the pass placed 15 verses that were simply the
    # neighbouring verse over again, one number off.
    claimed = {v["text"] for v in verses.values()}
    numbered = [(i, b) for i, b in enumerate(stream)
                if b["nums"] and not b["commentary"] and b["sarga"]]
    for pos, (i, b) in enumerate(numbered[:-1]):
        j, nxt = numbered[pos + 1]
        if b["sarga"] != nxt["sarga"]:
            continue
        lo, hi = max(b["nums"]), min(nxt["nums"])
        want = [v for v in range(lo + 1, hi) if (b["sarga"], v) not in verses]
        if not want:
            continue
        # A block already standing under an address is not an available
        # candidate, so it is filtered out here rather than disqualifying the
        # whole gap -- excluding the gap outright cost 19 verses that had a
        # perfectly good unclaimed block beside the claimed one.
        gap = [g for g in stream[i + 1:j]
               if not g["commentary"] and not g["nums"] and g["text"] not in claimed]
        # ONE BLOCK PER MISSING VERSE, or not at all. When the counts match the
        # mapping is forced and there is nothing to guess. When they do not --
        # 20 of the remaining gaps are one missing verse against two blocks,
        # which is what a verse printed across a page break looks like, but is
        # equally what a verse plus a stray heading looks like -- it declines.
        # Inventing addressing is worse than leaving a hole, because a hole is
        # visible and a wrong address is not.
        if len(gap) != len(want):
            # The counts disagree, so position alone cannot say which block is
            # which. The commentary can: it opens by quoting the verse's first
            # word. Where exactly one candidate starts with that stem, the
            # ambiguity is resolved by the edition itself rather than guessed.
            if len(want) == 1:
                stem = pratika_for(stream, b["sarga"], want[0])
                if stem and len(stem) >= 3:
                    hits = [g for g in gap
                            if g["text"].replace("\n", " ").lstrip().startswith(stem[:3])]
                    if len(hits) == 1 and hits[0]["text"] not in claimed:
                        verses[(b["sarga"], want[0])] = {
                            "sarga": b["sarga"], "verse": want[0],
                            "page": hits[0]["page"], "text": hits[0]["text"],
                            "how": "pratika"}
                        claimed.add(hits[0]["text"])
                        placed += 1
            continue
        for v, g in zip(want, gap):
            verses[(b["sarga"], v)] = {"sarga": b["sarga"], "verse": v,
                                       "page": g["page"], "text": g["text"],
                                       "how": "position"}
            claimed.add(g["text"])
            placed += 1
    return placed


def recover_by_pratika_sargawide(stream: list[dict], verses: dict) -> int:
    """Last pass: the commentary named a first word, but the verse did not sit
    in the window between its numbered neighbours.

    That happens when the neighbours are themselves unplaced, or when the
    block order on the page does not follow the verse order. Searching the
    whole sarga is looser than the windowed pass, so it still demands a UNIQUE
    hit on a prefix of at least three Devanagari characters and refuses a
    block already claimed by another verse.
    """
    placed = 0
    claimed = {id(v.get("text")) for v in verses.values()}
    per_sarga: dict[int, list] = collections.defaultdict(list)
    for b in stream:
        if b["sarga"] and not b["commentary"] and not b["nums"]:
            per_sarga[b["sarga"]].append(b)

    wanted = collections.defaultdict(list)
    for (sg, n) in verses:
        wanted[sg].append(n)
    for sg, got in wanted.items():
        for v in range(1, max(got) + 1):
            if (sg, v) in verses:
                continue
            stem = pratika_for(stream, sg, v)
            if not stem or len(stem) < 3:
                continue
            hits = [b for b in per_sarga[sg]
                    if b["text"].replace("\n", " ").lstrip().startswith(stem[:3])
                    and b["text"] not in
                    {x["text"] for x in verses.values() if x["sarga"] == sg}]
            if len(hits) == 1:
                verses[(sg, v)] = {"sarga": sg, "verse": v, "page": hits[0]["page"],
                                   "text": hits[0]["text"], "how": "pratika"}
                placed += 1
    return placed


def segment(pages: dict[int, str], recover: bool = True) -> dict:
    stream, unknown_headers = read_blocks(pages)
    verses: dict[tuple[int, int], dict] = {}
    # A verse is often printed ONE PADA PER BLOCK -- four blocks of 25-32
    # characters, then the marker. Keeping only the block that carries the
    # number leaves a quarter of a verse: that is what the 62 "fragments" were,
    # and 'भवत्याः ॥ ३४ ॥' is the last word of 7.34, not a stray. So unnumbered
    # verse-candidate blocks accumulate and are joined to the numbered one that
    # closes them. A gloss, a sarga title or a page without a sarga clears the
    # run, so nothing is carried across a boundary it does not belong to.
    pending: list[dict] = []
    for i, b in enumerate(stream):
        if b["commentary"] or not b["sarga"] or sarga_of(b["text"]):
            pending = []
            continue
        # A bare marker is an address, not a verse; it numbers the run above it.
        if b["bare"] is not None:
            continue
        # The verse's OWN closing marker. Not b["nums"], which collects every
        # number anywhere in the block, including ones quoted mid-sentence.
        n = b["close"]
        if n is None:
            tail = VERSE_NUM_END.search(b["text"])   # ...विरिञ्चम् ॥ ११  (one danda)
            if tail:
                n = int(tail.group(1).translate(DEV_DIGITS))
        if n is None:
            nxt = stream[i + 1] if i + 1 < len(stream) else None
            if nxt and nxt["bare"] is not None and nxt["sarga"] == b["sarga"]:
                n = nxt["bare"]
        if n is None or n < 1:
            pending.append(b)
            continue
        run = [x for x in pending if x["sarga"] == b["sarga"]] + [b]
        pending = []
        verses.setdefault((b["sarga"], n),
                          {"sarga": b["sarga"], "verse": n, "page": run[0]["page"],
                           "text": "\n".join(x["text"] for x in run), "how": "marker"})
    by_marker = len(verses)
    if recover:
        recover_by_gloss_close(stream, verses)
        recover_by_position(stream, verses)
        recover_by_pratika_sargawide(stream, verses)

    per = collections.defaultdict(list)
    for (s, n) in verses:
        per[s].append(n)
    sargas = []
    for s in sorted(per):
        got = sorted(per[s])
        high = max(got)
        sargas.append({"sarga": s, "found": len(got), "highest": high,
                       "missing": [i for i in range(1, high + 1) if i not in set(got)]})
    return {
        "pages": len(pages),
        "page_range": [min(pages), max(pages)] if pages else [],
        "page_gaps": [n for n in range(min(pages), max(pages) + 1)
                      if n not in pages] if pages else [],
        "commentary_blocks": sum(1 for b in stream if b["commentary"]),
        "unknown_sarga_headers": dict(unknown_headers),
        "sargas": sargas,
        "verses_by_marker": by_marker,
        "verses_by_gloss_close": sum(1 for v in verses.values() if v.get("how") == "gloss-close"),
        "verses_by_position": sum(1 for v in verses.values() if v.get("how") == "position"),
        "verses_by_pratika": sum(1 for v in verses.values() if v.get("how") == "pratika"),
        "verses_found": sum(s["found"] for s in sargas),
        "verses_missing": sum(len(s["missing"]) for s in sargas),
        "verses": verses,
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
    print(f"commentary blocks {rep['commentary_blocks']}")
    if rep["unknown_sarga_headers"]:
        print("unrecognised sarga headers:", rep["unknown_sarga_headers"])
    for s in rep["sargas"]:
        flag = "" if not s["missing"] else f"  MISSING {len(s['missing'])}: {s['missing'][:8]}"
        print(f"  sarga {s['sarga']:<3} {s['found']:>4} verses, highest {s['highest']:>3}{flag}")
    print(f"\n{rep['verses_found']} verses addressed "
          f"({rep['verses_by_marker']} by marker, {rep['verses_by_gloss_close']} by gloss close, "
          f"{rep['verses_by_position']} by position, "
          f"{rep['verses_by_pratika']} by pratika), "
          f"{rep['verses_missing']} missing")
    if args.json:
        out = dict(rep)
        out["verses"] = [{k: v for k, v in b.items()}
                         for _, b in sorted(rep["verses"].items())]
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print("report written to", args.json)

    # Non-zero while anything is missing: this is the gate that keeps an
    # incomplete mahakavya off the shelf.
    return 0 if rep["verses_missing"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
