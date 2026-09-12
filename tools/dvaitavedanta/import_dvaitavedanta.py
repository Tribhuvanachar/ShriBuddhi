#!/usr/bin/env python3
"""Extract the dvaitavedanta.in corpus into data/darshana/vedanta/dvaita/DvaitaVedantaIn/.

Runs on GitHub Actions (open network egress). It does NOT run inside the Cowork
sandbox, which has no scraping egress to this host — that is by design and
matches the established DGE import workflow (see tools/DvaitaVedanta/Itara/DasaSahitya/).

Pipeline per grantha
  1. discover  fetch the seed leaf, harvest the full sidebar -> the leaf id set
  2. fetch     GET each leaf through a resumable on-disk cache
  3. parse     breadcrumb -> hierarchy, stacked commentary layers -> items
  4. emit      one data.json per commentary layer, DGE canonical shape
  5. track     _extract_status.json + a GitHub step summary

Design notes
  * Sidebar harvesting beats id brute-force: the id space has gaps that return
    HTTP 500, and one leaf page carries the whole grantha tree already.
  * The cache is keyed by SHA1 of the URL, so re-runs resume for free and a
    failed shard never costs the others their work.
  * Nothing is written unless --write is passed; --dry-run is the default so a
    parser regression cannot land 15k pages of bad JSON.

Usage
    python tools/dvaitavedanta/import_dvaitavedanta.py \
        --config tools/dvaitavedanta/dv_sources.json \
        --sections dasha_prakarana_granthas \
        --limit-per-grantha 5 --dry-run
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, OrderedDict

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dv_parse import (  # noqa: E402
    BASE,
    extract_lazy_units,
    parse_load_fragment,
    author_core,
    author_name,
    canonical_url,
    devanagari_count,
    devanagari_ratio,
    layer_key,
    parse_page,
    split_attribution,
    strip_grantha_prefix,
)

STATUS_FILENAME = "_extract_status.json"
MIN_DEVANAGARI_RATIO = 0.55
MIN_ITEM_CHARS = 4
PROGRESS_EVERY = 25


# --------------------------------------------------------------------------- #
# slugging
# --------------------------------------------------------------------------- #

try:  # optional; the built-in map below covers us if it is absent
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate as _translit

    _HAVE_TRANSLIT = True
except Exception:  # pragma: no cover
    _HAVE_TRANSLIT = False

_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "ळ": "l",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
}
_INDEPENDENT_VOWELS = {
    "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u",
    "ऋ": "ri", "ॠ": "ri", "ऌ": "li", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}
_MATRAS = {
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "ॄ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
}
_SIGNS = {"ं": "m", "ः": "", "ँ": "n", "़": "", "ॐ": "om", "्": ""}
_VIRAMA = "्"


def _fallback_translit(text: str) -> str:
    """Devanagari -> ascii without indic_transliteration.

    A naive per-character map is wrong: it appends the inherent 'a' even when a
    matra or virama follows, turning प्रमाणलक्षणम् into 'paramaanalakashanama'.
    So consonants are emitted bare and the inherent vowel is added only when the
    next character is neither a matra nor a virama.
    """
    out: list[str] = []
    index, length = 0, len(text)
    while index < length:
        char = text[index]
        nxt = text[index + 1] if index + 1 < length else ""
        if char in _CONSONANTS:
            out.append(_CONSONANTS[char])
            if nxt in _MATRAS:
                out.append(_MATRAS[nxt])
                index += 2
                continue
            if nxt == _VIRAMA:
                index += 2
                continue
            out.append("a")
        elif char in _INDEPENDENT_VOWELS:
            out.append(_INDEPENDENT_VOWELS[char])
        elif char in _MATRAS:
            out.append(_MATRAS[char])
        elif char in _SIGNS:
            out.append(_SIGNS[char])
        else:
            out.append(char)
        index += 1
    return "".join(out)


def slugify_devanagari(text: str) -> str:
    """Deterministic ascii slug from a Devanagari title.

    Site slugs are unusable for this: they drop matras and truncate to four
    characters, so माण्डूक्य and मुण्डक both render as 'mana'.
    """
    if not text:
        return ""
    roman = ""
    if _HAVE_TRANSLIT:
        try:
            roman = _translit(text, sanscript.DEVANAGARI, sanscript.IAST)
        except Exception:
            roman = ""
    if not roman:
        roman = _fallback_translit(text)
    roman = roman.lower()
    for src, dst in (
        ("ā", "a"), ("ī", "i"), ("ū", "u"), ("ṛ", "ri"), ("ṝ", "ri"),
        ("ḷ", "li"), ("ṅ", "n"), ("ñ", "n"), ("ṭ", "t"), ("ḍ", "d"),
        ("ṇ", "n"), ("ś", "sh"), ("ṣ", "sh"), ("ṃ", "m"), ("ḥ", ""),
        ("ĺ", "l"), ("'", ""), ("’", ""),
    ):
        roman = roman.replace(src, dst)
    roman = re.sub(r"[^a-z0-9]+", "_", roman).strip("_")
    roman = re.sub(r"_+", "_", roman)
    return roman[:64]


def strip_ordinal_prefix(title: str) -> str:
    """'1. ब्रह्मसूत्रभाष्यम्' -> 'ब्रह्मसूत्रभाष्यम्'."""
    return re.sub(r"^\s*[\d०-९]+\s*[.)\-–]\s*", "", title or "").strip()


# --------------------------------------------------------------------------- #
# fetching
# --------------------------------------------------------------------------- #

class Fetcher:
    """Polite, resumable HTTP with an on-disk cache keyed by SHA1 of the URL."""

    def __init__(self, cache_dir, user_agent, delay=1.0, timeout=120,
                 retries=4, refresh=False):
        self.cache_dir = cache_dir
        self.delay = float(delay)
        self.timeout = int(timeout)
        self.retries = int(retries)
        self.refresh = bool(refresh)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "sa,hi;q=0.9,en;q=0.8",
        })
        self.failed: list[dict] = []
        self.stats = Counter()
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, url):
        if not self.cache_dir:
            return None
        return os.path.join(
            self.cache_dir, hashlib.sha1(url.encode("utf-8")).hexdigest() + ".html"
        )

    def get(self, url):
        """Return HTML, or None on permanent failure. Never raises."""
        path = self._cache_path(url)
        if path and not self.refresh and os.path.exists(path):
            self.stats["cache_hit"] += 1
            with open(path, encoding="utf-8") as handle:
                return handle.read()

        last_error = None
        for attempt in range(self.retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    html = response.text
                    self.stats["fetched"] += 1
                    if path:
                        with open(path, "w", encoding="utf-8") as handle:
                            handle.write(html)
                    time.sleep(self.delay)
                    return html
                if response.status_code in (403, 404, 410):
                    # Permanent: do not burn retries.
                    self.stats["gone"] += 1
                    self.failed.append({"url": url, "status": response.status_code,
                                        "error": "permanent"})
                    return None
                # 500 is how this backend reports a nonexistent id; still retry
                # once or twice because it also fires under load.
                last_error = f"HTTP {response.status_code}"
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(self.delay * (attempt + 2))

        self.stats["failed"] += 1
        self.failed.append({"url": url, "status": None, "error": last_error})
        return None


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #

def absolute_url(href):
    """Sidebar hrefs arrive both absolute and root-relative."""
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return BASE + ("" if href.startswith("/") else "/") + href


def discover_leaves(fetcher, grantha, log):
    """Fetch the seed page and harvest every content id in its sidebar.

    Returns (ordered_ids, seed_record, ancestor_id, url_by_id).
    """
    seed_url = grantha["seed_url"]
    html = fetcher.get(seed_url)
    if html is None:
        log(f"    ! seed fetch failed: {seed_url}")
        # Four values, like every other exit. Returning three crashed the
        # caller's unpacking, turning "one grantha's seed was unreachable"
        # into "the whole section died".
        return [], None, grantha.get("ancestor_id"), {}

    record = parse_page(html, seed_url)
    ancestor = grantha.get("ancestor_id") or record.get("ancestor_id")

    ids = OrderedDict()
    ids[record["content_id"]] = True
    urls = {record["content_id"]: seed_url}
    for link in record["sidebar"]:
        if link["in_breadcrumb"]:
            continue
        ids[link["content_id"]] = True
        # Keep the site's OWN href. canonical_url has to invent the trailing
        # slug (".../13528/937/x"), where the real link carries
        # ".../13528/937/thasha/1-para/managa/garana". Recon assumed only the
        # contentId is load-bearing; that is an assumption we do not need to
        # make when the exact URL is right here in the sidebar.
        urls.setdefault(link["content_id"], absolute_url(link["href"]))
    return list(ids.keys()), record, ancestor, urls


def _author_agrees(embedded: str, canonical: str) -> bool:
    """Do a heading's own attribution and a canonical layer's author match?

    Absence of either is not disagreement — most headings carry no attribution
    at all, and those keep behaving exactly as before.
    """
    if not embedded or not canonical:
        return True
    one, two = author_core(embedded), author_core(canonical)
    if not one or not two:
        return True
    return one in two or two in one


def resolve_layer_config(title, layer_config):
    """Map an observed heading onto a canonical layer.

    The site names each commentary after its own grantha, so Bhavadipa appears
    as "प्रमाणलक्षणटीकाभावदीपः" on one work and "कथालक्षणटीकाभावदीपः" on
    another. Match on SUFFIX, longest first, and never on a substring: the
    canonical "टीका" occurs mid-string in "प्रमाणलक्षणटीकाविवरणम्", and a
    substring rule would file Keshavacharya's Vivarana into Jayatirtha's tika
    folder — merging two different authors' works under one name.

    Suffix alone is not enough when the author sits INSIDE the heading. On
    Shatprashnopanishad both of these end in भाष्यटीका:

        श्रीमज्जयतीर्थभिक्षुविरचिता षट्प्रश्नभाष्यटीका
        श्रीवामनपण्डिताचार्यविरचिता षट्प्रश्रभाष्यटीका

    and the suffix rule filed Vamana Panditacharya's commentary into
    Jayatirtha's folder — 29 items on that grantha alone, showing up only as
    duplicate ids needing a -N suffix. So the heading's own attribution, where
    it has one, must agree with the canonical layer's author or the match is
    refused and the commentary keeps its own folder.

    Anything with no suffix match stays unmapped and is reported, which is the
    safe outcome: a distinct commentary gets its own auto-slugged folder.
    """
    attributed_to, work = split_attribution(title)

    def _ok(config):
        return config if _author_agrees(attributed_to, config.get("author") or "") else None

    exact = layer_config.get(title)
    if exact is not None:
        return _ok(exact)
    for candidate in (layer_key(title), layer_key(work)):
        if candidate in layer_config:
            return _ok(layer_config[candidate])
    normalised = layer_key(work)
    best, best_len = None, 0
    for canonical, config in layer_config.items():
        if normalised.endswith(canonical) and len(canonical) > best_len:
            best, best_len = config, len(canonical)
    return _ok(best) if best is not None else None


def build_items(records, grantha, layer_config, defaults, fetch_date, warnings):
    """Group parsed pages into per-layer item lists.

    The item id is DV_<articleId> in *every* layer, which satisfies the
    grantha_tika_text convention that a tika item's id matches its mula item's:
    a verse and its commentaries live inside the same #article<N> block.

    Keying on the page's content id instead (the original rule) collided
    wherever one leaf stacks several articles — an adhikarana covering more
    than one sutra serves them all from a single URL, so every verse on that
    page claimed the same id. That is what --strict caught in run 32036326082
    with 11 duplicate-id errors. Pages with no article anchor at all still fall
    back to the content id, where it is unique by construction.
    """
    layers: "OrderedDict[str, dict]" = OrderedDict()

    # ---- rare-heading folding (1 Sep 2026, the Nyāyasudhā 774-folder fix) --
    # On Nyāyasudhā the site's <h3>s mix two different things: the real
    # commentary layers (सुधा, परिमळ, वाक्यार्थचन्द्रिका… — each recurring on
    # 518-1,625 units) and one-off TOPIC/pratika headings inside a
    # commentary's own run ("वैशेषिकाधिकरणम् १", "अणुत्वमहत्वयोर्न…"). The
    # auto-slug fallback below minted a tika_<slug> folder per topic heading
    # — 745 one-to-25-item folders that read as raw dump in the Library.
    # Where the grantha config sets "fold_rare_headings" (true = threshold
    # 30), an UNMAPPED, UNATTRIBUTED heading seen on fewer units than the
    # threshold is treated as a section heading, not a layer: its text folds
    # into the record's previous layer's item (heading preserved as a line),
    # or into mula when it opens the record — so the सुधा spine reads
    # continuously and only real sub-commentaries keep folders. Measured
    # margin on the live corpus: topic headings max out at 25 units, the
    # smallest real sub-commentary has 518.
    fold_threshold = grantha.get("fold_rare_headings")
    if fold_threshold is True:
        fold_threshold = 30
    title_counts = Counter()
    if fold_threshold:
        for record in records:
            for layer in record["layers"]:
                if layer.get("title"):
                    title_counts[layer_key(layer["title"])] += 1
    fold_stats = warnings.setdefault("folded_rare_headings", Counter())

    for record in records:
        last_item = None   # this record's most recent emitted item (fold target)
        breadcrumb = record["breadcrumb"]
        # Drop the leading category + grantha labels; what remains is the
        # structural path (adhyaya / pada / adhikarana / sutra).
        inner = breadcrumb[2:] if len(breadcrumb) > 2 else breadcrumb[-1:]
        reference = " > ".join(breadcrumb) if breadcrumb else str(record["content_id"])
        section = inner[-2] if len(inner) >= 2 else (inner[0] if inner else "")
        unit_title = inner[-1] if inner else ""

        # Sanitized site markup for this unit (dv_parse.sanitize_article_html
        # -- headings, strong/em, class markers). Carried ONCE per record, on
        # its first surviving item, not duplicated across every layer: the
        # styled renderer wants the unit's whole block, and the text layers
        # keep powering search/reading exactly as before.
        source_html_pending = record.get("source_html") or ""
        for position, layer in enumerate(record["layers"]):
            title = layer["title"] or ("मूलम्" if position == 0 else f"layer_{position + 1}")
            config = resolve_layer_config(title, layer_config)
            # dv_parse.py hardcodes the h2.shloka layer's title to the
            # literal "मूलम्" regardless of which grantha it came from, so
            # this ALWAYS matches the canonical "मूलम्" entry below, which
            # defaults to Madhva -- correct for his own works, wrong for
            # every later_acharyas grantha (whose root verse is by that
            # grantha's own later author). dv_sources.json's per-grantha
            # "acharya" field already carried the real author (e.g.
            # karmavijaya -> Satyatmatirtha); it was threaded into `grantha`
            # but never actually consulted here, so every later_acharyas
            # mula/ folder was misattributed to Madhva until this override.
            # Scoped to position 0 only, not every config match, so a
            # genuinely canonical-matched named commentary (Jayatirtha's
            # tika, say) is never touched by this.
            if position == 0 and config is not None and grantha.get("acharya"):
                config = {**config, "author": grantha["acharya"]}
            if config is None:
                # Where the heading names its own author, the author IS the
                # discriminator — every commentary on this grantha shares the
                # work name, so slugging the whole title would just produce
                # near-identical folders.
                attributed_to, _work = split_attribution(title)
                if (fold_threshold and not attributed_to
                        and title_counts[layer_key(title)] < fold_threshold):
                    text = layer["text"]
                    if devanagari_count(text) < MIN_ITEM_CHARS:
                        continue
                    fold_stats[title] += 1
                    if last_item is not None:
                        # continuation of the record's current layer, under a
                        # topic heading — keep the heading as its own line.
                        last_item["sanskrit_text"] += f"\n{title}\n{text}"
                        continue
                    # A record OPENING with a rare heading is the grantha's
                    # own text (a सुधा prose section with no separate verse
                    # unit) — it belongs on the mula spine.
                    config = {
                        "folder": "mula",
                        "schema": defaults["mula_schema"],
                        "author": grantha.get("acharya"),
                    }
                    layer = {**layer, "text": f"{title}\n{text}"}
            # (still unmapped after the rare-heading fold — the original
            # auto-slug fallback, untouched)
            if config is None:
                # dv_sources.json's "single_work": true marks a grantha that
                # IS the mula (a metrical treatise with no separate known
                # commentator crawled here), whose page nonetheless splits
                # into several <h3> blocks per adhikarana/topic. Without this,
                # every such heading auto-slugged its own "tika_<name>"
                # folder as if it were a distinct sub-commentary -- found on
                # Anuvyakhyana, where 68 folders each held one adhikarana's
                # worth of Madhva's OWN verses, not a different author's
                # commentary (confirmed: every one of those folders' items
                # share the SAME id as a real Anuvyakhyana mula verse, and
                # their author field was always empty/garbage because there
                # never was a second author to find). An UNATTRIBUTED
                # position>0 heading on such a grantha is still the grantha's
                # own text, so it folds into "mula" rather than minting a
                # folder; an attributed heading (a real quoted commentator)
                # still gets its own tika folder as before.
                if grantha.get("single_work") and not attributed_to:
                    folder, schema = "mula", defaults["mula_schema"]
                else:
                    # Slug from the NORMALISED key, not the raw heading, or a
                    # stray space produces a second folder for the same work.
                    # strip_grantha_prefix additionally drops a self-referential
                    # repeat of the grantha's own title (see its own docstring --
                    # found via nyaya_sudha's Parimaḷa sub-commentary splitting
                    # across folders depending on whether the heading repeated
                    # "न्यायसुधा" or not).
                    folder = (f"tika_{slugify_devanagari(author_name(attributed_to))}"
                              if attributed_to else
                              slugify_devanagari(strip_grantha_prefix(layer_key(title), grantha.get("title"))) or f"layer_{position + 1}")
                    # An unmapped heading is ALWAYS a commentary, position 0
                    # included: the real mula layer (h2.shloka) is titled
                    # "मूलम्" and exact-maps above, so an unmapped layer sits
                    # at position 0 only when that mula was dropped (a
                    # structural heading) or absent — and giving it the mula
                    # schema in a bare unprefixed folder (the old branch here)
                    # is how nyaya_vivarana got a schema-less "bhavabodha/"
                    # twin of its real tika_bhavabodha/ on the 25 Aug cache
                    # replay. The tika treatment merges it there instead.
                    schema = defaults["tika_schema"]
                    if not folder.startswith("tika_"):
                        folder = f"tika_{folder}"
                # An unmapped commentary still carries its own "composed by"
                # line on the page, so it is attributed rather than anonymous.
                config = {
                    "folder": folder,
                    "schema": schema,
                    "author": attributed_to or layer.get("author") or None,
                }
                warnings["unmapped_layers"][title] += 1

            text = layer["text"]
            if devanagari_count(text) < MIN_ITEM_CHARS:
                continue
            ratio = devanagari_ratio(text)
            if ratio < MIN_DEVANAGARI_RATIO:
                warnings["low_devanagari"].append({
                    "url": record["url"], "layer": title, "ratio": round(ratio, 3),
                })

            bucket = layers.setdefault(config["folder"], {
                "schema": config["schema"],
                # Canonical author wins where the tradition fixes it (Jayatirtha's
                # tika); otherwise fall back to the "composed by" line on the page,
                # so a commentary whose author varies by grantha is still credited.
                "default_author": config.get("author") or layer.get("author") or "",
                "layer_titles": Counter(),
                "items": [],
            })
            bucket["layer_titles"][title] += 1

            item = {
                "id": f"DV_{layer.get('article_id') or record['content_id']}",
                "reference": reference,
                "section": section,
                "unit_title": unit_title,
                "sanskrit_text": text,
                "artha": "",
                "notes": "",
                "tags": [],
                "references": [],
                "audio": [],
                "breadcrumb": breadcrumb,
                "source": {
                    "site": "dvaitavedanta.in",
                    "url": record["url"],
                    "content_id": record["content_id"],
                    # The site's URLs are category-details/{node}/{work}/...:
                    # content_id above is the node, this is the constant work
                    # root (975 = Nyāya Sudhā). Stored explicitly so the
                    # numeric pair — not the transliterated URL path — is the
                    # canonical linkage key (25 Aug 2026 node-graph
                    # verification, PENDING part 10).
                    "work_id": grantha.get("ancestor_id") or record.get("ancestor_id"),
                    "layer": title,
                    "anchor": layer.get("anchor", ""),
                    "fetched": fetch_date,
                },
            }
            if source_html_pending:
                item["source_html"] = source_html_pending
                source_html_pending = ""
            if bucket["schema"] == "grantha_tika_text":
                item["tika_title"] = title
            elif bucket["schema"] == "grantha_tippani_text":
                item["tippani_title"] = title
                item["author"] = config.get("author") or ""
            # Belt and braces. The article id fixes the known collision, but an
            # id must be unique inside a data.json whatever the page does, so a
            # residual clash is disambiguated here and reported rather than
            # left for --strict to reject after a six-hour crawl.
            seen = bucket.setdefault("seen_ids", {})
            if item["id"] in seen:
                if seen[item["id"]]["sanskrit_text"] == item["sanskrit_text"]:
                    continue          # same verse served twice; keep one
                warnings["id_collisions"].append(
                    {"url": record["url"], "id": item["id"], "layer": title})
                suffix = 2
                while f"{item['id']}-{suffix}" in seen:
                    suffix += 1
                item["id"] = f"{item['id']}-{suffix}"
            seen[item["id"]] = item
            layers[config["folder"]]["items"].append(item)
            last_item = item

    return layers


def write_layer(out_root, rel_path, payload, site_cfg, grantha, dry_run):
    """Emit one data.json. Matches importers/common.write_grantha conventions:
    ensure_ascii=False, indent=1, Devanagari (never IAST)."""
    folder = os.path.join(out_root, rel_path)
    body = {
        "schema": payload["schema"],
        "default_author": payload["default_author"],
        "source_url": grantha["seed_url"],
        "source_note": site_cfg["license_note"],
        "items": payload["items"],
    }
    blob = json.dumps(body, ensure_ascii=False, indent=1)
    if not dry_run:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "data.json"), "w", encoding="utf-8") as handle:
            handle.write(blob)
    return len(blob.encode("utf-8"))


def write_meta(path, directory, description, schema, dry_run):
    if dry_run:
        return
    os.makedirs(path, exist_ok=True)
    meta_path = os.path.join(path, "_meta.json")
    if os.path.exists(meta_path):
        return
    meta = {"directory": directory, "description": description}
    if schema:
        meta["schema"] = schema
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


# --------------------------------------------------------------------------- #
# status tracker
# --------------------------------------------------------------------------- #

def load_status(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            pass
    return {
        "generated_note": "DvaitaVedanta extraction progress. Regenerate with "
                          "tools/dvaitavedanta/import_dvaitavedanta.py.",
        "source": "https://dvaitavedanta.in/",
        "license_note": "",
        "last_run": None,
        "totals": {},
        "sections": {},
        "granthas": {},
        "unmapped_layers": {},
        "failures": [],
    }


def recompute_totals(status):
    totals = Counter()
    sections: dict[str, Counter] = {}
    for key, entry in status["granthas"].items():
        section = key.split("/", 1)[0]
        bucket = sections.setdefault(section, Counter())
        for field in ("discovered", "fetched", "with_text", "containers",
                      "failed", "items", "bytes"):
            totals[field] += entry.get(field, 0) or 0
            bucket[field] += entry.get(field, 0) or 0
        totals["granthas"] += 1
        bucket["granthas"] += 1
        if entry.get("status") == "complete":
            totals["complete"] += 1
            bucket["complete"] += 1
    status["totals"] = dict(totals)
    status["sections"] = {name: dict(counts) for name, counts in sorted(sections.items())}
    return status


def render_summary(status, selected_keys):
    lines = ["## DvaitaVedanta extraction", ""]
    totals = status.get("totals", {})
    lines.append(
        f"**{totals.get('complete', 0)}/{totals.get('granthas', 0)} granthas complete** · "
        f"{totals.get('items', 0):,} items · {totals.get('with_text', 0):,} leaf pages · "
        f"{totals.get('failed', 0)} failures · {totals.get('bytes', 0) / 1_048_576:.1f} MB"
    )
    lines += ["", "| Grantha | Status | Leaves | With text | Items | Layers | Failed |",
              "|---|---|--:|--:|--:|--:|--:|"]
    for key in selected_keys:
        entry = status["granthas"].get(key)
        if not entry:
            continue
        icon = {"complete": "✅", "partial": "🟡", "failed": "❌"}.get(entry.get("status"), "⏳")
        layers = ", ".join(f"{k} ({v})" for k, v in (entry.get("layers") or {}).items()) or "—"
        lines.append(
            f"| `{key}`<br>{entry.get('title') or ''} | {icon} {entry.get('status')} | "
            f"{entry.get('discovered', 0)} | {entry.get('with_text', 0)} | "
            f"{entry.get('items', 0)} | {layers} | {entry.get('failed', 0)} |"
        )
    unmapped = status.get("unmapped_layers") or {}
    if unmapped:
        lines += ["", "### Unmapped commentary layers", "",
                  "Add these to `layers` in `dv_sources.json` to fix their folder, "
                  "schema and author:", ""]
        for title, count in sorted(unmapped.items(), key=lambda kv: -kv[1]):
            lines.append(f"- `{title}` — {count} items → auto-slugged")
    failures = status.get("failures") or []
    if failures:
        lines += ["", f"### Failures ({len(failures)})", ""]
        for failure in failures[:25]:
            lines.append(f"- `{failure.get('url')}` — {failure.get('error')}")
        if len(failures) > 25:
            lines.append(f"- …and {len(failures) - 25} more")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def select_granthas(config, sections_filter, granthas_filter):
    """Pick the granthas to crawl.

    Naming a grantha explicitly overrides its `enabled: false`. That flag means
    "not part of a routine sweep" — nyaya_sudha is held out of `scope=all`
    because it alone needs some 46 hours — and asking for it by name is not a
    routine sweep. Without this the only way to crawl it would be to edit the
    config, run, and remember to put the flag back.
    """
    selected = []
    for section in config["sections"]:
        named = set(granthas_filter or ())
        if section.get("enabled") is False and not named:
            continue
        if sections_filter and section["slug"] not in sections_filter:
            continue
        for grantha in section["granthas"]:
            if not grantha.get("seed"):
                continue
            if grantha.get("enabled") is False and grantha.get("slug") not in named:
                continue
            if granthas_filter and grantha.get("slug") not in granthas_filter:
                continue
            selected.append({
                "section_slug": section["slug"],
                "section_title": section["title"],
                "slug": grantha.get("slug"),
                "title": grantha.get("title"),
                "seed_url": config["site"]["base"] + grantha["seed"],
                "content_id": grantha.get("content_id"),
                "ancestor_id": grantha.get("ancestor_id"),
                "acharya": grantha.get("acharya"),
                "single_work": grantha.get("single_work"),
                # Run 33512729140 (1 Sep 2026): this whitelist silently
                # dropped the then-new fold_rare_headings flag — acharya
                # from the same config entry flowed, the fold never fired,
                # and the run reproduced all 745 topic folders. Any future
                # per-grantha behavior flag has to be threaded HERE too.
                "fold_rare_headings": grantha.get("fold_rare_headings"),
            })
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="tools/dvaitavedanta/dv_sources.json")
    parser.add_argument("--out", default=None, help="output root (default: config output_root)")
    parser.add_argument("--cache", default=".dv_cache")
    parser.add_argument("--sections", default="", help="comma-separated section slugs; blank = all")
    parser.add_argument("--granthas", default="", help="comma-separated grantha slugs; blank = all")
    parser.add_argument("--limit-per-grantha", type=int, default=0,
                        help="cap leaves per grantha (smoke test); 0 = no cap")
    parser.add_argument("--discover-only", action="store_true",
                        help="count each grantha's leaves and stop. One fetch per "
                             "grantha (the sidebar lists them all), so this sizes "
                             "the corpus without crawling it.")
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--retries", type=int, default=None)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--refresh-granthas", default="",
                        help="comma-separated slugs whose cache to ignore, leaving "
                             "every other grantha resumable. A refetch of one "
                             "grantha should not cost a refetch of 2,891 pages.")
    parser.add_argument("--probe-dir", default="",
                        help="also save raw HTML of the first N pages here for selector review")
    parser.add_argument("--probe-count", type=int, default=3)
    parser.add_argument("--fetch-date", default=_dt.date.today().isoformat())
    parser.add_argument("--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY", ""))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    group.add_argument("--write", dest="dry_run", action="store_false")
    args = parser.parse_args(argv)

    with open(args.config, encoding="utf-8") as handle:
        config = json.load(handle)
    site = config["site"]
    defaults = config["defaults"]
    layer_config = config["layers"]
    out_root = args.out or config["output_root"]

    selected = select_granthas(
        config,
        [s for s in args.sections.split(",") if s.strip()],
        [g for g in args.granthas.split(",") if g.strip()],
    )
    if not selected:
        # An explicit filter that matches nothing is a mistake worth failing on
        # (a typo in --granthas would otherwise look like a clean run). A scope
        # that is simply switched off in dv_sources.json is NOT an error: the
        # matrix still spawns a job per section, and failing it would fail the
        # whole run. later_acharyas is deliberately disabled while its ~105 s
        # per leaf is dealt with separately.
        known_sections = {s["slug"] for s in config["sections"]}
        known_granthas = {g.get("slug") for s in config["sections"]
                          for g in s["granthas"] if g.get("slug")}
        asked_sections = [s.strip() for s in args.sections.split(",") if s.strip()]
        asked_granthas = [g.strip() for g in args.granthas.split(",") if g.strip()]
        unknown = ([s for s in asked_sections if s not in known_sections]
                   + [g for g in asked_granthas if g not in known_granthas])
        if unknown:
            print(f"No granthas selected; unknown name(s): {', '.join(unknown)}",
                  file=sys.stderr)
            return 2
        print("No granthas selected — everything requested is disabled in "
              "dv_sources.json. Nothing to do.")
        return 0

    fetcher = Fetcher(
        cache_dir=args.cache,
        user_agent=site["user_agent"],
        delay=args.delay if args.delay is not None else defaults["delay"],
        timeout=args.timeout if args.timeout is not None else defaults["timeout"],
        retries=args.retries if args.retries is not None else defaults["retries"],
        refresh=args.refresh_cache,
    )

    status_path = os.path.join(out_root, STATUS_FILENAME)
    status = load_status(status_path)
    status["license_note"] = site["license_note"]
    status["last_run"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    global_unmapped = Counter(status.get("unmapped_layers") or {})
    run_failures: list[dict] = []
    selected_keys = []
    probes_saved = 0

    def log(message):
        print(message, flush=True)

    mode = "DRY RUN (no files written)" if args.dry_run else "WRITE"
    log(f"dvaitavedanta.in → {out_root}  [{mode}]")
    log(f"{len(selected)} grantha(s) selected\n")

    refresh_slugs = {s.strip() for s in args.refresh_granthas.split(",") if s.strip()}

    for grantha in selected:
        started = time.time()
        label = grantha["slug"] or f"id_{grantha['content_id']}"
        log(f"→ {grantha['section_slug']}/{label}")

        # A cache entry can be poisoned — rig_bhashya cached an unusable seed
        # during the invented-slug era and has reported 1 leaf ever since, on a
        # page that really lists twenty suktas. Re-fetching just that grantha
        # costs twenty requests; --refresh-cache would cost the whole corpus.
        # Set per iteration rather than saved-and-restored: the seed-failure
        # branch below does `continue`, so a restore at the end of the loop
        # would be the one path it skips.
        targeted = label in refresh_slugs or grantha["slug"] in refresh_slugs
        fetcher.refresh = bool(args.refresh_cache) or targeted
        if targeted:
            log("    (ignoring cache for this grantha)")

        ids, seed_record, ancestor, url_by_id = discover_leaves(fetcher, grantha, log)
        if seed_record is None:
            key = f"{grantha['section_slug']}/{label}"
            status["granthas"][key] = {
                "title": grantha.get("title"), "seed_url": grantha["seed_url"],
                "status": "failed", "discovered": 0, "fetched": 0, "with_text": 0,
                "containers": 0, "failed": 1, "items": 0, "bytes": 0, "layers": {},
                "last_run": status["last_run"],
            }
            selected_keys.append(key)
            continue

        # Resolve the real title and folder slug from the breadcrumb — the site's
        # own slugs are lossy and collide.
        breadcrumb = seed_record["breadcrumb"]
        discovered_title = strip_ordinal_prefix(breadcrumb[1]) if len(breadcrumb) > 1 else ""
        title = grantha.get("title") or discovered_title or label
        slug = grantha.get("slug") or slugify_devanagari(discovered_title) or f"id_{grantha['content_id']}"
        key = f"{grantha['section_slug']}/{slug}"
        selected_keys.append(key)
        if not grantha.get("slug"):
            log(f"    resolved slug: {slug}   (title: {discovered_title})")

        # Report the true sidebar total before capping. Logging the capped
        # figure makes a smoke run look like a complete one and hides the
        # denominator needed to size the corpus.
        discovered_total = len(ids)
        if args.limit_per_grantha:
            ids = ids[: args.limit_per_grantha]
        if len(ids) != discovered_total:
            log(f"    {discovered_total} leaf id(s) discovered · capped to {len(ids)}")
        else:
            log(f"    {discovered_total} leaf id(s) discovered")

        if args.discover_only:
            status["granthas"][key] = {
                "title": title, "seed_url": grantha["seed_url"],
                "status": "discovered", "discovered": discovered_total,
                "fetched": 0, "with_text": 0, "containers": 0, "failed": 0,
                "items": 0, "bytes": 0, "layers": {},
                "last_run": status["last_run"],
            }
            continue

        # The frontier grows as containers are opened. A grantha's sidebar does
        # not always list text leaves: Upanishad and Sutra granthas list
        # adhyaya/adhikarana INDEX nodes, which answer 200 with "No record
        # found!!". Treating those as dead ends silently lost most of the
        # corpus -- Chandogya reported "1 with text, 149 containers" and still
        # passed verify as complete. So when a page turns out to be a
        # container, fold its own sidebar back into the queue and keep going.
        seen_ids = set(ids)
        queue = list(ids)
        records, containers, failed = [], 0, 0
        index = 0
        while index < len(queue):
            content_id = queue[index]
            index += 1
            if args.limit_per_grantha and index > args.limit_per_grantha:
                break
            # A long crawl is otherwise silent until it ends, and Actions
            # serves no log at all for a running job — so nyaya_sudha's first
            # pass could not be told apart from a hang. Say where it is, and at
            # what rate, often enough to be useful and rarely enough to stay
            # readable.
            if index > 1 and index % PROGRESS_EVERY == 1:
                spent = time.time() - started
                rate = spent / max(index - 1, 1)
                left = (len(queue) - index + 1) * rate
                log(f"      … {index - 1}/{len(queue)} leaves · "
                    f"{rate:.1f}s each · ~{left / 3600:.1f}h to go")
            if content_id == seed_record["content_id"]:
                # Already fetched during discovery — don't pay for it twice
                # (the fetcher cache serves this instantly); the html is
                # still needed below for the page's lazy Load More units.
                record = seed_record
                html = fetcher.get(grantha["seed_url"])
            else:
                url = url_by_id.get(content_id) or canonical_url(content_id, ancestor)
                html = fetcher.get(url)
                if html is None:
                    failed += 1
                    continue
                if args.probe_dir and probes_saved < args.probe_count:
                    os.makedirs(args.probe_dir, exist_ok=True)
                    with open(os.path.join(args.probe_dir, f"{slug}_{content_id}.html"),
                              "w", encoding="utf-8") as handle:
                        handle.write(html)
                    probes_saved += 1
                record = parse_page(html, url)

            if record["is_container"]:
                containers += 1
                added = 0
                for link in record["sidebar"]:
                    child = link["content_id"]
                    if child in seen_ids or link["in_breadcrumb"]:
                        continue
                    seen_ids.add(child)
                    queue.append(child)
                    url_by_id.setdefault(child, absolute_url(link["href"]))
                    added += 1
                if added:
                    log(f"    + {added} id(s) from container {content_id}"
                        f" (queue now {len(queue)})")
                continue
            records.append(record)
            # Exhaust the page's lazy "Load More" units (see dv_parse
            # extract_lazy_units' own comment): the initial HTML carries
            # only the first #article block, and every further unit named
            # in the right-hand nav is served solely by /load-data. The
            # original import stopped at the first block — verified live,
            # 1 Sep 2026: node 977 (maṅgalamācaraṇam) held 9 units, our
            # data had exactly the 1 the initial HTML delivers.
            book_id, lazy_ids = extract_lazy_units(html or "")
            for uid in lazy_ids:
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)
                frag_url = (f"{BASE}/load-data?book_id="
                            f"{book_id or ancestor or ''}&id={uid}&search=")
                raw = fetcher.get(frag_url)
                if raw is None:
                    failed += 1
                    continue
                try:
                    payload = json.loads(raw)
                except (ValueError, TypeError):
                    failed += 1
                    continue
                frag = parse_load_fragment(payload.get("html", ""),
                                           record, uid, record["url"])
                if frag["layers"]:
                    records.append(frag)
            if index % 25 == 0:
                log(f"    …{index}/{len(queue)}")
        discovered_total = len(seen_ids)

        warnings = {"unmapped_layers": Counter(), "low_devanagari": [],
                    "id_collisions": []}
        layers = build_items(records, grantha, layer_config, defaults,
                             args.fetch_date, warnings)
        global_unmapped.update(warnings["unmapped_layers"])

        total_bytes, total_items, layer_counts = 0, 0, {}
        section_dir = os.path.join(out_root, grantha["section_slug"])
        grantha_dir = os.path.join(section_dir, slug)
        write_meta(out_root, "dvaitavedanta",
                   "DGE category structure file to anchor the directory.",
                   None, args.dry_run)
        write_meta(section_dir, grantha["section_slug"],
                   f"{grantha['section_title']} — extracted from dvaitavedanta.in.",
                   "grantha_prakarana_text", args.dry_run)
        write_meta(grantha_dir, slug,
                   f"{title} — extracted from dvaitavedanta.in.",
                   "grantha_prakarana_text", args.dry_run)

        for folder, payload in layers.items():
            size = write_layer(out_root, os.path.join(grantha["section_slug"], slug, folder),
                               payload, site, grantha, args.dry_run)
            total_bytes += size
            total_items += len(payload["items"])
            layer_counts[folder] = len(payload["items"])

        state = "complete" if failed == 0 and records else ("failed" if not records else "partial")
        if args.limit_per_grantha:
            state = "partial"
        previous = status["granthas"].get(key, {})
        status["granthas"][key] = {
            "title": title,
            "title_source": "config" if grantha.get("title") else "breadcrumb",
            "seed_url": grantha["seed_url"],
            "content_id": grantha["content_id"],
            "status": state,
            "discovered": len(ids),
            "fetched": len(records) + containers,
            "with_text": len(records),
            "containers": containers,
            "failed": failed,
            "items": total_items,
            "bytes": total_bytes,
            "layers": layer_counts,
            "low_devanagari_warnings": len(warnings["low_devanagari"]),
            "id_collisions": len(warnings["id_collisions"]),
            "first_run": previous.get("first_run") or status["last_run"],
            "last_run": status["last_run"],
            "duration_s": round(time.time() - started, 1),
            "dry_run": args.dry_run,
        }
        log(f"    {len(records)} with text · {containers} containers · {failed} failed · "
            f"{total_items} items · {total_bytes / 1024:.0f} KB · {state}")
        for folder, count in layer_counts.items():
            log(f"      {folder}: {count}")
        if warnings["low_devanagari"]:
            log(f"    ! {len(warnings['low_devanagari'])} item(s) below "
                f"{MIN_DEVANAGARI_RATIO:.0%} Devanagari — check selectors")
        if warnings["id_collisions"]:
            log(f"    ! {len(warnings['id_collisions'])} item id(s) disambiguated "
                f"with a -N suffix; first: {warnings['id_collisions'][0]['url']}")
        log("")

    run_failures.extend(fetcher.failed)
    status["failures"] = run_failures[-500:]
    status["unmapped_layers"] = dict(global_unmapped)
    recompute_totals(status)

    if not args.dry_run:
        os.makedirs(out_root, exist_ok=True)
        with open(status_path, "w", encoding="utf-8") as handle:
            json.dump(status, handle, ensure_ascii=False, indent=1)
            handle.write("\n")

    summary = render_summary(status, selected_keys)
    print(summary)
    if args.summary_file:
        with open(args.summary_file, "a", encoding="utf-8") as handle:
            handle.write(summary)

    log(f"cache hits {fetcher.stats['cache_hit']} · fetched {fetcher.stats['fetched']} · "
        f"failed {fetcher.stats['failed']} · gone {fetcher.stats['gone']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
