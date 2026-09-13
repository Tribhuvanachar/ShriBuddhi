#!/usr/bin/env python3
"""Acquire Sri Uttaradi Matha's Panchanga from a fresh copy of the "UM Sri
Uttaradi Math" app (org.uttaradimath.app).

Reproduces the 11 Sep 2026 manual extraction: pulls the packaged
um_app_seed.db, reads panchanga_table's real date coverage (not the app
version number -- the db's actual row dates are the ground truth), and
archives it to dge/sources/uttaradi_matha/panchanga/<date-range>/.

Usage: python3 tools/panchanga/acquire_uttaradi.py --apk path/to/um.apk
"""
from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acquire_common import apk_info, extract_from_apk, write_archive

ASSET = "assets/flutter_assets/assets/um_app_seed.db"


def date_range(db_bytes: bytes) -> tuple[str, str]:
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        tmp.write(db_bytes)
        tmp.flush()
        con = sqlite3.connect(tmp.name)
        lo, hi = con.execute("select min(date), max(date) from panchanga_table").fetchone()
        row_count = con.execute("select count(*) from panchanga_table").fetchone()[0]
        con.close()
    lo_d = datetime.datetime.utcfromtimestamp(lo).date()
    hi_d = datetime.datetime.utcfromtimestamp(hi).date()
    return lo_d.isoformat(), hi_d.isoformat(), row_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", required=True)
    args = ap.parse_args()

    info = apk_info(args.apk)
    if info["package"] != "org.uttaradimath.app":
        raise SystemExit(f"expected org.uttaradimath.app, got {info['package']} -- wrong APK?")

    db_bytes = extract_from_apk(args.apk, ASSET)
    lo, hi, row_count = date_range(db_bytes)
    year_range = f"{lo[:4]}-{hi[:4]}"

    manifest = {
        "institution": "Sri Uttaradi Matha",
        "source_name": "UM Sri Uttaradi Math app (Flutter)",
        "app_package": info["package"],
        "app_version": info["version"],
        "app_sha256": info["sha256"],
        "artifact": ASSET,
        "method": "apk_asset",
        "retrieved_at": datetime.date.today().isoformat(),
        "content_type": "application/vnd.sqlite3",
        "table": "panchanga_table",
        "row_count": row_count,
        "date_coverage": f"{lo} to {hi}",
        "languages": ["English", "Kannada", "Sanskrit", "Tamil", "Telugu"],
        "other_tables_present_not_extracted": [
            "main_deities_table - institutional deity data, see tools/build_pratima.py",
            "parampara_table - lineage data, Phase 2",
            "gallery_table, generic_media_table - photos, needs rights review before any use",
            "stotra_table, stotra_lyrics_table - stotra content, separate acquisition thread",
            "seva_table, contact_table, bank_account_table, announcement_table - NOT extracted: "
            "bank_account_table is sensitive institutional financial data and must never be "
            "published; contact_table not reviewed for personal-data content",
        ],
        "rights_status": "UNKNOWN - official app, no explicit licence/redistribution terms observed",
        "verification_status": "needs_review",
        "notes": "Acquired via tools/panchanga/acquire_uttaradi.py. The app syncs from a live "
                 "Firebase backend at runtime (confirmed 11 Sep 2026, see PENDING.md) but that "
                 "backend requires authorization DGE doesn't have -- this packaged asset is the "
                 "practical acquisition path until/unless authorized access is arranged.",
    }

    target = f"dge/sources/uttaradi_matha/panchanga/{year_range}"
    result = write_archive(target, {"um_app_seed.db": db_bytes}, manifest)
    print(f"{result}: {target} ({row_count} rows, {lo} to {hi})")


if __name__ == "__main__":
    main()
