"""
sacredtexts.py — parser for sacred-texts.com Sacred Books of the East volumes.

Zero-JS static HTML, stable since ~2000, and the cleanest public-domain source
for the Smṛti/Dharmasūtra translations DGE is missing:

    SBE 2  (Bühler 1879) — Āpastamba, Gautama Dharmasūtras
    SBE 7  (Jolly 1880)  — Viṣṇu Smṛti
    SBE 14 (Bühler 1882) — Vasiṣṭha, Baudhāyana Dharmasūtras
    SBE 25 (Bühler 1886) — Manu Smṛti
    SBE 33 (Jolly 1889)  — Nārada, Bṛhaspati Smṛtis

Page conventions this parser relies on:
  * chapter heading is a bare roman numeral or "CHAPTER I." in an <h1>/<h3>/<b>
  * verses/sūtras are line-initial "1. ", "2. " … inside <p>
  * diacritics are encoded as *n*, *s*, â, î, û  -> unwrapped via
    strip_sacred_texts_diacritics()
  * footnote anchors are <a href="#fn_..."> and are dropped
"""

from __future__ import annotations

import re
from typing import Dict, List

from bs4 import BeautifulSoup

from common import clean, strip_sacred_texts_diacritics

VERSE_START = re.compile(r"(?m)^\s*(\d+)\s*\.\s+")
ROMAN = re.compile(r"^\s*(?:CHAPTER\s+)?([IVXLC]+)\s*\.?\s*$", re.I)

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(s: str) -> int:
    s = (s or "").upper().strip()
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VALUES.get(ch, 0)
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def page_text(html: str) -> str:
    """Body text with footnotes and page navigation removed.

    Footnotes matter: SBE volumes end a chapter with a numbered footnote block
    ("1. See Manu VIII, 1.") that is indistinguishable from a verse once the
    markup is thrown away, and would silently append phantom verse 1 to every
    chapter. They are identified by their <a name="fn_..."> anchors, which
    sacred-texts has used consistently since the site was built."""
    soup = BeautifulSoup(html, "html.parser")
    for sel in ("script", "style", "table", "div.footnotes", "div.filenav"):
        for n in soup.select(sel):
            n.decompose()

    # Drop the footnote block: every element holding a <a name="fn*"> target,
    # plus everything after it (footnotes are always last).
    anchors = [a for a in soup.find_all("a")
               if (a.get("name") or "").lower().startswith(("fn", "fr"))]
    if anchors:
        first = anchors[0]
        block = first.find_parent(["div", "p", "blockquote"]) or first
        for sib in list(block.next_siblings):
            if getattr(sib, "decompose", None):
                sib.decompose()
        block.decompose()

    # Reference markers inside the running text, and prev/next links.
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#fn") or href.startswith("#fr"):
            a.decompose()
        elif re.match(r"^(next|previous)\b", clean(a.get_text(" ", strip=True)), re.I):
            (a.find_parent("p") or a).decompose()

    txt = soup.get_text("\n", strip=True)
    return clean(strip_sacred_texts_diacritics(txt))


def chapter_number(html: str, fallback: int = 0) -> int:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "b", "center"]):
        t = clean(strip_sacred_texts_diacritics(tag.get_text(" ", strip=True)))
        m = ROMAN.match(t)
        if m:
            n = roman_to_int(m.group(1))
            if n:
                return n
        m = re.match(r"^\s*(?:CHAPTER|ADHYAYA|PRASNA)\s+(\d+)", t, re.I)
        if m:
            return int(m.group(1))
    return fallback


def split_verses(text: str) -> List[Dict]:
    """Split a chapter's plain text into [{'number': n, 'text': ...}] on
    line-initial 'N. ' markers. Text before the first marker is dropped
    (it is the chapter heading / editor's preface)."""
    out: List[Dict] = []
    marks = list(VERSE_START.finditer(text))
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = clean(text[start:end])
        if body:
            out.append({"number": int(m.group(1)), "text": body})
    return out


def parse_chapter(html: str, fallback_chapter: int = 0) -> Dict:
    text = page_text(html)
    return {
        "chapter": chapter_number(html, fallback_chapter),
        "verses": split_verses(text),
        "raw_len": len(text),
    }
