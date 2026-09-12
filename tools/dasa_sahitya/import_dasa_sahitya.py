#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DGE — Dasa Sahitya (Dasara Padagalu) importer
=============================================

Crawls the public Haridasa-sahitya archives listed in ``dasa_sources.json`` and
builds a structured corpus of **Dasara Padas, Suladis and Ugabhogas** (plus the
related devotional song forms — devaranama, aarati, mangala, kolu, shobhane,
laali, dashavatara, sampradaya, kavya) for the DGE library.

For every composition it captures:
    - title (Kannada + Latin/transliterated where the source gives it)
    - composer (dasa / yati)
    - deity / subject
    - form  (pada | suladi | ugabhoga | ...)
    - the Kannada verse text, split into stanzas & lines
    - a Latin transliteration line if the source provides one
    - auto-generated Devanagari + IAST transliterations from the Kannada
    - source url + attribution + fetch date

Outputs (under --out, default ``data/DvaitaVedanta/Itara/DasaSahitya/``):
    index.json                         -- manifest of every composition
    composers/<slug>/data.json         -- full records grouped by composer
    _dump/dasa_sahitya_full.txt        -- human-readable plain-text dump
    _dump/DvaitaVedanta/Itara/DasaSahitya.jsonl           -- one JSON record per line

Design notes
------------
* Runs on GitHub Actions / Colab (open network egress). It does NOT run inside
  the Cowork sandbox, which has no scraping egress — that is by design and
  matches the established DGE import workflow.
* Strictly non-commercial: dharma-prachara / education / research. Every record
  keeps a visible source attribution.
* Idempotent + resumable: raw HTML is cached under --cache so re-runs are cheap
  and polite to the source servers.
