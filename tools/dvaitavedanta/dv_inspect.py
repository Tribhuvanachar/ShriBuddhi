#!/usr/bin/env python3
"""Structural probe for dvaitavedanta.in, reporting into the Actions log.

Why a log and not an artifact: the Cowork sandbox has no egress to the source
host AND cannot download run artifacts, so the only channel that reaches the
agent doing the analysis is the job log itself. Everything printed here is
therefore deliberately terse — shapes, ids, attribute names, counts — never
whole pages.

Three modes:

  --url URL ...        structural report: article blocks, AJAX hooks, the
                       left-hand commentary switcher, Load More
  --links URL ...      every /category-details child the page links to, with
                       labels — used to re-point a seed that landed on an
                       index node instead of on text
  --load-data BOOK:ID  call the AJAX endpoint directly and report what comes
                       back, which is the candidate route for the sections
                       whose commentaries are not in the first response

Run:  python tools/dvaitavedanta/dv_inspect.py --url https://dvaitavedanta.in/...
"""

import argparse
import json
import re
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from dv_parse import (  # noqa: E402
    ARTICLE_ID_RE, clean_text, devanagari_count, extract_layers, make_soup,
    parse_content_url, strip_noise,
)

BASE = "https://dvaitavedanta.in"
UA = ("BhumandalaBot/1.0 (+https://github.com/Tribhuvanachar/bhumandala; "
      "used with permission for non-commercial educational archiving)")
AJAX_RE = re.compile(r"(load-data|loadData|\$\.ajax|\$\.get|\$\.post|fetch\()", re.I)
INTERESTING_ATTR = re.compile(r"^(onclick|data-|href|id|class|book|sutra)", re.I)
MAX = 200


def short(value, limit=110):
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def get(url, timeout=120):
    response = requests.get(url, timeout=timeout, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json",
        "Accept-Language": "sa,hi;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
    })
    return response


def report_structure(url):
    print(f"\n{'=' * 72}\nURL {url}")
    response = get(url)
    html = response.text
    print(f"HTTP {response.status_code} · {len(html) / 1024:.0f} KB · "
          f"{response.headers.get('content-type', '?')}")

    soup = make_soup(html)

    # 1. Article blocks — the unit our importer keys items on.
    articles = [t for t in soup.find_all(id=ARTICLE_ID_RE)]
    print(f"\n[article blocks] {len(articles)}: "
          f"{short([t.get('id') for t in articles[:12]])}")

    # 2. What the current parser would actually harvest, unchanged. If this
    #    says 1 layer on a page the reader sees seven commentaries on, the
    #    commentaries are not in this response.
    layers = extract_layers(strip_noise(make_soup(html)))
    print(f"[layers our parser sees] {len(layers)}")
    for layer in layers[:10]:
        print(f"    {short(layer['title'], 46):48} "
              f"{devanagari_count(layer['text']):6} deva chars  "
              f"anchor={layer.get('anchor', '')}")

    # 3. AJAX hooks. The endpoint name and its parameter names are the whole
    #    prize: a payload with no navigation index in it is what makes the
    #    slow sections affordable.
    print("\n[ajax hooks in inline script]")
    seen = set()
    for script in soup.find_all("script"):
        body = script.string or script.get_text() or ""
        for line in body.splitlines():
            if AJAX_RE.search(line):
                key = line.strip()[:80]
                if key in seen:
                    continue
                seen.add(key)
                print(f"    {short(line.strip(), 150)}")
            if len(seen) >= 25:
                break
    if not seen:
        print("    (none — commentaries would have to come from the HTML)")

    # 4. The left-hand switcher: elements carrying click handlers or data-*
    #    ids. These are the links that swap the middle column.
    print("\n[clickable nodes carrying ids]")
    shown = 0
    for tag in soup.find_all(True):
        attrs = {k: v for k, v in (tag.attrs or {}).items()
                 if k.lower().startswith(("onclick", "data-")) or k.lower() in
                 ("book_id", "bookid", "sutraid")}
        if not attrs:
            continue
        label = clean_text(tag.get_text(" "))[:36]
        print(f"    <{tag.name}> {short(attrs, 130)}  | {label}")
        shown += 1
        if shown >= 30:
            print("    … truncated")
            break
    if not shown:
        print("    (none)")

    # 5. Load More / pagination.
    print("\n[load-more / pagination]")
    hits = [t for t in soup.find_all(True)
            if "load more" in clean_text(t.get_text(" ")).lower()
            and t.name in ("a", "button", "input", "div", "span")]
    for tag in hits[:6]:
        print(f"    <{tag.name}> {short(tag.attrs, 150)}")
    if not hits:
        print("    (none)")

    # 6. How much of the page is navigation. This is the 20-40 s question.
    nav_chars = sum(len(a.get_text(" ")) for a in soup.find_all("a"))
    body_chars = len(soup.get_text(" "))
    print(f"\n[weight] {len(soup.find_all('a')):,} links · "
          f"{nav_chars:,} chars inside <a> of {body_chars:,} total text "
          f"({nav_chars / max(body_chars, 1):.0%} navigation)")


