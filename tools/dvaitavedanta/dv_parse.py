"""HTML parsing for dvaitavedanta.in.

Kept separate from the crawler so it can be unit-tested against fixtures without
network access (the Cowork sandbox has no egress to the site; see README).

The site is Laravel, fully server-rendered. Every leaf page carries:
  * a breadcrumb chain  Home / category / grantha / adhyaya / pada / adhikarana / sutra
  * the grantha's ENTIRE nested sidebar as real <a href> elements
  * N stacked commentary layers, each a Devanagari heading + body, anchored #article<id>

Container (non-leaf) nodes return HTTP 200 with the body text "No record found!!".
Nonexistent ids return HTTP 500.

Selector strategy is deliberately defensive: we anchor on `id="article<N>"` when
present and fall back to a Devanagari-density heuristic otherwise, so a markup
change on the site degrades rather than silently emitting garbage.
"""

from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict

from bs4 import BeautifulSoup, NavigableString, Tag

BASE = "https://dvaitavedanta.in"

CATEGORY_DETAILS_RE = re.compile(r"/category-details/(\d+)(?:/(\d+))?")
# Tolerant on purpose: the site emits #article<id>, but a suffixed variant
# (article123b) must not silently drop a commentary layer.
ARTICLE_ID_RE = re.compile(r"^article[-_]?(\d+)[a-z0-9_-]*$", re.I)
NO_RECORD_RE = re.compile(r"no\s+record\s+found", re.I)

# Blocks stripped wholesale before any text extraction. `common.py` in this repo
# documents why a naive tag regex is not enough: leftover CSS text got
# transliterated character-by-character into narada_smriti's first "verse".
DROP_TAGS = ("script", "style", "noscript", "svg", "iframe", "form", "button")
CHROME_TAGS = ("nav", "header", "footer", "aside")
CHROME_CLASS_RE = re.compile(
    r"(sidebar|side-bar|side_menu|sidemenu|navbar|nav-|menu|breadcrumb|footer|header|"
    r"topbar|top-bar|offcanvas|drawer|pagination|social|copyright)",
    re.I,
)
BREADCRUMB_CLASS_RE = re.compile(r"breadcrumb", re.I)
HOME_LABELS = ("home", "मुख्यपृष्ठम्", "मुखपृष्ठ", "गृहम्")

# Confirmed against saved probe pages (run 31933375009, 5 leaves across two
# granthas): inside #article<N> the mula verse sits in <h2 class="shloka"> and
# every commentary lives in a flat #dynamicContent/.details block delimited by
# <h3>. Before this was known, the whole block parsed as ONE layer whose "name"
# was the mula verse text.
SHLOKA_CLASS_RE = re.compile(r"\bshloka\b", re.I)
DETAILS_ID = "dynamicContent"
DETAILS_CLASS_RE = re.compile(r"\bdetails\b", re.I)
MULA_TITLE = "मूलम्"
# The site marks a pāda/sarga/adhyāya section-boundary heading with the same
# <h2 class="shloka"> markup it uses for a real verse (probe run on Nyāya
# Sudhā's "प्रथमः पादः" and Sumadhva Vijaya's 16 sarga headings, all 16 of
# which the naive parse turned into fake single-word "verses" with real
# commentary sitting right alongside, under the same article id, unaffected —
# see _layers_from_article). A genuine verse is never just "<ordinal>
# <structural noun>" with no daṇḍa; this is a closed, short vocabulary, not a
# heuristic on length or punctuation (short real pratīkas exist and must not
# be dropped).
_ORDINAL_WORDS = (
    "प्रथम", "द्वितीय", "तृतीय", "चतुर्थ", "पञ्चम", "षष्ठ", "सप्तम", "अष्टम", "नवम", "दशम",
    "एकादश", "द्वादश", "त्रयोदश", "चतुर्दश", "पञ्चदश", "षोडश", "सप्तदश", "अष्टादश",
    "एकोनविंश", "विंश",
)
_STRUCTURAL_NOUNS = ("पाद", "अध्याय", "अधिकरण", "खण्ड", "प्रकरण", "काण्ड", "सर्ग", "अंश", "अष्टक", "परिच्छेद")
# The ordinal+noun sandhi (द्वितीयः + अध्यायः -> द्वितीयोऽध्यायः) elides the
# noun's own leading अ, so the surface form never contains "अध्याय" as a
# substring, only "ध्याय" -- match both the bare and अ-elided noun stem.
_STRUCTURAL_NOUN_ALTS = sorted(
    {n for n in _STRUCTURAL_NOUNS} | {n[1:] for n in _STRUCTURAL_NOUNS if n.startswith("अ")},
    key=len, reverse=True,
)
STRUCTURAL_HEADING_RE = re.compile(
    r"^(?:" + "|".join(_ORDINAL_WORDS) + r")[ःोऽ]{0,3}\s*(?:" + "|".join(_STRUCTURAL_NOUN_ALTS) + r")[ःम्]{0,2}$"
)


def is_structural_heading(text: str) -> bool:
    """True for a bare section-boundary label ("प्रथमः पादः", "द्वितीयोऽध्यायः"),
    never for actual verse or commentary text."""
    return bool(STRUCTURAL_HEADING_RE.match((text or "").strip()))


