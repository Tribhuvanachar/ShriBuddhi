"""
DGE — Inspect sanskritdocuments.org Veda spreadsheets
======================================================
Before writing any importer, check what these files ACTUALLY contain —
same discipline as with VedaWeb (where two structural guesses were wrong
before real data settled it).

Two files, both hosted by sanskritdocuments.org:
  1. FourVedas20200922.xlsx — Virendra Agarwal's digitisation. Advertised
     as having Rishi, Devata, Swar, mantra WITH and WITHOUT accent marks,
     and pada-patha WITH and WITHOUT accent marks.
  2. veda_anukriti.xlsx (10.6MB) — Jitendra Bansal's compilation of all
     four Vedas with kANDa/prapAThaka/anuvAka structure AND a list of
     Chandas (metre) — the field we've had no source for so far.

Usage (Colab):
    !pip install requests openpyxl pandas
    then run this script
"""

import requests
import pandas as pd
from pathlib import Path

FILES = {
    "FourVedas": "https://sanskritdocuments.org/doc_veda/FourVedas20200922.xlsx",
    "VedaAnukriti": "https://sanskritdocuments.org/doc_veda/veda_anukriti.xlsx",
}

WORK = Path("./veda_xlsx")
WORK.mkdir(exist_ok=True)

# The server returns 406 for requests with Python's default
# "python-requests/x.y" User-Agent, while the same URLs download normally
# in a browser. These are the standard headers a browser sends — this is
# just making the request acceptable to a strict server rule, not
# bypassing any access control (the files are publicly linked for
# download on the site's own veda page).
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def download(name, url):
    dest = WORK / f"{name}.xlsx"
    if dest.exists():
        print(f"{name}: already downloaded ({dest.stat().st_size:,} bytes)")
        return dest
    print(f"Downloading {name} from {url} ...")
    r = requests.get(url, timeout=300, headers=HEADERS)
    r.raise_for_status()
    dest.write_bytes(r.content)
    print(f"  saved {len(r.content):,} bytes")
    return dest


def inspect(name, path):
    print("\n" + "=" * 70)
    print(f"FILE: {name}")
    print("=" * 70)
    try:
        xl = pd.ExcelFile(path)
    except Exception as e:
        print(f"  Could not open as Excel: {e}")
        return

    print(f"Sheet names ({len(xl.sheet_names)}): {xl.sheet_names}")

    for sheet in xl.sheet_names[:5]:  # first 5 sheets is plenty to understand shape
        print("\n" + "-" * 70)
        print(f"SHEET: {sheet!r}")
        print("-" * 70)
        try:
            df = xl.parse(sheet, nrows=3)
            full = xl.parse(sheet, usecols=[0])
            print(f"  Columns ({len(df.columns)}):")
            for c in df.columns:
                print(f"    - {c!r}")
            print(f"  Approx row count: {len(full):,}")
            print("\n  First 2 rows (truncated to 80 chars per cell):")
            for idx, row in df.head(2).iterrows():
                print(f"\n   Row {idx}:")
                for c in df.columns:
                    val = str(row[c])
                    if len(val) > 80:
                        val = val[:80] + "…"
                    print(f"     {c!r}: {val}")
        except Exception as e:
            print(f"  Could not parse sheet: {e}")


def main():
    any_failed = False
    for name, url in FILES.items():
        try:
            path = download(name, url)
            inspect(name, path)
        except Exception as e:
            any_failed = True
            print(f"\n{name}: FAILED — {e}")

    if any_failed:
        print("\n" + "=" * 70)
        print("FALLBACK if a download still fails:")
        print("  1. Open the URL directly in your phone/desktop browser —")
        print("     it should download normally there.")
        print("  2. In Colab, open the Files panel (folder icon), tap the")
        print("     upload icon, and upload the .xlsx into ./veda_xlsx/")
        print("     named FourVedas.xlsx / VedaAnukriti.xlsx as appropriate.")
        print("  3. Re-run this script — it skips anything already present.")
        print("=" * 70)

    print("\n" + "=" * 70)
    print("Paste this whole output back. What matters most:")
    print("  - Which columns hold ACCENTED text (samhita and pada-patha)")
    print("  - Whether there's a Chandas/metre column, and its values")
    print("  - Which Vedas are covered, and how rows are keyed/numbered")
    print("=" * 70)


if __name__ == "__main__":
    main()
