#!/usr/bin/env python3
"""
segment_commentary.py -- the Sarvavyakhyanasarasangraha volumes, per padya.

Twenty-two scanned volumes of the ಸರ್ವವ್ಯಾಖ್ಯಾನಸಾರಸಂಗ್ರಹ commentary sit in
staging, one or a few sandhis each. Their layout repeats exactly, which is
what makes them machine-readable:

    ಪದ್ಯ ೧                       <- opens a block
    <the padya, six lines>
    ||೧||
    <ಅವತರಣಿಕೆ / prose vyakhyana>
    ಪ್ರತಿಪದಾರ್ಥ : <word-by-word gloss>
    ಪದ್ಯ ೨                       <- closes the previous block

So a block runs from one ಪದ್ಯ header to the next, and inside it the
`ಪ್ರತಿಪದಾರ್ಥ` marker splits running commentary from the gloss.

WHICH SANDHI. From the folder name, which is how the volumes were scanned
and named: `hks__13_hks` is sandhi 13, `hks__29_30_hks` is 29 and 30. For a
volume covering several, the sandhi headings inside it move the pointer --
the same headings and the same table of contents the mula segmenter uses.

WHAT IT WILL NOT DO. It does not attach a block to a padya the mula does not
have, and it does not attach two blocks to one padya. Both are reported and
dropped. A commentary hung on the wrong verse is worse than a missing one,
because it reads as authoritative and nothing on the page says otherwise.
"""
from __future__ import annotations

import argparse
import collections
import glob
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from segment_mula import (KN, SANDHI_HEAD, SANDHI_HEAD_NONUM, TAG,  # noqa: E402
                          RUNNING_HEAD, kn, load_resolved, toc_number)

GEMINI_DIR = os.path.join("data", "ocr_staging", "_gemini")

# `ಪದ್ಯ ೧`, `ಪದ್ಯ (೧)`, `ಪದ್ಯ - 1.`, `ಪದ್ಯ—೨`, `ಸಂಧಿಸೂಚನೆ + ಪದ್ಯ ೧`.
#
# The em dash is not decoration: volume 14 sets every one of its headers as
# `ಪದ್ಯ—೨`, and a pattern allowing only hyphen and en dash found 8 headers in
# that volume where there are 37.
#
# The header must sit alone on its line and ಪದ್ಯ must be followed by a
# separator or space and then a digit. That is what keeps the word out of the
# commentary prose, where it is constant -- ಪದ್ಯದಿಂದ, ಪದ್ಯದ ಭಾವ, ಈ ಪದ್ಯದಲ್ಲಿ
# all continue in Kannada letters rather than digits and none of them match.
PADYA_HEAD = re.compile(
    r"^\s*(?:ಸಂಧಿಸೂಚನೆ\s*[+]\s*)?ಪದ್ಯ\s*[-–—:.]?\s*[\(\[]?\s*"
    r"([0-9೦-೯]{1,3})\s*[\)\]]?\s*[.।:：]?\s*$")
PRATIPADARTHA = re.compile(r"ಪ್ರತಿ\s*ಪದಾರ್ಥ\s*[:：-]?")
VERSE_END = re.compile(r"[|।॥]{1,2}\s*[0-9೦-೯]{1,3}\s*[|।॥]{1,2}")


# A heading that puts the number AFTER the title, which is how the
# multi-sandhi volumes write it:
#     ಅವರೋಹಣತಾರತಮ್ಯ ಸಂಧಿ : ೨೬
#     ದೈತ್ಯತಾರತಮ್ಯ ಸಂಧಿ (ಸಂಧಿ-30)
# The second form also runs as a page header through that whole section,
# which is useful rather than noisy: it states, on every page, which sandhi
# the page belongs to.
#
# The printed number is read but NOT trusted. The cover of hks__29_30_hks
# prints "ಅಣುತಾರತಮ್ಯ ಸಂಧಿ (ಸಂಧಿ-30)" while the book's own contents page makes
# Anutaratamya the twenty-ninth and Daityataratamya the thirtieth. Where the
# two disagree the title decides, because a title cannot be off by one.
SANDHI_TAIL = re.compile(
    r"^\s*[\"\u201c\u201d(]*\s*([\u0C80-\u0CFF][\u0C80-\u0CFF\s]{3,34}?)\s*ಸಂ[ಧದ]ಿ"
    r"[\"\u201c\u201d\s:,.\-–()]*(?:ಸಂ[ಧದ]ಿ\s*[-–:]?\s*)?([0-9೦-೯]{1,2})\s*[).]*\s*$")


def volume_sandhis(name: str) -> list[int]:
    """`hks__29_30_hks` -> [29, 30]. `hks__hks` -> [] (that is the mula)."""
    core = name.replace("hks__", "").replace("_hks", "")
    return [int(x) for x in core.split("_") if x.isdigit()]