# A short bold line directly before an <h3> attributes the commentary that
# follows ("श्रीराघवेन्द्रतीर्थयतिकृतः"). Topic labels sit in the same position
# but carry no attribution verb, so match the verb rather than the position.
# The negative lookahead keeps the verb from matching INSIDE an unrelated
# stem: "प्रकृत्यधिकरणम्" (the प्रकृति-adhikaraṇa heading) contains कृत
# followed by ्, and without the guard it parsed as author "प्र" + work —
# which bypassed the single_work mula-fold on Anuvyākhyāna and minted a
# fake tika_pra folder (found on the 25 Aug cache replay, node DV_14492).
# Genuine attributions inflect as कृतः/कृता/कृतम्/विरचिता…, never कृत्/कृति.
ATTRIBUTION_RE = re.compile(r"(कृत|विरचित|प्रणीत|प्रोक्त|विरचयाम्)(?![ि्ी])")
ATTRIBUTION_MAX_CHARS = 90
# The same commentary is headed both "श्री कथालक्षणटीकाभावदीपः" and
# "कथालक्षणटीकाभावदीपः" on one page; without this they merge as two layers.
# श्रीमन् is श्रीमत् undergoing the standard त्→न् sandhi before a following
# nasal (श्रीमत् + न्यायसुधा -> श्रीमन्न्यायसुधा) -- a real, expected form,
# not a typo, and it must be listed before the bare "श्री" alternative or
# that shorter match wins first and leaves a stray "मन्" stuck to the title.
HONORIFIC_RE = re.compile(r"^(श्रीमत्|श्रीमद्|श्रीमन्|श्री)\s*")

DEVANAGARI_RANGE = (0x0900, 0x097F)
BLOCK_TAGS = {
    "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "blockquote", "pre", "td", "th",
}


# --------------------------------------------------------------------------- #
# text helpers
# --------------------------------------------------------------------------- #

def devanagari_ratio(text: str) -> float:
    """Fraction of *letter* characters that are Devanagari.

    Used as an integrity gate: a value near 0 on a supposed verse means we
    scraped chrome, CSS or Latin boilerplate instead of the text.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    dev = sum(1 for c in letters if DEVANAGARI_RANGE[0] <= ord(c) <= DEVANAGARI_RANGE[1])
    return dev / len(letters)


def devanagari_count(text: str) -> int:
    return sum(1 for c in text if DEVANAGARI_RANGE[0] <= ord(c) <= DEVANAGARI_RANGE[1])


# Word and other rich-text editors bracket a pasted selection with
# <!--StartFragment--> / <!--EndFragment--> comments. Somewhere upstream of
# dvaitavedanta.in those markers lost their delimiters, so the bare words
# survive in the stored HTML and read as part of the text: 1,590 of Nyaya
# Sudha's 9,929 entries carry a stray "EndFragment". It is never Sanskrit
# and never the editor's words, so it goes before anything measures the text.
CLIPBOARD_CHROME = re.compile(r"<!--\s*(?:Start|End)Fragment\s*-->|\b(?:Start|End)Fragment\b")


def clean_text(value: str) -> str:
    """Normalise whitespace while preserving intentional line breaks."""
    if not value:
        return ""
    value = unicodedata.normalize("NFC", value)
    value = CLIPBOARD_CHROME.sub("", value)
    value = value.replace(" ", " ").replace("​", "")
    lines = [re.sub(r"[ \t\f\v]+", " ", ln).strip() for ln in value.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines).strip()


def block_text(node: Tag) -> str:
    """Extract text from a node, turning block-level boundaries into newlines."""
    if node is None:
        return ""
    chunks: list[str] = []

    def walk(el):
        if isinstance(el, NavigableString):
            chunks.append(str(el))
            return
        if not isinstance(el, Tag):
            return
        name = (el.name or "").lower()
        if name in DROP_TAGS:
            return
        if name == "br":
            chunks.append("\n")
            return
        for child in el.children:
            walk(child)
        if name in BLOCK_TAGS:
            chunks.append("\n")

    walk(node)
    return clean_text("".join(chunks))


# --------------------------------------------------------------------------- #
# soup preparation
# --------------------------------------------------------------------------- #

def make_soup(html: str) -> BeautifulSoup:
    # html.parser DELIBERATELY, not lxml: the whole DV corpus (and
    # test_load_more's fixtures) were extracted and validated against
    # html.parser's lenient handling of the site's malformed fragments.
    # With lxml installed the old try-lxml-first order silently changed
    # parse results (a load-more fragment lost its परिमळ layer heading).
    return BeautifulSoup(html, "html.parser")


def _is_chrome(tag: Tag) -> bool:
    if not isinstance(tag, Tag):
        return False
    if (tag.name or "").lower() in CHROME_TAGS:
        return True
    attrs = " ".join(
        list(tag.get("class") or []) + [tag.get("id") or ""] + [tag.get("role") or ""]
    )
    return bool(CHROME_CLASS_RE.search(attrs))


def strip_noise(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove scripts/styles. Chrome is *not* removed here — the sidebar is still
    needed for link discovery. Content extraction filters chrome separately."""
    for tag in soup.find_all(DROP_TAGS):
        tag.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, NavigableString) and "<!--" in str(s)):
        pass
    return soup


# --------------------------------------------------------------------------- #
# URL helpers
# --------------------------------------------------------------------------- #

def parse_content_url(href: str):
    """Return (content_id, ancestor_id) for a /category-details/ URL, else None."""
    if not href:
        return None
    match = CATEGORY_DETAILS_RE.search(href)
    if not match:
        return None
    content_id = int(match.group(1))
    ancestor_id = int(match.group(2)) if match.group(2) else None
    return content_id, ancestor_id


def canonical_url(content_id: int, ancestor_id=None) -> str:
    """Minimal URL that reliably resolves.

    Only `content_id` is load-bearing; the ancestor id is not validated and the
    slugs are cosmetic. The Laravel route requires at least three params, so a
    single dummy slug segment is mandatory (2-segment URLs 404).
    """
    ancestor = ancestor_id if ancestor_id is not None else content_id
    return f"{BASE}/category-details/{content_id}/{ancestor}/x"


# --------------------------------------------------------------------------- #
# page components
# --------------------------------------------------------------------------- #

