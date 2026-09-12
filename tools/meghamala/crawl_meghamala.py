#!/usr/bin/env python3
"""
crawl_meghamala.py — the fetching half of the Śrī Rāmānuja Meghamālā sync.

importers/ramanuja_meghamala.py never touches the network: it turns a
knowledge-tree TSV plus a directory of cached pages into data.json files.
The TSV it was first run with was hand-made and is not in the repository.
This script rebuilds it from the live site and fills the cache, so the
importer can run unattended — and it does the one thing the importer cannot:
it knows WHICH granthas changed.

  1. The archive page (srivaishnavan.com/sri-ramanuja-meghamala/) is a
     server-rendered two-level accordion: category → grantha → leaf links.
     That is the tree; it is written to <work>/tree.tsv as
     "<category> > <grantha><TAB><leaf title><TAB><url>".
  2. Every leaf is a WordPress post. The site's REST API lists all posts
     with their modified_gmt (32 calls of 100), so a leaf that has not
     changed since the last run is known without fetching it.
  3. A grantha is re-fetched whole (all its leaves) when ANY of its leaves is
     new or modified, or when --all is given. The cache file name is
     md5(url).html, exactly what the importer expects. A grantha with a leaf
     that could not be fetched is reported and NOT passed on (the importer's
     --strict does the same on its side).
  4. State — the modified_gmt seen per leaf — lives in
     admin/config/sync/meghamala.state.json and is written with --write-state.

    python3 tools/meghamala/crawl_meghamala.py --work .mm --delay 1.0 --write-state
    python3 importers/ramanuja_meghamala.py --tree .mm/tree.tsv --cache .mm/cache \
        --granthas "$(cat .mm/changed.txt)" --strict --write

Prints a report; $GITHUB_STEP_SUMMARY gets it too. Exit 1 only when the
archive page itself cannot be read (nothing to sync from).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "importers"))

INDEX = "https://srivaishnavan.com/sri-ramanuja-meghamala/"
WP_POSTS = "https://srivaishnavan.com/wp-json/wp/v2/posts?per_page=100&_fields=link,modified_gmt&page={page}"
STATE = os.path.join(REPO, "admin", "config", "sync", "meghamala.state.json")
UA = ("DGE-source-sync/1.0 (+https://github.com/Tribhuvanachar/bhumandala; "
      "non-commercial, educational; permission recorded 2 Sep 2026)")


def fetch(url, timeout=90, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.headers, r.read()
        except Exception as exc:                                # noqa: BLE001
            last = exc
            time.sleep(3 * (i + 1))
    raise last


# --- 1. the tree ---------------------------------------------------------
ITEM_RE = re.compile(r'<div class="accordion-item">(.*?)(?=<div class="accordion-item">|$)', re.S)
BTN_RE = re.compile(r'<button[^>]*>(.*?)</button>', re.S)
LINK_RE = re.compile(r'<a href="(https://srivaishnavan\.com/[^"]+)"[^>]*>(.*?)</a>', re.S)


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s*\(\d+\)\s*$", "", s.strip())        # "Upanishads (70)" -> "Upanishads"
    return re.sub(r"\s+", " ", s).strip()


def scrape_tree(page: str):
    """-> rows [(category, grantha, leaf_title, url)], in page order."""
    rows = []
    # Outer items contain a nested accordion; split outer first, then inner.
    m = re.search(r'<div class="accordion" id="accordionExample">(.*)', page, re.S)
    if not m:
        raise SystemExit("archive page: no accordion found — the site's markup changed")
    body = m.group(1)
    outer_chunks = re.split(r'<div class="accordion-item"><h2 class="accordion-header" id="heading', body)[1:]
    for chunk in outer_chunks:
        b = BTN_RE.search(chunk)
        if not b:
            continue
        category = clean(b.group(1))
        inner_chunks = re.split(r'<div class="accordion-item"><h2[^>]*id="sub-heading', chunk)[1:]
        for ic in inner_chunks:
            ib = BTN_RE.search(ic)
            if not ib:
                continue
            grantha = clean(ib.group(1))
            for url, title in LINK_RE.findall(ic):
                rows.append((category, grantha, clean(title), html.unescape(url)))
    return rows


# --- 2. modified dates from the REST API --------------------------------------
def post_dates():
    out = {}
    page = 1
    while True:
        try:
            h, body = fetch(WP_POSTS.format(page=page))
        except Exception as exc:                                # noqa: BLE001
            print(f"  wp-json page {page}: {exc} — stopping; leaves not listed count as changed", file=sys.stderr)
            break
        for p in json.loads(body):
            out[p["link"]] = p.get("modified_gmt", "")
        total_pages = int(h.get("X-WP-TotalPages", "1") or 1)
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.5)
    return out


def cache_name(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest() + ".html"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default=".mm", help="working dir: tree.tsv, cache/, changed.txt, report.md")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--all", action="store_true", help="re-fetch every grantha, not only changed ones")
    ap.add_argument("--max-granthas", type=int, default=60, help="cap on granthas re-fetched in one run")
    ap.add_argument("--write-state", action="store_true")
    args = ap.parse_args()

    os.makedirs(os.path.join(args.work, "cache"), exist_ok=True)
    _, body = fetch(INDEX)
    page = body.decode("utf-8", "replace")
    rows = scrape_tree(page)
    if len(rows) < 1000:
        raise SystemExit(f"archive page: only {len(rows)} leaves scraped (expected ~2,400) — refusing to continue")
    with open(os.path.join(args.work, "tree.tsv"), "w", encoding="utf-8") as fh:
        for cat, gr, title, url in rows:
            fh.write(f"{cat} > {gr}\t{title}\t{url}\n")

    # importer-compatible keys, so --granthas can name exactly what changed
    from ramanuja_meghamala import CAT_SLUG, HELD_NODES, slugify  # noqa: E402
    by_grantha = {}
    unknown_cats = set()
    for cat, gr, title, url in rows:
        if gr in HELD_NODES:
            continue
        if cat not in CAT_SLUG:
            # "Periodicals", "Unpublished Manuscripts": magazine issues and
            # disclaimers, not granthas. Reported, never imported.
            unknown_cats.add(cat)
            continue
        key = f"{CAT_SLUG[cat]}/{slugify(gr)}"
        by_grantha.setdefault(key, []).append(url)

    dates = post_dates()
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"leaves": {}}
    seen = state.get("leaves", {})
    changed, reasons = [], {}
    for key, urls in by_grantha.items():
        why = None
        for u in urls:
            now = dates.get(u)
            was = seen.get(u)
            if now is None:
                why = why or "not listed by the API"
            elif was is None:
                why = why or "new"
            elif now != was:
                why = why or f"modified {now}"
        if args.all:
            why = "--all"
        if why:
            changed.append(key)
            reasons[key] = why
    changed.sort()
    if len(changed) > args.max_granthas:
        print(f"{len(changed)} granthas changed; fetching the first {args.max_granthas} this run (raise --max-granthas to do more)")
        changed = changed[: args.max_granthas]

    # 3. fetch every leaf of each changed grantha
    ok_granthas, bad = [], {}
    for key in changed:
        missing = 0
        for u in by_grantha[key]:
            dest = os.path.join(args.work, "cache", cache_name(u))
            try:
                _, b = fetch(u)
                if len(b) < 3000:
                    raise ValueError(f"only {len(b)} bytes")
                open(dest, "wb").write(b)
            except Exception as exc:                            # noqa: BLE001
                missing += 1
                bad.setdefault(key, []).append(f"{u} — {exc}")
            time.sleep(args.delay)
        if missing == 0:
            ok_granthas.append(key)
            for u in by_grantha[key]:
                if u in dates:
                    seen[u] = dates[u]
    with open(os.path.join(args.work, "changed.txt"), "w", encoding="utf-8") as fh:
        fh.write(",".join(ok_granthas))

    lines = ["## Meghamālā crawl", "",
             f"{len(rows)} leaves in {len(by_grantha)} granthas on the archive page; {len(dates)} posts listed by the API."
             + (f" Categories left out (not granthas): {', '.join(sorted(unknown_cats))}." if unknown_cats else ""),
             f"**{len(changed)} grantha(s) changed** ({len(ok_granthas)} fetched completely, {len(bad)} with missing pages).", ""]
    for key in changed:
        lines.append(f"- `{key}` — {reasons.get(key, '')}" + (f" — **{len(bad[key])} page(s) failed**" if key in bad else ""))
    for key, errs in bad.items():
        lines += ["", f"Failed for `{key}`:"] + [f"  - {e}" for e in errs[:5]]
    report = "\n".join(lines)
    print(report)
    open(os.path.join(args.work, "report.md"), "w", encoding="utf-8").write(report + "\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        open(summary, "a", encoding="utf-8").write(report + "\n")
    if args.write_state:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump({"_readme": "Written by tools/meghamala/crawl_meghamala.py: the modified_gmt last seen for each Meghamālā leaf that was fetched completely. Delete an entry to force a re-fetch of its grantha.",
                   "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "leaves": seen}, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        open(STATE, "a").write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