def read_pages(work_dir: str, resolved: dict | None = None) -> dict:
    resolved = resolved or {}
    pages = {}
    for f in sorted(glob.glob(os.path.join(work_dir, "vision_*.json"))):
        for p in (json.load(open(f, encoding="utf-8")).get("pages") or []):
            t = str(p.get("text") or "")
            if t.strip():
                pages[int(p["page"])] = t
    for f in sorted(glob.glob(os.path.join(work_dir, "sarvam_*.json"))):
        for p in (json.load(open(f, encoding="utf-8")).get("pages") or []):
            # Unescape BEFORE stripping tags. Sarvam sometimes returns a table
            # whose own markup is entity-escaped inside the html field, so the
            # page arrives carrying literal `&lt;td&gt;ಪದ್ಯ-೧&lt;/td&gt;`.
            # Strip tags first and that header survives wrapped in text that
            # stops it ever matching.
            t = TAG.sub("\n", html.unescape(str(p.get("html") or "")))
            if t.strip():
                pages[int(p["page"])] = t          # Sarvam wins where both exist

    # And the pages Gemini has already adjudicated win over both, which is the
    # whole point of having paid for them. segment_mula.py has read these from
    # the start; this did not, so every proofread commentary page was being
    # thrown away in favour of the raw reading it was bought to correct.
    for n, text in resolved.items():
        if str(text or "").strip():
            pages[int(n)] = text
    return pages


# The six commentaries this edition collects. Each is announced inside a
# padya block by a numbered heading -- "೧. ಶ್ರೀಸಂಕರ್ಷಣ ಒಡೆಯರ ವ್ಯಾಖ್ಯಾನ",
# "೨. ಭಾವಪ್ರಕಾಶಿಕೆ:-" -- and the numbering restarts every block, so the
# number orders them and the NAME identifies them.
#
# The variants are what the scan actually produced, counted across all 22
# volumes: ಒಡೆಯರ is read ಬಡೆಯರ about a quarter of the time (ಒ and ಬ differ by
# one stroke), and the compounds are spaced inconsistently by the typesetter.
# Matching is done on the name with all spaces removed, so only genuine
# letter differences need listing here.
COMMENTARIES = {
    "bhavaprakashika": ["ಭಾವಪ್ರಕಾಶಿಕೆ", "ಭಾವಪ್ರಕಾಶ", "ಭಾವಪ್ರಕಾಶಿ"],
    "bhavadarpana": ["ಭಾವದರ್ಪಣ", "ಭಾವದರ್ಪ"],
    "bhavadarshana": ["ಭಾವದರ್ಶನ", "ಭಾವದರ್ಶಣ"],
    "guruhrdaya_prakashika": ["ಶ್ರೀಗುರುಹೃದಯಪ್ರಕಾಶಿಕೆ", "ಗುರುಹೃದಯಪ್ರಕಾಶಿಕೆ"],
    "sankarshana_odeyara_vyakhyana": [
        "ಶ್ರೀಸಂಕರ್ಷಣಒಡೆಯರವ್ಯಾಖ್ಯಾನ", "ಶ್ರೀಸಂಕರ್ಷಣಬಡೆಯರವ್ಯಾಖ್ಯಾನ",
        "ಸಂಕರ್ಷಣಒಡೆಯರವ್ಯಾಖ್ಯಾನ", "ಸಂಕರ್ಷಣಬಡೆಯರವ್ಯಾಖ್ಯಾನ"],
    "vyasadasa_siddhanta_kaumudi": [
        "ಶ್ರೀವ್ಯಾಸದಾಸಸಿದ್ಧಾಂತಕೌಮುದೀ", "ಶ್ರೀವ್ಯಾಸದಾಸಸಿದ್ಧಾಂತಕೌಮುದಿ",
        "ವ್ಯಾಸದಾಸಸಿದ್ಧಾಂತಕೌಮುದೀ", "ವ್ಯಾಸದಾಸಸಿದ್ಧಾಂತಕೌಮುದಿ"],
}
_BY_NAME = {v.replace(" ", ""): k for k, vs in COMMENTARIES.items() for v in vs}

SUBHEAD = re.compile(
    r"^\s*([0-9೦-೯]{1,2})\s*[.।]\s*([\u0C80-\u0CFF][\u0C80-\u0CFF\s]{3,44}?)\s*[:：\-]*\s*$")


def commentary_key(title: str):
    """Which of the six, or None. Longest name first so that ಭಾವಪ್ರಕಾಶಿಕೆ is
    not claimed by ಭಾವಪ್ರಕಾಶ, which is a prefix of it."""
    t = re.sub(r"\s+", "", str(title))
    for name in sorted(_BY_NAME, key=len, reverse=True):
        if name in t:
            return _BY_NAME[name]
    return None