def extract_breadcrumb(soup: BeautifulSoup) -> list[str]:
    """Ordered ancestor labels, Home excluded. This IS the hierarchy."""
    candidates = soup.find_all(
        lambda t: isinstance(t, Tag)
        and BREADCRUMB_CLASS_RE.search(
            " ".join(list(t.get("class") or []) + [t.get("id") or ""])
        )
    )
    # Fallback: the container holding a "Home" link plus category-details links.
    if not candidates:
        for anchor in soup.find_all("a"):
            label = clean_text(anchor.get_text(" ")).lower()
            if label in HOME_LABELS or label.rstrip(" /›>") in HOME_LABELS:
                parent = anchor.parent
                for _ in range(3):
                    if parent is None:
                        break
                    if len(parent.find_all("a")) >= 2:
                        candidates = [parent]
                        break
                    parent = parent.parent
                if candidates:
                    break

    for container in candidates:
        parts: list[str] = []
        for node in container.find_all(["li", "a", "span"], recursive=True):
            if node.find(["li", "a"], recursive=False):
                continue
            label = clean_text(node.get_text(" "))
            if not label or label.lower() in HOME_LABELS:
                continue
            if label in parts:
                continue
            parts.append(label)
        parts = [p for p in parts if p not in ("/", ">", "›", "»")]
        if parts:
            return parts
    return []


def extract_sidebar_links(soup: BeautifulSoup, exclude_ids=()) -> list[dict]:
    """Every /category-details/ link on the page, deduped by content id.

    One leaf page renders the grantha's whole tree, so this yields the complete
    sibling set in a single fetch — far cheaper and safer than id brute-force,
    which triggers HTTP 500s on the gaps.
    """
    seen: dict[int, dict] = {}
    breadcrumb_ids = set(exclude_ids)

    for container in soup.find_all(
        lambda t: isinstance(t, Tag)
        and BREADCRUMB_CLASS_RE.search(
            " ".join(list(t.get("class") or []) + [t.get("id") or ""])
        )
    ):
        for anchor in container.find_all("a", href=True):
            parsed = parse_content_url(anchor["href"])
            if parsed:
                breadcrumb_ids.add(parsed[0])

    for anchor in soup.find_all("a", href=True):
        parsed = parse_content_url(anchor["href"])
        if not parsed:
            continue
        content_id, ancestor_id = parsed
        if content_id in seen:
            continue
        seen[content_id] = {
            "content_id": content_id,
            "ancestor_id": ancestor_id,
            "href": anchor["href"],
            "label": clean_text(anchor.get_text(" ")),
            "in_breadcrumb": content_id in breadcrumb_ids,
        }
    return list(seen.values())


def _heading_for(node: Tag) -> str:
    """Find the Devanagari label for a commentary layer."""
    inner = node.find(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"])
    if inner:
        label = clean_text(inner.get_text(" "))
        if label and devanagari_count(label) > 0 and len(label) < 120:
            return label
    prev = node
    for _ in range(6):
        prev = prev.find_previous(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "legend"])
        if prev is None:
            break
        label = clean_text(prev.get_text(" "))
        if label and devanagari_count(label) > 0 and len(label) < 120:
            return label
    return ""


def _strip_heading(text: str, heading: str) -> str:
    if heading and text.startswith(heading):
        return text[len(heading):].lstrip(" \n:।")
    return text


def _content_root(soup: BeautifulSoup) -> Tag | None:
    """Pick the main content container by Devanagari density minus link density.

    The sidebar contains a lot of Devanagari too, but almost all of it sits
    inside <a> tags — subtracting anchor text separates the two reliably.
    """
    body = soup.body or soup
    best, best_score = None, 0
    for tag in body.find_all(["main", "article", "section", "div", "td"]):
        if _is_chrome(tag):
            continue
        if tag.find(["main", "article"]):
            continue
        text = tag.get_text(" ")
        anchor_text = " ".join(a.get_text(" ") for a in tag.find_all("a"))
        score = devanagari_count(text) - devanagari_count(anchor_text)
        if score > best_score:
            best, best_score = tag, score
    return best if best_score >= 20 else None


def _text_between(start: Tag, stop: Tag | None, within: Tag) -> str:
    """Text from just after `start` up to `stop`, bounded by `within`.

    Walking `next_elements` rather than siblings keeps nested markup (the site
    wraps most body text in <span> inside <p>) without assuming a flat shape.
    """
    chunks: list[str] = []
    for node in start.next_elements:
        if stop is not None and node is stop:
            break
        if isinstance(node, Tag):
            if node.name == "br":
                chunks.append("\n")
            elif node.name in BLOCK_TAGS:
                chunks.append("\n")
            continue
        if not isinstance(node, NavigableString):
            continue
        parent = node.parent
        if parent is None or (parent.name or "").lower() in DROP_TAGS:
            continue
        # Stop at the end of the details block instead of running on into
        # page chrome for the final heading.
        if within is not None and within not in parent.parents and parent is not within:
            break
        chunks.append(str(node))
    return clean_text("".join(chunks))


def article_id_from(value: str) -> str:
    """`article13531` -> `13531`. Empty when the id is not an article anchor.

    A leaf page can stack several #article<N> blocks (one per sutra under a
    multi-sutra adhikarana). The page has ONE content id, so keying items on it
    made every block collide; the article id is what actually identifies the
    verse, and mula + its commentaries share one block, so cross-layer ids
    still line up.
    """
    match = ARTICLE_ID_RE.match(value or "")
    return match.group(1) if match else ""


