#!/usr/bin/env python3
"""Acquire Vishwesha Panchanga (= Sri Pejavara Adhokshaja Matha's official
Panchanga -- one source, see DGE_Madhva_Acquisition_Architecture.md
§14/§18/§20) from a fresh copy of the "Vishwesha Panchanga" app
(maha.kani).

Reproduces the 11 Sep 2026 manual extraction: pulls assets/vss4.vss (the
festival/special-day annotation file -- see dge/sources/README.md for why
this is a PARTIAL acquisition, not the full five-anga daily Panchanga,
which is packed in undecoded numeric codes elsewhere in this app).

Usage: python3 tools/panchanga/acquire_vishwesha.py --apk path/to/vishwesha.apk
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acquire_common import apk_info, extract_from_apk, write_archive

ASSET = "assets/vss4.vss"


def year_span(vss4_bytes: bytes) -> tuple[str, str, int]:
    lines = [l for l in vss4_bytes.decode("utf-8", errors="replace").splitlines() if l.strip()]
    years = sorted({line.split("-", 1)[0] for line in lines if line[:4].isdigit()})
    return years[0], years[-1], len(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", required=True)
    args = ap.parse_args()

    info = apk_info(args.apk)
    if info["package"] != "maha.kani":
        raise SystemExit(f"expected maha.kani, got {info['package']} -- wrong APK? "
                          "(note: the sibling Udupi Panchanga B4A app shares most of this "
                          "app's asset naming but is a different package -- see architecture "
                          "doc §14)")

    data = extract_from_apk(args.apk, ASSET)
    lo_year, hi_year, row_count = year_span(data)

    manifest = {
        "institution": "Sri Pejavara Adhokshaja Matha (Panchanga published as Vishwesha "
                        "Panchanga; one source, not two -- see architecture doc §14/§18/§20)",
        "source_name": "Vishwesha Panchanga app (B4A/Basic4Android)",
        "app_package": info["package"],
        "app_version": info["version"],
        "app_sha256": info["sha256"],
        "artifact": ASSET,
        "method": "apk_asset",
        "content_type": "text/csv (custom, YYYY-DD-Mon-notes per line)",
        "retrieved_at": datetime.date.today().isoformat(),
        "row_count": row_count,
        "date_coverage": f"{lo_year} to {hi_year}, special-day/festival annotations only "
                          "(not full five-anga daily Panchanga)",
        "rights_status": "UNKNOWN - official app, no explicit licence/redistribution terms observed",
        "verification_status": "PARTIAL - incomplete acquisition",
        "notes": "Acquired via tools/panchanga/acquire_vishwesha.py. This app's full daily "
                 "five-anga Panchanga is NOT stored as readable text -- it's packed as opaque "
                 "numeric codes elsewhere in the app (assets/thithi.vss), decoded by compiled "
                 "B4A bytecode not yet reverse-engineered. The numbered monthly files "
                 "(assets/1-YYYY.vss etc.) are JPEG calendar-page scans despite the .vss "
                 "extension, not text. ph.vss (a pontiffs' contact directory with personal "
                 "phone numbers) is deliberately never extracted by this script.",
    }

    target = f"dge/sources/vishwesha_panchanga/panchanga/festival_notes_{lo_year}-{hi_year}"
    result = write_archive(target, {"vss4.vss": data}, manifest)
    print(f"{result}: {target} ({row_count} rows, {lo_year} to {hi_year})")


if __name__ == "__main__":
    main()
