#!/usr/bin/env python3
"""Segment the staged Uṣāharaṇa into addressed verses.

उषाहरणम् of Śrī Trivikrama Paṇḍitācārya, a mahākāvya in nine sargas, printed
with a Sanskrit commentary and a Kannada introduction. 534 pages of Sarvam
Document AI covering 6-539 with no gaps, and a Google Vision pass over 1-539.

WHAT THE EDITION GIVES US:

  * The SARGA is a running header -- प्रथमः सर्गः through नवमः सर्गः -- which
    also carries the work's name, उषाहरणम्, on 257 pages.
  * The VERSE closes with ॥ N ॥, and SO DOES ITS COMMENTARY, which opens by
    quoting the verse's first word with इति attached: न प्रौढशब्देति ।।,
    न चात्रेति ।।. So the marker does not say which a block is; the verse is
    the first VERSE-SHAPED closer on its number. 716 of the 740 first-closers
    are 200 characters or less, median 93.
  * The front matter is KANNADA -- ಮುನ್ನುಡಿ, ಕವಿಪರಿಚಯ, ಕೃತಿಪರಿಚಯ -- and the
    back has a सार्धश्लोकानुक्रमणिका, an index of half-verses. Neither belongs
    to a sarga, and neither has one, so both fall outside the addressing.

The reading itself is tools/ocr_common/verse_commentary.py, which the
Pāṣaṇḍakhaṇḍana and Rukmiṇīśa Vijaya share.

    python3 tools/ushaharana/segment.py --staged-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ocr_common"))
import staged as S  # noqa: E402
import verse_commentary as VC  # noqa: E402

SARGA = {"प्रथमः": 1, "द्वितीयः": 2, "तृतीयः": 3, "चतुर्थः": 4, "पञ्चमः": 5,
         "षष्ठः": 6, "सप्तमः": 7, "अष्टमः": 8, "नवमः": 9}
ORDINAL_NAME = {v: k for k, v in SARGA.items()}
# The index of half-verses at the back, and the Kannada front matter. A page of
# either carries no sarga header, so nothing there is addressed; this only
# stops a stray heading being read as one.
NOT_A_SARGA = re.compile(r"अनुक्रमणिका|ಮುನ್ನುಡಿ|ಪರಿಚಯ")
# Lines that belong to no verse:
#   * the volume's own titles and colophons;
#   * the commentary's LINK SENTENCE, which introduces the verse about to be
#     quoted and ends on a dash -- नृसिंहभावं स्तौति- , वावदूकत्वमेव विशदयति- .
#     Short enough to look like a verse line, it was prepended to 38 verses;
#   * the pratīka with which a gloss opens, X इति ।। , which is commentary.
TITLE_LINE = re.compile(
    r"विरचित|अनुक्रमणिका|श्रीगुरुभ्यो|महाकाव्य"
    r"|[-–—]\s*$"
    r"|^\S+\s*इति\s*[।॥]{1,2}")


# ॥ अथ प्रथमः सर्गः ॥ -- all nine sargas open this way, and it is the reliable
# signal. The running header repeats the sarga on every page, but it LAGS: the
# first verses of a sarga are printed before its header first appears, so a
# header-only reading lost verses 1 and 2 of every sarga. The opener is tagged
# section-title six times, headline twice and paragraph once, so it has to be
# matched by its text and not by its layout.
SARGA_OPEN = re.compile(r"अथ\s+(\S+?)\s*सर्गः")


def section_of(kind: str, text: str) -> int | None:
    """The sarga a block announces, by its opener or by the running header."""
    if "सर्ग" not in text or NOT_A_SARGA.search(text):
        return None
    m = SARGA_OPEN.search(text)
    if m and len(text) < 70:
        return SARGA.get(m.group(1))
    if kind == "header":
        first = text.split()[0] if text.split() else ""
        return SARGA.get(first)
    return None


def segment(pages: dict[int, str]) -> dict:
    # A line waiting for its marker can be as long as a verse here, because
    # this edition sets a whole verse in ONE block (median 108 characters)
    # rather than a pāda at a time as the Pāṣaṇḍakhaṇḍana does. With the
    # pāda-sized cap of 90, every verse whose marker stood alone in the next
    # block was refused, and 108 addresses came out with no text at all.
    return VC.segment(pages, section_of, max_verse=200, min_verse=25,
                      max_pending_line=200, max_pending_lines=2,
                      max_pending_chars=280, drop_line=TITLE_LINE)


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
    for x in rep["sections"]:
        flag = "" if not x["missing"] else f"  MISSING {x['missing'][:8]}"
        print(f"  sarga {x['section']}  {x['found']:>4} verses, "
              f"highest {x['highest']:>3}{flag}")
    print(f"\n{rep['verses_found']} verses, {rep['verses_missing']} missing; "
          f"{rep['with_commentary']} with the commentary")
    print(f"   {rep['stats']}")
    q = VC.quality(rep["units"])
    print(f"   quality: {q}")
    if args.json:
        out = {k: v for k, v in rep.items() if k != "units"}
        out["units"] = [v for _, v in sorted(rep["units"].items())]
        json.dump(out, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    return 0 if rep["verses_missing"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