"""The `.details` preamble — everything between the block's start and its
first <h3> — was originally dropped whenever <h3>s existed, and the no-<h3>
fallback captured nothing (it walked from the OUTSIDE h2.shloka and broke on
the first node not inside .details, i.e. immediately). Live-compared one leaf
per section against dvaitavedanta.in (25 Aug 2026, see
dge/MULTI_LAYER_READER_ARCHITECTURE.md §1): that preamble is where the site
puts the FULL mula verse (the h2.shloka is only the leaf's truncated pratīka)
and, on bhāṣya-granthas, Madhva's own bhāṣya under an inner <h1>/<h2> heading
— so gita_bhashya had nine ṭīkā folders and no bhāṣya, and rig_bhashya /
mahabharata_tatparya_nirnaya ingested only pratīkas.

The preamble scan below is deliberately CLOSED-VOCABULARY (the corpus's own
heading-as-layer bug is what happens when arbitrary headings mint layers):
only an <h1>/<h2> inside .details whose text has no daṇḍa and normalises to
मूलम्/मूल/उपनिषत्, to the grantha's own title, or to *भाष्यम् opens a bucket.
Everything else — verse lines the site also marks up as <h1>, topic labels,
attribution lines — is inert content of the current bucket."""
MULA_ALIAS_KEYS = {"मूलम्", "मूल", "उपनिषत्"}
BHASHYA_TITLE = "भाष्यम्"
_DANDA_RE = re.compile(r"[।॥]")
_LEADING_NUM_RE = re.compile(r"^\s*\d+\.\s*")
# "अथ प्रथमोऽध्यायः", "।। अथ प्रथमोऽध्यायः ।।" — the same closed structural
# vocabulary as STRUCTURAL_HEADING_RE, with the ceremonial wrappers the
# preamble adds around it.
_ATHA_WRAPPER_RE = re.compile(r"^[\s।॥]*(?:अथ\s+)?")


def _text_within(within: Tag, start_after: Tag | None, stop: Tag | None) -> str:
    """Text of `within`'s own content between two of its descendants.

    Unlike `_text_between` (which walks next_elements from a node OUTSIDE the
    block and bounds itself by parentage), this iterates `within.descendants`
    directly, so content that begins at the very start of the block is
    reachable. `start_after`'s own subtree is excluded — it is the boundary
    heading, not content.
    """
    chunks: list[str] = []
    started = start_after is None
    for nd in within.descendants:
        if stop is not None and nd is stop:
            break
        if not started:
            if nd is start_after:
                started = True
            continue
        if start_after is not None and start_after in nd.parents:
            continue
        if isinstance(nd, Tag):
            if nd.name == "br" or nd.name in BLOCK_TAGS:
                chunks.append("\n")
            continue
        if not isinstance(nd, NavigableString):
            continue
        parent = nd.parent
        if parent is None or (parent.name or "").lower() in DROP_TAGS:
            continue
        chunks.append(str(nd))
    return clean_text("".join(chunks))


def _preamble_bucket(heading: Tag, grantha_key: str) -> str | None:
    """'mula' / 'bhashya' when this h1/h2 opens a preamble bucket, else None."""
    text = clean_text(heading.get_text(" "))
    if not text or _DANDA_RE.search(text):
        return None  # a verse line the site marked up as a heading
    key = layer_key(text)
    if not key or len(key) > 40 or devanagari_count(key) < 2:
        return None
    if key in MULA_ALIAS_KEYS:
        return "mula"
    if grantha_key and key == grantha_key:
        # e.g. an <h1>न्यायामृतम्</h1> opening the work's own root text. A
        # *भाष्यम् grantha title falls through to the bhashya rule below on
        # purpose: there the block holds Madhva's bhāṣya, not the base text.
        if not key.endswith(BHASHYA_TITLE):
            return "mula"
    if key.endswith(BHASHYA_TITLE):
        return "bhashya"
    return None


def _squash_for_match(text: str) -> str:
    return re.sub(r"[\s।॥.ॐँऽ]+", "", text or "")


def _preamble_matches_pratika(candidate: str, pratika: str) -> bool:
    """True when the preamble text actually contains the leaf's own verse.

    The h2.shloka pratīka is the full verse's opening (often truncated with
    `..`), so the honest test for "this preamble IS the full mula text" is
    stem containment — gita_bhashya's invocation-only preambles fail it and
    keep their already-complete h2 verse untouched.
    """
    stem = _squash_for_match(pratika)[:24]
    return len(stem) >= 8 and stem in _squash_for_match(candidate)


def _strip_preamble_label_lines(text: str, grantha_key: str) -> str:
    """Drop pure label lines from a captured preamble bucket.

    Structural section markers (अथ प्रथमोऽध्यायः), restatements of the
    grantha's own title, and — in the first few lines only — bare attribution
    credits (…विरचितः). Verse and prose lines always survive: everything
    dropped here must have no daṇḍa and match a closed pattern.
    """
    kept: list[str] = []
    for index, line in enumerate(text.split("\n")):
        stripped = line.strip(" \t।॥:-")
        if not stripped:
            continue
        if is_structural_heading(_ATHA_WRAPPER_RE.sub("", stripped).strip(" ।॥")):
            continue
        key = layer_key(_LEADING_NUM_RE.sub("", stripped))
        if key and (key in MULA_ALIAS_KEYS or (grantha_key and key == grantha_key)):
            continue
        if (index < 3 and len(stripped) <= ATTRIBUTION_MAX_CHARS
                and not _DANDA_RE.search(stripped) and ATTRIBUTION_RE.search(stripped)):
            continue
        kept.append(line)
    return clean_text("\n".join(kept))


def _preamble_segments(details: Tag, first_h3: Tag | None, grantha_key: str) -> list[tuple]:
    """[(bucket, text, boundary_elem_or_None)] for the pre-<h3> region."""
    region_headings: list[Tag] = []
    for nd in details.descendants:
        if first_h3 is not None and nd is first_h3:
            break
        if isinstance(nd, Tag) and nd.name in ("h1", "h2"):
            region_headings.append(nd)

    boundaries = [(h, _preamble_bucket(h, grantha_key)) for h in region_headings]
    boundaries = [(h, b) for h, b in boundaries if b is not None]
    if not boundaries:
        # No recognised structure: the whole region is one block — the
        # rig_bhashya / mahabharata_tatparya_nirnaya shape, where the full
        # verse text just follows the (strong-tagged, not h1/h2) labels.
        whole = _text_within(details, None, first_h3)
        return [("mula", whole, None)] if whole else []
    segments = []
    for index, (elem, bucket) in enumerate(boundaries):
        stop = boundaries[index + 1][0] if index + 1 < len(boundaries) else first_h3
        segments.append((bucket, _text_within(details, elem, stop), elem))
    return segments