"""

import argparse
import json
import os
import re
import sys
import time
import hashlib
import datetime as _dt
from collections import deque
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    sys.exit("Please `pip install requests beautifulsoup4 indic-transliteration`")
from bs4 import BeautifulSoup

try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate as _tr
    _HAVE_TR = True
except Exception:
    _HAVE_TR = False

    class _SanscriptShim:
        KANNADA = "kannada"
        IAST = "iast"
        DEVANAGARI = "devanagari"

    sanscript = _SanscriptShim()   # keeps references valid; kn_to() no-ops


# --------------------------------------------------------------------------- #
# Unicode helpers
# --------------------------------------------------------------------------- #
KANNADA_RE = re.compile(r"[ಀ-೿]")          # Kannada block
DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
LATIN_RE = re.compile(r"[A-Za-z]")


def script_of(line: str) -> str:
    """Rough per-line script classification."""
    if KANNADA_RE.search(line):
        return "kn"
    if DEVANAGARI_RE.search(line):
        return "sa"
    if LATIN_RE.search(line):
        return "iast_src"      # source-supplied roman transliteration
    return "other"


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text or "", flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "_", text)
    return text or "untitled"


def kn_to(script_target: str, kn_text: str) -> str:
    """Transliterate Kannada -> target script; safe no-op if lib missing."""
    if not _HAVE_TR or not kn_text.strip():
        return ""
    try:
        return _tr(kn_text, sanscript.KANNADA, script_target)
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# HTTP with on-disk cache + polite throttling
# --------------------------------------------------------------------------- #
class Fetcher:
    def __init__(self, cache_dir, delay=1.0, timeout=30):
        self.cache_dir = cache_dir
        self.delay = delay
        self.timeout = timeout
        os.makedirs(cache_dir, exist_ok=True)
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "DGE-DasaSahitya-Importer/1.0 (non-commercial; dharma-prachara; +https://tribhuvanachar.github.io/bhumandala)"
        })
        # URLs that never yielded usable HTML -- surfaced in pending_review.json
        # so a human can open them directly rather than the failure silently
        # vanishing into stderr.
        self.failed = []

    def get(self, url):
        key = hashlib.sha1(url.encode("utf-8")).hexdigest() + ".html"
        path = os.path.join(self.cache_dir, key)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        last_reason = "unknown"
        for attempt in range(4):
            try:
                r = self.s.get(url, timeout=self.timeout)
                if r.status_code == 200 and r.text:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(r.text)
                    time.sleep(self.delay)
                    return r.text
                if r.status_code in (403, 404, 410):
                    print(f"  ! {r.status_code} {url}", file=sys.stderr)
                    self.failed.append({"url": url, "reason": f"HTTP {r.status_code}"})
                    return None
                last_reason = f"HTTP {r.status_code}"
            except requests.RequestException as e:
                print(f"  ! {e} ({url})", file=sys.stderr)
                last_reason = str(e)
            time.sleep(self.delay * (attempt + 2))
        self.failed.append({"url": url, "reason": last_reason})
        return None


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _content_node(soup):
    for sel in ("div.entry-content", "div.post-content", "article", "div.entry",
                "div#content", "main"):
        node = soup.select_one(sel)
        if node:
            return node
    return soup.body or soup


def extract_links(html, base_url, post_pattern):
    """Return absolute composition-post URLs found on an index page."""
    soup = BeautifulSoup(html, "html.parser")
    node = _content_node(soup)
    pat = re.compile(post_pattern)
    out, seen = [], set()
    base_host = urlparse(base_url).netloc.replace("www.", "")
    base_path = urlparse(base_url).path.rstrip("/")
    for a in node.find_all("a", href=True):
        href = urljoin(base_url, a["href"].split("#")[0])
        parsed = urlparse(href)
        # Jetpack's "sharedaddy" share buttons (WordPress) link back to the
        # CURRENT post with a `?share=facebook`/`jetpack-whatsapp`/`pinterest`/
        # `twitter` tracking query string appended -- same path, so they still
        # match post_url_pattern, and get counted as if they were distinct
        # composition links. A listing page with one real post and its own
        # share widget would otherwise discover 4 "compositions" that are all
        # just the listing page itself, none of them containing lyric text.
        if parsed.query:
            continue
        host = parsed.netloc.replace("www.", "")
        # allow the same site + declared wordpress mirror host
        if base_host.split(".")[0] not in host:
            continue
        if parsed.path.rstrip("/") == base_path:
            continue
        href = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if not pat.search(parsed.path):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append({"url": href, "anchor": a.get_text(" ", strip=True)})
    return out


def looks_like_index(links):
    """A page with many internal post links is itself an index, not a song."""
    return len(links) >= 12


def parse_composition(html, url):
    """Extract title + stanzas (kn lines) + source roman transliteration."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    for sel in ("h1.entry-title", "h1.post-title", "h1", "title"):
        t = soup.select_one(sel)
        if t and t.get_text(strip=True):
            title = t.get_text(" ", strip=True)
            break
    title = re.sub(r"\s*[|–-]\s*Madhwa.*$", "", title).strip()
    title = re.sub(r"\s*[|–-]\s*.*Kamadhenu.*$", "", title).strip()

    node = _content_node(soup)
    # Drop navigation / share / related cruft
    for bad in node.select("div.sharedaddy, div.jp-relatedposts, script, style, "
                            "div.wpcnt, nav, footer, .sd-block, .post-navigation, "
                            "div.jp-relatedposts-headline, .wp-block-buttons"):
        bad.decompose()

    # Each <br> becomes an explicit line break inside its block.
    for br in node.find_all("br"):
        br.replace_with("\n")

    # A stanza == one block-level child (<p>/<div>/<li>/<blockquote>). Lines
    # within the stanza come from the <br>-injected newlines.
    blocks = node.find_all(["p", "div", "li", "blockquote"], recursive=False)
    if not blocks:
        # WordPress sometimes nests one level deeper; fall back to any blocks,
        # else the whole node split on blank lines.
        blocks = node.find_all(["p", "div", "li", "blockquote"])
    if not blocks:
        blocks = [node]

    kn_stanzas, roman_stanzas, meaning_lines = [], [], []
    in_meaning = False
    for blk in blocks:
        # skip a block that merely contains nested blocks we'll visit separately
        if blk.find(["p", "div", "li", "blockquote"], recursive=False) and blk.name == "div":
            continue
        txt = blk.get_text("\n")
        lines = [l.strip() for l in txt.split("\n") if l.strip()]
        if not lines:
            continue
        kn_here, roman_here = [], []
        for ln in lines:
            low = ln.lower()
            if re.match(r"^(meaning|artha\b|word meaning|explanation|಄?ಅರ್ಥ)", low):
                in_meaning = True
            if in_meaning:
                meaning_lines.append(ln)
                continue
            sc = script_of(ln)
            if sc == "kn":
                kn_here.append(ln)
            elif sc == "iast_src":
                roman_here.append(ln)
            # 'sa'/'other' dropped from verse body
        if kn_here:
            kn_stanzas.append(kn_here)
        if roman_here:
            roman_stanzas.append(roman_here)

    # Fallback for unknown markup (e.g. sites that don't use <p> stanzas):
    # if block-parsing found nothing, harvest every Kannada line on the page and
    # group consecutive ones into stanzas.
    if not kn_stanzas:
        cur = []
        for ln in node.get_text("\n").split("\n"):
            ln = ln.strip()
            if ln and script_of(ln) == "kn":
                cur.append(ln)
            elif cur:
                kn_stanzas.append(cur)
                cur = []
        if cur:
            kn_stanzas.append(cur)

    return {
        "title_src": title,
        "kn_stanzas": kn_stanzas,
        "roman_stanzas": roman_stanzas,
        "meaning": "\n".join(meaning_lines).strip(),
    }


