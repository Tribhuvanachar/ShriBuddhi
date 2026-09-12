#!/usr/bin/env python3
"""
import_veda_phase2.py — commentary and translation for the Vedas OUTSIDE the
Ṛgveda, which today carry none at all.

THE GAP THIS CLOSES (measured against the repo, 18 Aug 2026)

    Atharvaveda Śaunaka Saṃhitā          5,977 items   0 commentary, 0 translation
    Śukla Yajurveda Mādhyandina Saṃhitā  1,975 items   0 commentary, 0 translation
    Kṛṣṇa Yajurveda Taittirīya Saṃhitā     696 items   0 commentary, 0 translation
    Sāmaveda Kauthuma (both ārcikas)     1,875 items   -> see propagate_samaveda.py
    Taittirīya Brāhmaṇa / Āraṇyaka       2,404 items   -> no PD translation exists

    12,927 items in total. The Ṛgveda's five Western translation layers stop at
    the Ṛgveda; everything else in the Vedic corpus is bare mūla.

WHAT IT ADDS, per mantra, into the existing `commentaries` dict:

    Atharvaveda      commentaries.griffith        Griffith 1895–6
                     commentaries.whitney         Whitney & Lanman 1905 (translation)
                     commentaries.whitney_notes   Whitney's apparatus — THIS IS THE
                                                  ONE THAT REPORTS SĀYAṆA'S READINGS
    Śukla Yajurveda  commentaries.griffith        Griffith 1899
    Taittirīya S.    commentaries.keith           Keith 1914 (HOS 18–19)

WHY NO SANSKRIT SĀYAṆA HERE EITHER
    Same as the Ṛgveda: none of the four has a digitised Sanskrit bhāṣya. Only
    page scans (Ānandāśrama TS 1940, the AV Sāyaṇa-bhāṣya volumes, Mahīdhara's
    Vedadīpa), and Devanagari OCR from those is not ingestible unreviewed.
    Whitney and Keith are the closest available: both translate from, and argue
    with, Sāyaṇa on the page.

WHY NO GRIFFITH SĀMAVEDA
    Griffith follows Benfey's Rāṇāyanīya arrangement — 585 verses in Part One
    against DGE's 650 in the Pūrvārcika, because Benfey omits the Āraṇyaka-gāna
    and the Mahānāmnī ārcika. Rather than guess an offset, the Sāmaveda is
    served by propagate_samaveda.py, which reaches 94% coverage from the
    Ṛgveda parallels already recorded in the data. No fetching, no guessing.

USAGE
    python import_veda_phase2.py --dge-root ../bhumandala/dge --corpus av
    python import_veda_phase2.py --dge-root ../bhumandala/dge --corpus all
    python import_veda_phase2.py --dge-root ../bhumandala/dge --corpus ts --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import Fetcher, append_jsonl, load_json, save_json
from parsers import sacredtexts_veda as stv
from parsers import wikisource as wk

AV_DIR = "data/vedas/atharvaveda/shaunaka_shakha/samhita"
SYV = "data/vedas/yajurveda/shukla_yajurveda/vajasaneyi_madhyandina_shakha/samhita/data.json"
TS_DIR = "data/vedas/yajurveda/krishna_yajurveda/taittiriya_shakha/samhita"

ATTRIBUTION = {
    "griffith_av": {"commentator": "R. T. H. Griffith", "work": "Hymns of the Atharvaveda (1895–6)",
                    "language": "en", "via": "sacred-texts.com", "licence": "Public domain."},
    "whitney": {"commentator": "W. D. Whitney & C. R. Lanman",
                "work": "Atharva-Veda Saṃhitā (Harvard Oriental Series 7–8, 1905)",
                "language": "en", "via": "en.wikisource.org",
                "licence": "Public domain (1905); Wikisource transcription CC BY-SA. "
                           "Whitney's notes report Sāyaṇa's readings throughout."},
    "griffith_yv": {"commentator": "R. T. H. Griffith", "work": "The Texts of the White Yajurveda (1899)",
                    "language": "en", "via": "sacred-texts.com", "licence": "Public domain."},
    "keith": {"commentator": "A. B. Keith",
              "work": "The Veda of the Black Yajus School: Taittirīya Saṃhitā (HOS 18–19, 1914)",
              "language": "en", "via": "sacred-texts.com",
              "licence": "Public domain. Keith's footnotes carry his references to "
                         "Sāyaṇa and Bhaṭṭa Bhāskara."},
}


def group_ids(items, depth):
    """{(k, s): [r, …]} for depth 3, {k: [n, …]} for depth 2."""
    out = defaultdict(list)
    for it in items:
        parts = it["id"].split(".")
        if len(parts) < depth:
            continue
        try:
            nums = [int(p) for p in parts[:depth]]
        except ValueError:
            continue
        out[tuple(nums[:depth - 1])].append(nums[depth - 1])
    return out


def merge(item, key, text, stats, overwrite):
    if not text:
        return
    comm = item.setdefault("commentaries", {})
    if comm.get(key) and not overwrite:
        stats[f"{key}_existing"] += 1
        return
    comm[key] = text
    stats[f"{key}_added"] += 1


# --------------------------------------------------------------- Atharvaveda

def do_atharvaveda(dge: Path, f: Fetcher, args, dump):
    stats = Counter()
    for kanda in range(1, 21):
        path = dge / AV_DIR / f"kanda_{kanda:02d}" / "data.json"
        if not path.exists():
            continue
        data = load_json(path)
        items = data.get("items", [])
        by_id = {it["id"]: it for it in items}
        suktas = group_ids(items, 3)
        print(f"\n== Atharvaveda kāṇḍa {kanda}: {len(items)} mantras in {len(suktas)} sūktas")

        for (k, s), verses in sorted(suktas.items()):
            html = f.get(stv.av_url(k, s), allow_missing=True)
            stats["pages"] += 1
            if not html:
                stats["page_missing"] += 1
                continue
            hymn = stv.parse_av_hymn(html)
            if hymn["book"] and hymn["book"] != k:
                stats["page_misaligned"] += 1
                continue
            for r in verses:
                text = hymn["verses"].get(r)
                if not text:
                    stats["verse_missing"] += 1
                    continue
                merge(by_id[f"{k}.{s}.{r}"], "griffith", text, stats, args.overwrite)
                append_jsonl(dump, [{"corpus": "atharvaveda", "id": f"{k}.{s}.{r}",
                                     "layer": "griffith", "text": text,
                                     "url": stv.av_url(k, s)}])

        if stats["griffith_added"] and not args.dry_run:
            data.setdefault("commentary_sources", {})["griffith"] = ATTRIBUTION["griffith_av"]
            save_json(path, data)
            print(f"   -> wrote {path.relative_to(dge)}")
    return stats


def do_atharvaveda_whitney(dge: Path, f: Fetcher, args, dump):
    """Books I–XIX only; Book XX is not transcribed on Wikisource."""
    stats = Counter()
    for kanda in range(1, 20):
        path = dge / AV_DIR / f"kanda_{kanda:02d}" / "data.json"
        if not path.exists():
            continue
        data = load_json(path)
        items = data.get("items", [])
        by_id = {it["id"]: it for it in items}
        suktas = group_ids(items, 3)
        print(f"\n== Whitney AV kāṇḍa {kanda}: {len(suktas)} hymns")
        for (k, s), verses in sorted(suktas.items()):
            body = f.get(wk.parse_url(wk.av_title(k, s)), allow_missing=True)
            stats["pages"] += 1
            html = wk.html_from_parse(body or "")
            if not html:
                stats["page_missing"] += 1
                continue
            parsed = wk.parse_whitney_hymn(html)
            for r in verses:
                row = parsed.get(r)
                if not row:
                    stats["verse_missing"] += 1
                    continue
                merge(by_id[f"{k}.{s}.{r}"], "whitney", row["translation"], stats, args.overwrite)
                merge(by_id[f"{k}.{s}.{r}"], "whitney_notes", row["commentary"], stats, args.overwrite)
                append_jsonl(dump, [{"corpus": "atharvaveda", "id": f"{k}.{s}.{r}",
                                     "layer": "whitney", **row}])
        if stats["whitney_added"] and not args.dry_run:
            src = data.setdefault("commentary_sources", {})
            src["whitney"] = ATTRIBUTION["whitney"]
            src["whitney_notes"] = dict(ATTRIBUTION["whitney"],
                                        work=ATTRIBUTION["whitney"]["work"] + " — critical notes")
            save_json(path, data)
            print(f"   -> wrote {path.relative_to(dge)}")
    return stats


# ---------------------------------------------------------- Śukla Yajurveda

def do_shukla_yajurveda(dge: Path, f: Fetcher, args, dump):
    stats = Counter()
    path = dge / SYV
    if not path.exists():
        print(f"!! missing {path}", file=sys.stderr)
        return stats
    data = load_json(path)
    items = data.get("items", [])
    by_id = {it["id"]: it for it in items}
    books = group_ids(items, 2)
    print(f"\n== Śukla Yajurveda: {len(items)} mantras in {len(books)} adhyāyas")

    for (b,), verses in sorted(books.items()):
        html = f.get(stv.wyv_url(b), allow_missing=True)
        stats["pages"] += 1
        if not html:
            stats["page_missing"] += 1
            continue
        page = stv.parse_wyv_book(html, fallback=b)
        if page["book"] and page["book"] != b:
            stats["page_misaligned"] += 1
            continue
        for n in verses:
            text = page["verses"].get(n)
            if not text:
                stats["verse_missing"] += 1
                continue
            merge(by_id[f"{b}.{n}"], "griffith", text, stats, args.overwrite)
            append_jsonl(dump, [{"corpus": "shukla_yajurveda", "id": f"{b}.{n}",
                                 "layer": "griffith", "text": text, "url": stv.wyv_url(b)}])

    if stats["griffith_added"] and not args.dry_run:
        data.setdefault("commentary_sources", {})["griffith"] = ATTRIBUTION["griffith_yv"]
        save_json(path, data)
        print(f"   -> wrote {path.relative_to(dge)}")
    return stats


# -------------------------------------------------------------- Taittirīya

def do_taittiriya(dge: Path, f: Fetcher, args, dump):
    """Keith's refs are kāṇḍa.prapāṭhaka.anuvāka, which is exactly DGE's id
    scheme here — verified: DGE's TS 1.1 holds 14 units, the standard
    prapāṭhaka has 14 anuvākas."""
    stats = Counter()
    for kanda in range(1, 8):
        path = dge / TS_DIR / f"kanda_{kanda:02d}" / "data.json"
        if not path.exists():
            continue
        html = f.get(stv.ts_url(kanda), allow_missing=True)
        stats["pages"] += 1
        if not html:
            stats["page_missing"] += 1
            continue
        keith = stv.parse_ts_kanda(html)
        data = load_json(path)
        items = data.get("items", [])
        print(f"\n== Taittirīya kāṇḍa {kanda}: {len(items)} units, "
              f"{len(keith)} anuvākas parsed from Keith")
        for it in items:
            text = keith.get(it["id"])
            if not text:
                stats["verse_missing"] += 1
                continue
            merge(it, "keith", text, stats, args.overwrite)
            append_jsonl(dump, [{"corpus": "taittiriya_samhita", "id": it["id"],
                                 "layer": "keith", "text": text, "url": stv.ts_url(kanda)}])
        if stats["keith_added"] and not args.dry_run:
            data.setdefault("commentary_sources", {})["keith"] = ATTRIBUTION["keith"]
            save_json(path, data)
            print(f"   -> wrote {path.relative_to(dge)}")
    return stats


CORPORA = {
    "av": ("Atharvaveda — Griffith", do_atharvaveda),
    "av-whitney": ("Atharvaveda — Whitney & Lanman", do_atharvaveda_whitney),
    "syv": ("Śukla Yajurveda — Griffith", do_shukla_yajurveda),
    "ts": ("Taittirīya Saṃhitā — Keith", do_taittiriya),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dge-root", required=True)
    ap.add_argument("--corpus", action="append",
                    help=f"one of {', '.join(CORPORA)} or 'all' (repeatable)")
    ap.add_argument("--out-dir", default="dump")
    ap.add_argument("--cache-dir", default=".httpcache")
    ap.add_argument("--delay", type=float, default=1.2)
    ap.add_argument("--min-match", type=float, default=0.5,
                    help="fail a corpus if fewer than this fraction of its mantras "
                         "matched — catches a parser that quietly fell apart")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    dge = Path(args.dge_root)
    if not (dge / "data" / "schemas.json").exists():
        print(f"!! {dge} does not look like the dge/ directory", file=sys.stderr)
        return 2

    wanted = args.corpus or ["all"]
    if "all" in wanted:
        wanted = list(CORPORA)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dump = out / "veda_phase2.jsonl"
    if dump.exists():
        dump.unlink()

    f = Fetcher(cache_dir=args.cache_dir, delay=args.delay, offline=args.offline)
    report = {}
    failed = []
    for key in wanted:
        if key not in CORPORA:
            print(f"!! unknown corpus '{key}'", file=sys.stderr)
            return 2
        label, fn = CORPORA[key]
        print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
        stats = fn(dge, f, args, dump)
        added = sum(v for k, v in stats.items() if k.endswith("_added"))
        missing = stats.get("verse_missing", 0)
        denom = added + missing
        rate = added / denom if denom else 0.0
        report[key] = {"label": label, **dict(stats), "match_rate": round(rate, 3)}
        print(f"\n   {added:,} entries added, {missing:,} unmatched "
              f"({rate:.0%} match rate)")
        if denom and rate < args.min_match:
            failed.append(f"{key}: only {rate:.0%} of mantras matched")

    save_json(out / "COUNTS_veda_phase2.json", {"corpora": report, "http": f.stats}, indent=2)
    print("\n" + json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        print("\n!! LOW MATCH RATE:\n   " + "\n   ".join(failed), file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
