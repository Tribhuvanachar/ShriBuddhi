"""
sacredtexts_veda.py — parsers for the four public-domain Vedic translations on
sacred-texts.com that cover everything in DGE *outside* the Ṛgveda.

    Atharvaveda    Griffith 1895–6   av/av{KK}{SSS}.htm     one page per sūkta
    Śukla Yajurveda Griffith 1899    wyv/wyvbk{NN}.htm      one page per adhyāya
    Taittirīya S.  Keith 1914        yv/yv{0N}.htm          one page per kāṇḍa

All three are structural filenames, so the whole URL list is generated from
DGE's own counts — no index crawl, same principle as the Ṛgveda doc map.

Page conventions, verified against live pages 18 Aug 2026:

  Griffith AV (av01001.htm)
      <h1>BOOK I</h1>
      <h3>HYMN I</h3>
      <h4>A prayer to Vāchaspati for divine illumination and help.</h4>
      then verses run together, each opening with a superscript number:
      "1Now may Vāchaspati assign…  2Come thou again…"

  Griffith WYV (wyvbk01.htm)
      <h1>THE TEXTS OF THE WHITE YAJURVEDA</h1>   <- masthead, every page
      <h1>OR VÂJASANEYA-SAMHITÂ.</h1>             <- masthead, every page
      <h3>BOOK THE FIRST.</h3>                    <- the real marker
      verses open with a plain numeral: "2 Strainer of Vasu art thou"

  Keith TS (yv02.htm)
      <h1>KANDA II</h1>
      <h2>PRAPATHAKA I</h2>
      <h3>The Special Animal Sacrifices</h3>      <- prapāṭhaka title
      <h3>ii. 1. 1.</h3>                          <- anuvāka reference
      clauses lettered a, b, c … ; footnote markers [1], [2] carry Keith's
      references to Sāyaṇa and Bhaṭṭa Bhāskara.
      NOTE the collision: title and reference are both <h3>. Disambiguated by
      matching ^[ivxlc]+\\.\\s*\\d+\\.\\s*\\d+\\.$ — never by position.
"""

from __future__ import annotations

import re
from typing import Dict, List

from bs4 import BeautifulSoup

from common import clean, strip_sacred_texts_diacritics
from parsers.sacredtexts import page_text, roman_to_int

# ------------------------------------------------------------------- helpers

TS_REF = re.compile(r"^\s*([ivxlc]+)\s*\.\s*(\d+)\s*\.\s*(\d+)\s*\.?\s*$", re.I)


def _soup(html: str) -> BeautifulSoup:
    s = BeautifulSoup(html, "html.parser")
    for sel in ("script", "style", "table.footnote", "div.filenav", "div.footnotes"):
        for n in s.select(sel):
            n.decompose()
    # Footnotes are anchored with <a name="fn_N"> and always sit at the end of
    # the page. Left in place they get appended to whichever verse or anuvaka
    # came last -- and since Keith's footnotes are precisely where he cites
    # Sayana, that failure looks like real content and would not be noticed.
    anchors = [a for a in s.find_all("a")
               if (a.get("name") or "").lower().startswith(("fn", "fr"))]
    if anchors:
        block = anchors[0].find_parent(["div", "p", "blockquote"]) or anchors[0]
        for sib in list(block.next_siblings):
            if getattr(sib, "decompose", None):
                sib.decompose()
        block.decompose()
    return s


# --------------------------------------------------------------- Griffith AV

def av_url(kanda: int, sukta: int) -> str:
    return f"https://sacred-texts.com/hin/av/av{kanda:02d}{sukta:03d}.htm"


def parse_av_hymn(html: str) -> Dict:
    """-> {'book', 'hymn', 'subtitle', 'verses': {n: text}}

    Verse splitting is done on the <sup> nodes in the DOM — see
    _split_av_verses() for why the flattened text is not good enough."""
    s = _soup(html)
    book = hymn = 0
    subtitle = ""
    for h in s.find_all(["h1", "h2", "h3", "h4"]):
        t = clean(strip_sacred_texts_diacritics(h.get_text(" ", strip=True)))
        m = re.match(r"^BOOK\s+([IVXLC]+)$", t, re.I)
        if m:
            book = roman_to_int(m.group(1))
            continue
        m = re.match(r"^HYMN\s+([IVXLC]+)$", t, re.I)
        if m:
            hymn = roman_to_int(m.group(1))
            continue
        if h.name == "h4" and not subtitle:
            subtitle = t

    verses = _split_av_verses(s, subtitle)
    return {"book": book, "hymn": hymn, "subtitle": subtitle, "verses": verses}