# --------------------------------------------------------------------------- #
# Record building
# --------------------------------------------------------------------------- #
FORM_KEYWORDS = [
    ("ugabhoga", ["ugabhoga", "ugabhog", "ಉಗಾಭೋಗ", "ಉಗಾ ಭೋಗ"]),
    ("suladi", ["suladi", "sulaadhi", "suladhi", "ಸುಳಾದಿ", "ಸುಳಾಧಿ"]),
    ("mangala", ["mangala", "ಮಂಗಳ"]),
    ("aarati", ["aarati", "aarathi", "ಆರತಿ", "ಆರಥಿ"]),
    ("laali", ["laali", "jo jo", "ಲಾಲಿ", "ಜೋ ಜೋ"]),
    ("kolu", ["kolu", "ಕೋಲು"]),
    ("shobhane", ["shobhane", "ಶೋಭನ"]),
]


def refine_form(form, *texts):
    """Promote a generic/ambiguous form using keywords in title/section text."""
    blob = " ".join(t for t in texts if t).lower()
    for canon, kws in FORM_KEYWORDS:
        if any(k in blob for k in kws):
            return canon
    return form


def _kn_from_hint(hint):
    """Pull a Kannada run out of a title hint like 'Bhootaraja (ಭೂತರಾಜ ಸ್ತೋತ್ರ)'."""
    if not hint:
        return ""
    m = re.findall(r"[ಀ-೿][ಀ-೿\s]*", hint)
    return (max(m, key=len).strip() if m else "")


def build_record(comp, meta, url, fetch_date):
    kn_flat = "\n".join("\n".join(s) for s in comp["kn_stanzas"]).strip()
    title_kn = comp["title_src"] if script_of(comp["title_src"]) == "kn" else ""
    title_latin = comp["title_src"] if script_of(comp["title_src"]) != "kn" else ""

    # Fallbacks from the category-page hint (dasasahitya lists Kannada titles there)
    hint = meta.get("title_hint", "")
    if not title_kn:
        title_kn = _kn_from_hint(hint)
    if not title_latin and script_of(hint) != "kn":
        title_latin = re.sub(r"\s*\([^)]*\)\s*", " ", hint).strip()

    # Refine the form: the composition's own title/hint wins over the (possibly
    # mixed, e.g. "Suladi & Ugabhoga") section heading the base form came from.
    title_form = refine_form("__none__", title_kn, title_latin, hint)
    if title_form != "__none__":
        form = title_form
    else:
        form = meta.get("form", "pada")
        sec = (meta.get("section", "") or "").lower()
        mixed = ("suladi" in sec or "sulaadhi" in sec) and "ugabhoga" in sec
        if form == "suladi" and mixed:
            n = sum(len(s) for s in comp["kn_stanzas"])
            if n and n <= 4:      # short => ugabhoga; long multi-taala => suladi
                form = "ugabhoga"

    rec = {
        "id": slugify(meta.get("composer", "")) + "__" +
              hashlib.sha1(url.encode()).hexdigest()[:8],
        "form": form,
        "title": {
            "kn": title_kn,
            "latin": title_latin,
            "iast": kn_to(sanscript.IAST, title_kn) if title_kn else "",
            "devanagari": kn_to(sanscript.DEVANAGARI, title_kn) if title_kn else "",
        },
        "composer": meta.get("composer", ""),
        "deity": meta.get("deity", ""),
        "tags": sorted(set(meta.get("tags", []))),
        "raga": "",
        "tala": "",
        "language": "kn",
        "text": {
            "kannada": [["".join(l) for l in [ln for ln in st]] for st in comp["kn_stanzas"]],
            "iast": [[kn_to(sanscript.IAST, ln) for ln in st] for st in comp["kn_stanzas"]] if _HAVE_TR else [],
            "devanagari": [[kn_to(sanscript.DEVANAGARI, ln) for ln in st] for st in comp["kn_stanzas"]] if _HAVE_TR else [],
            "source_roman": comp["roman_stanzas"],
        },
        "meaning": comp.get("meaning", ""),
        "source": {
            "site": meta.get("site", ""),
            "url": url,
            "attribution": meta.get("license_note", ""),
            "fetched": fetch_date,
        },
        "_has_text": bool(kn_flat),
    }
    return rec


