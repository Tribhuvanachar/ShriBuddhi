#!/usr/bin/env python3
"""
import_upanishads.py — fill DGE's thirteen empty principal-Upaniṣad folders.

THE STATE THIS FIXES
    Every one of these exists in taxonomy.json and holds ZERO items:

      rigveda/…/upanishads/aitareya_upanishad, kausitaki_upanishad
      samaveda/…/upanishad/chandogya_upanishad, kena_upanishad
      yajurveda/krishna/…/katha_upanishad, taittiriya_upanishad,
                          maitrayaniya_upanishad
      yajurveda/shukla/…/isha_upanishad (+ _kanva),
                          brihadaranyaka_upanishad_madhyandina (+ _kanva)
      atharvaveda/…/upanishads/mundaka_upanishad, mandukya_upanishad,
                          prashna_upanishad

    The most-read texts in the whole corpus, and the shelf is bare.

WHY THE IDS LINE UP WITHOUT GUESSWORK
    Both sources are self-describing at exactly the level DGE needs:

    * GRETIL tags each unit with its own reference — `ChUp_1,1.1` is
      prapāṭhaka 1, khaṇḍa 1, verse 1, and `ChUpBh_1,1.1` is Śaṅkara on it, in
      the same file. The tag IS the id.
    * Müller's SBE prints one file per khaṇḍa/section, in order, and the
      section counts of each Upaniṣad are fixed and known (Chāndogya's eight
      prapāṭhakas run 13, 24, 19, 17, 24, 16, 26, 15 khaṇḍas = 154 files =
      exactly the 154 files SBE 1 devotes to it). So file index -> (chapter,
      section) is arithmetic, not inference — and it is asserted at run time:
      if the page count in a range does not equal the structure's total, that
      Upaniṣad is skipped rather than written misaligned.

WHAT LANDS
    items[].samhita_patha        Sanskrit mūla (IAST, as GRETIL publishes it)
    items[].commentaries.muller  Müller's English (SBE 1 / SBE 15, 1879–1884)
    items[].commentaries.shankara  Śaṅkara's bhāṣya, where the GRETIL file
                                   carries it — a bonus from the same fetch

USAGE
    python import_upanishads.py --dge-root ../bhumandala/dge
    python import_upanishads.py --dge-root ../bhumandala/dge --only chandogya --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from common import Fetcher, load_json, save_json
from parsers.upanishad import parse_gretil_upanishad, parse_sbe_sections, sbe_url

GRC = "https://gretil.sub.uni-goettingen.de/gretil/corpustei/transformations/html"

VEDAS = "data/vedas"

# structure: the number of verses is irrelevant; what matters is how many
# SECTIONS each chapter has, because that is what maps file index -> id.
UPANISHADS = {
    "chandogya": {
        "title": "Chāndogya Upaniṣad",
        "folder": f"{VEDAS}/samaveda/kauthuma_shakha/upanishad/chandogya_upanishad",
        "gretil": f"{GRC}/sa_chAndogyopaniSad-comm.htm",
        "sbe": {"volume": 1, "first": 22, "last": 175},
        "structure": [13, 24, 19, 17, 24, 16, 26, 15],       # 154 khaṇḍas
        "levels": 3,
    },
    "kena": {
        "title": "Kena Upaniṣad",
        "folder": f"{VEDAS}/samaveda/jaiminiya_shakha/upanishad/kena_upanishad",
        "gretil": None,          # GRETIL lists it but hosts no converted file
        "sbe": {"volume": 1, "first": 176, "last": 179},
        "structure": [1, 1, 1, 1],
        "levels": 2,
    },
    "kausitaki": {
        "title": "Kauṣītaki Upaniṣad",
        "folder": f"{VEDAS}/rigveda/shakala_shakha/upanishads/kausitaki_upanishad",
        "gretil": None,
        "sbe": {"volume": 1, "first": 239, "last": 242},
        "structure": [1, 1, 1, 1],
        "levels": 2,
    },
    "isha": {
        "title": "Īśā Upaniṣad",
        "folder": f"{VEDAS}/yajurveda/shukla_yajurveda/vajasaneyi_madhyandina_shakha/upanishad/isha_upanishad",
        "also": [f"{VEDAS}/yajurveda/shukla_yajurveda/vajasaneyi_kanva_shakha/upanishad/isha_upanishad_kanva"],
        "gretil": f"{GRC}/sa_IzopaniSad-or-IzAvAsyopaniSadkANva-recension-comm.htm",
        "sbe": {"volume": 1, "first": 243, "last": 243},
        "structure": [1],
        "levels": 1,
    },
    "katha": {
        "title": "Kaṭha Upaniṣad",
        "folder": f"{VEDAS}/yajurveda/krishna_yajurveda/katha_shakha/upanishad/katha_upanishad",
        "gretil": f"{GRC}/sa_kaThopaniSad.htm",
        "sbe": {"volume": 15, "first": 10, "last": 15},
        "structure": [1, 1, 1, 1, 1, 1],                     # six vallīs
        "levels": 2,
    },
    "mundaka": {
        "title": "Muṇḍaka Upaniṣad",
        "folder": f"{VEDAS}/atharvaveda/shaunaka_shakha/upanishads/mundaka_upanishad",
        "gretil": None,
        "sbe": {"volume": 15, "first": 16, "last": 21},
        "structure": [2, 2, 2],                              # 3 muṇḍakas × 2 khaṇḍas
        "levels": 3,
    },
    "taittiriya": {
        "title": "Taittirīya Upaniṣad",
        "folder": f"{VEDAS}/yajurveda/krishna_yajurveda/taittiriya_shakha/upanishad/taittiriya_upanishad",
        "gretil": f"{GRC}/sa_taittirIyopaniSad-zaMkarabhASya.htm",
        "sbe": {"volume": 15, "first": 22, "last": 52},
        "structure": [12, 9, 10],                            # 31 anuvākas
        "levels": 3,
    },
    "brihadaranyaka": {
        "title": "Bṛhadāraṇyaka Upaniṣad",
        "folder": f"{VEDAS}/yajurveda/shukla_yajurveda/vajasaneyi_kanva_shakha/upanishad/brihadaranyaka_upanishad_kanva",
        "also": [f"{VEDAS}/yajurveda/shukla_yajurveda/vajasaneyi_madhyandina_shakha/upanishad/brihadaranyaka_upanishad_madhyandina"],
        "gretil": f"{GRC}/sa_bRhadAraNyakopaniSadkANva-recension-comm.htm",
        # sbe15098 is a duplicate of VI,4 in Hume's translation, not Müller's —
        # it must be skipped or every id after it shifts by one.
        "sbe": {"volume": 15, "first": 53, "last": 99, "skip": [98]},
        "structure": [6, 6, 9, 6, 15, 5],                    # 47 brāhmaṇas
        "levels": 3,
    },
    "svetasvatara": {
        "title": "Śvetāśvatara Upaniṣad",
        "folder": f"{VEDAS}/yajurveda/krishna_yajurveda/katha_shakha/upanishad/svetasvatara_upanishad",
        "create_if_missing": True,
        "gretil": f"{GRC}/sa_zvetAzvataropaniSad.htm",
        "sbe": {"volume": 15, "first": 100, "last": 105},
        "structure": [1, 1, 1, 1, 1, 1],
        "levels": 2,
    },
    "prashna": {
        "title": "Praśna Upaniṣad",
        "folder": f"{VEDAS}/atharvaveda/shaunaka_shakha/upanishads/prashna_upanishad",
        "gretil": f"{GRC}/sa_praznopaniSad-comm.htm",
        "sbe": {"volume": 15, "first": 106, "last": 111},
        "structure": [1, 1, 1, 1, 1, 1],                     # six questions
        "levels": 2,
    },
    "maitrayaniya": {
        "title": "Maitrāyaṇīya Upaniṣad",
        "folder": f"{VEDAS}/yajurveda/krishna_yajurveda/maitrayani_shakha/upanishad/maitrayaniya_upanishad",
        "gretil": None,
        "sbe": {"volume": 15, "first": 112, "last": 118},
        "structure": [1, 1, 1, 1, 1, 1, 1],                  # seven prapāṭhakas
        "levels": 2,
    },
    "mandukya": {
        "title": "Māṇḍūkya Upaniṣad",
        "folder": f"{VEDAS}/atharvaveda/shaunaka_shakha/upanishads/mandukya_upanishad",
        "gretil": f"{GRC}/sa_mANDUkyopaniSad-comm.htm",
        "sbe": None,          # Müller did not translate it in SBE 1 or 15
        "levels": 1,
    },
    "aitareya": {
        "title": "Aitareya Upaniṣad",
        "folder": f"{VEDAS}/rigveda/shakala_shakha/upanishads/aitareya_upanishad",
        "gretil": f"{GRC}/sa_aitareyopaniSad-comm.htm",
        "sbe": None,          # SBE 1 gives the whole Aitareya-Āraṇyaka instead
        "levels": 3,
    },
}

ATTRIBUTION = {
    "muller": {"commentator": "F. Max Müller", "work": "The Upanishads (SBE 1, 1879 / SBE 15, 1884)",
               "language": "en", "via": "sacred-texts.com", "licence": "Public domain."},
    "shankara": {"commentator": "Śaṅkarācārya", "work": "Bhāṣya", "language": "sa",
                 "via": "GRETIL corpustei",
                 "licence": "Text ancient; GRETIL digitisation carries its source edition's terms. "
                            "Keep attribution to GRETIL."},
    "mula": {"work": "Mūla text, IAST", "via": "GRETIL corpustei", "language": "sa",
             "licence": "Text ancient; GRETIL digitisation. Keep attribution to GRETIL."},
}


def section_ids(structure, levels):
    """File index -> id prefix. [13,24,…] with levels=3 gives
    ('1.1', '1.2', … '1.13', '2.1', …); with levels=2 it is just the running
    section number. Returns a list, one entry per SBE file, in page order."""
    out = []
    for chapter, count in enumerate(structure, start=1):
        for section in range(1, count + 1):
            if levels >= 3:
                out.append(f"{chapter}.{section}")
            elif levels == 2:
                out.append(str(chapter))
            else:
                out.append("")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dge-root", required=True)
    ap.add_argument("--only", action="append")
    ap.add_argument("--out-dir", default="dump")
    ap.add_argument("--cache-dir", default=".httpcache")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    dge = Path(args.dge_root)
    f = Fetcher(cache_dir=args.cache_dir, delay=args.delay, offline=args.offline)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = []

    for slug, cfg in UPANISHADS.items():
        if args.only and not any(o in slug for o in args.only):
            continue
        print(f"\n== {cfg['title']}")
        items: dict = {}
        stats = Counter()

        # ---- Sanskrit mūla (+ Śaṅkara, free with the same fetch) -----------
        if cfg.get("gretil"):
            body = f.get(cfg["gretil"], allow_missing=True)
            if not body:
                print(f"   !! GRETIL fetch failed: {cfg['gretil']}", file=sys.stderr)
                stats["gretil_missing"] += 1
            else:
                parsed = parse_gretil_upanishad(body)
                for ref, text in parsed["mula"]:
                    items.setdefault(ref, {"id": ref})["samhita_patha"] = text
                    stats["mula"] += 1
                for ref, text in parsed["bhashya"]:
                    items.setdefault(ref, {"id": ref}).setdefault("commentaries", {})["shankara"] = text
                    stats["shankara"] += 1
                print(f"   GRETIL: {stats['mula']} mūla units, {stats['shankara']} bhāṣya")

        # ---- Müller's English ----------------------------------------------
        sbe = cfg.get("sbe")
        if sbe:
            skip = set(sbe.get("skip", []))
            pages = [p for p in range(sbe["first"], sbe["last"] + 1) if p not in skip]
            prefixes = section_ids(cfg["structure"], cfg["levels"])

            # Collect SECTIONS, not pages. Müller occasionally prints two
            # sections in one file (sbe15054 holds both the second and third
            # brāhmaṇa of Bṛhadāraṇyaka I), so a file count is one short of the
            # section count and every id after it would shift by one.
            groups = []
            for page in pages:
                html = f.get(sbe_url(sbe["volume"], page), allow_missing=True)
                stats["sbe_pages"] += 1
                if not html:
                    stats["sbe_missing"] += 1
                    continue
                found = parse_sbe_sections(html)
                if not found:
                    stats["sbe_empty_pages"] += 1
                groups.extend(found)

            if len(groups) != len(prefixes):
                print(f"   !! SKIPPING English: {len(pages)} pages yielded "
                      f"{len(groups)} sections, but the structure describes "
                      f"{len(prefixes)}. Writing this would misalign every verse.",
                      file=sys.stderr)
                stats["structure_mismatch"] = 1
            else:
                for group, prefix in zip(groups, prefixes):
                    for n, text in group["verses"].items():
                        ref = f"{prefix}.{n}" if prefix else str(n)
                        items.setdefault(ref, {"id": ref}).setdefault(
                            "commentaries", {})["muller"] = text
                        stats["muller"] += 1
                print(f"   SBE {sbe['volume']}: {stats['sbe_pages']} pages -> "
                      f"{len(groups)} sections, {stats['muller']} verses")

        if not items:
            print("   -- nothing parsed")
            report.append({"slug": slug, "title": cfg["title"], **dict(stats), "items": 0})
            continue

        def sort_key(ref):
            try:
                return tuple(int(x) for x in ref.split("."))
            except ValueError:
                return (10 ** 6,)

        ordered = [items[k] for k in sorted(items, key=sort_key)]
        for it in ordered:
            it["reference"] = f"{cfg['title']} {it['id']}"
        data = {
            "schema": "vedic_text",
            "default_author": "Apaurusheya (Upaniṣad)",
            "commentary_sources": {k: v for k, v in ATTRIBUTION.items()
                                   if k != "shankara" or stats["shankara"]},
            "items": ordered,
        }
        n_mula = sum(1 for i in ordered if i.get("samhita_patha"))
        n_en = sum(1 for i in ordered if (i.get("commentaries") or {}).get("muller"))
        n_sb = sum(1 for i in ordered if (i.get("commentaries") or {}).get("shankara"))
        print(f"   => {len(ordered)} units · {n_mula} with mūla · {n_en} with Müller "
              f"· {n_sb} with Śaṅkara")
        report.append({"slug": slug, "title": cfg["title"], "items": len(ordered),
                       "mula": n_mula, "muller": n_en, "shankara": n_sb, **dict(stats)})

        save_json(out / f"upanishad__{slug}.json", data)
        targets = [cfg["folder"]] + cfg.get("also", [])
        for rel in targets:
            target = dge / rel / "data.json"
            if not target.exists() and not cfg.get("create_if_missing"):
                print(f"   -- {rel} does not exist; dump only")
                continue
            if args.dry_run:
                continue
            existing = load_json(target) if target.exists() else None
            if existing and existing.get("items"):
                print(f"   -- {rel} already has {len(existing['items'])} items; not overwriting")
                continue
            save_json(target, data)
            print(f"   -> wrote {rel}/data.json")

    save_json(out / "COUNTS_upanishads.json", {"upanishads": report, "http": f.stats}, indent=2)
    print("\n" + json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
