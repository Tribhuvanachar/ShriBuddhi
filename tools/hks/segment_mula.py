#!/usr/bin/env python3
"""
segment_mula.py -- Harikathamrtasara: OCR pages in, 33 sandhis of padyas out.

The mula edition is 127 scanned pages of continuous text. What makes it
segmentable is that Jagannatha Dasa's own form does the work: every padya is
a Bhamini Shatpadi closed by its number in double dandas, `||17||`, and every
sandhi opens with a numbered heading, `2. ಕರುಣಾ ಸಂಧಿ`. Nothing here guesses
where a verse ends; the text says.

BEST TEXT PER PAGE. Three readings may exist for one page and they are not
equal. A page Gemini has already adjudicated is the best text available, so
it wins. Otherwise Sarvam, which keeps layout and is the stronger reader on
Kannada. Vision last, and only where neither of the others reached -- Sarvam's
run starts at page 6, so pages 1-5 exist in Vision alone.

WHAT IT REFUSES TO DO. It does not renumber, fill a gap, or infer a missing
padya. If sandhi 12 jumps from 14 to 16, the report says so and the gap stays
a gap. An edition that silently closes its own holes is worse than one with
holes, because nobody can see which verses to go and check.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

KN = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")

# `||17||`, `॥17॥`, and the mixed forms OCR produces. The number may be in
# either digit set; a stray space inside the dandas is common.
PADYA_END = re.compile(r"[|।॥]{1,2}\s*([0-9೦-೯]{1,3})\s*[|।॥]{1,2}")
# `2. ಕರುಣಾ ಸಂಧಿ` -- a heading is a short line, so the line length guard
# keeps prose that merely mentions a sandhi from opening a new one.
# Three things this book actually does that a tighter pattern missed:
#   * ಸಂದಿ for ಸಂಧಿ. The scan of sandhi 12 reads "ಶ್ರೀ ನಾಡೀಪ್ರಕರಣ ಸಂದಿ";
#     ಧ and ದ differ by one stroke and this edition's print is soft.
#   * Two titles joined by a slash, because several sandhis are known by two
#     names: "24. ಶ್ರೀ ಕಲ್ಪಸಾಧನ ಸಂಧಿ/ಶ್ರೀ ಅಪರೋಕ್ಷ ತಾರತಮ್ಯ ಸಂಧಿ". The first
#     becomes the title and the rest `also_called`.
#   * A heading with no number at all, in dandas: "||ಶ್ರೀ ಫಲಶ್ರುತಿ ಸಂಧಿ||"
#     for the thirty-third.
SANDHI_WORD = r"ಸಂ[ಧದ]ಿ"
SANDHI_HEAD = re.compile(
    r"^\s*[|।॥]{0,2}\s*([0-9೦-೯]{1,2})\s*[.।]?\s*"
    r"([\u0C80-\u0CFF][\u0C80-\u0CFF\s]{2,34}?)\s*" + SANDHI_WORD +
    r"\s*(?:/\s*(.+?)\s*)?[|।॥]{0,2}\s*$")
# The same line without a number. Resolved against the book's own table of
# contents below -- never by counting, which would invent a number the page
# does not carry.
SANDHI_HEAD_NONUM = re.compile(
    r"^\s*[|।॥]{1,2}\s*([\u0C80-\u0CFF][\u0C80-\u0CFF\s]{2,34}?)\s*" +
    SANDHI_WORD + r"\s*[|।॥]{1,2}\s*$")

# Pages 2-3 of this very scan ARE the book's table of contents. These are its
# 33 titles read off it, and they exist only to recover a number the OCR
# dropped from a heading -- the book's own evidence, not a list from elsewhere.
TOC = {
    "ಮಂಗಳಾಚರಣ": 1, "ಕರುಣಾ": 2, "ವ್ಯಾಪ್ತಿ": 3, "ಭೋಜನ": 4, "ವಿಭೂತಿ": 5,
    "ಪಂಚಮಹಾಯಜ್ಞ": 6, "ಪಂಚತನ್ಮಾತ್ರ": 7, "ಮಾತೃಕಾ": 8, "ವರ್ಣಪ್ರಕ್ರಿಯ": 9,
    "ಸರ್ವಪ್ರತೀಕ": 10, "ಸ್ಥಾವರಜಂಗಮ": 11, "ನಾಡೀಪ್ರಕರಣ": 12, "ನಾಮಸ್ಮರಣ": 13,
    "ಪಿತೃಗಣ": 14, "ಶ್ವಾಸ": 15, "ದತ್ತಸ್ವಾತಂತ್ರ್ಯ": 16, "ಸ್ವಗತಸ್ವಾತಂತ್ರ್ಯ": 17,
    "ಕ್ರೀಡಾವಿಲಾಸ": 18, "ಬಿಂಬಾಪರೋಕ್ಷ": 19, "ಗುಣತಾರತಮ್ಯ": 20,
    "ಕರ್ಮವಿಮೋಚನ": 21, "ಭಕ್ತಾಪರಾಧಸಹಿಷ್ಣು": 22, "ಬೃಹತ್ತಾರತಮ್ಯ": 23,
    "ಕಲ್ಪಸಾಧನ": 24, "ಆರೋಹಣತಾರತಮ್ಯ": 25, "ಅವರೋಹಣತಾರತಮ್ಯ": 26,
    "ಅನುಕ್ರಮಣಿಕಾತಾರತಮ್ಯ": 27, "ವಿಘ್ನೇಶ್ವರಸ್ತೋತ್ರ": 28, "ಅಣುತಾರತಮ್ಯ": 29,
    "ದೈತ್ಯತಾರತಮ್ಯ": 30, "ನೈವೇದ್ಯಪ್ರಕರಣ": 31, "ಕಕ್ಷಾತಾರತಮ್ಯ": 32,
    "ಫಲಶ್ರುತಿ": 33,
}


def toc_number(title):
    """The sandhi number for a title, or None. `ಶ್ರೀ` is an honorific the scan
    applies unevenly, and a space inside a compound is a typesetting choice;
    neither is allowed to decide a match."""
    key = re.sub(r"\s+", "", str(title)).replace("ಶ್ರೀ", "")
    return TOC.get(key)
TAG = re.compile(r"<[^>]+>")
RUNNING_HEAD = re.compile(r"^\s*(HariKathaamrutaSaara|Page\s*\d+|https?://\S+)\s*$", re.I)


def kn(s: str) -> int:
    return int(str(s).translate(KN))


def strip_html(s: str) -> str:
    return TAG.sub("\n", str(s or ""))


def best_text(work_dir: str, resolved: dict) -> dict:
    """{page number: text}, each page from the best reading available."""
    pages: dict[int, str] = {}
    src: dict[int, str] = {}

    def take(n, text, label, rank):
        n = int(n)
        if not str(text or "").strip():
            return
        if n in pages and RANK[src[n]] <= rank:
            return
        pages[n], src[n] = text, label

    RANK = {"gemini": 0, "sarvam": 1, "vision": 2}

    for f in sorted(glob.glob(os.path.join(work_dir, "vision_*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for p in (d.get("pages") or []):
            take(p.get("page"), p.get("text") or strip_html(p.get("html")), "vision", 2)
    for f in sorted(glob.glob(os.path.join(work_dir, "sarvam_*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for p in (d.get("pages") or []):
            take(p.get("page"), strip_html(p.get("html")), "sarvam", 1)
    for n, text in resolved.items():
        take(n, text, "gemini", 0)

    return {"text": pages, "source": src}


def load_resolved(gemini_dir: str, work: str) -> dict:
    out = {}
    for f in sorted(glob.glob(os.path.join(gemini_dir, "resolved_*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        rows = d if isinstance(d, list) else (d.get("pages") or d.get("resolutions") or [])
        for r in rows:
            if (r.get("work") or "") == work and r.get("text"):
                out[int(r["page"])] = r["text"]
    return out


def clean_lines(text: str) -> list[str]:
    out = []
    for line in str(text).split("\n"):
        line = line.strip()
        if not line or RUNNING_HEAD.match(line):
            continue
        out.append(line)
    return out


def segment(pages: dict, order: list[int]) -> tuple[list, list]:
    """Walk the pages in order, opening a sandhi at each heading and closing a
    padya at each `||n||`. Text before the first heading is the front matter
    and is dropped, not guessed at."""
    sandhis, cur, buf, notes = [], None, [], []
    for pno in order:
        for line in clean_lines(pages[pno]):
            m = SANDHI_HEAD.match(line)
            number = title = alt = None
            if m:
                number, title, alt = kn(m.group(1)), m.group(2).strip(), m.group(3)
            else:
                m2 = SANDHI_HEAD_NONUM.match(line)
                if m2:
                    title = m2.group(1).strip()
                    number = toc_number(title)
                    if number is None:
                        # A heading-shaped line whose title the contents page
                        # does not know. Left as ordinary text rather than
                        # opening a sandhi on a guess.
                        notes.append("page %d: heading-shaped line not in the "
                                     "table of contents: %r" % (pno, line))
                        title = None
            if title is not None and number is not None:
                if buf and cur is not None:
                    notes.append("sandhi %s: %d line(s) after its last numbered padya"
                                 % (cur["number"], len(buf)))
                buf = []
                cur = {"number": number, "title": title, "padyas": [],
                       "first_page": pno}
                if alt:
                    cur["also_called"] = [a.strip() for a in alt.split("/") if a.strip()]
                sandhis.append(cur)
                continue
            if cur is None:
                continue
            buf.append(line)
            for pm in PADYA_END.finditer(line):
                body = "\n".join(buf).strip()
                body = PADYA_END.sub("", body).strip()
                if body:
                    cur["padyas"].append({"number": kn(pm.group(1)), "text": body,
                                          "page": pno})
                buf = []
                break
    return sandhis, notes


def report(sandhis: list) -> list[str]:
    out = []
    seen = collections.Counter(s["number"] for s in sandhis)
    for n in range(1, 34):
        if seen[n] == 0:
            out.append("sandhi %d: no heading found" % n)
        elif seen[n] > 1:
            out.append("sandhi %d: heading found %d times" % (n, seen[n]))
    for s in sandhis:
        nums = [p["number"] for p in s["padyas"]]
        if not nums:
            out.append("sandhi %d (%s): no padyas" % (s["number"], s["title"]))
            continue
        gaps = [i for i in range(1, max(nums) + 1) if i not in nums]
        dupes = [k for k, v in collections.Counter(nums).items() if v > 1]
        if gaps:
            out.append("sandhi %d: %d padya(s) missing: %s%s"
                       % (s["number"], len(gaps), gaps[:12],
                          " ..." if len(gaps) > 12 else ""))
        if dupes:
            out.append("sandhi %d: padya number(s) repeated: %s" % (s["number"], sorted(dupes)))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--work-dir", required=True, help="folder holding the engines' output")
    ap.add_argument("--work", default="hks__hks", help="work id as the resolved files spell it")
    ap.add_argument("--gemini-dir", default="data/ocr_staging/_gemini")
    ap.add_argument("--out", default="", help="write the segmented JSON here")
    args = ap.parse_args(argv)

    resolved = load_resolved(args.gemini_dir, args.work)
    best = best_text(args.work_dir, resolved)
    order = sorted(best["text"])
    used = collections.Counter(best["source"].values())

    sandhis, notes = segment(best["text"], order)
    problems = report(sandhis) + notes

    print("pages read: %d  (%s)" % (len(order), ", ".join(
        "%s %d" % (k, v) for k, v in sorted(used.items()))))
    print("sandhis found: %d   padyas: %d"
          % (len(sandhis), sum(len(s["padyas"]) for s in sandhis)))
    print()
    for s in sandhis:
        print("  %2d  %-28s %4d padyas   pages from %d"
              % (s["number"], s["title"], len(s["padyas"]), s["first_page"]))

    if problems:
        print("\n%d thing(s) a person needs to look at:" % len(problems))
        for p in problems[:40]:
            print("    %s" % p)
        if len(problems) > 40:
            print("    ... and %d more" % (len(problems) - 40))

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        json.dump({"schema": "hks_mula_segmented/1", "work": args.work,
                   "page_source": best["source"], "sandhis": sandhis,
                   "problems": problems},
                  open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