# --------------------------------------------------------------------------- #
# dasasahitya.net — recursive category crawl
# --------------------------------------------------------------------------- #
# The site lists, on each /category/<slug>/ page, songs grouped under section
# headings ("Miscellenous", "Suladigalu & Ugabhogagalu", "<Composer> Songs"),
# each with a "(Lyrics)" link to the actual text. Categories (composers + deities)
# live in the sidebar on every page, so we auto-discover the full set from any one
# page and BFS across them, collecting every "(Lyrics)" target with its section-
# inferred form + composer/deity from the category slug.

_DS_COMPOSER_HINT = ("dasa", "tirtha", "teertha", "acharya", "swamy", "raja", "jayatirtha")


def _ds_axis_for_slug(slug):
    s = slug.replace("-", " ")
    if "info" in s:
        return (None, None)   # e.g. hari-dasa-info — skip as attribution
    if any(h in s for h in _DS_COMPOSER_HINT):
        return ("composer", s.title())
    return ("deity", s.title())


def _ds_section_form(section):
    sec = (section or "").lower()
    # suladi first: the common combined heading "Suladigalu & Ugabhogagalu"
    # defaults to suladi; per-song titles refine ugabhogas back out in build_record.
    if "suladi" in sec or "sulaadhi" in sec or "ಸುಳಾದಿ" in section:
        return "suladi"
    if "ugabhoga" in sec or "ಉಗಾಭೋಗ" in section:
        return "ugabhoga"
    if "mangala" in sec:
        return "mangala"
    if "aarati" in sec or "aarathi" in sec:
        return "aarati"
    return "pada"


