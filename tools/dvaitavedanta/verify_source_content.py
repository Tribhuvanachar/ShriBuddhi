#!/usr/bin/env python3
"""Re-fetch the live dvaitavedanta.in pages behind a data.json tree and check
that each stored item's sanskrit_text is still genuinely present on the site.

verify_extract.py checks the STORED data's own internal shape (Devanagari
ratio, duplicate ids, missing source.url) — it never touches the network.
This is the complementary check the project lead asked for: does the text we
extracted still match what the original source actually says, verified by
re-fetching the exact source.url on every item and re-running the SAME parser
(dv_parse.parse_page) that produced the stored data in the first place, so
the comparison is apples-to-apples rather than a second, differently-biased
extraction path.

One page backs many items (a grantha's mula + every commentary layer on it
share a URL), so this fetches each unique source.url once and checks every
item that claims it, using the on-disk HTTP cache (default .dv_cache, the
same cache import_dvaitavedanta.py uses) so a re-run resumes for free and a
full sweep never re-downloads a page it already checked today.

Per item, one of:
  MATCH        stored text found verbatim (whitespace-normalised) in the
               live page's re-parsed text.
  MATCH_LOOSE  found only after also collapsing all whitespace -- almost
               certainly the same content, reformatted.
  DRIFT        not found, but a close match exists elsewhere on the live
               page (similarity ratio reported) -- likely edited upstream.
  MISSING      not found anywhere on the live page, no close match either --
               the passage may have been removed or the page restructured.
  PAGE_EMPTY   the URL now returns no content at all (container/removed).
  UNREACHABLE  the URL could not be fetched (404/403/410/network failure).
  BLOCKED      the URL kept answering with a bot-challenge interstitial
               instead of real content even after retries -- rate-limiting,
               not evidence anything is actually missing; excluded from
               --strict's failure count for that reason.

Usage
    python tools/dvaitavedanta/verify_source_content.py \\
        --data data/darshana/vedanta/dvaita/DvaitaVedantaIn/dasha_prakarana_granthas \\
        --limit 50 --out /tmp/verify_report.json

    # Full sweep of everything scraped from dvaitavedanta.in, resumable:
    python tools/dvaitavedanta/verify_source_content.py --strict
"""

from __future__ import annotations

import argparse
import difflib
import glob
import json
import os
import random
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dv_parse import clean_text, parse_page  # noqa: E402
from import_dvaitavedanta import Fetcher  # noqa: E402

DEFAULT_DATA = "data/darshana/vedanta/dvaita/DvaitaVedantaIn"
DEFAULT_CACHE = ".dv_cache"
DEFAULT_UA = "Mozilla/5.0 (compatible; BhumandalaVerify/1.0; +https://github.com/Tribhuvanachar/bhumandala)"
PROGRESS_EVERY = 5
LOOSE_MIN_LEN = 6          # below this, whitespace-collapsed substring checks are too noisy
DRIFT_SIMILARITY_FLOOR = 0.6  # below this, call it MISSING rather than DRIFT
CHALLENGE_RETRIES = 3
CHALLENGE_BACKOFF = 5.0

# dvaitavedanta.in occasionally answers a real request with an HTTP-200
# holding page instead of content -- a "One moment, please..." spinner that
# JS-reloads after 5s (a bot-challenge/rate-limit interstitial, not a 3xx/5xx
# so Fetcher's own retry-on-status logic never sees it and happily caches it
# forever as if it were the real page). Caught live during this tool's own
# testing: a page that legitimately had 6 commentary layers came back as
# this spinner and would otherwise have been misreported as PAGE_EMPTY --
# "the source removed this content" -- when nothing was actually removed.
CHALLENGE_RE = re.compile(r"One moment, please\.\.\.|window\.location\.reload\(\)")


def collapse(text: str) -> str:
    return "".join(text.split())


def fetch_clean(fetcher: Fetcher, url: str):
    """fetcher.get(url), but never trust/cache a bot-challenge interstitial.

    Returns the real HTML, None (permanent fetch failure), or the sentinel
    "__BLOCKED__" if every retry kept hitting the challenge page.
    """
    for attempt in range(1, CHALLENGE_RETRIES + 1):
        html = fetcher.get(url)
        if html is None:
            return None
        if not CHALLENGE_RE.search(html):
            return html
        cache_path = fetcher._cache_path(url)
        if cache_path and os.path.exists(cache_path):
            os.remove(cache_path)  # never trust this html, never leave it cached
        time.sleep(CHALLENGE_BACKOFF * attempt)
    return "__BLOCKED__"


def find_data_jsons(root: str):
    for path in sorted(glob.glob(os.path.join(root, "**", "data.json"), recursive=True)):
        yield path


def load_items(root: str):
    """url -> list of {path, item, stored_text}."""
    by_url = defaultdict(list)
    n_files = n_items = 0
    for path in find_data_jsons(root):
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  ! skipping {path}: {exc}", file=sys.stderr)
            continue
        items = payload.get("items") or []
        if not items:
            continue
        n_files += 1
        top_url = payload.get("source_url")
        for item in items:
            source = item.get("source") or {}
            url = source.get("url") or top_url
            text = item.get("sanskrit_text") or ""
            if not url or not text:
                continue
            by_url[url].append({"path": path, "id": item.get("id"), "text": text})
            n_items += 1
    return by_url, n_files, n_items


