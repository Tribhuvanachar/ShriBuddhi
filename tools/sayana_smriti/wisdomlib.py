"""
wisdomlib.py — a structure-agnostic parser for wisdomlib.org book pages.

Why heading-driven and not CSS-selector-driven
----------------------------------------------
wisdomlib's markup changes; its *heading strings* are stable and are what a
human reads. So we flatten the article body into (heading, block-of-text)
pairs and classify by heading text. If wisdomlib reskins the site tomorrow,
this keeps working; a `div.entry > div.node` selector would not.

Verified heading strings (fetched 17 Aug 2026):

  Rig Veda (translation and commentary)  — /hinduism/book/rig-veda-english-translation
    "Rig Veda 1.164.1"
    "Sanskrit text [Accents, Plain, Transliterated]:"
    "English translation:"
    "Commentary by Sāyaṇa: Ṛgveda-bhāṣya"
    "Details:"
    "Padapatha [Accents, Plain, Transliterated]:"
    "Multi-layer Annotation of the Ṛgveda"

  Manusmriti with the Commentary of Medhatithi
    "Verse 1.1 [Question of the Sages]"
    "Sanskrit text, Unicode transliteration and English translation by Ganganath Jha:"
    "Medhātithi's commentary (manubhāṣya):"
    "Explanatory notes by Ganganath Jha"
    "Comparative notes by various authors"

  Yajnavalkya-smriti with Mitakshara and Viramitrodaya
    "Verse 1.1"
    "The Mitākṣarā commentary of Vijñāneśvara Bhikṣu:"
    "The Vīramitrodaya commentary of Mitramiśra):"   <-- note the stray ')'
    "Footnotes and references:"

  Dharmasutras (Apastamba / Gautama / Baudhayana / Vasistha, Bühler)
    "Praśna I, Adhyāya 1, Kaṇḍikā 2"
    "Footnotes and references:"
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

from common import clean, has_devanagari

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")

# Canonical field <- heading keyword. Order matters: first match wins.
# Matching is done on a casefolded, diacritic-insensitive form of the heading,
# so "Sāyaṇa" and "Sayana" both hit.
HEADING_RULES: List[Tuple[str, str]] = [
    ("sayana",        r"commentary by say?a?[nṇ]a|rgveda-?bhasya|ṛgveda-?bhāṣya"),
    ("medhatithi",    r"medhatithi'?s commentary|manubhasya|manubhāṣya"),
    ("mitakshara",    r"mitaksara commentary|mitākṣarā commentary"),
    ("viramitrodaya", r"viramitrodaya commentary|vīramitrodaya commentary"),
    ("kulluka",       r"kulluka|kullūka"),
    ("translation",   r"english translation|unicode transliteration and english translation"),
    ("sanskrit",      r"^sanskrit text"),
    ("padapatha",     r"^padapatha"),
    ("details",       r"^details"),
    ("notes_jha",     r"explanatory notes"),
    ("notes_comp",    r"comparative notes"),
    ("footnotes",     r"footnotes and references"),
    ("annotation",    r"multi-?layer annotation"),
]

_DIACRITIC_FOLD = str.maketrans({
    "ā": "a", "ī": "i", "ū": "u", "ṛ": "r", "ṝ": "r", "ḷ": "l", "ḹ": "l",
    "ṃ": "m", "ṁ": "m", "ḥ": "h", "ñ": "n", "ṅ": "n", "ṇ": "n", "ṭ": "t",
    "ḍ": "d", "ś": "s", "ṣ": "s", "â": "a", "î": "i", "û": "u", "ê": "e",
    "’": "'", "‘": "'",
})


def fold(s: str) -> str:
    return (s or "").strip().lower().translate(_DIACRITIC_FOLD)


def classify_heading(heading: str) -> str:
    f = fold(heading)
    for key, pat in HEADING_RULES:
        if re.search(pat, f):
            return key
    return ""


REF_PATTERNS = [
    re.compile(r"\bRig\s*Veda\s+(\d+)\.(\d+)\.(\d+)\b", re.I),
    re.compile(r"\bVerse\s+(\d+)\.(\d+)\b", re.I),
]


def parse_reference(title: str):
    """('rv', m, s, r) or ('verse', chapter, verse) or None."""
    m = REF_PATTERNS[0].search(title or "")
    if m:
        return ("rv", int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = REF_PATTERNS[1].search(title or "")
    if m:
        return ("verse", int(m.group(1)), int(m.group(2)))
    return None


def _article_root(soup: BeautifulSoup):
    """Best-effort narrowing to the content column. Falls back to <body>, which
    is fine because the section splitter ignores nav/footer (no headings we
    classify) anyway."""
    for sel in ("article", "main", "div#content", "div.entry", "div.node"):
        node = soup.select_one(sel)
        if node:
            return node
    return soup.body or soup


def _drop_chrome(root):
    for sel in ("script", "style", "nav", "footer", "form", "noscript",
                "div.breadcrumb", "ul.breadcrumb", "div.adsbygoogle",
                "div.sub-contents", "div.toc"):
        for n in root.select(sel):
            n.decompose()


def parse_page(html: str) -> Dict:
    """-> {'title', 'sections': {canonical_key: text}, 'raw_sections':[(heading,text)]}"""
    soup = BeautifulSoup(html, "html.parser")
    root = _article_root(soup)
    _drop_chrome(root)

    title = ""
    h1 = root.find(HEADING_TAGS)
    if h1:
        title = clean(h1.get_text(" ", strip=True))
    if not title and soup.title:
        title = clean(soup.title.get_text(" ", strip=True))

    raw: List[Tuple[str, str]] = []
    current_head = title
    buf: List[str] = []
    for el in root.descendants:
        name = getattr(el, "name", None)
        if name in HEADING_TAGS:
            raw.append((current_head, clean("\n".join(buf))))
            current_head = clean(el.get_text(" ", strip=True))
            buf = []
        elif name in ("p", "blockquote", "li", "pre", "div"):
            # Only take leaf-ish blocks, else nested divs duplicate text.
            if el.find(["p", "blockquote", "li", "pre"]):
                continue
            t = clean(el.get_text(" ", strip=True))
            if t:
                buf.append(t)
    raw.append((current_head, clean("\n".join(buf))))

    sections: Dict[str, str] = {}
    for head, body in raw:
        if not body:
            continue
        key = classify_heading(head)
        if not key:
            continue
        sections[key] = (sections.get(key, "") + "\n\n" + body).strip() if key in sections else body

    return {"title": title, "sections": sections, "raw_sections": raw}


def split_sanskrit_block(block: str):
    """wisdomlib's 'Sanskrit text [Accents, Plain, Transliterated]:' block holds
    three parallel lines. Returns (accented_devanagari, plain_devanagari, iast)."""
    lines = [l.strip() for l in (block or "").split("\n") if l.strip()]
    deva = [l for l in lines if has_devanagari(l)]
    roman = [l for l in lines if not has_devanagari(l)]
    accented = deva[0] if deva else ""
    plain = deva[1] if len(deva) > 1 else (deva[0] if deva else "")
    iast = roman[0] if roman else ""
    return accented, plain, iast


TOC_LINK = re.compile(r"/d/doc(\d+)\.html")


def toc_links(html: str, base="https://www.wisdomlib.org"):
    """All /d/docNNN.html links on a page, in document order, deduped."""
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        m = TOC_LINK.search(a["href"])
        if not m:
            continue
        href = a["href"]
        if href.startswith("/"):
            href = base + href
        if href in seen:
            continue
        seen.add(href)
        out.append({"url": href, "doc_id": int(m.group(1)),
                    "text": clean(a.get_text(" ", strip=True))})
    return out
