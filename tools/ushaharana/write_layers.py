#!/usr/bin/env python3
"""Turn the segmented Uṣāharaṇa into the Kāvya shelf's sarga files.

उषाहरणम् of Śrī Trivikrama Paṇḍitācārya, nine sargas, with the commentary that
names itself रसिकरञ्जनी. It sits on the Kāvya shelf beside the other mahākāvyas.

    data/Tattvavada/Itara/Kavya/ushaharana/sarga_N/data.json
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

TARGET = pathlib.Path("data/Tattvavada/Itara/Kavya/ushaharana")
COMMENTARY_KEY = "rasikaranjani"
COMMENTARY_TITLE = "रसिकरञ्जनी — व्याख्या"
SOURCE = {
    "edition": "उषाहरणम् — Uṣāharaṇa, a mahākāvya of Śrī Trivikrama "
               "Paṇḍitācārya, with the Rasikarañjanī commentary",
    "ocr": "Sarvam Document AI, 534 pages, with a Google Vision pass over the "
           "same book; segmented by tools/ushaharana/segment.py",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir",
                    default="data/ocr_staging/"
                            "usha_harna_trivikram__irtha_vadirajacharya_l_s")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    pages = S.load_sarvam(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    rep = seg.segment(pages)
    files, stats = W.build(
        rep,
        title=lambda n: f"Uṣāharaṇa सर्गः {n}",
        author="Trivikrama Panditacharya",
        source=SOURCE,
        commentary_key=COMMENTARY_KEY,
        commentary_title=COMMENTARY_TITLE,
        section_name=lambda n: f"{seg.ORDINAL_NAME.get(n, n)} सर्गः",
        file_name=lambda n: f"sarga_{n}",
    )
    W.report(files, stats)
    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    print(f"\nwrote {W.write(files, TARGET)} sarga file(s) to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
