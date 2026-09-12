#!/usr/bin/env python3
"""Import Sāyaṇa's Ṛgveda-bhāṣya into DGE from Sanskrit Wikisource.

Why this source rather than the archive.org scan (see SOURCES.md §5): the text
is transcribed rather than OCR'd, it is wrapped in a named template
``{{सायणभाष्यम्|…}}`` so extraction is a parse instead of a fuzzy match, its
licence is stated (CC BY-SA), and it covers 1,022 of the Ṛgveda's 1,028 sūktas.

How the alignment works, and why it is self-verifying
-----------------------------------------------------
Each page holds one sūkta. Inside the template the edition prints, per mantra
and in order::

    <saṃhitā-pāṭha, accented>   … ॥N
    <pada-pāṭha, accented>      … ॥N
    <pada-pāṭha, plain>         … ॥N
    <Sāyaṇa's gloss on mantra N>

DGE already holds all four of the first three forms' sources — ``samhita_patha``
and ``pada_patha``, accented and plain — for every one of the 10,552 mantras.
So a cut is never made on a number alone: the number ``N`` must agree *and* the
text immediately above the marker must resemble the mantra DGE already has. A
wrong cut therefore cannot look right, which is the property the archive.org
route was built for and the reason its logic is reused here verbatim
(``skeleton``/``similarity`` are imported from ``archive_sayana``).

The gloss for mantra N runs from the last marker numbered N that matches, up to
the first matching marker for N+1 — i.e. up to the top of the next mantra's
printed saṃhitā-pāṭha.

Rights
------
Sanskrit Wikisource is CC BY-SA 4.0. Sāyaṇa's own text is long out of
copyright, but the transcription is not, and share-alike is an obligation
rather than a courtesy: it is written into each maṇḍala's
``commentary_sources`` block by this importer, not assumed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from difflib import SequenceMatcher  # noqa: E402
from archive_sayana import skeleton, similarity, to_int  # noqa: E402
from common import sniff_indent  # noqa: E402

API = "https://sa.wikisource.org/w/api.php"
UA = ("DGE-import/1.0 (Digital Grantha Engine; non-commercial educational "
      "digital library; github.com/Tribhuvanachar/bhumandala)")

TEMPLATE = "सायणभाष्यम्"
SEARCH = f'insource:"{TEMPLATE}" intitle:"ऋग्वेदः"'
SAMHITA = "data/vedas/rigveda/shakala_shakha/samhita/mandala_{m:02d}/data.json"

# Sūktas per maṇḍala, Śākala recension -- used only to report coverage against
# the real denominator rather than against whatever the search happened to
# return.
SUKTA_COUNTS = {1: 191, 2: 43, 3: 62, 4: 58, 5: 87,
                6: 75, 7: 104, 8: 103, 9: 114, 10: 191}

ATTRIBUTION = {
    "sayana": {
        "commentator": "Sāyaṇācārya",
        "work": "Ṛgveda-bhāṣya (सायणभाष्यम्)",
        "edition": "Transcribed text as published on Sanskrit Wikisource "
                   "(sa.wikisource.org), one page per sūkta.",
        "source": "https://sa.wikisource.org/wiki/ऋग्वेदः",
        "licence": "CC BY-SA 4.0. Share-alike: any redistribution of this "
                   "commentary text, modified or not, must carry the same "
                   "licence and attribute Sanskrit Wikisource.",
        "licence_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": "Sanskrit Wikisource contributors, "
                       "https://sa.wikisource.org/",
        "note": "Split per mantra by matching the saṃhitā- and pada-pāṭha the "
                "page prints above each gloss against the mantra DGE already "
                "holds, so every cut is anchored to known text rather than to "
                "the verse numbering alone.",
    }
}


# ------------------------------------------------------------------- fetching

class Wiki:
    """MediaWiki API client: descriptive UA, on-disk cache, backoff on 429.

    Anonymous clients get ``srlimit``/``titles`` batches of 50, not 500, and
    exceeding it is answered with 429 rather than a truncated result. The cache
    matters more than the politeness delay: a full run touches ~1,030 pages, and
    re-running the alignment while tuning it should not re-fetch any of them.
    """

    def __init__(self, cache_dir: Path | None = None, delay: float = 0.2):
        self.cache = Path(cache_dir) if cache_dir else None
        self.delay = delay
        self.fetched = 0
        self.cached = 0
        if self.cache:
            self.cache.mkdir(parents=True, exist_ok=True)

    def get(self, post: bool = False, **params) -> dict:
        params.setdefault("format", "json")
        params.setdefault("formatversion", "2")
        query = urllib.parse.urlencode(sorted(params.items()))
        path = None
        if self.cache:
            import hashlib
            path = self.cache / (hashlib.sha1(query.encode()).hexdigest() + ".json")
            if path.exists():
                self.cached += 1
                return json.loads(path.read_text(encoding="utf-8"))

        last = None
        for attempt in range(9):
            try:
                # Devanagari titles percent-encode to nine bytes a character,
                # so a 50-title batch overruns the URI limit and comes back 414.
                # Read requests may be POSTed; the API treats them identically.
                if post:
                    req = urllib.request.Request(
                        API, data=query.encode("utf-8"),
                        headers={"User-Agent": UA,
                                 "Content-Type": "application/x-www-form-urlencoded"})
                else:
                    req = urllib.request.Request(API + "?" + query,
                                                 headers={"User-Agent": UA})
                body = urllib.request.urlopen(req, timeout=120).read()
                data = json.loads(body.decode("utf-8"))
                self.fetched += 1
                if path:
                    path.write_text(json.dumps(data, ensure_ascii=False),
                                    encoding="utf-8")
                time.sleep(self.delay)
                return data
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                last = exc
                code = getattr(exc, "code", None)
                if code is not None and code not in (429, 500, 502, 503, 504):
                    raise
                wait = min(60, 2 ** attempt)
                print(f"   .. {code or exc}; retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError(f"giving up on {query}: {last}")


_TITLE_RE = re.compile(r"सूक्तं\s*([०-९0-9]+)\s*[.।]\s*([०-९0-9]+)")


def parse_title(title: str) -> tuple[int, int] | None:
    """``ऋग्वेदः सूक्तं १.१७२`` -> ``(1, 172)``.

    The heading is not spelled consistently across the wiki -- ``ऋग्वेदः`` and
    ``ऋग्वेद:`` (visarga vs. colon) both occur, and spacing around the dot
    varies -- so the maṇḍala and sūkta numbers are read out of the title rather
    than the title being reconstructed and compared.
    """
    m = _TITLE_RE.search(title)
    if not m:
        return None
    mandala, sukta = to_int(m.group(1)), to_int(m.group(2))
    if mandala is None or sukta is None:
        return None
    if not (1 <= mandala <= 10 and 1 <= sukta <= SUKTA_COUNTS[mandala]):
        return None
    return mandala, sukta


_ASCII_TO_DEVA = str.maketrans("0123456789", "०१२३४५६७८९")

# Both spellings occur on the wiki -- visarga and colon -- and neither is
# consistently the redirect.
TITLE_FORMS = ("ऋग्वेदः सूक्तं {n}", "ऋग्वेद: सूक्तं {n}")


def sukta_titles(mandala: int, sukta: int) -> list[str]:
    n = f"{mandala}.{sukta}".translate(_ASCII_TO_DEVA)
    return [f.format(n=n) for f in TITLE_FORMS]


def find_suktas(wiki: Wiki, limit: int | None = None,
                probe_missing: bool = True) -> dict[tuple[int, int], str]:
    """Every sūkta page that carries the bhāṣya template, keyed by (maṇḍala, sūkta).

    Search alone under-reports. ``insource:`` answers from the search index,
    which lags the wiki: it returns 990 sūktas, but probing the 38 it omits by
    title finds the template on 29 of them. So the search is used to find pages
    cheaply and a direct title probe fills the gap -- 1,019 of 1,028 (99.1%).

    The nine that genuinely lack it are RV 8.49-8.55, 8.57 and 8.59: the
    Vālakhilya, the appendix to maṇḍala 8 that much of the manuscript tradition
    transmits separately from Sāyaṇa's commentary. That is a property of the
    text, not a gap in the wiki, and no amount of retrying will close it.
    """
    found: dict[tuple[int, int], str] = {}
    offset = 0
    while True:
        res = wiki.get(action="query", list="search", srsearch=SEARCH,
                       srlimit="50", sroffset=str(offset), srnamespace="0")
        hits = res.get("query", {}).get("search", [])
        for hit in hits:
            key = parse_title(hit["title"])
            if key and key not in found:
                found[key] = hit["title"]
        if limit and len(found) >= limit:
            return found
        cont = res.get("continue", {}).get("sroffset")
        if cont is None or not hits:
            break
        offset = cont

    if not probe_missing:
        return found

    gaps = [(m, s) for m in range(1, 11)
            for s in range(1, SUKTA_COUNTS[m] + 1) if (m, s) not in found]
    if not gaps:
        return found
    candidates = [(m, s, t) for (m, s) in gaps for t in sukta_titles(m, s)]
    texts = fetch_wikitext(wiki, [t for _m, _s, t in candidates])
    for m, s, title in candidates:
        if (m, s) in found:
            continue
        wt = texts.get(title)
        if wt and find_template(wt) is not None:
            found[(m, s)] = title
    return found


def fetch_wikitext(wiki: Wiki, titles: list[str]) -> dict[str, str]:
    """Wikitext for up to 50 titles per request."""
    out: dict[str, str] = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        res = wiki.get(post=True, action="query", prop="revisions",
                       rvprop="content", rvslots="main", titles="|".join(batch))
        for page in res.get("query", {}).get("pages", []):
            if page.get("missing"):
                continue
            revs = page.get("revisions") or []
            if not revs:
                continue
            content = revs[0].get("slots", {}).get("main", {}).get("content")
            if content:
                out[page["title"]] = content
    return out


# -------------------------------------------------------------- wikitext parse

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_REF = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", re.S | re.I)
_FILE = re.compile(r"\[\[\s*(?:File|Image|चित्रम्)\s*:[^\[\]]*(?:\[\[[^\[\]]*\]\][^\[\]]*)*\]\]",
                   re.I)
_TAG = re.compile(r"</?(?:poem|span|div|center|small|big|br|p|blockquote)[^>]*>", re.I)
_LINK_PIPED = re.compile(r"\[\[[^\[\]|]*\|([^\[\]|]*)\]\]")
_LINK_PLAIN = re.compile(r"\[\[([^\[\]|]*)\]\]")
_BOLDITALIC = re.compile(r"'{2,5}")


def find_template(wikitext: str, name: str = TEMPLATE) -> str | None:
    """The first argument of ``{{name|…}}``, brace-matched.

    A regex cannot do this: the bhāṣya quotes other templates and its prose is
    full of braces-adjacent punctuation, so the closing ``}}`` has to be found
    by counting depth rather than by matching the first one that appears.
    """
    open_at = wikitext.find("{{" + name)
    if open_at < 0:
        return None
    i = wikitext.find("|", open_at)
    if i < 0:
        return None
    body_start = i + 1
    depth = 1
    i = body_start
    while i < len(wikitext) - 1:
        two = wikitext[i:i + 2]
        if two == "{{":
            depth += 1
            i += 2
            continue
        if two == "}}":
            depth -= 1
            if depth == 0:
                return wikitext[body_start:i]
            i += 2
            continue
        i += 1
    # Unclosed template -- take the rest of the page rather than nothing, since
    # a missing final }} costs the tail of one sūkta, not the sūkta.
    return wikitext[body_start:]


def clean_wikitext(s: str) -> str:
    """Strip markup, keeping the text a reader would see.

    Order matters: comments and <ref> first (they can contain anything),
    file links before ordinary links (their captions nest links), and the
    tag strip last so that <poem> line breaks survive as newlines.
    """
    s = _COMMENT.sub(" ", s)
    s = _REF.sub(" ", s)
    for _ in range(3):                      # captions nest one or two deep
        new = _FILE.sub(" ", s)
        if new == s:
            break
        s = new
    s = _LINK_PIPED.sub(r"\1", s)
    s = _LINK_PLAIN.sub(r"\1", s)
    s = _TAG.sub(" ", s)
    s = _BOLDITALIC.sub("", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# The wiki prints the verse number as ``॥२`` far more often than ``॥२॥`` -- the
# closing danda is frequently dropped -- so the trailing one is optional.
_WS_MARKER = re.compile(r"॥\s*([०-९0-9]{1,3})\s*॥?")


def markers(body: str) -> list[tuple[int, int, int]]:
    """``(number, start, end)`` for every ॥N in the template body."""
    out = []
    for m in _WS_MARKER.finditer(body):
        num = to_int(m.group(1))
        if num is not None:
            out.append((num, m.start(), m.end()))
    return out


def fold_with_map(s: str) -> tuple[str, list[int]]:
    """``skeleton(s)``, plus the original index each surviving character came from.

    ``skeleton`` is applied per character so that a position found in the folded
    string can be turned back into a position in the real text. That is what
    lets the cut between one mantra's gloss and the next mantra's printed
    saṃhitā-pāṭha be made exactly, instead of at the nearest blank line.
    """
    # Normalise first: NFC can compose across a base/nukta pair, which a
    # per-character fold would miss.
    s = unicodedata.normalize("NFC", s)
    folded, idx = [], []
    for i, ch in enumerate(s):
        f = skeleton(ch)
        if f:
            folded.append(f)
            idx.extend([i] * len(f))
    return "".join(folded), idx


# ------------------------------------------------------------------ alignment

class Cut:
    """One mantra's gloss, with everything needed to judge whether it is right."""

    __slots__ = ("mid", "rik", "text", "score", "numbered", "start", "end")

    def __init__(self, mid, rik, text, score, numbered, start, end):
        self.mid, self.rik, self.text = mid, rik, text
        self.score, self.numbered = score, numbered
        self.start, self.end = start, end

    def __repr__(self):
        return f"Cut({self.mid}, {self.score:.2f}, {self.text[:30]!r})"