def _layers_from_article(node: Tag, grantha_label: str = "") -> list[dict]:
    """Split one #article<N> block into its real layers.

    Confirmed shape (probe run 31933375009, preamble shapes re-confirmed live
    25 Aug 2026):

        <div id="article13531">
          <h2 class="shloka">   the leaf's pratika (often truncated with ..)
          <div id="dynamicContent" class="details">
            <p><strong>topic or attribution</strong></p>
            [preamble: full mula verse under an h1/h2 मूल-alias heading,
             and/or Madhva's bhashya under an h1/h2 *भाष्यम् heading]
            <h3>  commentary name
            <p>   body ...
            <h3>  next commentary ...

    One leaf carries exactly one mula verse. A single commentary's body may be
    split across several <h3> passes over that verse (Kathalakshana runs three
    commentaries through five passes each), so same-named chunks are merged in
    document order instead of becoming separate layers.
    """
    details = node.find(id=DETAILS_ID) or node.find(class_=DETAILS_CLASS_RE)
    headings = details.find_all("h3") if details else []
    article_id = article_id_from(node.get("id", ""))

    layers: list[dict] = []
    shloka = node.find("h2", class_=SHLOKA_CLASS_RE)
    if shloka is not None:
        verse = clean_text(shloka.get_text(" "))
        if devanagari_count(verse) >= 4 and not is_structural_heading(verse):
            layers.append({
                "title": MULA_TITLE,
                "text": verse,
                "anchor": node.get("id", ""),
                "article_id": article_id,
                "author": "",
                "role": "mula",
            })

    # ---- the pre-<h3> preamble (see the module comment above MULA_ALIAS_KEYS)
    if details is not None:
        grantha_key = layer_key(_LEADING_NUM_RE.sub("", grantha_label or ""))
        mula_parts: list[str] = []
        bhashya_parts: list[str] = []
        bhashya_author = ""
        for bucket, text, elem in _preamble_segments(
                details, headings[0] if headings else None, grantha_key):
            text = _strip_preamble_label_lines(text, grantha_key)
            if devanagari_count(text) < 4:
                continue
            if bucket == "mula":
                mula_parts.append(text)
            else:
                bhashya_parts.append(text)
                if elem is not None and not bhashya_author:
                    bhashya_author = _attribution_before(elem)
        if mula_parts and layers and layers[0]["role"] == "mula":
            candidate = "\n".join(mula_parts)
            # Replace the pratika only when the preamble demonstrably IS the
            # full verse; an invocation-only preamble (gita_bhashya) is
            # dropped rather than glued onto a verse it does not contain.
            if _preamble_matches_pratika(candidate, layers[0]["text"]):
                layers[0]["text"] = candidate
        if bhashya_parts:
            layers.append({
                "title": BHASHYA_TITLE,
                "text": "\n".join(bhashya_parts),
                "anchor": node.get("id", ""),
                "article_id": article_id,
                "author": bhashya_author,
                "role": "tika",
            })

    if not headings:
        # A leaf can carry a verse with no commentary at all. Returning nothing
        # here drops it to the pre-probe path, which labels the single layer
        # with the verse itself — the original bug, on ~1 leaf per grantha.
        # (The old `_text_between(shloka, None, details)` body-recovery that
        # sat here never captured anything — it broke on its first step — and
        # is replaced by the preamble pass above, which reads the same region
        # correctly.)
        return layers

    merged: "OrderedDict[str, dict]" = OrderedDict()

    def _fold_into(key, title, text, heading):
        entry = merged.get(key)
        if entry is None:
            merged[key] = {
                "title": title,
                "text": text,
                "anchor": (heading.get("id", "") if heading is not None else "") or node.get("id", ""),
                "article_id": article_id,
                "author": _attribution_before(heading) if heading is not None else "",
                "role": "tika",
            }
        else:
            entry["text"] = f"{entry['text']}\n{text}"
            if heading is not None:
                entry["author"] = entry["author"] or _attribution_before(heading)

    grantha_key = layer_key(_LEADING_NUM_RE.sub("", grantha_label or ""))
    for index, heading in enumerate(headings):
        title = clean_text(heading.get_text(" ")).strip(" ।॥:-")
        if not title:
            continue
        stop = headings[index + 1] if index + 1 < len(headings) else None
        own_text, quotes = _split_quoted_base_text(heading, stop, details, grantha_key)
        if devanagari_count(own_text) >= 4:
            _fold_into(layer_key(title), title, own_text, heading)
        for qtitle, qtext in quotes:
            if devanagari_count(qtext) >= 4:
                _fold_into(layer_key(qtitle), qtitle, qtext, None)
    layers.extend(merged.values())
    return layers


# Inside an <h3> commentary run the site sometimes quotes the BASE TEXT being
# glossed under an inner <h1>/<h2> heading — live-confirmed on Nyāya Sudhā
# (node 9360): the सुधा run carries <h2>अनुव्याख्यानम्</h2> followed by
# Madhva's verse in <strong><em> paragraphs, after which Jayatīrtha's plain
# prose resumes. Folding all of that into the सुधा layer (the old behaviour)
# buried the very verse the commentary explains inside the commentary and
# implicitly misattributed it. The split below is doubly gated so it cannot
# misfire into a new heading-as-layer bug: the inner heading must match the
# same CLOSED quote vocabulary (मूलम्-aliases / अनुव्याख्यानम् / *भाष्यम् /
# the grantha's own title), AND only paragraphs whose Devanagari sits
# entirely inside <strong>+<em> — the site's visual convention for the quoted
# verse — are taken; the first plain paragraph returns the run to the
# commentary layer.
QUOTED_BASE_ALIAS_KEYS = MULA_ALIAS_KEYS | {"अनुव्याख्यानम्", "अनुव्याख्यानं"}


def _quote_heading_title(tag: Tag, grantha_key: str) -> str | None:
    text = clean_text(tag.get_text(" ")).strip(" ।॥:-")
    if not text or _DANDA_RE.search(text):
        return None
    key = layer_key(text)
    if not key or len(key) > 40 or devanagari_count(key) < 2:
        return None
    if (key in QUOTED_BASE_ALIAS_KEYS or key.endswith(BHASHYA_TITLE)
            or (grantha_key and key == grantha_key)):
        return text
    return None


