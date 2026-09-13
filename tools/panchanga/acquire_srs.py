#!/usr/bin/env python3
"""Acquire SRS Matha (Mantralaya)'s Panchanga from a fresh copy of the
"SRS Matha Panchanga" app (com.panchanga).

Reproduces the 11 Sep 2026 manual extraction: pulls the packaged JSON
bundle (daily panchanga + aradhana/ekadashi/festivals/tarpana), reads the
daily records' actual date coverage, and archives to
dge/sources/srs_matha/panchanga/<date-range>/.

Usage: python3 tools/panchanga/acquire_srs.py --apk path/to/srs.apk
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acquire_common import apk_info, extract_from_apk, write_archive

ASSETS = {
    "panchanga.en.json": "assets/flutter_assets/assets/data/panchanga_bundle/panchanga.en.json",
    "aradhana.json": "assets/flutter_assets/srsmatha.org/srsmatha_panchanga/storage/sacred_calendars/aradhana.json",
    "ekadashi.json": "assets/flutter_assets/srsmatha.org/srsmatha_panchanga/storage/sacred_calendars/ekadashi.json",
    "festivals.json": "assets/flutter_assets/srsmatha.org/srsmatha_panchanga/storage/sacred_calendars/festivals.json",
    "tarpana.json": "assets/flutter_assets/srsmatha.org/srsmatha_panchanga/storage/sacred_calendars/tarpana.json",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", required=True)
    args = ap.parse_args()

    info = apk_info(args.apk)
    if info["package"] != "com.panchanga":
        raise SystemExit(f"expected com.panchanga, got {info['package']} -- wrong APK? "
                          "(note: the OLDER srsmatha.com.srsmatha legacy app is a different, "
                          "unrelated package -- see dge/sources/README.md)")

    files = {fname: extract_from_apk(args.apk, member) for fname, member in ASSETS.items()}
    daily = json.loads(files["panchanga.en.json"])
    dates = sorted(r["date"] for r in daily)
    lo, hi = dates[0], dates[-1]
    year_range = f"{lo[:4]}-{hi[:4]}"
    location = daily[0].get("location_name", "unknown")

    manifest = {
        "institution": "Sri Raghavendra Swamy Matha (SRS Matha, Mantralaya)",
        "source_name": "SRS Matha Panchanga app (Flutter)",
        "app_package": info["package"],
        "app_version": info["version"],
        "app_sha256": info["sha256"],
        "method": "apk_asset",
        "retrieved_at": datetime.date.today().isoformat(),
        "content_type": "application/json",
        "row_count": len(daily),
        "date_coverage": f"{lo} to {hi}",
        "location_name": location,
        "rights_status": "UNKNOWN - official app, no explicit licence/redistribution terms observed",
        "verification_status": "needs_review",
        "notes": "Acquired via tools/panchanga/acquire_srs.py. Daily schema already close to "
                 "DGE's canonical panchanga_day shape. aradhana/ekadashi/festivals/tarpana are "
                 "separate curated collections, not yet cross-checked against the daily records "
                 "for consistency (architecture doc §41).",
    }

    target = f"dge/sources/srs_matha/panchanga/{year_range}"
    result = write_archive(target, files, manifest)
    print(f"{result}: {target} ({len(daily)} rows, {lo} to {hi}, {location})")


if __name__ == "__main__":
    main()
