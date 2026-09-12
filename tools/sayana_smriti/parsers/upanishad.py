"""
upanishad.py — parsers for the two sources that fill DGE's empty Upaniṣad
shelves: GRETIL for the Sanskrit mūla, Müller's SBE for the English.

Thirteen principal-Upaniṣad folders exist in the taxonomy and every one of them
holds **zero items** today.

GRETIL corpustei
----------------
`gretil/corpustei/transformations/html/sa_<name>-comm.htm` — the same source
family the repo's existing shankara_bhashya importer already reads successfully.
Each file interleaves the mūla and Śaṅkara's commentary, tagged separately:

    ChUp_1,1.1        mūla
    ChUpBh_1,1.1      bhāṣya on it

so both can be split out of one fetch, and the reference IS the id — no
alignment guessing anywhere. Note the two-level separator: `1,1.1` means
adhyāya 1, khaṇḍa 1, verse 1. Some texts are flat (`IsUp_1`).

Sacred Books of the East
------------------------
Müller SBE 1 and SBE 15, one file per khaṇḍa/section, verified page ranges in
UPANISHAD_SOURCES below. Headings are shouty transliterations with the diacritic
letters wrapped in tags, so `FIRST KHAN D A.` and `KH ÂNDOGYA-UPANISHAD.` are
what survives a text extraction — matching is done on a squashed form for that
reason. Verse numbers are plain `1. ` at paragraph start; superscripts on these
pages are footnote references only, never verse numbers.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

from common import clean, strip_sacred_texts_diacritics
from parsers.sacredtexts import page_text, roman_to_int

# `|| ChUp_1,1.1 ||`, `// KaU_1.1 //`, `|| IsUp_1 ||`, with or without delimiters.
TAG = re.compile(
    r"[|/]{0,2}\s*([A-Za-zĀĪŪṚṢŚṆṬḌÑṄ]+?)(Bh)?_(\d+)(?:\s*[,.]\s*(\d+))?(?:\s*[.]\s*(\d+))?\s*[|/]{0,2}"
)

ORDINALS = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5, "SIXTH": 6,
    "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10, "ELEVENTH": 11,
    "TWELFTH": 12, "THIRTEENTH": 13, "FOURTEENTH": 14, "FIFTEENTH": 15,
    "SIXTEENTH": 16, "SEVENTEENTH": 17, "EIGHTEENTH": 18, "NINETEENTH": 19,
    "TWENTIETH": 20, "TWENTY-FIRST": 21, "TWENTY-SECOND": 22, "TWENTY-THIRD": 23,
    "TWENTY-FOURTH": 24, "TWENTY-FIFTH": 25, "TWENTY-SIXTH": 26,
}

# The unit word varies by text and carries no information we need — Müller uses
# KHANDA, BRAHMANA, ANUVAKA, VALLI, ADHYAYA, MUNDAKA, PRAPATHAKA, QUESTION.
UNIT_WORDS = ("KHANDA", "BRAHMANA", "ANUVAKA", "VALLI", "ADHYAYA", "MUNDAKA",
              "PRAPATHAKA", "QUESTION", "ARANYAKA")


def squash(s: str) -> str:
    """'SECOND BRÂHMAN A.' -> 'SECONDBRAHMANA'.

    Two things have to happen and both are easy to miss. sacred-texts splits
    letters that carry diacritics into their own tags, so whitespace inside a
    word is an artefact of the markup — hence dropping it. And the accented
    letters must be FOLDED to ASCII, not deleted: strip Â outright and
    'BRÂHMANA' becomes 'BRHMANA', which matches no unit word, so every
    Bṛhadāraṇyaka section heading goes unrecognised."""
    t = strip_sacred_texts_diacritics(s or "").upper()
    t = unicodedata.normalize("NFD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z-]", "", t)


GRETIL_HEADER_END = re.compile(
    r"(?:FOR REFERENCE PURPOSES ONLY[^\n]*|\[GRETIL-Version[^\]]*\]|^\s*source:[^\n]*)", re.I | re.M)


def strip_gretil_header(text: str) -> str:
    marks = list(GRETIL_HEADER_END.finditer(text or ""))
    return text[marks[-1].end():] if marks else text


# ------------------------------------------------------------------ GRETIL

def parse_gretil_upanishad(html_or_text: str) -> Dict[str, List[Tuple[str, str]]]:
    """-> {'mula': [(ref, text)], 'bhashya': [(ref, text)]}

    `ref` is the source's own reference with the levels joined by dots
    ('1.1.1', or '1' for a flat text), which is exactly what DGE wants as an id.
    Text belonging to a tag is everything since the previous tag — GRETIL puts
    the marker at the END of the unit it labels."""
    text = html_or_text or ""
    if "<" in text[:2000]:
        soup = BeautifulSoup(text, "html.parser")
        for n in soup.select("script, style"):
            n.decompose()
        text = soup.get_text("\n", strip=True)

    # Every GRETIL file opens with a header block (title/source/input-by, closed
    # by a version stamp or the reference-purposes notice). Left in place it is
    # swallowed by the FIRST verse, which then silently carries the file's
    # bibliography as scripture.
    text = strip_gretil_header(text)

    out: Dict[str, List[Tuple[str, str]]] = {"mula": [], "bhashya": []}
    prev_end = 0
    for m in TAG.finditer(text):
        levels = [g for g in (m.group(3), m.group(4), m.group(5)) if g]
        if not levels:
            continue
        body = clean(text[prev_end:m.start()])
        prev_end = m.end()
        if not body:
            continue
        ref = ".".join(str(int(x)) for x in levels)
        out["bhashya" if m.group(2) else "mula"].append((ref, body))
    return out


# ------------------------------------------------------------------ SBE

UNIT_HEADING = re.compile(
    r"^(" + "|".join(sorted(ORDINALS, key=len, reverse=True)) + r")(" +
    "|".join(UNIT_WORDS) + r")$")


def parse_sbe_sections(html: str) -> List[Dict]:
    """-> [{'ordinal': int|None, 'unit': str, 'verses': {n: text}}], one entry
    per SECTION on the page.

    Normally a page is one section, but Müller occasionally prints two under
    one file — sbe15054 carries both `SECOND BRÂHMANA` and `THIRD BRÂHMANA`.
    Counting files instead of sections there shifts every subsequent
    Bṛhadāraṇyaka id by one, which is the kind of error that reads as
    plausible scripture forever. So sections are counted, not files."""
    soup = BeautifulSoup(html, "html.parser")
    for sel in ("script", "style", "div.footnotes"):
        for n in soup.select(sel):
            n.decompose()
    anchors = [a for a in soup.find_all("a")
               if (a.get("name") or "").lower().startswith(("fn", "fr"))]
    if anchors:
        block = anchors[0].find_parent(["div", "p", "blockquote"]) or anchors[0]
        for sib in list(block.next_siblings):
            if getattr(sib, "decompose", None):
                sib.decompose()
        block.decompose()

    groups: List[Dict] = []
    current = None
    for el in soup.find_all(["h1", "h2", "h3", "h4", "center", "b", "p", "blockquote"]):
        t = clean(strip_sacred_texts_diacritics(el.get_text(" ", strip=True)))
        t = re.sub(r"\[\d+\]", "", t).strip()
        if not t:
            continue
        m = UNIT_HEADING.match(squash(t))
        if m and el.name in ("h1", "h2", "h3", "h4", "center", "b"):
            current = {"ordinal": ORDINALS.get(m.group(1)), "unit": m.group(2), "verses": {}}
            groups.append(current)
            continue
        if el.name not in ("p", "blockquote"):
            continue
        t = re.sub(r"\bp\.\s*\d+\b", " ", t)
        if current is None:
            current = {"ordinal": None, "unit": "", "verses": {}}
            groups.append(current)
        marks = list(re.finditer(r"(?:^|(?<=\s))(\d{1,3})\s*\.\s+", t))
        for i, mm in enumerate(marks):
            n = int(mm.group(1))
            start = mm.end()
            end = marks[i + 1].start() if i + 1 < len(marks) else len(t)
            body = clean(t[start:end])
            if body and len(body) > 5 and n not in current["verses"]:
                current["verses"][n] = body
    return [g for g in groups if g["verses"]]


def parse_sbe_page(html: str) -> Dict:
    """-> {'headings': [...], 'chapter': int|None, 'verses': {n: text}}

    `chapter` is read from the last ordinal heading on the page that names a
    unit word. Müller prints the adhyāya heading only on its FIRST section page,
    so a caller walking a range must carry the outer level forward itself."""
    soup = BeautifulSoup(html, "html.parser")
    heads = []
    for h in soup.find_all(["h1", "h2", "h3", "h4", "center", "b"]):
        t = clean(strip_sacred_texts_diacritics(h.get_text(" ", strip=True)))
        t = re.sub(r"\[\d+\]", "", t).strip()
        if t:
            heads.append(t)

    chapter = None
    for t in heads:
        sq = squash(t)
        for word in UNIT_WORDS:
            if sq.endswith(word):
                ordinal = sq[: -len(word)]
                if ordinal in ORDINALS:
                    chapter = ORDINALS[ordinal]
                break
        m = re.match(r"^(?:ADHYAYA|KHANDA|SECTION)([IVXLC]+)$", sq)
        if m:
            chapter = roman_to_int(m.group(1))

    body = page_text(html)
    body = re.sub(r"\bp\.\s*\d+\b", " ", body)          # printed page markers
    verses: Dict[int, str] = {}
    marks = list(re.finditer(r"(?m)^\s*(\d{1,3})\s*\.\s+", body))
    for i, mm in enumerate(marks):
        n = int(mm.group(1))
        start = mm.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        t = clean(body[start:end])
        if t and len(t) > 5 and n not in verses:
            verses[n] = t
    return {"headings": heads, "chapter": chapter, "verses": verses}


def sbe_url(volume: int, page: int) -> str:
    """SBE 1 and 15 use three-digit page numbers."""
    return f"https://sacred-texts.com/hin/sbe{volume:02d}/sbe{volume:02d}{page:03d}.htm"
