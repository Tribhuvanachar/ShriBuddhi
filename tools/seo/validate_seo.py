#!/usr/bin/env python3
"""Validate a generated DGE site (tools/seo/build_seo_site.py output) the way Search Console would judge it.

    python3 tools/seo/validate_seo.py --site _site [--report seo-validation.json] [--max-bytes 400000]

Per page: one <title> (unique), a <meta name=description> (unique, 40–320 chars), one <link rel=canonical> that
points at the page's own URL, <html lang>, exactly one <h1>, real text (Devanagari present on text pages), no
noindex, crawlable internal links that resolve to a generated file, a breadcrumb <nav>, JSON-LD that parses and
carries a BreadcrumbList, and a sane size. Site-wide: every page is in a sitemap, every sitemap URL exists, no
orphan page (reachable from the root index by following links), no two pages with the same canonical.
Exit 1 when a blocking check fails; the JSON report lists everything.
"""
import argparse, json, re, sys
from collections import Counter, deque
from html.parser import HTMLParser
from pathlib import Path


class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.title = []; self.in_title = False; self.desc = None; self.canon = []; self.robots = None; self.generator = None
        self.lang = None; self.h1 = 0; self.links = []; self.ld = []; self.in_ld = False; self.crumbs = False; self.text = []; self.in_script = False; self.in_style = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html": self.lang = a.get("lang")
        if tag == "title": self.in_title = True
        if tag == "meta":
            if a.get("name") == "description": self.desc = a.get("content", "")
            if a.get("name") == "robots": self.robots = a.get("content", "")
            if a.get("name") == "generator": self.generator = a.get("content", "")
        if tag == "link" and a.get("rel") == "canonical": self.canon.append(a.get("href", ""))
        if tag == "h1": self.h1 += 1
        if tag == "a" and a.get("href"): self.links.append(a["href"])
        if tag == "nav" and (a.get("class") or "").startswith("crumbs"): self.crumbs = True
        if tag == "script":
            self.in_script = True; self.in_ld = a.get("type") == "application/ld+json"
        if tag == "style": self.in_style = True
    def handle_endtag(self, tag):
        if tag == "title": self.in_title = False
        if tag == "script": self.in_script = False; self.in_ld = False
        if tag == "style": self.in_style = False
    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        elif self.in_ld: self.ld.append(data)
        elif not self.in_script and not self.in_style: self.text.append(data)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--site", default="_site"); ap.add_argument("--report", default=None)
    ap.add_argument("--max-bytes", type=int, default=400000); ap.add_argument("--origin", default=None)
    a = ap.parse_args(argv)
    site = Path(a.site)
    cfg = json.load(open(Path(__file__).resolve().parents[2] / "admin/config/seo.json", encoding="utf-8"))
    origin = a.origin or (cfg["siteOrigin"].rstrip("/") + cfg.get("sitePrefix", "").rstrip("/"))
    public_root = cfg.get("publicRoot", "/dge")
    pages = sorted(p for p in site.rglob("index.html") if p.relative_to(site).parts[0] == public_root.strip("/"))
    urls, app_pages = {}, {}
    problems = {"blocking": [], "warnings": []}
    titles, descs, canons = Counter(), Counter(), Counter()
    graph = {}
    sizes = []
    for p in pages:
        url = "/" + str(p.relative_to(site).parent).replace("\\", "/") + "/"
        if url == "//": url = "/"
        raw = p.read_bytes(); sizes.append((len(raw), url))
        pg = Page(); pg.feed(raw.decode("utf-8", "replace"))
        title = "".join(pg.title).strip()
        if pg.generator != "dge-seo":
            # the reader's own hand-written pages (the app shell, tools, views) share the tree but are not
            # generated: they are valid link targets, nothing more is checked about them here
            app_pages[url] = title
            continue
        urls[url] = title
        b = problems["blocking"]; w = problems["warnings"]
        if not title: b.append(f"{url}: no <title>")
        titles[title] += 1
        if not pg.desc: b.append(f"{url}: no meta description")
        else:
            descs[pg.desc] += 1
            if len(pg.desc) < 40: w.append(f"{url}: short description ({len(pg.desc)} chars)")
            if len(pg.desc) > 320: w.append(f"{url}: long description ({len(pg.desc)} chars)")
        if len(pg.canon) != 1: b.append(f"{url}: {len(pg.canon)} canonical links")
        else:
            canons[pg.canon[0]] += 1
            if pg.canon[0] != origin + url: b.append(f"{url}: canonical points elsewhere ({pg.canon[0]})")
        if pg.robots and "noindex" in pg.robots: b.append(f"{url}: noindex")
        if not pg.lang: b.append(f"{url}: <html> has no lang")
        if pg.h1 != 1: b.append(f"{url}: {pg.h1} <h1>")
        if not pg.crumbs: b.append(f"{url}: no breadcrumb nav")
        txt = " ".join(pg.text)
        if len(re.sub(r"\s+", "", txt)) < 200: w.append(f"{url}: thin page ({len(txt)} chars of text)")
        if url.count("/") > 3 and not re.search(r"[ऀ-ॿ]", txt): w.append(f"{url}: no Devanagari text")
        ok_ld = False
        for chunk in pg.ld:
            try:
                d = json.loads(chunk)
                items = d if isinstance(d, list) else [d]
                if any(x.get("@type") == "BreadcrumbList" for x in items): ok_ld = True
            except Exception as e:  # noqa: BLE001
                b.append(f"{url}: JSON-LD does not parse ({e})")
        if not ok_ld: b.append(f"{url}: no BreadcrumbList JSON-LD")
        if len(raw) > a.max_bytes: w.append(f"{url}: {len(raw) // 1024} KB page")
        internal = [l.split("#")[0] for l in pg.links if l.startswith(public_root + "/")]
        graph[url] = set(internal)
    # link targets + sitemap
    b = problems["blocking"]; w = problems["warnings"]
    for url, links in graph.items():
        for l in links:
            if l.startswith(public_root + "/") and l.endswith("/") and l not in urls and l not in app_pages: b.append(f"{url}: broken link {l}")
    for t, n in titles.items():
        if n > 1: b.append(f"duplicate title ×{n}: {t}")
    for d, n in descs.items():
        if n > 1: w.append(f"duplicate description ×{n}: {d[:80]}")
    for c, n in canons.items():
        if n > 1: b.append(f"duplicate canonical ×{n}: {c}")
    sm = set()
    for f in site.glob("sitemap*.xml"):
        if f.name == "sitemap-static.xml":       # the reader's own static pages live in the repo, not in this tree
            continue
        sm.update(re.findall(r"<loc>([^<]+)</loc>", f.read_text(encoding="utf-8")))
    sm_pages = {u[len(origin):] for u in sm if u.startswith(origin + public_root + "/")}
    missing = [u for u in urls if u not in sm_pages]
    stale = [u for u in sm_pages if u not in urls]
    if missing: b.append(f"{len(missing)} pages missing from the sitemap, e.g. {missing[:3]}")
    if stale: b.append(f"{len(stale)} sitemap URLs with no page, e.g. {stale[:3]}")
    # orphans: BFS from the root index
    root = cfg.get("catalogueUrl") or (public_root + "/texts/")
    if root not in graph: b.append(f"catalogue root {root} was not generated")
    seen = set(); dq = deque([root])
    while dq:
        u = dq.popleft()
        if u in seen: continue
        seen.add(u)
        for l in graph.get(u, ()):
            if l in graph and l not in seen: dq.append(l)
    orphans = [u for u in urls if u not in seen]
    if orphans: b.append(f"{len(orphans)} orphan pages (not reachable from {root}), e.g. {orphans[:3]}")
    big = sorted(sizes, reverse=True)[:5]
    rep = {"pages": len(urls), "appPages": len(app_pages), "sitemapUrls": len(sm), "blocking": problems["blocking"][:200], "blockingCount": len(problems["blocking"]),
           "warnings": problems["warnings"][:200], "warningCount": len(problems["warnings"]), "largest": [(s, u) for s, u in big],
           "orphans": len(orphans), "duplicateTitles": sum(1 for n in titles.values() if n > 1)}
    out = json.dumps(rep, ensure_ascii=False, indent=1)
    if a.report: Path(a.report).write_text(out, encoding="utf-8")
    print(f"{rep['pages']} pages · {rep['sitemapUrls']} sitemap URLs · {rep['blockingCount']} blocking · {rep['warningCount']} warnings · {rep['orphans']} orphans · {rep['duplicateTitles']} duplicate titles")
    for x in rep["blocking"][:15]: print("  BLOCKING", x)
    for x in rep["warnings"][:8]: print("  warn", x)
    return 1 if rep["blockingCount"] else 0


if __name__ == "__main__":
    sys.exit(main())
