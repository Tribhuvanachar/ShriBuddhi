#!/usr/bin/env python3
"""
check_sources.py — has anything we imported from changed since we last looked?

The corpus was gathered from seventeen places over the life of this project and
none of them tells us when it changes. GRETIL adds a text, dvaitavedanta.in
publishes a section, madhwafestivals posts a pada, a Wikisource page is
corrected -- and the library goes stale without a symptom. This is the cheap
half of fixing that: it does NOT import anything. It takes one small
fingerprint per source, compares it with the fingerprint from last time, and
says what moved.

Deliberately separated from importing, for two reasons. A check is safe to run
unattended every fortnight; an import is not -- it rewrites granthas, and this
project's own history has a case where an unattended one would have appended a
second copy of the Raghuvamsa. And a change detected is not the same as a
change wanted: a Wikisource edit might be a correction or might be vandalism,
and a human should see the diff before it reaches a reader.

    python3 tools/check_sources.py                  # check everything, report
    python3 tools/check_sources.py --only gretil,ambuda
    python3 tools/check_sources.py --write-state    # remember what was seen

Reads  admin/config/sources.registry.json
Writes admin/config/sources.state.json   (with --write-state)
       the report on stdout, and to $GITHUB_STEP_SUMMARY when set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(REPO, "admin", "config", "sources.registry.json")
STATE = os.path.join(REPO, "admin", "config", "sources.state.json")
UA = ("DGE-source-check/1.0 (+https://github.com/Tribhuvanachar/bhumandala; "
      "non-commercial, educational; checks for updates every 15 days)")


def fetch(url, timeout=90, tries=3, head=False):
    last = None
    headers = {"User-Agent": UA}
    # GitHub's API is 60 requests an hour unauthenticated and 403s behind a
    # shared egress; in Actions the token is already there for the asking.
    if "api.github.com" in url and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers,
                                         method="HEAD" if head else "GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.headers, (b"" if head else r.read())
        except Exception as exc:                                # noqa: BLE001
            last = exc
            time.sleep(2 * (i + 1))
    raise last


def digest(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else str(p).encode("utf-8"))
    return h.hexdigest()[:16]


def probe_html_index(p):
    """Fingerprint the LIST of things a page links to, not the page.

    An index page changes every time a footer date or a visitor counter does.
    What matters is whether the set of texts it offers has changed, so the
    fingerprint is over the extracted links, sorted -- and the count is
    reported, which is what makes a diff readable: "GRETIL: 803 files, was 800".
    """
    _, body = fetch(p["url"])
    text = body.decode("utf-8", "replace")
    items = sorted(set(re.findall(p.get("extract", r"href=\"([^\"]+)\""), text)))
    return digest(*items), {"items": len(items)}


def probe_http_headers(p):
    """ETag or Last-Modified for a file that is republished wholesale."""
    try:
        h, _ = fetch(p["url"], head=True)
    except Exception:                                            # noqa: BLE001
        h, _ = fetch(p["url"])                                   # some hosts refuse HEAD
    key = h.get("ETag") or h.get("Last-Modified") or h.get("Content-Length") or "?"
    return digest(key), {"etag": str(key)[:40], "length": h.get("Content-Length", "")}


def probe_github_commit(p):
    url = "https://api.github.com/repos/%s/commits/%s" % (p["repo"], p.get("branch", "main"))
    try:
        _, body = fetch(url)
        d = json.loads(body)
        sha = d.get("sha", "")[:12]
        when = (d.get("commit", {}).get("committer") or {}).get("date", "")
        return digest(sha), {"commit": sha, "date": when}
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            # Unauthenticated API calls are rate limited; fall back to the
            # branch page, which carries the same sha in its markup.
            _, body = fetch("https://github.com/%s/commits/%s" % (p["repo"], p.get("branch", "main")))
            m = re.search(r"/commit/([0-9a-f]{40})", body.decode("utf-8", "replace"))
            sha = (m.group(1) if m else "")[:12]
            return digest(sha), {"commit": sha, "via": "html"}
        raise


def probe_feed(p):
    """A blog: fingerprint the newest post, and count what is in the feed."""
    _, body = fetch(p["url"])
    text = body.decode("utf-8", "replace")
    links = re.findall(r"<link>([^<]+)</link>", text) or re.findall(r'href="([^"]+)"', text)
    dates = re.findall(r"<pubDate>([^<]+)</pubDate>", text)
    newest = dates[0] if dates else (links[1] if len(links) > 1 else "")
    return digest(newest), {"newest": newest[:40], "in_feed": len(dates) or len(links)}


def probe_mediawiki(p):
    """Revision ids of the pages we actually import, not the whole wiki."""
    pages = []
    cfg = os.path.join(REPO, p.get("pages_from", ""))
    if os.path.exists(cfg):
        works = json.load(open(cfg, encoding="utf-8")).get("works", [])
        for w in works:
            ws = (w.get("sources") or {}).get("wikisource") or {}
            pages.extend(ws.get("pages") or ([ws["page"]] if ws.get("page") else []))
    if not pages:
        return digest(""), {"pages": 0}
    revs = {}
    for i in range(0, len(pages), 20):
        q = urllib.parse.urlencode({"action": "query", "prop": "revisions",
                                    "titles": "|".join(pages[i:i + 20]),
                                    "rvprop": "ids", "format": "json",
                                    "formatversion": "2"})
        _, body = fetch(p["api"] + "?" + q)
        for pg in json.loads(body).get("query", {}).get("pages", []):
            rid = (pg.get("revisions") or [{}])[0].get("revid")
            if rid:
                revs[pg["title"]] = rid
        time.sleep(1)
    return digest(*[f"{k}:{v}" for k, v in sorted(revs.items())]), {"pages": len(revs)}


def probe_crawl_seeds(p):
    """Fetch a few known pages and fingerprint what the site links FROM them.

    dvaitavedanta.in has no sitemap (its /sitemap.xml is a soft 404) and its
    front page is a jstree shell whose content arrives by script, so there is
    nothing at the top to fingerprint. There is at a seed: a category page
    carries the whole branch's links in its markup -- 155 of them for the
    Dasaprakaranas. Hashing the union over one seed per section is a cheap,
    honest answer to "has the library grown".
    """
    cfg = json.load(open(os.path.join(REPO, p["seeds_from"]), encoding="utf-8"))
    base = p.get("base") or cfg.get("site", {}).get("base", "")
    seeds = []
    for section in cfg.get("sections", []):
        for g in (section.get("granthas") or [])[:1]:
            if g.get("seed"):
                seeds.append(base + g["seed"])
    found = set()
    for url in seeds[: p.get("max_seeds", 8)]:
        try:
            _, body = fetch(url)
        except Exception:                                        # noqa: BLE001
            continue
        found.update(re.findall(p.get("extract", r"category-details/\d+/\d+"),
                                body.decode("utf-8", "replace")))
        time.sleep(1)
    return digest(*sorted(found)), {"seeds": len(seeds), "linked": len(found)}


def probe_json_fields(p):
    """A site that publishes its own version stamp as JSON.

    sarvamulavani.com is a single-page reader over one SQLite file; the app
    asks `<db host>/version.json` for the current database revision before it
    loads anything. That stamp is the cleanest change signal a site can give:
    the fingerprint is the named fields of that JSON, nothing else.
    """
    _, body = fetch(p["url"])
    d = json.loads(body)
    fields = p.get("fields") or sorted(d.keys())
    picked = {k: d.get(k) for k in fields}
    return digest(*[f"{k}={v}" for k, v in sorted(picked.items())]), \
        {k: str(v)[:40] for k, v in picked.items()}


def probe_wp_json(p):
    """A WordPress site through its REST API.

    Two numbers say everything: how many published posts (or pages) there are
    (`X-WP-Total`) and when the newest one was last modified. A rewritten post
    moves `modified_gmt`; a new one moves the total. `path` picks the
    collection -- `posts` for a blog like setutila.in, `pages?slug=...` for one
    long page like the Meghamālā on srivaishnavan.com.
    """
    base = p["base"].rstrip("/") + "/wp-json/wp/v2/"
    path = p.get("path", "posts")
    sep = "&" if "?" in path else "?"
    url = base + path + sep + "per_page=1&orderby=modified&order=desc&_fields=id,slug,modified_gmt"
    h, body = fetch(url)
    items = json.loads(body)
    newest = items[0] if items else {}
    total = h.get("X-WP-Total", "")
    return digest(total, newest.get("modified_gmt", ""), newest.get("id", "")), \
        {"total": total, "newest_modified": str(newest.get("modified_gmt", ""))[:19],
         "newest_slug": str(newest.get("slug", ""))[:40]}


def probe_mediawiki_recentchanges(p):
    """A whole MediaWiki, through its recent-changes list.

    anandamakaranda.in is a wiki: any edit or new page in the main namespace
    is a change worth hearing about, so the fingerprint is the newest content
    revision id, and the detail reports the wiki's own article/page counts.
    """
    q = urllib.parse.urlencode({"action": "query", "list": "recentchanges",
                                "rcnamespace": p.get("namespace", "0"),
                                "rctype": "edit|new", "rclimit": "1",
                                "rcprop": "ids|timestamp|title",
                                "meta": "siteinfo", "siprop": "statistics",
                                "format": "json"})
    _, body = fetch(p["api"] + "?" + q)
    d = json.loads(body).get("query", {})
    rc = (d.get("recentchanges") or [{}])[0]
    stats = d.get("statistics") or {}
    return digest(rc.get("revid", ""), stats.get("pages", "")), \
        {"newest_rev": str(rc.get("revid", "")), "when": str(rc.get("timestamp", ""))[:19],
         "title": str(rc.get("title", ""))[:40], "pages": str(stats.get("pages", ""))}


PROBES = {
    "crawl_seeds": probe_crawl_seeds,
    "html_index": probe_html_index,
    "http_headers": probe_http_headers,
    "github_commit": probe_github_commit,
    "feed": probe_feed,
    "mediawiki_revisions": probe_mediawiki,
    "mediawiki_recentchanges": probe_mediawiki_recentchanges,
    "wp_json": probe_wp_json,
    "json_fields": probe_json_fields,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated source ids")
    ap.add_argument("--write-state", action="store_true")
    args = ap.parse_args()

    reg = json.load(open(REGISTRY, encoding="utf-8"))["sources"]
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"sources": {}}
    old = state.get("sources", {})
    only = {s for s in args.only.split(",") if s}

    changed, unchanged, skipped, failed = [], [], [], []
    now = {}
    for src in reg:
        sid = src["id"]
        if only and sid not in only:
            continue
        kind = src["probe"]["kind"]
        # A site we never imported from is normally not worth a request -- unless
        # it is marked watch_only, which means "we have not taken from it yet,
        # but tell us when it moves" (sarvamulavani.com).
        if kind == "manual" or not (src.get("imported", False) or src.get("watch_only", False)):
            skipped.append((sid, "no automatic probe" if kind == "manual" else "not imported"))
            continue
        try:
            fp, detail = PROBES[kind](src["probe"])
        except Exception as exc:                                 # noqa: BLE001
            failed.append((sid, "%s: %s" % (type(exc).__name__, str(exc)[:70])))
            continue
        now[sid] = {"fingerprint": fp, "detail": detail}
        was = (old.get(sid) or {}).get("fingerprint")
        if was is None:
            changed.append((sid, "first look", detail, src))
        elif was != fp:
            changed.append((sid, "CHANGED (was %s)" % was, detail, src))
        else:
            unchanged.append(sid)

    lines = ["## Source check", ""]
    if changed:
        lines += ["| source | what | detail | importer |", "|---|---|---|---|"]
        for sid, what, detail, src in changed:
            lines.append("| **%s** | %s | %s | %s |" % (
                sid, what, ", ".join(f"{k}: {v}" for k, v in detail.items()),
                src.get("importer") or "_none — a human decides_"))
        lines.append("")
    lines.append("%d changed · %d unchanged · %d skipped · %d unreachable"
                 % (len(changed), len(unchanged), len(skipped), len(failed)))
    if failed:
        lines += ["", "Unreachable:"] + ["- %s — %s" % f for f in failed]
    if skipped:
        lines += ["", "No automatic probe: " + ", ".join(s for s, _ in skipped)]
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    if args.write_state:
        merged = dict(old)
        merged.update(now)
        json.dump({"_readme": "Written by tools/check_sources.py. Fingerprints only -- "
                              "no content. Delete an entry to force a first-look report.",
                   "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "sources": merged},
                  open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # A changed source is news, not a failure: exit 0 so the workflow can keep
    # going and report it. Only an unreachable source is worth a red run, and
    # only if everything was unreachable (i.e. the runner has no network).
    return 1 if failed and not (changed or unchanged) else 0


if __name__ == "__main__":
    sys.exit(main())