def best_match(stored_norm: str, live_blob_norm: str, live_layers_norm: list[str]):
    """Return (verdict, detail) for one item against a page's live text.

    The DRIFT/MISSING similarity check is run per LIVE LAYER, not against
    the whole concatenated page blob: a page can carry a dozen unrelated
    commentary layers, and SequenceMatcher's ratio degrades with the size
    mismatch between a short item and a huge multi-layer blob, misreporting
    a genuinely close match (against its one real counterpart layer) as
    MISSING just because the blob around it is long. Comparing layer by
    layer and taking the best score is both the mathematically sound
    measure and matches how a page is actually organised.
    """
    if not live_blob_norm:
        return "PAGE_EMPTY", None
    if stored_norm in live_blob_norm:
        return "MATCH", None
    if len(stored_norm) >= LOOSE_MIN_LEN and collapse(stored_norm) in collapse(live_blob_norm):
        return "MATCH_LOOSE", None
    best_ratio = 0.0
    for layer_norm in live_layers_norm:
        if not layer_norm:
            continue
        ratio = difflib.SequenceMatcher(None, stored_norm, layer_norm).quick_ratio()
        if ratio > best_ratio:
            best_ratio = ratio
    if best_ratio >= DRIFT_SIMILARITY_FLOOR:
        return "DRIFT", round(best_ratio, 3)
    return "MISSING", round(best_ratio, 3)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=DEFAULT_DATA,
                        help="root to scan for data.json files (default: the whole DvaitaVedanta tree)")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="HTTP cache dir (SHA1-of-URL, shared with the importer)")
    parser.add_argument("--refresh-cache", action="store_true", help="ignore cached HTML, force a live refetch")
    parser.add_argument("--user-agent", default=DEFAULT_UA)
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between live fetches (cache hits are free)")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="max unique URLs to check (spot-check runs)")
    parser.add_argument("--sample", type=int, default=None, help="random sample of N unique URLs instead of all/first-N")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for --sample, for a reproducible spot-check")
    parser.add_argument("--out", default=None, help="write the full per-item JSON report here")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero if any item is DRIFT, MISSING, PAGE_EMPTY or UNREACHABLE")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.data):
        print(f"nothing to verify: {args.data} does not exist")
        return 0

    print(f"Scanning {args.data} ...")
    by_url, n_files, n_items = load_items(args.data)
    urls = list(by_url)
    print(f"  {n_files} data.json files, {n_items} items, {len(urls)} unique source URLs")

    if args.sample:
        rng = random.Random(args.seed)
        urls = rng.sample(urls, min(args.sample, len(urls)))
    elif args.limit:
        urls = urls[:args.limit]

    fetcher = Fetcher(args.cache, args.user_agent, delay=args.delay,
                      timeout=args.timeout, retries=args.retries, refresh=args.refresh_cache)

    counts = defaultdict(int)
    report = []
    start = time.time()
    for i, url in enumerate(urls, 1):
        if i == 1 or i % PROGRESS_EVERY == 0:
            print(f"  ({i}/{len(urls)}) fetching {url}")
        html = fetch_clean(fetcher, url)
        if html is None or html == "__BLOCKED__":
            verdict = "UNREACHABLE" if html is None else "BLOCKED"
            for entry in by_url[url]:
                counts[verdict] += 1
                report.append({"url": url, "path": entry["path"], "id": entry["id"],
                               "verdict": verdict})
            continue

        parsed = parse_page(html, url)
        live_layers_norm = [clean_text(layer.get("text", "")) for layer in parsed.get("layers", [])]
        live_blob_norm = clean_text("\n".join(live_layers_norm))

        for entry in by_url[url]:
            stored_norm = clean_text(entry["text"])
            verdict, detail = best_match(stored_norm, live_blob_norm, live_layers_norm)
            counts[verdict] += 1
            row = {"url": url, "path": entry["path"], "id": entry["id"], "verdict": verdict}
            if detail is not None:
                row["similarity"] = detail
            if verdict in ("DRIFT", "MISSING"):
                row["stored_preview"] = stored_norm[:120]
            report.append(row)

        if i % PROGRESS_EVERY == 0 or i == len(urls):
            elapsed = time.time() - start
            print(f"  [{i}/{len(urls)}] urls checked ({elapsed:.0f}s) — "
                  f"MATCH={counts['MATCH']+counts['MATCH_LOOSE']} "
                  f"DRIFT={counts['DRIFT']} MISSING={counts['MISSING']} "
                  f"PAGE_EMPTY={counts['PAGE_EMPTY']} UNREACHABLE={counts['UNREACHABLE']} "
                  f"BLOCKED={counts['BLOCKED']}")

    print()
    print("## verify_source_content summary")
    print(f"- URLs checked: {len(urls)} of {len(by_url)} total")
    print(f"- items checked: {sum(counts.values())}")
    for verdict in ("MATCH", "MATCH_LOOSE", "DRIFT", "MISSING", "PAGE_EMPTY", "UNREACHABLE", "BLOCKED"):
        if counts[verdict]:
            print(f"  {verdict}: {counts[verdict]}")
    print(f"- fetch stats: {dict(fetcher.stats)}")
    if counts["BLOCKED"]:
        print(f"- {counts['BLOCKED']} item(s) came from a URL that kept answering with a "
              f"bot-challenge page instead of content, even after {CHALLENGE_RETRIES} retries -- "
              f"not evidence of anything missing on the source, just rate-limiting. Re-run later "
              f"(the poisoned cache entries were already purged) rather than trusting this as a finding.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({"counts": dict(counts), "items": report}, handle, ensure_ascii=False, indent=1)
        print(f"- full report written to {args.out}")

    if args.strict:
        bad = counts["DRIFT"] + counts["MISSING"] + counts["PAGE_EMPTY"] + counts["UNREACHABLE"]
        if bad:
            print(f"\nSTRICT: {bad} item(s) did not verify cleanly.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