# Heads tried in turn when locating a mantra. The long one is decisive; the
# short ones exist because a few pages spell a sandhi differently from DGE's
# edition in the first akṣaras, and losing a mantra to that would be silly.
_HEADS = (20, 14, 10)


def _locate(folded: str, key: str, lo: int, hi: int) -> tuple[float, int, int]:
    """Best occurrence of ``key`` in ``folded[lo:hi]`` -> (score, start, end)."""
    best = (0.0, -1, -1)
    for hlen in _HEADS:
        if len(key) < hlen:
            continue
        head = key[:hlen]
        # The slack absorbs a spelling the wiki writes slightly longer than
        # DGE's edition. It has to scale with the key: a flat 30 characters is
        # a tenth of a long triṣṭubh but three quarters of a short gāyatrī
        # pāda, which dragged maṇḍala 9's scores down for no real reason.
        slack = max(8, len(key) // 6)
        i = folded.find(head, lo, hi)
        while i >= 0:
            sc = max(similarity(key, folded[i:i + len(key)]),
                     similarity(key, folded[i:i + len(key) + slack]))
            if sc > best[0]:
                best = (sc, i, i + len(key))
            i = folded.find(head, i + 1, hi)
        if best[1] >= 0:
            break
    return best


def _fold_pos(fmap: list[int], orig: int) -> int:
    """First folded index at or after original index ``orig``."""
    lo, hi = 0, len(fmap)
    while lo < hi:
        mid = (lo + hi) // 2
        if fmap[mid] < orig:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _orig_pos(fmap: list[int], folded_i: int, default: int) -> int:
    if 0 <= folded_i < len(fmap):
        return fmap[folded_i]
    return default


class Placement:
    __slots__ = ("rik", "score", "block_start", "block_end", "numbered")

    def __init__(self, rik, score, block_start, block_end, numbered):
        self.rik, self.score = rik, score
        self.block_start, self.block_end = block_start, block_end
        self.numbered = numbered


def place_mantras(folded: str, fmap: list[int], marks, keyed) -> dict[int, Placement]:
    """Find each mantra's *printed* text inside the template body.

    The anchor is the mantra itself -- the saṃhitā- and pada-pāṭha DGE already
    holds -- not the verse number. That ordering is deliberate. The number is a
    weaker witness than it looks: pages drop it (RV 10.90 prints only 12 of its
    16), repeat it for quoted verses, and carry sūkta and anuvāka numbers in the
    same form. The mantra's own text cannot be any of those things, so a block
    that matches it is that mantra's block. Where a marker with the right number
    does sit between the printed text and the gloss it is recorded on the cut as
    ``numbered``, and the verifier reports how often that second witness agreed.

    The edition prints up to three forms per mantra -- accented saṃhitā-pāṭha,
    accented pada-pāṭha, plain pada-pāṭha -- and accents fold away, so the pada
    key matches two of them. All of them belong to the printed block, and the
    gloss begins after the last.
    """
    placed: dict[int, Placement] = {}
    cursor = 0
    for _it, rik, keys in keyed:
        hits = []
        for key in keys:
            sc, a, b = _locate(folded, key, cursor, len(folded))
            if a >= 0:
                hits.append((sc, a, b))
        if not hits:
            continue
        score = max(h[0] for h in hits)
        # The printed block opens with the *accented saṃhitā-pāṭha* and closes
        # with the plain pada-pāṭha, so its start is the EARLIEST of the strong
        # matches and its end the latest -- not the position of whichever key
        # happened to score highest. Taking the best-scoring match instead
        # leaves the saṃhitā-pāṭha stranded at the tail of the previous
        # mantra's gloss, which reads exactly like a one-late cut.
        strong = [h for h in hits if h[0] >= max(0.7, score - 0.12)]
        if not strong:
            # Nothing matched well enough to bound a block. Keep the best hit
            # anyway so the caller's threshold rejects it explicitly, rather
            # than dropping it here where the miss would go unreported.
            strong = [max(hits, key=lambda h: h[0])]
        start = min(h[1] for h in strong)
        end = max(h[2] for h in strong)
        # Pull in the repeats of the same mantra that follow immediately: the
        # accented and plain pada-pāṭha are the same text once accents fold.
        span = max(len(k) for k in keys) if keys else 0
        for key in keys:
            probe = end
            for _ in range(3):
                sc2, a2, b2 = _locate(folded, key, probe, min(len(folded), probe + span + 240))
                if a2 < 0 or sc2 < 0.75:
                    break
                end = max(end, b2)
                probe = b2
        placed[rik] = Placement(rik, score, start, end, False)
        cursor = end

    # Second witness: a marker carrying this mantra's number, sitting between
    # the printed text and the gloss.
    for rik, p in placed.items():
        o_start = _orig_pos(fmap, p.block_start, 0)
        o_end = _orig_pos(fmap, p.block_end, len(fmap))
        p.numbered = any(num == rik and o_start <= ms <= o_end + 12
                         for num, ms, _me in marks)
    return placed


def split_sukta(body: str, items: list[dict], *,
                threshold: float = 0.75) -> tuple[list[Cut], str, list[str]]:
    """Cut one sūkta's template body into per-mantra glosses.

    Returns the cuts, the sūkta-level preamble that precedes the first mantra
    (Sāyaṇa's viniyoga/ṛṣi/chandas note, which glosses no single mantra), and
    the ids that could not be placed.

    A gloss runs from the end of its own mantra's printed text to the start of
    the next mantra's printed text. Both ends are therefore anchored on text
    DGE already holds, which is what makes a wrong cut impossible to mistake
    for a right one: the mantra quoted above the commentary either is the
    mantra we asked for or it is not.
    """
    folded, fmap = fold_with_map(body)
    marks = markers(body)

    keyed = []
    for it in items:
        rik = to_int((it.get("id") or "").split(".")[-1])
        if rik is None:
            continue
        sam = skeleton(it.get("samhita_patha_plain") or it.get("samhita_patha") or "")
        pad = skeleton(it.get("pada_patha_plain") or it.get("pada_patha") or "")
        keyed.append((it, rik, [k for k in (sam, pad) if k]))

    placed = place_mantras(folded, fmap, marks, keyed)
    order = sorted(placed.values(), key=lambda p: p.block_start)

    cuts: list[Cut] = []
    misses: list[str] = []
    for it, rik, _keys in keyed:
        mid = it.get("id", "")
        p = placed.get(rik)
        if p is None or p.score < threshold:
            misses.append(mid)
            continue
        start = _orig_pos(fmap, p.block_end, len(body))
        nxt = next((q for q in order if q.block_start > p.block_end), None)
        end = _orig_pos(fmap, nxt.block_start, len(body)) if nxt else len(body)
        text = clean_span(body[start:end], rik, it)
        if not text or is_mantra_fragment(text, it):
            misses.append(mid)
            continue
        cuts.append(Cut(mid, rik, text, p.score, p.numbered, start, end))

    preamble = ""
    if order:
        preamble = clean_span(body[:_orig_pos(fmap, order[0].block_start, 0)])
    return cuts, preamble, misses


# The gloss begins after the printed mantra, so it opens on that mantra's
# closing danda and verse number. Strip those, plus any leading separator.
_LEAD = re.compile(r"^[\s।॥|॰०-९.,;:–—-]+")
# The printed mantra's last akṣara can be split across the cut, leaving a bare
# vowel sign, anusvāra, visarga or virāma at the head of the gloss. No Sanskrit
# word begins with any of them, so a leading run of them is always debris.
_LEAD_MARKS = re.compile(r"^[ऀ-ःऺ-ॏ॑-ॗॢॣ]+")
# It ends just before the next mantra's printed text, so it can pick up the
# varga/anuvāka tally the edition prints between the two (``॥ ॥ २२ ॥``).
_TRAIL = re.compile(r"(?:[\s।॥|]*॥\s*[०-९0-9]{1,3}\s*॥?)+[\s।॥|]*$")


def _is_mantra_tail(prefix: str, item: dict | None) -> bool:
    """Is this head fragment the end of the printed mantra rather than prose?

    Required before the head-marker trim fires. Without it the trim also cuts
    genuine commentary that happens to quote a numbered verse in its first
    line, which cost 22 mantras when the rule ran on the marker alone.
    """
    folded = skeleton(prefix)
    if not folded:
        return True
    if item is None:
        # No mantra to compare against is not evidence that this is one. Left
        # permissive, the trim swallowed a whole gloss whose closing tally sat
        # inside the head window.
        return False
    if len(folded) < 4:
        return True
    hay = skeleton(item.get("samhita_patha_plain") or item.get("samhita_patha") or "") \
        + skeleton(item.get("pada_patha_plain") or item.get("pada_patha") or "")
    if not hay:
        return False
    match = SequenceMatcher(None, folded, hay).find_longest_match(
        0, len(folded), 0, len(hay))
    return match.size >= max(4, 0.5 * len(folded))


def clean_span(s: str, rik: int | None = None, item: dict | None = None,
               head: int = 240) -> str:
    """Trim a cut down to the commentary itself.

    The printed mantra block always terminates in ``॥N``. So when that marker
    turns up near the *head* of a gloss, the cut opened inside the printed text
    rather than after it, and everything up to the marker is the tail of the
    mantra -- RV 9.113.7 opened with ``स्रव ॥७॥``, the last word of the refrain
    every Soma Pavamāna hymn repeats. Cutting there is safe in a way that
    trimming whatever resembles the mantra is not: Sāyaṇa opens most of his
    glosses by quoting the mantra's own words, so resemblance alone would eat
    the commentary's first line.
    """
    for _ in range(4):
        before = s
        s = _LEAD.sub("", s)
        s = _LEAD_MARKS.sub("", s)
        if s == before:
            break
    m = _WS_MARKER.search(s[:head])
    if (m and (rik is None or to_int(m.group(1)) == rik)
            and _is_mantra_tail(s[:m.start()], item)):
        s = s[m.end():]
        for _ in range(4):
            before = s
            s = _LEAD.sub("", s)
            s = _LEAD_MARKS.sub("", s)
            if s == before:
                break
    s = re.sub(r"\s+", " ", s)
    s = _TRAIL.sub("", s)
    return s.strip()


def is_mantra_fragment(text: str, item: dict) -> bool:
    """Is this 'gloss' just leftover printed mantra?

    Where the cut lands inside the printed text rather than after it, what
    reaches the reader is a scrap of the verse labelled as commentary. Short
    genuine glosses exist and must survive -- Sāyaṇa disposes of a repeated
    refrain with ``पूर्वं व्याख्याता``, "explained earlier" -- so length alone
    cannot decide it. Whether the text appears *inside the mantra* can.
    """
    folded = skeleton(text)
    if not folded:
        return True
    if len(folded) >= 60:
        return False
    # The cut can fall mid-word, so the scrap ends in a virāma the running text
    # does not have (``सोमं पिबतम्`` against ``…सोमं पिबतमश्विना``). Dropping
    # the virāma on both sides makes the containment test see through that.
    probe = folded.replace("्", "")
    for key in ("samhita_patha_plain", "samhita_patha",
                "pada_patha_plain", "pada_patha"):
        hay = skeleton(item.get(key) or "")
        if hay and probe and probe in hay.replace("्", ""):
            return True
    return len(folded) < 8


# --------------------------------------------------------------- verification

def mantra_words(item: dict, min_len: int = 4) -> list[str]:
    """The mantra's own content words, folded, long enough to be distinctive.

    Taken from the pada-pāṭha because it is already word-separated; the
    saṃhitā-pāṭha's sandhi would fuse exactly the boundaries this needs.
    """
    pada = item.get("pada_patha_plain") or item.get("pada_patha") or ""
    out = []
    for raw in re.split(r"[।॥|\s]+", pada):
        w = skeleton(raw)
        if len(w) >= min_len:
            out.append(w)
    return out


def head_window(words: list[str], per_word: int = 55, floor: int = 400) -> int:
    """How much of a gloss to read when asking which mantra it quotes.

    Fixed at 400 characters this test called a long triṣṭubh's commentary
    inconclusive: Sāyaṇa glosses word by word, so a 20-word mantra is only a
    quarter quoted by the time 400 characters are up, while a 9-word gāyatrī is
    fully quoted. Scaling the window with the mantra keeps the measure
    comparable across metres instead of penalising the long ones.
    """
    return max(floor, per_word * len(words))


def opening_overlap(gloss: str, words: list[str], head_chars: int = 400) -> float:
    """Fraction of a mantra's words that appear in the gloss's opening.

    Not a prefix test. Sāyaṇa quotes the mantra's words as he glosses them, but
    in his own order -- RV 1.1.9's comment opens ``हे “अग्ने “सः त्वं “नः``
    against a pada-pāṭha beginning ``सः । नः । पिताऽइव`` -- so asking whether
    the gloss *starts with* the mantra's first words answers "no" for correct
    pairings. Asking how much of the mantra's vocabulary the opening quotes
    separates a right cut from a wrong one cleanly.
    """
    if not words or not gloss:
        return 0.0
    head = skeleton(gloss[:head_chars])
    if not head:
        return 0.0
    return sum(1 for w in words if w in head) / len(words)


def check_offbyone(cuts: list[Cut], items: list[dict], *,
                   floor: float = 0.30) -> dict:
    """Does each gloss quote its own mantra, or the next one?

    This is the check a coverage figure and a similarity median cannot do. A
    systematic one-step slip leaves every score untouched -- each mantra still
    sits above *some* commentary -- but it shows up immediately here, because
    the commentary then quotes the following mantra's vocabulary instead of its
    own. ``late`` is the count that does; anything above a fraction of a percent
    means the cut is wrong, and the guard in ``main`` refuses to write on it.
    """
    by_id = {it.get("id"): it for it in items}
    words = {mid: mantra_words(it) for mid, it in by_id.items()}
    order = sorted(by_id, key=lambda i: [int(p) for p in i.split(".")])
    nxt_of = {order[i]: order[i + 1] for i in range(len(order) - 1)}

    own = late = weak = 0
    late_ids: list[str] = []
    weak_ids: list[str] = []
    for c in cuts:
        if c.mid not in by_id:
            continue
        mine = words.get(c.mid, [])
        # One window for both comparisons, sized by this mantra, so that "does
        # it quote me or the next one" is a fair question.
        win = head_window(mine)
        own_r = opening_overlap(c.text, mine, win)
        nid = nxt_of.get(c.mid)
        next_r = opening_overlap(c.text, words.get(nid, []), win) if nid else 0.0
        if own_r >= floor and own_r >= next_r:
            own += 1
        elif next_r > own_r and next_r >= floor:
            late += 1
            late_ids.append(c.mid)
        else:
            weak += 1
            weak_ids.append(c.mid)
    return {"own": own, "late": late, "weak": weak,
            "late_ids": late_ids, "weak_ids": weak_ids[:40]}


# ------------------------------------------------------------------ the import

def import_mandala(wiki: Wiki, dge: Path, mandala: int, suktas: dict, *,
                   threshold: float, dry_run: bool, overwrite: bool,
                   sukta_intro: bool):
    path = dge / SAMHITA.format(m=mandala)
    raw = path.read_text(encoding="utf-8")
    raw_indent = sniff_indent(raw)
    data = json.loads(raw)
    items = data.get("items", [])
    by_sukta: dict[int, list[dict]] = {}
    for it in items:
        parts = (it.get("id") or "").split(".")
        if len(parts) >= 2:
            s = to_int(parts[1])
            if s is not None:
                by_sukta.setdefault(s, []).append(it)

    wanted = {s: t for (m, s), t in suktas.items() if m == mandala}
    texts = fetch_wikitext(wiki, [wanted[s] for s in sorted(wanted)])

    all_cuts: list[Cut] = []
    intros: dict[int, str] = {}
    stat = {"suktas_on_wiki": len(wanted), "suktas_parsed": 0, "no_template": [],
            "mantras": len(items), "misses": []}

    for s in sorted(wanted):
        wt = texts.get(wanted[s])
        if not wt:
            stat["no_template"].append(f"{mandala}.{s} (no wikitext)")
            continue
        tpl = find_template(wt)
        if tpl is None:
            stat["no_template"].append(f"{mandala}.{s} (no template)")
            continue
        cuts, preamble, misses = split_sukta(clean_wikitext(tpl),
                                             by_sukta.get(s, []),
                                             threshold=threshold)
        stat["suktas_parsed"] += 1
        stat["misses"] += misses
        all_cuts += cuts
        if preamble:
            intros[s] = preamble

    # A cut that quotes the FOLLOWING mantra more than its own is wrong,
    # whatever it scored. Refuse it here rather than only counting it: the
    # commonest cause is real and structural -- the dvipadā sūktas (RV 1.65-70)
    # are printed as pairs of half-verses under one combined gloss, which DGE
    # splits into two mantras, so the first of each pair has no gloss of its
    # own to be given. Dropping is the honest outcome; the pair's commentary
    # still reaches the reader on the second mantra.
    ob_all = check_offbyone(all_cuts, items)
    refused = set(ob_all["late_ids"])
    stat["refused_offbyone"] = sorted(refused)
    if refused:
        stat["misses"] += sorted(refused)
        all_cuts = [c for c in all_cuts if c.mid not in refused]

    stat["missing_suktas"] = sorted(
        s for s in range(1, SUKTA_COUNTS[mandala] + 1) if s not in wanted)
    stat["aligned"] = len(all_cuts)
    stat["numbered"] = sum(1 for c in all_cuts if c.numbered)
    stat["offbyone"] = check_offbyone(all_cuts, items)
    scores = sorted(c.score for c in all_cuts)
    stat["median_score"] = round(scores[len(scores) // 2], 3) if scores else 0.0
    stat["min_score"] = round(scores[0], 3) if scores else 0.0

    if dry_run:
        stat["written"] = 0
        return stat, all_cuts

    by_id = {it["id"]: it for it in items}
    written = 0
    for c in all_cuts:
        it = by_id.get(c.mid)
        if it is None:
            continue
        comm = it.setdefault("commentaries", {})
        if comm.get("sayana") and not overwrite:
            continue
        comm["sayana"] = c.text
        written += 1
    if sukta_intro:
        for s, text in intros.items():
            group = by_sukta.get(s) or []
            if not group:
                continue
            first = min(group, key=lambda i: to_int(i["id"].split(".")[-1]) or 0)
            comm = first.setdefault("commentaries", {})
            if comm.get("sayana_sukta") and not overwrite:
                continue
            comm["sayana_sukta"] = text
    if written:
        data.setdefault("commentary_sources", {}).update(ATTRIBUTION)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=raw_indent) + "\n",
                        encoding="utf-8")
    stat["written"] = written
    return stat, all_cuts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dge-root", required=True)
    ap.add_argument("--mandala", type=int, action="append",
                    help="restrict to these maṇḍalas (repeatable; default all ten)")
    ap.add_argument("--cache-dir", default=".wscache")
    ap.add_argument("--threshold", type=float, default=0.75,
                    help="minimum match against DGE's own mantra to accept a cut")
    ap.add_argument("--min-coverage", type=float, default=0.85,
                    help="abort without writing if a maṇḍala aligns below this")
    ap.add_argument("--max-late", type=float, default=0.01,
                    help="abort if more than this fraction of glosses quote the "
                         "NEXT mantra rather than their own (an off-by-one)")
    ap.add_argument("--no-sukta-intro", action="store_true",
                    help="drop Sāyaṇa's per-sūkta introduction instead of "
                         "storing it as commentaries.sayana_sukta")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--report", help="write the full per-mantra report here as JSON")
    args = ap.parse_args(argv)

    dge = Path(args.dge_root)
    if not (dge / "data" / "schemas.json").exists():
        print(f"!! {dge} does not look like the dge/ directory", file=sys.stderr)
        return 2

    wiki = Wiki(cache_dir=args.cache_dir)
    print("Enumerating sūkta pages that carry the bhāṣya template ...")
    suktas = find_suktas(wiki)
    total_suktas = sum(SUKTA_COUNTS.values())
    print(f"  {len(suktas)} sūkta pages of {total_suktas} "
          f"({100*len(suktas)/total_suktas:.1f}%)")

    mandalas = sorted(set(args.mandala)) if args.mandala else list(range(1, 11))
    grand = {"mantras": 0, "aligned": 0, "written": 0, "own": 0, "late": 0,
             "weak": 0, "numbered": 0}
    per: dict[str, dict] = {}
    report: dict[str, dict] = {}
    blocked: list[int] = []

    for m in mandalas:
        path = dge / SAMHITA.format(m=m)
        if not path.exists():
            print(f"!! no data.json at {path}; skipping maṇḍala {m}", file=sys.stderr)
            continue
        print(f"\n== Maṇḍala {m}")
        stat, cuts = import_mandala(
            wiki, dge, m, suktas, threshold=args.threshold, dry_run=True,
            overwrite=args.overwrite, sukta_intro=not args.no_sukta_intro)

        cov = stat["aligned"] / max(stat["mantras"], 1)
        ob = stat["offbyone"]
        late_rate = ob["late"] / max(stat["aligned"], 1)
        print(f"   sūktas on wiki {stat['suktas_on_wiki']}/{SUKTA_COUNTS[m]}, "
              f"parsed {stat['suktas_parsed']}")
        print(f"   aligned {stat['aligned']}/{stat['mantras']} ({100*cov:.1f}%), "
              f"median {stat['median_score']:.2f}, min {stat['min_score']:.2f}, "
              f"verse-number confirmed {stat['numbered']}")
        print(f"   quotes own mantra {ob['own']}, quotes NEXT mantra "
              f"{ob['late']} ({100*late_rate:.2f}%), inconclusive {ob['weak']}")
        if stat["refused_offbyone"]:
            print(f"   refused {len(stat['refused_offbyone'])} cuts that quoted "
                  f"the next mantra: {stat['refused_offbyone'][:8]}"
                  + (" ..." if len(stat["refused_offbyone"]) > 8 else ""))

        per[str(m)] = {k: v for k, v in stat.items()
                       if k not in ("offbyone", "refused_offbyone")}
        per[str(m)]["offbyone"] = {k: v for k, v in ob.items()
                                   if not k.endswith("_ids")}
        per[str(m)]["refused_offbyone"] = len(stat["refused_offbyone"])
        per[str(m)]["coverage"] = round(cov, 4)
        grand["mantras"] += stat["mantras"]
        grand["aligned"] += stat["aligned"]
        for k in ("own", "late", "weak"):
            grand[k] += ob[k]
        grand["numbered"] += stat["numbered"]
        if args.report:
            for c in cuts:
                report[c.mid] = {"score": round(c.score, 3), "numbered": c.numbered,
                                 "chars": len(c.text), "head": c.text[:220]}

        if cov < args.min_coverage:
            print(f"   !! coverage {100*cov:.1f}% below --min-coverage "
                  f"{100*args.min_coverage:.0f}%; not writing maṇḍala {m}",
                  file=sys.stderr)
            blocked.append(m)
            continue
        if late_rate > args.max_late:
            print(f"   !! {100*late_rate:.1f}% of glosses quote the next mantra "
                  f"rather than their own. That is an off-by-one, not a "
                  f"threshold to raise. Not writing maṇḍala {m}.", file=sys.stderr)
            print(f"      first offenders: {ob['late_ids'][:10]}", file=sys.stderr)
            blocked.append(m)
            continue
        if args.dry_run:
            continue

        stat2, _ = import_mandala(
            wiki, dge, m, suktas, threshold=args.threshold, dry_run=False,
            overwrite=args.overwrite, sukta_intro=not args.no_sukta_intro)
        print(f"   -> wrote {path} (+{stat2['written']})")
        grand["written"] += stat2["written"]

    if args.report:
        Path(args.report).write_text(
            json.dumps({"per_mandala": per, "totals": grand, "mantras": report},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nreport -> {args.report}")

    print("\n" + json.dumps({"per_mandala": per, "totals": grand,
                             "blocked": blocked}, ensure_ascii=False, indent=2))
    print(f"\nHTTP: {wiki.fetched} fetched, {wiki.cached} from cache")

    # A run that exits 0 having imported nothing is the failure mode worth
    # making loud -- the first wisdomlib run did exactly that, and its exit
    # code said nothing was wrong.
    if grand["mantras"] and grand["aligned"] == 0:
        print("!! aligned 0 mantras", file=sys.stderr)
        return 3
    if not args.dry_run and grand["aligned"] and grand["written"] == 0:
        print("!! aligned mantras but wrote none", file=sys.stderr)
        return 3
    if blocked:
        print(f"!! maṇḍalas not written: {blocked}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
