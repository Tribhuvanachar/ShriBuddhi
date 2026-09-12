"""
DGE — Validate FourVedas.xlsx against independent sources
==========================================================
Two checks, before importing ~20,000 mantras from this file:

1. AUTOMATED: compare all 10,552 Rigveda mantras in FourVedas against
   the Rigveda already live on the DGE site — which came from a
   completely independent source (VedaWeb's TEI, "eichler" witness,
   Cologne University). Two unrelated scholarly digitisations agreeing
   across 10,552 verses is far stronger evidence than eyeballing a few.

2. MANUAL: print random samples from Yajurveda, Samaveda and Atharvaveda
   (which have no independent copy on the site yet) for review against
   whatever reference you prefer.

Usage (Colab, after inspect_veda_xlsx.py has downloaded the file):
    !pip install requests openpyxl pandas
"""

import json
import random
import re
import unicodedata

import pandas as pd
import requests

XLSX = "./veda_xlsx/FourVedas.xlsx"
LIVE_URL = ("https://tribhuvanachar.github.io/bhumandala/data/vedas/rigveda/"
            "shakala_shakha/samhita/mandala_{:02d}/data.json")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DGE-validator/1.0)"}


def normalize(text):
    """
    Strip differences that are formatting rather than textual:
      - the "ओ३म्" invocation some editions prefix to every mantra
      - pada separators (VedaWeb uses "/", this file uses "।"/"॥")
      - all whitespace
      - Unicode normalisation (NFC) so identical glyphs compare equal
    What remains is the actual akshara + accent content.
    """
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFC", text)
    t = t.replace("ओ३म्", "").replace("ॐ", "")
    t = re.sub(r"[।॥/]", "", t)
    t = re.sub(r"\s+", "", t)
    return t.strip()


def load_rigveda_from_xlsx():
    # Row 0 of the sheet is the real header row; actual data starts at row 1.
    df = pd.read_excel(XLSX, sheet_name="Rik", header=1)
    cols = list(df.columns)
    # Column positions confirmed from the earlier structure inspection:
    #  5 = mandala.sukta.mantra reference, 15 = accented samhita,
    #  16 = accented padapatha, 20 = devata, 21 = chandas, 23 = rishi
    out = {}
    for _, row in df.iterrows():
        ref = str(row[cols[5]]).strip()
        if not ref or ref == "nan":
            continue
        out[ref] = {
            "samhita": str(row[cols[15]]),
            "padapatha": str(row[cols[16]]),
            "devata": str(row[cols[20]]),
            "chandas": str(row[cols[21]]),
            "rishi": str(row[cols[23]]),
        }
    return out


def load_rigveda_from_site():
    live = {}
    for m in range(1, 11):
        url = LIVE_URL.format(m)
        print(f"  fetching mandala {m:02d} ...")
        r = requests.get(url, timeout=120, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            # Site ids look like "1.1.01"; xlsx refs look like "1.1.1".
            parts = item.get("id", "").split(".")
            if len(parts) == 3:
                key = f"{int(parts[0])}.{int(parts[1])}.{int(parts[2])}"
                live[key] = item.get("samhita_patha", "")
    return live


def main():
    print("Loading FourVedas Rigveda sheet ...")
    xlsx_rv = load_rigveda_from_xlsx()
    print(f"  {len(xlsx_rv):,} mantras in xlsx")

    print("\nFetching live Rigveda from the DGE site (VedaWeb/eichler source) ...")
    live_rv = load_rigveda_from_site()
    print(f"  {len(live_rv):,} mantras live")

    print("\n" + "=" * 70)
    print("AUTOMATED CROSS-CHECK: FourVedas vs VedaWeb/eichler")
    print("=" * 70)

    common = set(xlsx_rv) & set(live_rv)
    only_xlsx = set(xlsx_rv) - set(live_rv)
    only_live = set(live_rv) - set(xlsx_rv)
    print(f"Reference IDs in both: {len(common):,}")
    print(f"Only in xlsx: {len(only_xlsx):,}   Only on site: {len(only_live):,}")
    if only_xlsx:
        print(f"  sample xlsx-only ids: {sorted(only_xlsx)[:5]}")
    if only_live:
        print(f"  sample site-only ids: {sorted(only_live)[:5]}")

    exact = 0
    mismatches = []
    for key in sorted(common):
        a = normalize(xlsx_rv[key]["samhita"])
        b = normalize(live_rv[key])
        if a == b:
            exact += 1
        else:
            mismatches.append(key)

    pct = (exact / len(common) * 100) if common else 0
    print(f"\nEXACT text matches: {exact:,} / {len(common):,}  ({pct:.2f}%)")
    print(f"Mismatches: {len(mismatches):,}")

    if mismatches:
        print("\nUp to 8 mismatches shown in full, for judging whether they're")
        print("real textual differences or just edition/formatting variants:")
        for key in random.sample(mismatches, min(8, len(mismatches))):
            print("\n" + "-" * 60)
            print(f"  {key}")
            print(f"  xlsx: {xlsx_rv[key]['samhita']}")
            print(f"  site: {live_rv[key]}")

    print("\n" + "=" * 70)
    print("RANDOM SAMPLES — Rigveda (with the NEW fields we're importing)")
    print("=" * 70)
    for key in random.sample(sorted(common), min(5, len(common))):
        r = xlsx_rv[key]
        print(f"\n  RV {key}")
        print(f"    samhita  : {r['samhita']}")
        print(f"    padapatha: {r['padapatha'][:120]}")
        print(f"    rishi    : {r['rishi']}")
        print(f"    devata   : {r['devata']}")
        print(f"    chandas  : {r['chandas']}")

    # The other three Vedas have no independent copy on the site yet, so
    # these are printed for manual review rather than automated comparison.
    for sheet, label, hdr, refcol, textcol, extracols in [
        ("Yaju", "YAJURVEDA (Shukla)", 1, 1, 6, {"rishi": 12, "devata": 11, "chandas": 13}),
        ("Atharva", "ATHARVAVEDA (Shaunaka)", 1, 5, 9, {"rishi": 13, "devata": 14, "chandas": 15}),
        ("Saam", "SAMAVEDA (Kauthuma)", 1, 2, 22, {"rishi": 27, "devata": 29, "chandas": 28}),
    ]:
        print("\n" + "=" * 70)
        print(f"RANDOM SAMPLES — {label} (for manual verification)")
        print("=" * 70)
        try:
            df = pd.read_excel(XLSX, sheet_name=sheet, header=hdr)
            cols = list(df.columns)
            df = df.dropna(subset=[cols[textcol]])
            for _, row in df.sample(min(5, len(df))).iterrows():
                print(f"\n  ref: {row[cols[refcol]]}")
                print(f"    text   : {str(row[cols[textcol]])[:160]}")
                for name, idx in extracols.items():
                    print(f"    {name:9s}: {row[cols[idx]]}")
        except Exception as e:
            print(f"  Could not sample {sheet}: {e}")

    print("\n" + "=" * 70)
    print("Paste this output back. The headline number is the % exact match")
    print("on Rigveda — two independent digitisations agreeing there is the")
    print("real evidence that this data is sound.")
    print("=" * 70)


if __name__ == "__main__":
    main()