def crawl_dasasahitya(sname, src, fetcher, limit_per_index=None,
                      max_pages=60, verbose=True):
    """BFS category pages; return {lyrics_url: meta}."""
    discovered = {}
    seeds = [idx["url"] for idx in src.get("indexes", [])] or [src["base"] + "/"]
    base_host = urlparse(src["base"]).netloc.replace("www.", "")
    seen_cat, queue = set(), deque(seeds)
    lyric_pat = re.compile(src.get("post_url_pattern", r"/\d{4}/\d{2}/\d{2}/[^/]+/?$"))

    # Config-provided axis/value for seeded categories is authoritative (more
    # accurate than the slug-keyword heuristic, e.g. raghavendra-swamy is a
    # subject category, not a composer). Keyed by category slug.
    seed_axis = {}
    for idx in src.get("indexes", []):
        sm = re.search(r"/category/([^/]+)/?", urlparse(idx["url"]).path)
        if sm and idx.get("axis") and idx.get("value"):
            seed_axis[sm.group(1)] = (idx["axis"], idx["value"])

    while queue and len(seen_cat) < max_pages:
        cat_url = queue.popleft()
        if cat_url in seen_cat:
            continue
        seen_cat.add(cat_url)
        html = fetcher.get(cat_url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")

        # (a) discover more categories from the WHOLE page (sidebar included)
        for a in soup.find_all("a", href=True):
            href = urljoin(cat_url, a["href"].split("#")[0])
            hu = urlparse(href)
            if hu.netloc.replace("www.", "") != base_host:
                continue
            if "/category/" in hu.path and href not in seen_cat:
                queue.append(href)

        # (b) attribution: config axis/value wins; else slug-keyword heuristic
        m = re.search(r"/category/([^/]+)/?", urlparse(cat_url).path)
        slug = m.group(1) if m else ""
        axis, value = seed_axis.get(slug) or _ds_axis_for_slug(slug)

        # (c) walk entry-content in order, tracking the current section heading,
        #     collecting each "(Lyrics)" link
        content = _content_node(soup)
        for bad in content.select("div.sharedaddy, .jp-relatedposts, script, style"):
            bad.decompose()
        section = ""
        count = 0
        for el in content.descendants:
            name = getattr(el, "name", None)
            if name in ("h1", "h2", "h3", "h4", "u", "strong", "b"):
                txt = el.get_text(" ", strip=True)
                if txt and len(txt) < 80:
                    section = txt
            if name == "a" and el.get("href"):
                label = el.get_text(" ", strip=True).lower()
                if "lyric" not in label or "english" in label:
                    continue
                href = urljoin(cat_url, el["href"].split("#")[0])
                if urlparse(href).netloc.replace("www.", "") != base_host:
                    continue
                if not lyric_pat.search(urlparse(href).path):
                    continue
                # title hint = enclosing list item / paragraph text, minus link labels
                host = el.find_parent(["li", "p"]) or el.parent
                hint = host.get_text(" ", strip=True) if host else ""
                hint = re.sub(r"\(?\s*(lyrics[\-\s]*english|lyrics|video|audio)\s*\)?",
                              "", hint, flags=re.I)
                hint = re.sub(r"^\s*\d+[\.\)]\s*", "", hint).strip()

                meta = discovered.setdefault(href, {
                    "site": src["base"], "license_note": src.get("license_note", ""),
                    "form": _ds_section_form(section), "composer": "", "deity": "",
                    "tags": [], "title_hint": hint, "section": section,
                })
                if axis == "composer" and value and not meta["composer"]:
                    meta["composer"] = value
                if axis in ("deity", "yati") and value:
                    meta["deity"] = value
                if value:
                    meta["tags"].append(f"{axis}:{value}")
                # section form wins over default pada
                sf = _ds_section_form(section)
                if sf != "pada":
                    meta["form"] = sf
                count += 1
                if limit_per_index and count >= limit_per_index:
                    break

        # (d) Fallback for archive-style categories: some categories (often
        # deities) are an ARCHIVE OF MANY SONG POSTS rather than one index post
        # with "(Lyrics)" links. If we found no lyrics links, treat each post
        # link in the content as a composition (title from the post's own page).
        if count == 0:
            for ln in extract_links(str(content), cat_url,
                                    src.get("post_url_pattern",
                                            r"/\d{4}/\d{2}/\d{2}/[^/]+/?$")):
                href = ln["url"]
                if href in discovered:
                    continue
                meta = discovered.setdefault(href, {
                    "site": src["base"], "license_note": src.get("license_note", ""),
                    "form": "pada", "composer": "", "deity": "",
                    "tags": [], "title_hint": ln.get("anchor", ""), "section": "",
                })
                if axis == "composer" and value and not meta["composer"]:
                    meta["composer"] = value
                if axis in ("deity", "yati") and value:
                    meta["deity"] = value
                if value:
                    meta["tags"].append(f"{axis}:{value}")
                count += 1
                if limit_per_index and count >= limit_per_index:
                    break

        if verbose:
            print(f"[dasasahitya] {slug or cat_url}: +{count} songs "
                  f"({len(discovered)} total, {len(queue)} cats queued)")
    return discovered


# --------------------------------------------------------------------------- #
# Crawl orchestration
# --------------------------------------------------------------------------- #
def crawl(config, fetcher, limit_per_index=None, verbose=True):
    """Return {url: meta} of every discovered composition + accumulated tags."""
    discovered = {}   # url -> meta dict
    for sname, src in config["sources"].items():
        # Skip sources explicitly disabled in the config (see each block's
        # "_status"). A source with no "enabled" key defaults to enabled, so the
        # working sources are unaffected.
        if src.get("enabled") is False:
            if verbose:
                reason = (src.get("_status", "") or "").split("—")[0].strip() or "disabled"
                print(f"[skip] {sname}: {reason}")
            continue
        # site-specific recursive crawler
        if src.get("parser") == "dasasahitya":
            for u, meta in crawl_dasasahitya(sname, src, fetcher,
                                             limit_per_index=limit_per_index,
                                             verbose=verbose).items():
                discovered[u] = meta
            continue
        post_pat = src.get("post_url_pattern", r"/\d{4}/\d{2}/\d{2}/")
        for idx in src.get("indexes", []):
            if verbose:
                print(f"[index] {sname}:{idx.get('axis')}={idx.get('value')}  {idx['url']}")
            html = fetcher.get(idx["url"])
            if not html:
                continue
            # 'kind' decides how to treat the page. Listing => crawl its links.
            # Page => the URL itself is a composition (or a collection page, e.g.
            # an ugabhoga sheet whose stanzas are individual ugabhogas).
            axis = idx.get("axis", "")
            kind = idx.get("kind") or (
                "listing" if axis in ("composer", "deity", "yati", "theme",
                                       "suladi_index", "kavya") else "page")

            if kind == "page":
                page_links = [{"url": idx["url"], "anchor": idx.get("value", "")}]
            else:
                links = extract_links(html, idx["url"], post_pat)
                # Fallback safety: a 'listing' that yielded no links is treated
                # as a page so we don't silently drop it.
                page_links = links if links else [{"url": idx["url"], "anchor": idx.get("value", "")}]
                if limit_per_index:
                    page_links = page_links[:limit_per_index]

            for ln in page_links:
                u = ln["url"]
                meta = discovered.setdefault(u, {
                    "site": src["base"],
                    "license_note": src.get("license_note", ""),
                    "form": idx.get("form", "pada"),
                    "composer": "",
                    "deity": "",
                    "tags": [],
                    "anchor": ln.get("anchor", ""),
                })
                axis = idx.get("axis", "")
                val = idx.get("value", "")
                # form: promote away from generic 'pada' when a specific form is known
                if idx.get("form") and (meta["form"] == "pada" or idx["form"] in ("suladi", "ugabhoga", "kavya")):
                    meta["form"] = idx["form"]
                if axis in ("composer", "ugabhoga", "suladi") and val and not meta["composer"]:
                    meta["composer"] = val
                if axis == "deity" and val:
                    meta["deity"] = val
                if axis == "yati" and val:
                    meta["tags"].append(f"on:{val}")
                if axis == "theme" and val:
                    meta["tags"].append(f"theme:{val}")
                if val:
                    meta["tags"].append(f"{axis}:{val}")
    return discovered


def main():
    ap = argparse.ArgumentParser(description="DGE Dasa Sahitya importer")
    ap.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "dasa_sources.json"))
    ap.add_argument("--out", default="data/DvaitaVedanta/Itara/DasaSahitya")
    ap.add_argument("--cache", default=".dasa_cache")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--limit-per-index", type=int, default=None,
                    help="cap compositions per index (for a quick test run)")
    ap.add_argument("--fetch-date", default=None,
                    help="override fetch date (YYYY-MM-DD); Actions/Colab pass today")
    args = ap.parse_args()

    fetch_date = args.fetch_date or _dt.date.today().isoformat()
    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    fetcher = Fetcher(args.cache, delay=args.delay)

    print("== Discovering compositions from index pages ==")
    discovered = crawl(config, fetcher, limit_per_index=args.limit_per_index)
    print(f"   discovered {len(discovered)} unique composition URLs")

    print("== Fetching + parsing compositions ==")
    records = []
    no_text = []
    for i, (url, meta) in enumerate(sorted(discovered.items()), 1):
        html = fetcher.get(url)
        if not html:
            continue
        comp = parse_composition(html, url)
        # skip pages that turned out to be sub-indexes with no verse text
        if not comp["kn_stanzas"] and not comp["roman_stanzas"]:
            no_text.append({"url": url, "title_hint": meta.get("title_hint", ""),
                            "form": meta.get("form", ""), "composer": meta.get("composer", ""),
                            "site": meta.get("site", "")})
            continue
        rec = build_record(comp, {**meta, "site": meta.get("site", "")}, url, fetch_date)
        records.append(rec)
        if i % 25 == 0:
            print(f"   parsed {i}/{len(discovered)}")

    raw_count = len(records)
    records, dup_count = dedupe(records)
    print(f"   {raw_count} fetched -> {len(records)} unique "
          f"({dup_count} cross-source duplicates merged)")

    stats = {"fetched": raw_count, "unique": len(records),
             "duplicates_merged": dup_count}
    write_outputs(records, args.out, fetch_date, stats,
                  failed_fetch=fetcher.failed, no_text=no_text)