def _is_verse_quote_para(p: Tag) -> bool:
    if p.name != "p":
        return False
    if devanagari_count(clean_text(p.get_text(" "))) < 2:
        return False
    for s in p.find_all(string=True):
        if devanagari_count(str(s)) == 0:
            continue
        names = {a.name for a in s.parents}
        if "strong" not in names or "em" not in names:
            return False
    return True


def _split_quoted_base_text(heading: Tag, stop: Tag | None, details: Tag,
                            grantha_key: str) -> tuple[str, list[tuple[str, str]]]:
    """(commentary_text, [(quote_title, quote_text)]) for one <h3> run."""
    # Locate recognised inner quote headings between this h3 and the next.
    quote_heads: list[tuple[Tag, str]] = []
    for nd in heading.next_elements:
        if stop is not None and nd is stop:
            break
        if not isinstance(nd, Tag):
            continue
        if details is not None and details not in nd.parents:
            break
        if nd.name in ("h1", "h2"):
            qtitle = _quote_heading_title(nd, grantha_key)
            if qtitle:
                quote_heads.append((nd, qtitle))
    if not quote_heads:
        return _text_between(heading, stop, details), []

    own_parts: list[str] = []
    quotes: list[tuple[str, str]] = []
    cursor: Tag = heading
    first_span = True
    for qh, qtitle in quote_heads:
        # _text_between for the very first span (matches the established
        # h3-run behaviour, heading's own title line included, as all landed
        # data has it); _text_within afterwards, since the cursor is then a
        # consumed verse paragraph (or quote heading) whose own subtree must
        # NOT re-emit into the commentary text.
        own_parts.append(_text_between(cursor, qh, details) if first_span
                         else _text_within(details, cursor, qh))
        first_span = False
        verse_paras: list[str] = []
        cursor = qh
        for nd in qh.next_elements:
            if nd is stop or (isinstance(nd, Tag) and nd.name in ("h1", "h2", "h3")):
                break
            if not isinstance(nd, Tag) or nd.name != "p":
                continue
            if details is not None and details not in nd.parents:
                break
            if _is_verse_quote_para(nd):
                verse_paras.append(clean_text(nd.get_text(" ")))
                cursor = nd
            elif devanagari_count(clean_text(nd.get_text(" "))) > 0:
                break  # plain prose — the commentary has resumed
        if verse_paras:
            quotes.append((qtitle, "\n".join(verse_paras)))
    own_parts.append(_text_within(details, cursor, stop))
    own_text = clean_text("\n".join(part for part in own_parts if part))
    return own_text, quotes


def layer_key(title: str) -> str:
    """Normalised identity for a layer heading, for merging repeated passes.

    Internal spacing is dropped as well as honorifics. The site's headings are
    typed by hand, so the same commentary arrives as both "काशीटिप्पणी" and
    "काशी टिप्पणी", and "अभिनवचन्द्रिका" picks up a stray space as
    "अ भिनवचन्द्रिका" — 29 heading forms across the corpus differ from another
    form by whitespace alone, and each one was opening a second folder for a
    work that already had one. Devanagari compound spacing is not meaningful
    here, so squashing it merges the variants and separates nothing real.

    ळ (retroflex la) is also folded to ल (dental la): found via
    "न्यायसुधापरिमळ" vs "न्यायसुधापरिमलः" opening two separate folders for
    the same Nyāyasudhā sub-commentary (Parimaḷa/Parimala) under
    later_acharyas/nyaya_sudha. This is a real, common regional-orthography
    interchange in Kannada/Marathi-region printed Sanskrit (the Dvaita
    tradition's own home region) — not an OCR artefact, and not safe to
    assume everywhere, but safe here as an identity-key fold: it only
    changes which headings are treated as the SAME work, never the stored
    heading text itself (the raw `title` this function receives is what
    still gets displayed).
    """
    core = HONORIFIC_RE.sub("", clean_text(title)).replace("ळ", "ल")
    return re.sub(r"\s+", "", core).strip(" ।॥:-")


def strip_grantha_prefix(key: str, grantha_title: str) -> str:
    """Drop a leading self-reference to the grantha's own title from an
    already-normalised layer key.

    A commentary heading sometimes repeats the base work's name before its
    own — "न्यायसुधापरिमळ" for a Nyāyasudhā sub-commentary the site
    elsewhere just calls "परिमळ" — which, left alone, slugs to a second
    folder for the same work (`layer_key` alone cannot fix this: it
    normalises ONE heading at a time and has no notion of "this corpus's
    own grantha title"). Only strips when the prefix is a proper prefix
    (something remains after it) so a heading that IS just the grantha's
    own title, verbatim, is left alone rather than emptied out.
    """
    grantha_key = layer_key(grantha_title or "")
    if grantha_key and key.startswith(grantha_key) and len(key) > len(grantha_key):
        return key[len(grantha_key):]
    return key


def split_attribution(title: str) -> tuple[str, str]:
    """`श्रीमज्जयतीर्थभिक्षुविरचिताषट्प्रश्नभाष्यटीका` -> (author, work).

    Many headings name their author inside the heading itself rather than in a
    line above it, and on a grantha whose commentaries are all called
    "<grantha>भाष्यटीका" that prefix is the ONLY thing telling two authors
    apart. Returns ("", title) when no attribution verb is present.
    """
    text = clean_text(title)
    match = ATTRIBUTION_RE.search(text)
    if not match:
        return "", text
    author = text[: match.start()].strip(" ।॥:-")
    # The verb inflects (विरचिता / विरचितः / विरचितम् …); step past its tail.
    rest = text[match.end():]
    work = rest.lstrip("ािीःम्ंँ ").strip(" ।॥:-")
    if not author or not work:
        return "", text
    return author, work