def _split_av_verses(soup: BeautifulSoup, subtitle: str) -> Dict[int, str]:
    """Griffith marks each verse with a <sup> number and then runs the verses of
    a hymn together in one <p>. Split on the <sup> nodes in the DOM rather than
    on the flattened text: once markup is gone, '1' and 'Now may' are separated
    by a line break and no text-level pattern distinguishes a verse number from
    a numeral inside the prose."""
    verses: Dict[int, str] = {}
    current = None
    buf: List[str] = []

    def flush():
        if current is not None:
            text = clean(" ".join(buf))
            if text and len(text) > 15 and current not in verses:
                verses[current] = text

    for p in soup.find_all(["p", "blockquote"]):
        for node in p.descendants:
            name = getattr(node, "name", None)
            if name == "sup":
                t = clean(node.get_text(" ", strip=True))
                if t.isdigit():
                    flush()
                    current = int(t)
                    buf = []
                continue
            if name is not None:
                continue                       # element -- its text arrives via strings
            if node.find_parent("sup"):
                continue
            t = clean(strip_sacred_texts_diacritics(str(node)))
            if t and current is not None:
                buf.append(t)
    flush()

    if verses:
        return verses

    # Fallback for pages that number verses in plain text rather than <sup>.
    body = page_text(str(soup))
    if subtitle and subtitle in body:
        body = body[body.index(subtitle) + len(subtitle):]
    marks = list(re.finditer(r"(?m)(?:^|\s)(\d{1,3})\s*(?=[A-ZĀĪŪṚṢŚṆṬḌÑṄ'‘“])", body))
    for i, m in enumerate(marks):
        n = int(m.group(1))
        start, end = m.end(), (marks[i + 1].start() if i + 1 < len(marks) else len(body))
        text = clean(body[start:end])
        if text and len(text) > 15 and n not in verses:
            verses[n] = text
    return verses


# -------------------------------------------------------------- Griffith WYV

def wyv_url(adhyaya: int) -> str:
    return f"https://sacred-texts.com/hin/wyv/wyvbk{adhyaya:02d}.htm"


# Griffith spells the adhyāya out in full — "BOOK THE FORTIETH." — and the
# White Yajurveda runs to 40 books, so the list has to go all the way. A short
# list would not fail loudly: parse_wyv_book() falls back to the book number the
# caller asked for, which would silently disarm the misalignment guard.
_ORDINALS = [
    "", "FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH",
    "EIGHTH", "NINTH", "TENTH", "ELEVENTH", "TWELFTH", "THIRTEENTH",
    "FOURTEENTH", "FIFTEENTH", "SIXTEENTH", "SEVENTEENTH", "EIGHTEENTH",
    "NINETEENTH", "TWENTIETH", "TWENTY-FIRST", "TWENTY-SECOND", "TWENTY-THIRD",
    "TWENTY-FOURTH", "TWENTY-FIFTH", "TWENTY-SIXTH", "TWENTY-SEVENTH",
    "TWENTY-EIGHTH", "TWENTY-NINTH", "THIRTIETH", "THIRTY-FIRST",
    "THIRTY-SECOND", "THIRTY-THIRD", "THIRTY-FOURTH", "THIRTY-FIFTH",
    "THIRTY-SIXTH", "THIRTY-SEVENTH", "THIRTY-EIGHTH", "THIRTY-NINTH",
    "FORTIETH",
]
BOOK_WORDS = {w: i for i, w in enumerate(_ORDINALS) if w}


def parse_wyv_book(html: str, fallback: int = 0) -> Dict:
    """-> {'book': n, 'verses': {n: text}}"""
    s = _soup(html)
    book = fallback
    for h in s.find_all(["h1", "h2", "h3"]):
        t = clean(strip_sacred_texts_diacritics(h.get_text(" ", strip=True))).upper()
        m = re.match(r"^BOOK\s+THE\s+([A-Z\- ]+?)\.?$", t)
        if m:
            word = re.sub(r"\s+", "-", m.group(1).strip())
            book = BOOK_WORDS.get(word, BOOK_WORDS.get(word.split("-")[0], book))
            break
        m = re.match(r"^BOOK\s+([IVXLC]+)\.?$", t)
        if m:
            book = roman_to_int(m.group(1))
            break

    body = page_text(html)
    body = re.sub(r"^.*?VÂJASANEYA-SAMHITÂ\.?", "", body, flags=re.S | re.I)
    verses: Dict[int, str] = {}
    marks = list(re.finditer(r"(?m)(?:^|\s)(\d{1,3})\s+(?=[A-ZÂÎÛ])", body))
    for i, m in enumerate(marks):
        n = int(m.group(1))
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        text = clean(body[start:end])
        if text and len(text) > 10 and n not in verses:
            verses[n] = text
    return {"book": book, "verses": verses}


# ------------------------------------------------------------------ Keith TS

def ts_url(kanda: int) -> str:
    return f"https://sacred-texts.com/hin/yv/yv{kanda:02d}.htm"


def parse_ts_kanda(html: str) -> Dict[str, str]:
    """-> {'1.1.1': 'a For food thee… b Ye are winds…', …}

    Keys are exactly DGE's Taittirīya ids (kāṇḍa.prapāṭhaka.anuvāka) — verified:
    DGE's TS 1.1 holds 14 units and the standard prapāṭhaka has 14 anuvākas."""
    s = _soup(html)
    out: Dict[str, str] = {}
    current = None
    buf: List[str] = []

    for el in s.find_all(["h1", "h2", "h3", "h4", "p", "div"]):
        if el.name in ("h1", "h2", "h3", "h4"):
            t = clean(strip_sacred_texts_diacritics(el.get_text(" ", strip=True)))
            m = TS_REF.match(t)
            if m:
                if current and buf:
                    out[current] = clean("\n".join(buf))
                current = f"{roman_to_int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"
                buf = []
            # a non-matching heading (prapāṭhaka title) is simply ignored
        elif current is not None:
            if el.find(["p", "div"]):
                continue
            t = clean(strip_sacred_texts_diacritics(el.get_text(" ", strip=True)))
            t = re.sub(r"\[\d+\]", "", t).strip()
            if t:
                buf.append(t)
    if current and buf:
        out[current] = clean("\n".join(buf))
    return out
