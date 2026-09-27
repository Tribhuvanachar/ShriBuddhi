#!/usr/bin/env python3
"""Turn the segmented Bṛhatīsahasram into its shelf file.

बृहतीसहस्रम् with the Tattvasāra of Śrī Raghunātha Tīrtha, one continuous run
of verses under Tattvavada/Itara.

    data/Tattvavada/Itara/brhatisahasra/mula/data.json

THE COUNT BEARS THE NAME OUT. बृहती-सहस्रम् is "a thousand bṛhatīs", and the
work's own numbering reaches exactly 1000. 986 of them are here; the 14 that
are not are declared.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ocr_common"))
import segment as seg  # noqa: E402
import shelf_writer as W  # noqa: E402
import staged as S  # noqa: E402

TARGET = pathlib.Path("data/Tattvavada/Itara/brhatisahasra")
COMMENTARY_KEY = "tattvasara"
COMMENTARY_TITLE = "तत्त्वसारः — श्रीरघुनाथतीर्थः"
SOURCE = {
    "edition": "बृहतीसहस्रम् — Bṛhatīsahasram, with the Tattvasāra of Śrī "
               "Raghunātha Tīrtha",
    "extent": "The work's own numbering reaches 1000, which is what its name "
              "says; the volume's appendices — सुमुक्तामञ्जरी, a "
              "विष्णुसहस्रनामस्तोत्रपाठः, ऐतरेयारण्यकम् and a निघण्टुः — are "
              "separate texts and are not included",
    "ocr": "Sarvam Document AI, 568 pages, with a Google Vision pass over the "
           "same book; segmented by tools/brhatisahasra/segment.py",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir",
                    default="data/ocr_staging/"
                            "brhatisahasram_tattvasara_raghunatha_tirtha")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    pages = S.load_sarvam(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    rep = seg.segment(pages)
    files, stats = W.build(
        rep,
        title=lambda n: "Bṛhatīsahasram",
        author="Raghunatha Tirtha",
        source=SOURCE,
        commentary_key=COMMENTARY_KEY,
        commentary_title=COMMENTARY_TITLE,
        section_name=lambda n: "",
        file_name=lambda n: "mula",
    )
    W.report(files, stats)
    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    print(f"\nwrote {W.write(files, TARGET)} file(s) to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