def author_name(name: str) -> str:
    """An author's name as it should be filed, with only the unambiguous
    honorifics removed.

    श्रीमत् / श्रीमद् / श्रीमज् / श्रीमन् are always honorific, so they go. A
    bare श्री does NOT: it opens Shrinivasatirtha's, Shripadaraja's and
    Shridhara's actual names, and stripping it filed one Shrinivasatirtha under
    `tika_shrinivasatirtha` and another under `tika_nivasatirtha` — the same
    acharya, split in two.
    """
    core = clean_text(name).strip(" ।॥:-")
    # A doubled श्री is an honorific stacked on a name that already starts with
    # one: श्रीश्रीनिवासतीर्थ is Shrinivasatirtha, and keeping both opened a
    # second folder beside his own.
    while core.startswith("श्रीश्री"):
        core = core[len("श्री"):]
    for prefix in ("श्रीमत्", "श्रीमद्", "श्रीमज्", "श्रीमन्"):
        if core.startswith(prefix):
            core = core[len(prefix):]
            break
    return core.rstrip("ःम्ंाौ")


def author_core(name: str) -> str:
    """Comparable core for deciding whether two attributions mean one person.

    Honorific-insensitive, bare श्री included, because the canonical author is
    recorded as श्रीजयतीर्थः while the heading says श्रीमज्जयतीर्थभिक्षु.
    Never use this for a folder name — see author_name.
    """
    return HONORIFIC_RE.sub("", author_name(name)).strip(" ।॥:-")


def _attribution_before(heading: Tag) -> str:
    """The 'composed by X' line the site places just above a commentary."""
    node = heading
    for _ in range(3):
        node = node.find_previous(["p", "h3", "h2"])
        if node is None or node.name in ("h3", "h2"):
            return ""
        label = clean_text(node.get_text(" "))
        if not label or len(label) > ATTRIBUTION_MAX_CHARS:
            continue
        match = ATTRIBUTION_RE.search(label)
        if match:
            # "…केशवाचार्यविरचितम् प्रमाणलक्षणटीकाविवरणम्" — keep the credit,
            # drop the restated work title that follows it.
            end = label.find(" ", match.end())
            return label if end == -1 else label[:end].strip()
    return ""


def extract_layers(soup: BeautifulSoup, grantha_label: str = "") -> list[dict]:
    """Return the stacked commentary layers as [{title, text, anchor}].

    Primary path: the real #article<N> / #dynamicContent shape.
    Second:      one layer per `id="article<N>"` block (pre-probe assumption,
                 kept for pages that do not carry a details block).
    Fallback:    split the densest non-chrome container on its headings.

    `grantha_label` (the breadcrumb's grantha segment) lets the preamble scan
    recognise the work's own title as a mula-opening heading.
    """
    layers: list[dict] = []

    anchored = [
        t for t in soup.find_all(id=ARTICLE_ID_RE)
        if isinstance(t, Tag) and not _is_chrome(t)
    ]
    for node in anchored:
        layers.extend(_layers_from_article(node, grantha_label))
    if layers:
        return _dedupe_layers(layers)

    for node in anchored:
        heading = _heading_for(node)
        text = _strip_heading(block_text(node), heading)
        if devanagari_count(text) < 4:
            continue
        # Deliberately no article_id here. On this shape each layer is its OWN
        # #article<N> block, so the mula and its tika have different article
        # ids; keying items on them would break the cross-layer link. The page
        # is one verse either way, so the content id is the right key.
        layers.append({
            "title": heading,
            "text": text,
            "anchor": node.get("id", ""),
        })
    if layers:
        return _dedupe_layers(layers)

    root = _content_root(soup)
    if root is None:
        return []

    headings = [
        h for h in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        if devanagari_count(clean_text(h.get_text(" "))) > 0
    ]
    if not headings:
        text = block_text(root)
        if devanagari_count(text) >= 4:
            layers.append({"title": "", "text": text, "anchor": ""})
        return layers

    for index, heading in enumerate(headings):
        title = clean_text(heading.get_text(" "))
        stop = headings[index + 1] if index + 1 < len(headings) else None
        chunks: list[str] = []
        for sibling in heading.next_elements:
            if sibling is stop:
                break
            if isinstance(sibling, NavigableString):
                parent_name = (sibling.parent.name or "").lower() if sibling.parent else ""
                if parent_name in DROP_TAGS:
                    continue
                chunks.append(str(sibling))
            elif isinstance(sibling, Tag) and sibling.name == "br":
                chunks.append("\n")
        text = clean_text("".join(chunks))
        if devanagari_count(text) < 4:
            continue
        layers.append({"title": title, "text": text, "anchor": heading.get("id", "")})
    return _dedupe_layers(layers)


def _dedupe_layers(layers: list[dict]) -> list[dict]:
    """Drop layers whose text is wholly contained in an earlier layer.

    Nested `id="article<N>"` wrappers would otherwise emit the same body twice.

    The mula layer is exempt. A tika routinely opens by quoting its verse
    verbatim (Pramanalakshana 13529 does exactly this), so containment would
    otherwise delete the mula of every such leaf — the base text, silently.
    """
    kept: list[dict] = []
    for layer in layers:
        if layer.get("role") == "mula":
            kept.append(layer)
            continue
        if any(layer["text"] and layer["text"] in other["text"] for other in kept):
            continue
        kept = [
            k for k in kept
            if k.get("role") == "mula" or not (k["text"] and k["text"] in layer["text"])
        ]
        kept.append(layer)
    return kept


def is_container_page(soup: BeautifulSoup, html: str) -> bool:
    """Section/container nodes return 200 with 'No record found!!' and no text."""
    if NO_RECORD_RE.search(html or ""):
        return True
    return not extract_layers(soup)