def split_block(lines: list[str]) -> dict:
    """One ಪದ್ಯ block into its parts. The verse is whatever precedes the
    closing `||n||`; ಪ್ರತಿಪದಾರ್ಥ splits the rest."""
    text = "\n".join(lines).strip()
    verse, rest_lines = "", lines
    m = VERSE_END.search(text)
    if m:
        verse = text[:m.start()].strip()
        rest_lines = text[m.end():].strip().split("\n")

    # Walk what follows the verse, opening a named commentary at each numbered
    # subheading. Whatever precedes the first one is the edition's own running
    # gloss -- the ಪ್ರತಿಪದಾರ್ಥ and the ಅವತರಣಿಕೆ around it -- and is kept under
    # its own key rather than credited to a commentator who did not write it.
    lead, named, cur = [], {}, None
    for line in rest_lines:
        h = SUBHEAD.match(line.strip())
        key = commentary_key(h.group(2)) if h else None
        if key:
            cur = key
            named.setdefault(cur, [])
            continue
        (named[cur] if cur else lead).append(line)

    lead_text = "\n".join(lead).strip()
    parts = PRATIPADARTHA.split(lead_text, 1)
    out = {"verse": verse,
           "vyakhyana": parts[0].strip(),
           "pratipadartha": parts[1].strip() if len(parts) > 1 else "",
           "commentaries": {k: "\n".join(v).strip() for k, v in named.items()
                            if "\n".join(v).strip()}}
    return out


def segment(work_dir: str, name: str, gemini_dir: str = GEMINI_DIR) -> dict:
    sandhis = volume_sandhis(name)
    cur_sandhi = sandhis[0] if sandhis else None
    pages = read_pages(work_dir, load_resolved(gemini_dir, name))
    blocks, notes = [], []
    open_block, buf = None, []
    seen_a_padya = False

    def close(page):
        if open_block is None:
            return
        parts = split_block(buf)
        if not (parts["vyakhyana"] or parts["pratipadartha"] or parts["commentaries"]):
            notes.append("sandhi %s padya %s: block has no commentary text"
                         % (open_block[0], open_block[1]))
            return
        blocks.append({"sandhi": open_block[0], "padya": open_block[1],
                       "page": open_block[2], "end_page": page, **parts})

    for pno in sorted(pages):
        for raw in pages[pno].split("\n"):
            line = raw.strip()
            if not line or RUNNING_HEAD.match(line):
                continue
            m = SANDHI_HEAD.match(line) or SANDHI_HEAD_NONUM.match(line)
            if m:
                n = kn(m.group(1)) if m.re is SANDHI_HEAD else toc_number(m.group(1))
                if n and n in sandhis:
                    close(pno)
                    open_block, buf = None, []
                    cur_sandhi = n
                    continue
            mt = SANDHI_TAIL.match(line)
            if mt and seen_a_padya:
                # Title decides, not the printed number. Only after the first
                # padya header, so the front matter -- which lists every
                # sandhi in the volume -- cannot move the pointer.
                n = toc_number(mt.group(1))
                if n and n in sandhis and n != cur_sandhi:
                    close(pno)
                    open_block, buf = None, []
                    cur_sandhi = n
                    continue
            pm = PADYA_HEAD.match(line)
            if pm:
                close(pno)
                seen_a_padya = True
                open_block = (cur_sandhi, kn(pm.group(1)), pno)
                buf = []
                continue
            if open_block is not None:
                buf.append(line)
    close(max(pages) if pages else 0)

    # A padya number appearing more than once in a volume is NOT an error and
    # must not be deduplicated away. These volumes append other dasas' works
    # after the commentary proper: volume 33 carries Jagannatha Dasa's
    # Phalastuti, then Manohara Vithala's Phalastuti, then Bhimesha Vithala's
    # Sandhimala Sandhi, each numbering its own padyas from 1. They are
    # different texts that happen to share a number.
    #
    # The FIRST pass is the one keyed to the mula this repository holds, so
    # that is the one attached. The later passes are counted and reported as
    # appended works awaiting their own entries -- dropped from this output,
    # not from the staging they came from.
    first, extra = {}, collections.Counter()
    for b in blocks:
        k = (b["sandhi"], b["padya"])
        if k in first:
            extra[b["sandhi"]] += 1
        else:
            first[k] = b
    for sandhi, n in sorted(extra.items()):
        notes.append("sandhi %s: %d block(s) in a later pass over the same padya "
                     "numbers -- an appended work, not attached" % (sandhi, n))
    blocks = [first[k] for k in sorted(first)]
    return {"volume": name, "sandhis": sandhis, "pages": len(pages),
            "blocks": blocks, "notes": notes}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--staging", required=True, help="folder holding the hks__* volumes")
    ap.add_argument("--gemini-dir", default=GEMINI_DIR,
                    help="where the adjudicated pages live")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    out, total = [], 0
    for d in sorted(glob.glob(os.path.join(args.staging, "hks__*"))):
        name = os.path.basename(d)
        if not volume_sandhis(name):
            continue                                   # the mula volume
        r = segment(d, name, args.gemini_dir)
        total += len(r["blocks"])
        out.append(r)
        got = collections.Counter(b["sandhi"] for b in r["blocks"])
        print("%-20s sandhi %-10s %4d page(s)  %s" % (
            name, ",".join(map(str, r["sandhis"])), r["pages"],
            "  ".join("s%d:%d" % (k, v) for k, v in sorted(got.items())) or "none"))
        for n in r["notes"][:3]:
            print("      ! %s" % n)

    print("\n%d commentary block(s) across %d volume(s)" % (total, len(out)))
    if args.out:
        json.dump({"schema": "hks_commentary_segmented/1", "volumes": out},
                  open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