# --------------------------------------------------------------------------- #
# Cross-source de-duplication
# --------------------------------------------------------------------------- #
_PUNCT_RE = re.compile(r"[\s।॥.,\-–—’‘'\"()\[\]:;!?|/]+")


def _fingerprint(rec):
    """Normalized identity: composer + first ~80 non-space Kannada chars, else title."""
    comp = slugify(rec.get("composer", ""))
    body = "".join("".join(st) for st in rec["text"]["kannada"])
    body = _PUNCT_RE.sub("", body)
    if body:
        return "b:" + hashlib.sha1((comp + "|" + body[:80]).encode()).hexdigest()
    t = (rec["title"].get("kn") or rec["title"].get("latin") or "").strip().lower()
    t = _PUNCT_RE.sub("", t)
    return "t:" + hashlib.sha1((comp + "|" + t).encode()).hexdigest()


def _text_len(rec):
    return sum(len(l) for st in rec["text"]["kannada"] for l in st)


def dedupe(records):
    """Merge the same composition seen across sources/axes. Keeps the richest
    text as primary, records the other source URLs in 'also_at', unions tags,
    and back-fills blank deity/meaning. Returns (unique_records, dup_count)."""
    by_key, dups = {}, 0
    for r in records:
        r.setdefault("also_at", [])
        k = _fingerprint(r)
        if k not in by_key:
            by_key[k] = r
            continue
        dups += 1
        keep = by_key[k]
        # choose the richer text as the primary record
        if _text_len(r) > _text_len(keep):
            primary, other = r, keep
        else:
            primary, other = keep, r
        # merge provenance
        urls = [primary["source"]["url"]] + primary["also_at"]
        for u in [other["source"]["url"]] + other["also_at"]:
            if u not in urls:
                primary["also_at"].append(u)
        primary["tags"] = sorted(set(primary["tags"]) | set(other["tags"]))
        if not primary["deity"] and other["deity"]:
            primary["deity"] = other["deity"]
        if not primary["composer"] and other["composer"]:
            primary["composer"] = other["composer"]
        if not primary["meaning"] and other["meaning"]:
            primary["meaning"] = other["meaning"]
        # keep a non-'pada' form over a generic 'pada'
        if primary["form"] == "pada" and other["form"] != "pada":
            primary["form"] = other["form"]
        by_key[k] = primary
    return list(by_key.values()), dups


