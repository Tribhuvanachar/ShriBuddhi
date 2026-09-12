#!/usr/bin/env python3
"""Ask dvaitavedanta.in what pages each grantha has, and diff against last time.

check_sources.py already answers "did the site change AT ALL" with one seed
page per section. This tool answers the follow-up that actually drives work:
WHICH granthas gained (or lost) pages, precisely enough to dispatch
extract-dvaitavedanta.yml for just those granthas instead of re-crawling the
whole corpus (nyaya_sudha alone is ~18 hours of fetching).

It fetches exactly one page per grantha — the same seed page the importer's
discovery uses — and harvests the sidebar's content-id census, ~56 requests
for the whole corpus. It IMPORTS NOTHING and never touches the network beyond
those seeds. The census is diffed against admin/config/dv_sync.state.json;
--write-state records the new census so the next run reports the NEXT change.

The first run for a grantha records a baseline and says so, rather than
reporting every page the site has ever had as "new".

A seed that fails, answers with a bot-challenge interstitial, or comes back
with a suspiciously shrunken sidebar (less than half of last time) is
reported as UNREADABLE and its state is left untouched — a rate-limited fetch
must not masquerade as "the site removed 800 pages".

Report format: markdown on stdout. Changed granthas render as table rows
beginning `| **` — the same marker check-sources.yml greps for — so the
workflow can decide "did anything move" with the same one-liner.

    python tools/dvaitavedanta/sync_check.py                # report only
    python tools/dvaitavedanta/sync_check.py --write-state  # ...and remember
    python tools/dvaitavedanta/sync_check.py --sections later_acharyas \
        --json-out /tmp/dv_sync_changes.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

DEFAULT_STATE = os.path.join(REPO, "admin", "config", "dv_sync.state.json")
DEFAULT_CONFIG = os.path.join(HERE, "dv_sources.json")

# A challenge interstitial is a 200 with no library in it. Both markers have
# been seen from this site; the sidebar-count guard below catches variants.
CHALLENGE_MARKERS = ("One moment", "Just a moment", "challenge-platform")

# A sidebar that shrank below this fraction of the remembered census is far
# more likely a half-rendered or rate-limited page than a mass deletion.
SHRINK_GUARD = 0.5


def load_config(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def all_granthas(config, sections_filter=()):
    """Every grantha with a seed, disabled ones included.

    The importer's select_granthas honours `enabled: false` because a CRAWL of
    nyaya_sudha is 18 hours; a sync check is one request, so the census should
    cover everything the config knows about.
    """
    out = []
    for section in config["sections"]:
        if sections_filter and section["slug"] not in sections_filter:
            continue
        for grantha in section["granthas"]:
            if not grantha.get("seed"):
                continue
            out.append({
                "key": f"{section['slug']}/{grantha.get('slug') or grantha.get('content_id')}",
                "section": section["slug"],
                "slug": grantha.get("slug"),
                "title": grantha.get("title") or grantha.get("slug") or "",
                "seed_url": config["site"]["base"] + grantha["seed"],
            })
    return out


def discover_census(granthas, delay=2.0, timeout=60, user_agent="",
                    log=lambda s: None):
    """Fetch each grantha's seed once; return {key: {...census or failure}}.

    Imports the crawler's own Fetcher/discover_leaves so the census is taken
    exactly the way the importer would take it — no second, differently-biased
    discovery path. That includes the User-Agent: the site's protection
    challenges strangers but has let the importer's own identity through for
    the whole 6,012-page corpus, so introducing ourselves any other way just
    earns a challenge page (run 33075520117 proved it: 56/56 seeds blocked
    under a novel UA minutes after the importer's UA fetched fine).
    """
    from import_dvaitavedanta import Fetcher, discover_leaves  # noqa: PLC0415

    # No cache directory, deliberately: a cached seed page answers "what did
    # the site look like last time", which is the one question a change
    # detector must never answer from memory.
    fetcher = Fetcher(cache_dir=None, user_agent=user_agent,
                      delay=delay, timeout=timeout, retries=3)
    census = {}
    for grantha in granthas:
        html = fetcher.get(grantha["seed_url"])
        if html is None:
            census[grantha["key"]] = {"ok": False, "why": "seed fetch failed",
                                      "title": grantha["title"]}
            log(f"  ! {grantha['key']}: seed fetch failed")
            continue
        if any(marker in html for marker in CHALLENGE_MARKERS):
            census[grantha["key"]] = {"ok": False, "why": "bot-challenge page",
                                      "title": grantha["title"]}
            log(f"  ! {grantha['key']}: bot-challenge page")
            continue
        ids, _record, _ancestor, urls = discover_leaves(fetcher, grantha, log)
        if not ids:
            census[grantha["key"]] = {"ok": False, "why": "empty sidebar",
                                      "title": grantha["title"]}
            log(f"  ! {grantha['key']}: empty sidebar")
            continue
        census[grantha["key"]] = {
            "ok": True,
            "title": grantha["title"],
            "section": grantha["section"],
            "slug": grantha["slug"],
            "ids": sorted(str(i) for i in ids),
            "urls": {str(k): v for k, v in urls.items()},
        }
        log(f"  {grantha['key']}: {len(ids)} sidebar id(s)")
    return census


def diff_census(old_state, census):
    """Pure diff of a fresh census against remembered state.

    Returns (rows, changed, unreadable) where rows is per-grantha detail:
      {"key", "title", "status": baseline|same|changed|unreadable|suspect,
       "added": [...], "removed": [...], "count", "prev_count"}
    """
    remembered = old_state.get("granthas", {})
    rows = []
    for key in sorted(census):
        entry = census[key]
        prev = remembered.get(key)
        if not entry.get("ok"):
            rows.append({"key": key, "title": entry.get("title", ""),
                         "status": "unreadable", "why": entry.get("why", ""),
                         "added": [], "removed": [],
                         "count": None,
                         "prev_count": len(prev["ids"]) if prev else None})
            continue
        ids = set(entry["ids"])
        if prev is None:
            rows.append({"key": key, "title": entry["title"],
                         "status": "baseline", "added": [], "removed": [],
                         "count": len(ids), "prev_count": None})
            continue
        prev_ids = set(prev.get("ids", []))
        if prev_ids and len(ids) < len(prev_ids) * SHRINK_GUARD:
            rows.append({"key": key, "title": entry["title"],
                         "status": "suspect",
                         "why": f"sidebar shrank {len(prev_ids)} -> {len(ids)}; "
                                "treating as an unreadable page, not a deletion",
                         "added": [], "removed": [],
                         "count": len(ids), "prev_count": len(prev_ids)})
            continue
        added = sorted(ids - prev_ids)
        removed = sorted(prev_ids - ids)
        rows.append({"key": key, "title": entry["title"],
                     "status": "changed" if (added or removed) else "same",
                     "added": added, "removed": removed,
                     "count": len(ids), "prev_count": len(prev_ids)})
    changed = [r for r in rows if r["status"] == "changed"]
    unreadable = [r for r in rows if r["status"] in ("unreadable", "suspect")]
    return rows, changed, unreadable


def next_state(old_state, census, now_iso):
    """The state to remember: fresh census where readable, old entry where not."""
    granthas = dict(old_state.get("granthas", {}))
    for key, entry in census.items():
        if not entry.get("ok"):
            continue        # never overwrite memory with a failed read
        granthas[key] = {
            "title": entry["title"],
            "discovered": len(entry["ids"]),
            "sha": hashlib.sha1("\n".join(entry["ids"]).encode()).hexdigest(),
            "ids": entry["ids"],
            "checked": now_iso,
        }
    return {
        "generated_note": "Per-grantha sidebar census of dvaitavedanta.in. "
                          "Written by tools/dvaitavedanta/sync_check.py; the "
                          "diff against it names which granthas to re-extract.",
        "checked": now_iso,
        "granthas": granthas,
    }


def render_report(rows, changed, unreadable, census):
    """Markdown report. Changed granthas use the `| **` row marker."""
    out = []
    baselines = [r for r in rows if r["status"] == "baseline"]
    same = [r for r in rows if r["status"] == "same"]
    out.append("## dvaitavedanta.in sync check")
    out.append("")
    out.append(f"{len(rows)} granthas asked · {len(same)} unchanged · "
               f"{len(changed)} changed · {len(baselines)} baseline recorded · "
               f"{len(unreadable)} unreadable")
    out.append("")
    if changed:
        out.append("| Grantha | Was | Now | Added | Removed |")
        out.append("|---|--:|--:|--:|--:|")
        for r in changed:
            out.append(f"| **{r['key']}**<br>{r['title']} | {r['prev_count']} "
                       f"| {r['count']} | {len(r['added'])} | {len(r['removed'])} |")
        out.append("")
        for r in changed:
            entry = census.get(r["key"], {})
            urls = entry.get("urls", {})
            for cid in r["added"][:5]:
                out.append(f"- new in `{r['key']}`: id {cid} — "
                           f"{urls.get(cid, '(url in sidebar)')}")
            if len(r["added"]) > 5:
                out.append(f"- …and {len(r['added']) - 5} more new in `{r['key']}`")
            for cid in r["removed"][:5]:
                out.append(f"- gone from `{r['key']}`: id {cid}")
        out.append("")
        sections = {}
        for r in changed:
            sec, slug = r["key"].split("/", 1)
            sections.setdefault(sec, []).append(slug)
        out.append("To pull these in, dispatch `extract-dvaitavedanta.yml` per section:")
        for sec, slugs in sorted(sections.items()):
            out.append(f"- scope=`{sec}` granthas=`{','.join(slugs)}` "
                       "limit_per_grantha=0 delay=2.0 dry_run=false open_pr=true"
                       + (" job_timeout=350 (chain runs — this grantha alone "
                          "takes ~18h of fetching)" if "nyaya_sudha" in slugs
                          else " job_timeout=240"))
        out.append("")
    if baselines:
        out.append(f"Baseline recorded for {len(baselines)} grantha(s) "
                   "(first sighting; nothing to diff yet): "
                   + ", ".join(f"`{r['key']}`" for r in baselines[:8])
                   + ("…" if len(baselines) > 8 else ""))
        out.append("")
    if unreadable:
        out.append("Unreadable this run (state untouched, will retry next time):")
        for r in unreadable:
            out.append(f"- `{r['key']}`: {r.get('why', '')}")
        out.append("")
    if not changed and not unreadable and not baselines:
        out.append("Nothing moved. The census matches last time's exactly.")
    return "\n".join(out)


def main(argv=None, discover_fn=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--sections", default="",
                    help="comma-separated section slugs; blank = all")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--write-state", action="store_true")
    ap.add_argument("--json-out", default="",
                    help="write {changed: {section: [slugs]}, unreadable: [...]} here")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    config = load_config(args.config)
    sections_filter = tuple(s.strip() for s in args.sections.split(",") if s.strip())
    granthas = all_granthas(config, sections_filter)
    log = (lambda s: print(s, file=sys.stderr)) if args.verbose else (lambda s: None)

    user_agent = config.get("site", {}).get("user_agent") or (
        "DGE-DvaitaVedanta-Importer/1.0 (non-commercial; dharma-prachara; "
        "+https://tribhuvanachar.github.io/bhumandala)")
    discover = discover_fn or (lambda gs: discover_census(
        gs, delay=args.delay, timeout=args.timeout, user_agent=user_agent,
        log=log))
    census = discover(granthas)

    old_state = {}
    if os.path.exists(args.state):
        with open(args.state, encoding="utf-8") as handle:
            old_state = json.load(handle)

    rows, changed, unreadable = diff_census(old_state, census)
    print(render_report(rows, changed, unreadable, census))

    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    if args.write_state:
        state = next_state(old_state, census, now_iso)
        os.makedirs(os.path.dirname(args.state), exist_ok=True)
        with open(args.state, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=1)
            handle.write("\n")

    if args.json_out:
        sections = {}
        for r in changed:
            sec, slug = r["key"].split("/", 1)
            sections.setdefault(sec, []).append(slug)
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump({"changed": sections,
                       "unreadable": [r["key"] for r in unreadable],
                       "baseline": [r["key"] for r in rows
                                    if r["status"] == "baseline"]}, handle, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
