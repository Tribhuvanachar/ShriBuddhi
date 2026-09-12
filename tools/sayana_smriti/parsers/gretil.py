"""
gretil.py — parser for GRETIL plain e-texts (Göttingen Register of Electronic
Texts in Indian Languages).

Used here for the Sanskrit MŪLA of the Smṛtis DGE currently has as stubs.

Verified verse-tag conventions:
    Manu          // Mn_1.1 //
    Yājñavalkya   // Yj_1.1 //
    Parāśara      // Par_1.1 //     (plus page refs like "(I,1, p. 37)")
    Nārada        (Nar_M1.1)
    Bṛhaspati     [Brh_1,1.1]

Every GRETIL file carries a header ending in the literal line

    THIS GRETIL TEXT FILE IS FOR REFERENCE PURPOSES ONLY!
    COPYRIGHT AND TERMS OF USAGE AS FOR SOURCE FILE.

which we split on — and which is a real licence constraint, not boilerplate:
GRETIL's terms inherit from whatever print edition the file was keyed from.
Files derived from pre-1930 editions (Parāśara: Islāmpurkar 1893–1919) are
fine; files derived from modern critical editions (Nārada: Lariviere 1989;
Bṛhaspati: Aiyangar 1941) are flagged rights_encumbered in sources.json and
are NOT imported by default — pass --include-encumbered to override.
"""

from __future__ import annotations

import re
from typing import Dict, List

from bs4 import BeautifulSoup

from common import clean

HEADER_MARK = re.compile(r"FOR REFERENCE PURPOSES ONLY!?.*?$", re.I | re.M)

TAG_PATTERNS = [
    # name,           regex with (chapter)(verse)
    ("slashes", re.compile(r"//\s*[A-Za-z]+_(\d+)[.,](\d+)[a-z]?\s*//")),
    ("parens",  re.compile(r"\(\s*[A-Za-z]+_?M?(\d+)[.,](\d+)[a-z]?\s*\)")),
    ("brackets", re.compile(r"\[\s*[A-Za-z]+_(\d+)[.,](\d+)[a-z]?\s*\]")),
]


def to_text(html_or_txt: str) -> str:
    s = html_or_txt or ""
    if "<" in s[:2000] and ("</p>" in s or "<pre" in s or "<body" in s.lower()):
        soup = BeautifulSoup(s, "html.parser")
        for n in soup.select("script, style"):
            n.decompose()
        s = soup.get_text("\n", strip=True)
    return s


def strip_header(text: str) -> str:
    m = list(HEADER_MARK.finditer(text))
    if m:
        return text[m[-1].end():]
    return text


def parse(text_or_html: str) -> List[Dict]:
    """-> [{'chapter': int, 'verse': int, 'text': str}] in document order.

    The text belonging to a tag is everything BEFORE it since the previous tag
    — GRETIL puts the reference marker at the end of the verse it labels."""
    text = strip_header(to_text(text_or_html))
    best, best_n = None, 0
    for _name, pat in TAG_PATTERNS:
        n = len(pat.findall(text))
        if n > best_n:
            best, best_n = pat, n
    if not best or best_n < 5:
        return []

    out: List[Dict] = []
    prev_end = 0
    for m in best.finditer(text):
        body = clean(text[prev_end:m.start()])
        body = re.sub(r"\(\s*[IVXLC]+\s*,\s*\d+\s*,?\s*p\.\s*\d+\s*\)", "", body).strip()
        prev_end = m.end()
        if body:
            out.append({"chapter": int(m.group(1)), "verse": int(m.group(2)), "text": body})
    return out
