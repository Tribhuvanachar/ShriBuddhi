#!/usr/bin/env python3
"""Segment the staged Bṛhatīsahasram into addressed verses.

बृहतीसहस्रम् with the Tattvasāra of Śrī Raghunātha Tīrtha. 568 pages of Sarvam
Document AI over 12-580 (page 567 missing) and a Google Vision pass over
1-580.

WHAT THE EDITION GIVES US:

  * ONE CONTINUOUS RUN of verse numbers across the whole work, 1 to 1139 --
    "a thousand bṛhatīs", and the count bears the name out. The book is
    divided into प्राग्भागः, three तृचाशीति sections and उत्तरभागः, and the
    numbering does NOT restart at each: प्राग्भागः ends at 317, गायत्रतृचाशीतिः
    runs 318-475, वार्हततृचाशीतिः 476-722, औष्णिही 723-897, उत्तरभागः 898-1139.
    Treating the sections as separate made each look like a text missing its
    first few hundred verses.
  * The VERSE closes with ॥ N ॥ and SO DOES ITS COMMENTARY. 992 of the 1,006
    first-closers are 200 characters or less, median 111.
  * The running title is OCR'd four ways -- बृहतीसहस्रम्, बृहतीसहस्रम,
    बृहतीसहस्रम्., and as त्र्यहतीसहस्रम् and नृहतीसहस्रम् on 22 pages between
    them. None of it carries information, so all of it is ignored.

The volume also carries appendices after the work -- सुमुक्तामञ्जरी, a
विष्णुसहस्रनामस्तोत्रपाठः, and ऐतरेयारण्यकम् -- which are separate texts and
are not addressed here.

    python3 tools/brhatisahasra/segment.py --staged-dir <dir>
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

# Where the appendices begin. सुमुक्तामञ्जरी is the first of them; everything
# from there on is a different text.
APPENDIX = re.compile(r"सुमुक्तामञ्जरी|विष्णुसहस्रनाम|ऐतरेयारण्यकम्|एतरेयारण्यकम्")
TITLE_LINE = re.compile(
    r"विरचित|अनुक्रम|सहस्रनाम|[-–—]\s*$|^\S+\s*इति\s*[।॥]{1,2}")


def body_pages(pages: dict[int, str]) -> tuple[dict[int, str], int | None]:
    """The work itself, stopping where the appendices begin.

    The boundary is a HEADER naming one of them, not any mention: the contents
    page names विष्णुसहस्रनाम on p22 and cutting there left ten pages of front
    matter and no verses at all.
    """
    first = None
    for p in sorted(pages):
        for m in S.BLOCK.finditer(pages[p]):
            if m.group(2) != "header":
                continue
            if APPENDIX.search(S.flat(S.untag(m.group(3)))):
                first = p
                break
        if first is not None:
            break
    body = {p: h for p, h in pages.items() if first is None or p < first}
    return body, first


def segment(pages: dict[int, str]) -> dict:
    body, appendix_from = body_pages(pages)
    rep = VC.segment(body, None,          # one section: see the docstring
                     max_verse=200, min_verse=25,
                     max_pending_line=200, max_pending_lines=2,
                     max_pending_chars=280, drop_line=TITLE_LINE)
    rep["body_pages"] = len(body)
    rep["appendix_from"] = appendix_from
    return rep


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
          f"gaps {len(rep['page_gaps'])}; appendices from p{rep['appendix_from']}")
    for x in rep["sections"]:
        print(f"  {x['found']} verses, highest {x['highest']}, "
              f"missing {len(x['missing'])} {x['missing'][:10]}")
    print(f"{rep['with_commentary']} with the Tattvasāra;  {rep['stats']}")
    print(f"   quality: {VC.quality(rep['units'])}")
    if args.json:
        out = {k: v for k, v in rep.items() if k != "units"}
        out["units"] = [v for _, v in sorted(rep["units"].items())]
        json.dump(out, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    return 0 if rep["verses_missing"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