def report_links(url):
    print(f"\n{'=' * 72}\nLINKS UNDER {url}")
    response = get(url)
    soup = make_soup(response.text)
    rows, seen = [], set()
    for anchor in soup.find_all("a", href=True):
        parsed = parse_content_url(anchor["href"])
        if not parsed or parsed[0] in seen:
            continue
        seen.add(parsed[0])
        rows.append((parsed[0], parsed[1], clean_text(anchor.get_text(" "))[:40],
                     anchor["href"]))
    # Raw anchors vs what the importer's own discovery sees. rig_bhashya
    # discovered 1 leaf on a page whose sidebar lists 20 suktas, so the two
    # numbers disagreeing is the bug, and printing both localises it.
    from dv_parse import parse_page                      # noqa: PLC0415
    record = parse_page(response.text, url)
    sidebar = record.get("sidebar") or []
    print(f"HTTP {response.status_code} · {len(rows)} raw content links · "
          f"parse_page sidebar: {len(sidebar)} "
          f"({sum(1 for s in sidebar if s['in_breadcrumb'])} in breadcrumb, "
          f"so {sum(1 for s in sidebar if not s['in_breadcrumb'])} usable) · "
          f"layers here: {len(record.get('layers') or [])}")
    # The breadcrumb names the work — which is how the fifteen later_acharyas
    # seeds that carry no title in the config get one.
    print(f"    breadcrumb: {' > '.join(record.get('breadcrumb') or []) or '(none)'}")
    for content_id, ancestor, label, href in rows[:60]:
        print(f"    {content_id:>7} anc={str(ancestor):>6}  {label:42} {short(href, 70)}")
    if len(rows) > 60:
        print(f"    … {len(rows) - 60} more")


def report_load_data(spec):
    book_id, _, sutra_id = spec.partition(":")
    url = f"{BASE}/load-data?book_id={book_id}&id={sutra_id}&search="
    print(f"\n{'=' * 72}\nLOAD-DATA {url}")
    response = get(url)
    print(f"HTTP {response.status_code} · {len(response.text) / 1024:.1f} KB · "
          f"{response.headers.get('content-type', '?')}")
    try:
        payload = response.json()
    except ValueError:
        print("    not JSON. First 300 chars:")
        print("    " + short(response.text, 300))
        return
    print(f"    keys: {list(payload)}")
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > 120:
            print(f"    {key}: {len(value)} chars")
        else:
            print(f"    {key}: {short(value, 120)}")
    fragment = payload.get("html") or ""
    if fragment:
        soup = strip_noise(make_soup(fragment))
        layers = extract_layers(soup)
        print(f"    parsed layers in fragment: {len(layers)}")
        for layer in layers[:8]:
            print(f"      {short(layer['title'], 40):42} "
                  f"{devanagari_count(layer['text']):6} deva chars")
        links = len(BeautifulSoup(fragment, "lxml").find_all("a"))
        print(f"    links inside fragment: {links}  "
              f"({'no nav index — cheap' if links < 50 else 'still carries nav'})")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", nargs="*", default=[])
    parser.add_argument("--links", nargs="*", default=[])
    parser.add_argument("--load-data", nargs="*", default=[],
                        help="book_id:sutra_id pairs")
    args = parser.parse_args(argv)

    for url in args.url:
        try:
            report_structure(url)
        except Exception as error:                      # never abort the batch
            print(f"    !! {type(error).__name__}: {error}")
    for url in args.links:
        try:
            report_links(url)
        except Exception as error:
            print(f"    !! {type(error).__name__}: {error}")
    for spec in args.load_data:
        try:
            report_load_data(spec)
        except Exception as error:
            print(f"    !! {type(error).__name__}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