def write_outputs(records, out_dir, fetch_date, stats=None, failed_fetch=None, no_text=None):
    os.makedirs(out_dir, exist_ok=True)
    comp_dir = os.path.join(out_dir, "composers")
    dump_dir = os.path.join(out_dir, "_dump")
    os.makedirs(comp_dir, exist_ok=True)
    os.makedirs(dump_dir, exist_ok=True)

    # group by composer
    groups = {}
    for r in records:
        slug = slugify(r["composer"]) or "unknown_composer"
        groups.setdefault(slug, []).append(r)

    def host_of(u):
        try:
            return urlparse(u).netloc.replace("www.", "")
        except Exception:
            return ""

    manifest = {
        "category": "DvaitaVedanta/Itara/DasaSahitya",
        "label": {"kn": "ದಾಸ ಸಾಹಿತ್ಯ", "sa": "दाससाहित्यम्", "en": "Dasa Sahitya"},
        "generated": fetch_date,
        "count_total": len(records),
        "dedup": stats or {},
        "counts_by_form": {},
        "counts_by_source": {},
        "counts_by_composer": {},
        "composers": [],
    }
    for r in records:
        manifest["counts_by_form"][r["form"]] = manifest["counts_by_form"].get(r["form"], 0) + 1
        h = host_of(r["source"]["url"])
        manifest["counts_by_source"][h] = manifest["counts_by_source"].get(h, 0) + 1
    manifest["counts_by_form"] = dict(sorted(manifest["counts_by_form"].items(),
                                             key=lambda x: -x[1]))
    manifest["counts_by_source"] = dict(sorted(manifest["counts_by_source"].items(),
                                               key=lambda x: -x[1]))

    for slug, recs in sorted(groups.items()):
        # composers/<slug>/data.json, not a flat composers/<slug>.json -- the
        # taxonomy/library.json leaf convention every other DGE grantha uses
        # (see tools/audit_library.py, tools/register_layers.py), so this
        # corpus is a real, browsable/searchable Library entry per composer
        # instead of only reachable through DvaitaVedanta/Itara/DasaSahitya.html's own fetch.
        slug_dir = os.path.join(comp_dir, slug)
        os.makedirs(slug_dir, exist_ok=True)
        with open(os.path.join(slug_dir, "data.json"), "w", encoding="utf-8") as f:
            json.dump({"schema": "dasa_pada_text", "default_author": recs[0]["composer"],
                       "composer": recs[0]["composer"], "count": len(recs),
                       "bio_notes": "", "items": recs}, f, ensure_ascii=False, indent=2)
        manifest["counts_by_composer"][recs[0]["composer"] or slug] = len(recs)
        manifest["composers"].append({"slug": slug, "composer": recs[0]["composer"],
                                      "count": len(recs), "file": f"composers/{slug}/data.json"})

    # untitled_composer_count is derivable from records but cheap to precompute
    # here so the capture tool doesn't have to load every composer file just
    # to build the review queue's headline number.
    manifest["pending"] = {
        "untitled_composer": sum(1 for r in records if not r.get("composer")),
        "failed_fetch": len(failed_fetch or []),
        "no_text": len(no_text or []),
    }
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # Review queue: URLs that never made it into a clean record, so a human
    # can open them directly and manually capture what the crawler couldn't.
    with open(os.path.join(dump_dir, "pending_review.json"), "w", encoding="utf-8") as f:
        json.dump({
            "generated": fetch_date,
            "failed_fetch": failed_fetch or [],
            "no_text": no_text or [],
        }, f, ensure_ascii=False, indent=2)

    # JSONL
    with open(os.path.join(dump_dir, "DvaitaVedanta/Itara/DasaSahitya.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # human-readable text dump
    with open(os.path.join(dump_dir, "dasa_sahitya_full.txt"), "w", encoding="utf-8") as f:
        f.write("DGE — DASA SAHITYA (Dasara Padagalu, Suladis, Ugabhogas)\n")
        f.write(f"Generated {fetch_date} · {len(records)} compositions\n")
        f.write("Non-commercial · dharma-prachara / education / research\n")
        f.write("=" * 70 + "\n\n")
        for slug, recs in sorted(groups.items()):
            f.write("\n" + "#" * 70 + "\n")
            f.write(f"## {recs[0]['composer'] or slug}  ({len(recs)})\n")
            f.write("#" * 70 + "\n")
            for r in recs:
                t = r["title"]["kn"] or r["title"]["latin"] or "(untitled)"
                f.write(f"\n--- [{r['form']}] {t}")
                if r["title"]["iast"]:
                    f.write(f"  ({r['title']['iast']})")
                f.write("\n")
                if r["deity"]:
                    f.write(f"    deity: {r['deity']}\n")
                if r["tags"]:
                    f.write(f"    tags: {', '.join(r['tags'])}\n")
                f.write(f"    source: {r['source']['url']}\n\n")
                for st in r["text"]["kannada"]:
                    for line in st:
                        f.write("    " + line + "\n")
                    f.write("\n")
                if r["meaning"]:
                    f.write("    [meaning]\n    " + r["meaning"].replace("\n", "\n    ") + "\n")
            f.write("\n")

    # --- counts report (counts.json + COUNTS.txt) ---
    report = {
        "generated": fetch_date,
        "total_unique": len(records),
        "dedup": stats or {},
        "by_form": manifest["counts_by_form"],
        "by_source": manifest["counts_by_source"],
        "by_composer": manifest["counts_by_composer"],
        "with_text": sum(1 for r in records if r.get("_has_text")),
        "multi_source": sum(1 for r in records if r.get("also_at")),
    }
    with open(os.path.join(out_dir, "counts.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    def _tbl(d):
        return "\n".join(f"    {k:<26} {v:>5}" for k, v in d.items())

    with open(os.path.join(dump_dir, "COUNTS.txt"), "w", encoding="utf-8") as f:
        f.write("DGE — DASA SAHITYA · COUNTS REPORT\n")
        f.write(f"Generated {fetch_date}\n")
        f.write("=" * 50 + "\n\n")
        if stats:
            f.write(f"Fetched (raw)          {stats.get('fetched', '?'):>5}\n")
            f.write(f"Cross-source dups merged {stats.get('duplicates_merged', 0):>3}\n")
        f.write(f"UNIQUE compositions    {len(records):>5}\n")
        f.write(f"  with verse text      {report['with_text']:>5}\n")
        f.write(f"  found on >1 site     {report['multi_source']:>5}\n")
        p = manifest["pending"]
        f.write(f"  untitled composer    {p['untitled_composer']:>5}\n")
        f.write(f"  failed fetch         {p['failed_fetch']:>5}  (see _dump/pending_review.json)\n")
        f.write(f"  no verse text        {p['no_text']:>5}  (see _dump/pending_review.json)\n\n")
        f.write("BY FORM\n" + _tbl(manifest["counts_by_form"]) + "\n\n")
        f.write("BY SOURCE (primary)\n" + _tbl(manifest["counts_by_source"]) + "\n\n")
        f.write("BY COMPOSER\n" + _tbl(dict(sorted(
            manifest["counts_by_composer"].items(), key=lambda x: -x[1]))) + "\n")

    print("\n== DONE ==")
    print(f"  {len(records)} unique compositions")
    print(f"  by form  : {manifest['counts_by_form']}")
    print(f"  by source: {manifest['counts_by_source']}")
    print(f"  written under: {out_dir}")
    print(f"    index.json, counts.json, composers/*.json,")
    print(f"    _dump/dasa_sahitya_full.txt, _dump/DvaitaVedanta/Itara/DasaSahitya.jsonl, _dump/COUNTS.txt")


if __name__ == "__main__":
    main()
