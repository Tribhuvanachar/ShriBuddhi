#!/usr/bin/env python3
"""
wayback_fetch.py -- list and fetch a site's archived pages from the Wayback Machine, politely.

Built for the IITK Valmiki Ramayana site (valmiki.iitk.ac.in), which no longer answers; its six Sanskrit
commentaries survive only in the archive. Runs in a GitHub Actions job (the session sandbox cannot reach
web.archive.org). Raw bytes only: nothing is parsed, cleaned or rearranged here -- they go to ParaBuddhi
`source/_raw/<id>/` unchanged (tools/watch/dump_to_parabuddhi.py), and are built into data/ afterwards.

    python3 tools/wayback_fetch.py probe --host valmiki.iitk.ac.in --out .wb --report report.md
    python3 tools/wayback_fetch.py fetch --host valmiki.iitk.ac.in --out .wb --limit 200 [--prefix commentary]

probe  lists captures (CDX, status 200, one per URL), writes <out>/cdx.json and a report of path patterns.
fetch  downloads the newest 200 capture of each listed URL with the `id_` flag (original bytes, no Wayback
       banner or rewritten links) at ~1 request/second. Files already on disk are skipped (on a fresh runner that means nothing is,
       so split big sites into runs with --prefix).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CDX = "https://web.archive.org/cdx/search/cdx"
UA = "ShriBuddhi-wayback-fetch/1.0 (research archive; contact via Tribhuvanachar/ShriBuddhi)"


def get(url: str, tries: int = 5) -> bytes:
    delay = 5
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            err = "HTTP %s" % e.code
        except Exception as e:  # reset, timeout, DNS
            err = repr(e)
        print("  retry %d/%d after %s: %s" % (n + 1, tries, err, url), file=sys.stderr)
        time.sleep(delay)
        delay = min(delay * 2, 120)
    raise RuntimeError("gave up: " + url)


def list_captures(host: str) -> list[dict]:
    q = urllib.parse.urlencode({
        "url": host + "/*", "output": "json", "fl": "timestamp,original,mimetype,statuscode,digest,length",
        "filter": "statuscode:200", "collapse": "urlkey", "limit": 200000})
    rows = json.loads(get(CDX + "?" + q) or b"[]")
    if not rows:
        return []
    head, body = rows[0], rows[1:]
    return [dict(zip(head, r)) for r in body]


def pattern(url: str) -> str:
    p = urllib.parse.urlparse(url)
    segs = [re.sub(r"\d+", "N", s) for s in p.path.strip("/").split("/")[:3]]
    return "/" + "/".join(segs) + ("?" + re.sub(r"=[^&]*", "=*", p.query) if p.query else "")


def local_path(out: str, row: dict) -> str:
    u = urllib.parse.urlparse(row["original"])
    path = u.path.lstrip("/") or "index.html"
    if path.endswith("/"):
        path += "index.html"
    if u.query:
        path += "__" + re.sub(r"[^A-Za-z0-9._=-]", "_", u.query)[:120]
    return os.path.join(out, "raw", u.netloc.split(":")[0], path)


def cmd_probe(a) -> int:
    rows = list_captures(a.host)
    os.makedirs(a.out, exist_ok=True)
    json.dump(rows, open(os.path.join(a.out, "cdx.json"), "w"), ensure_ascii=False)
    pats = collections.Counter(pattern(r["original"]) for r in rows)
    mimes = collections.Counter(r["mimetype"] for r in rows)
    size = sum(int(r.get("length") or 0) for r in rows)
    lines = ["# Wayback probe: %s" % a.host, "", "%d archived URLs (status 200, one per URL), ~%.1f MB compressed" % (len(rows), size / 1e6), "",
             "## mime types"] + ["- %s: %d" % kv for kv in mimes.most_common()] + ["", "## path patterns (digits -> N)"] \
        + ["- `%s`: %d" % kv for kv in pats.most_common(60)] + ["", "## sample URLs"] \
        + ["- %s %s" % (r["timestamp"], r["original"]) for r in rows[:40]]
    text = "\n".join(lines)
    print(text)
    if a.report:
        open(a.report, "w", encoding="utf-8").write(text + "\n")
    return 0 if rows else 3


def cmd_fetch(a) -> int:
    rows = json.load(open(os.path.join(a.out, "cdx.json"))) if os.path.exists(os.path.join(a.out, "cdx.json")) else list_captures(a.host)
    if a.prefix:
        rows = [r for r in rows if a.prefix in r["original"]]
    done = failed = skipped = 0
    for r in rows:
        if done >= a.limit:
            break
        dest = local_path(a.out, r)
        if os.path.exists(dest):
            skipped += 1
            continue
        url = "https://web.archive.org/web/%sid_/%s" % (r["timestamp"], r["original"])
        try:
            data = get(url)
        except Exception as e:
            failed += 1
            print("FAILED %s: %s" % (r["original"], e), file=sys.stderr)
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(data)
        done += 1
        time.sleep(a.delay)
    print("fetched %d, already had %d, failed %d, of %d listed" % (done, skipped, failed, len(rows)))
    return 0 if done or skipped else 3


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("probe", "fetch"):
        s = sub.add_parser(name)
        s.add_argument("--host", default="valmiki.iitk.ac.in")
        s.add_argument("--out", default=".wb")
        if name == "probe":
            s.add_argument("--report", default="")
        else:
            s.add_argument("--limit", type=int, default=200)
            s.add_argument("--prefix", default="", help="only URLs containing this text")
            s.add_argument("--delay", type=float, default=1.0)
    a = ap.parse_args(argv)
    return cmd_probe(a) if a.cmd == "probe" else cmd_fetch(a)


if __name__ == "__main__":
    sys.exit(main())