# ---- lazy "Load More" units -------------------------------------------------
# A category-details page's initial HTML carries exactly ONE #article<id>
# block (the page's `first_sutra_id`); every further unit listed in the
# RIGHT-hand nav (`.explanation-text` entries) is only ever delivered by the
# site's Load More ajax: GET /load-data?book_id=<b>&id=<unit>&search=
# which returns {"html": "<div id=article<unit>>…", "tag": …, "sutraId": …}.
# The original import never followed that endpoint, so every page
# contributed only its first unit — verified live, 1 Sep 2026, against
# category-details/977/975 (maṅgalamācaraṇam): total_sutra_count=9, initial
# HTML holds article978 alone, units 979–986 exist only behind /load-data,
# and exactly those eight were absent from dge/data (the reported missing
# "गुरुराजेन" passages among them).
_QQ = "[\"']"
_BOOK_ID_RE = re.compile(
    "id=" + _QQ + "category_book_id" + _QQ + "[^>]*value=" + _QQ + r"(\d+)")
_LAZY_ID_RES = (
    re.compile("class=" + _QQ + "explanation-text" + _QQ + "[^>]*id=" + _QQ + r"(\d+)" + _QQ),
    re.compile("id=" + _QQ + r"(\d+)" + _QQ + "[^>]*class=" + _QQ + "explanation-text" + _QQ),
)


def extract_lazy_units(html: str):
    """(book_id, [unit_id, ...]) still waiting behind the page's Load More."""
    html = html or ""
    m = _BOOK_ID_RE.search(html)
    ids = []
    for rx in _LAZY_ID_RES:
        ids = rx.findall(html)
        if ids:
            break
    seen, ordered = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            ordered.append(i)
    return (m.group(1) if m else None), ordered


# ---- source-markup preservation (1 Sep 2026, project-lead ask) -------------
# The site styles its units with real markup — h3 commentary names, strong/em
# quoted base text, per-class colouring — and the text-only pipeline above
# throws all of that away. Each record now also carries `source_html`: a
# SANITIZED copy of its #article block, so a future renderer can style by the
# site's own class markers. Sanitized = structural/styling tags only, and only
# class/lang/id attributes; scripts, links, images, event handlers and every
# other attribute are stripped. Takes effect on (re-)harvest — data already
# committed predates this field and needs its section re-run (the restored
# .dv_cache makes that mostly a re-parse, not a re-crawl).
_HTML_KEEP_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "span",
                   "strong", "b", "em", "i", "u", "br", "hr", "sup", "sub",
                   "ol", "ul", "li", "table", "thead", "tbody", "tr", "td",
                   "th", "blockquote"}
_HTML_DROP_TAGS = {"script", "style", "noscript", "iframe", "form", "input",
                   "button", "select", "nav", "img", "svg", "video", "audio"}
_HTML_KEEP_ATTRS = {"class", "lang", "id"}
_HTML_MAX_BYTES = 250_000


def sanitize_article_html(node) -> str:
    """Sanitized markup of one #article block (empty string when the block is
    absent, over the size cap, or carries no styling signal beyond plain
    paragraphs)."""
    if node is None:
        return ""
    dup = make_soup(str(node))
    for tag in list(dup.find_all(True)):
        if getattr(tag, "decomposed", False) or tag.parent is None:
            continue          # detached by an earlier decompose()/unwrap()
        name = (tag.name or "").lower()
        if name in _HTML_DROP_TAGS:
            tag.decompose()
        elif name == "a":
            tag.unwrap()                      # keep the text, drop the link
        elif name not in _HTML_KEEP_TAGS:
            tag.unwrap()
        else:
            tag.attrs = {k: v for k, v in tag.attrs.items()
                         if k.lower() in _HTML_KEEP_ATTRS}
    out = "".join(str(c) for c in (dup.body.children if dup.body else dup.children))
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if len(out.encode("utf-8")) > _HTML_MAX_BYTES:
        return ""
    # No signal = nothing a renderer could style that the text doesn't
    # already carry; skip rather than double the data for plain prose.
    if not re.search(r'class=|<(h[1-6]|strong|b|em|i|u|sup|sub|table)\b', out):
        return ""
    return out


def _first_article_node(soup: BeautifulSoup):
    for t in soup.find_all(id=ARTICLE_ID_RE):
        if isinstance(t, Tag) and not _is_chrome(t):
            return t
    return None


def parse_load_fragment(fragment_html: str, page_record: dict,
                        unit_id: str, page_url: str) -> dict:
    """Parse one /load-data response's `html` into the same record shape
    parse_page() emits — the fragment carries the identical #article<id>
    structure, so the layer extraction is shared, and the page's own
    breadcrumb/ancestor carry over (the fragment has none of its own)."""
    soup = strip_noise(make_soup(fragment_html or ""))
    crumb = page_record.get("breadcrumb") or []
    layers = extract_layers(soup, crumb[1] if len(crumb) > 1 else "")
    return {
        "url": page_url.split("#")[0] + "#article" + str(unit_id),
        "content_id": str(unit_id),
        "ancestor_id": page_record.get("ancestor_id"),
        "breadcrumb": crumb,
        "layers": layers,
        "sidebar": [],
        "is_container": not layers,
        "no_record_marker": False,
        "source_html": sanitize_article_html(_first_article_node(soup)),
    }


def parse_page(html: str, url: str) -> dict:
    """Parse one leaf page into a structured record."""
    soup = strip_noise(make_soup(html))
    breadcrumb = extract_breadcrumb(soup)
    # breadcrumb[1] is the grantha segment ("1. प्रमाणलक्षणम्") — the preamble
    # scan uses it to recognise the work's own title as a mula heading.
    layers = extract_layers(soup, breadcrumb[1] if len(breadcrumb) > 1 else "")
    parsed = parse_content_url(url) or (None, None)
    no_record = bool(NO_RECORD_RE.search(html or ""))
    return {
        "url": url,
        "content_id": parsed[0],
        "ancestor_id": parsed[1],
        "breadcrumb": breadcrumb,
        "layers": layers,
        "sidebar": extract_sidebar_links(soup),
        "is_container": no_record or not layers,
        "no_record_marker": no_record,
        "source_html": sanitize_article_html(_first_article_node(soup)),
    }
