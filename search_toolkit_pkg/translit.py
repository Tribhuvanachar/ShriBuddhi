"""
translit.py — Transliteration to a single canonical internal encoding: SLP1.

Why SLP1: it maps exactly one ASCII byte to each Sanskrit phoneme (letter).
That property is what makes edit-distance, n-gramming and phonetic folding
behave sanely downstream — one substitution = one sound changed. IAST/HK/ITRANS
use multi-char sequences and combining diacritics, which break those operations.

This module is dependency-free on purpose. In production you would swap these
tables for `vidyut-lipi` (Rust core, with Python + WASM/JS bindings so the SAME
normalizer runs at index time on the server and at query time in the browser).
The public API here mirrors what you'd call there: `to_slp1(text, scheme=None)`.

Supported input schemes: Devanagari, IAST, Harvard-Kyoto (HK), and SLP1 itself.
`detect_scheme` gives a best-effort guess when the scheme isn't specified.
"""
from __future__ import annotations
import re
import unicodedata

# ---------------------------------------------------------------------------
# SLP1 reference alphabet (what everything converts INTO)
# vowels:      a A i I u U f F x X e E o O   (A=aa, I=ii, ... f=r-vocalic, E=ai, O=au)
# consonants:  k K g G N / c C j J Y / w W q Q R / t T d D n / p P b B m
#              y r l v / S z s h L
# signs:       M=anusvara  H=visarga  ~=candrabindu  '=avagraha
# ---------------------------------------------------------------------------

# ---- Devanagari -> SLP1 ----------------------------------------------------
_DEVA_INDEP_VOWEL = {
    "अ": "a", "आ": "A", "इ": "i", "ई": "I", "उ": "u", "ऊ": "U",
    "ऋ": "f", "ॠ": "F", "ऌ": "x", "ॡ": "X",
    "ए": "e", "ऐ": "E", "ओ": "o", "औ": "O",
    "ऎ": "e", "ऒ": "o",  # southern short e/o -> fold to e/o
    "ऍ": "E", "ऑ": "O",  # candra e/o -> approximate
}
_DEVA_MATRA = {
    "ा": "A", "ि": "i", "ी": "I", "ु": "u", "ू": "U",
    "ृ": "f", "ॄ": "F", "ॢ": "x", "ॣ": "X",
    "े": "e", "ै": "E", "ो": "o", "ौ": "O",
    "ॆ": "e", "ॊ": "o", "ॅ": "E", "ॉ": "O",
}
_DEVA_CONS = {
    "क": "k", "ख": "K", "ग": "g", "घ": "G", "ङ": "N",
    "च": "c", "छ": "C", "ज": "j", "झ": "J", "ञ": "Y",
    "ट": "w", "ठ": "W", "ड": "q", "ढ": "Q", "ण": "R",
    "त": "t", "थ": "T", "द": "d", "ध": "D", "न": "n",
    "प": "p", "फ": "P", "ब": "b", "भ": "B", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "S", "ष": "z", "स": "s", "ह": "h", "ळ": "L",
    # common nukta forms -> nearest base
    "क़": "k", "ख़": "K", "ग़": "g", "ज़": "j", "ड़": "q", "ढ़": "Q", "फ़": "P", "य़": "y",
}
_DEVA_SIGN = {
    "ं": "M", "ः": "H", "ँ": "~", "ऽ": "'",
    "।": " | ", "॥": " || ",
}
_DEVA_VIRAMA = "्"
_DEVA_DIGITS = {d: str(i) for i, d in enumerate("०१२३४५६७८९")}


def _deva_to_slp1(s: str) -> str:
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        two = s[i:i + 2]
        if two in _DEVA_CONS:          # nukta composed as two code points
            ch, adv = two, 2
        else:
            adv = 1
        if ch in _DEVA_CONS:
            base = _DEVA_CONS[ch]
            nxt = s[i + adv] if i + adv < n else ""
            if nxt == _DEVA_VIRAMA:
                out.append(base)                 # bare consonant, no vowel
                i += adv + 1
            elif nxt in _DEVA_MATRA:
                out.append(base + _DEVA_MATRA[nxt])
                i += adv + 1
            else:
                out.append(base + "a")           # inherent 'a'
                i += adv
        elif ch in _DEVA_INDEP_VOWEL:
            out.append(_DEVA_INDEP_VOWEL[ch]); i += 1
        elif ch in _DEVA_MATRA:                  # stray matra -> treat as vowel
            out.append(_DEVA_MATRA[ch]); i += 1
        elif ch in _DEVA_SIGN:
            out.append(_DEVA_SIGN[ch]); i += 1
        elif ch in _DEVA_DIGITS:
            out.append(_DEVA_DIGITS[ch]); i += 1
        else:
            out.append(ch); i += 1               # spaces / latin / punctuation
    return "".join(out)


# ---- IAST -> SLP1 ----------------------------------------------------------
# multi-char keys first; NFC-normalize input so diacritics are single code points.
_IAST_MAP = [
    ("kh", "K"), ("gh", "G"), ("ch", "C"), ("jh", "J"),
    ("ṭh", "W"), ("ḍh", "Q"), ("th", "T"), ("dh", "D"),
    ("ph", "P"), ("bh", "B"),
    ("ai", "E"), ("au", "O"),
    ("ā", "A"), ("ī", "I"), ("ū", "U"),
    ("ṛ", "f"), ("ṝ", "F"), ("ḷ", "x"), ("ḹ", "X"),
    ("ṃ", "M"), ("ṁ", "M"), ("ḥ", "H"), ("m̐", "~"), ("ã", "~"),
    ("ṅ", "N"), ("ñ", "Y"), ("ṭ", "w"), ("ḍ", "q"), ("ṇ", "R"),
    ("ś", "S"), ("ṣ", "z"), ("ḻ", "L"),
    ("a", "a"), ("i", "i"), ("u", "u"), ("e", "e"), ("o", "o"),
    ("k", "k"), ("g", "g"), ("c", "c"), ("j", "j"),
    ("t", "t"), ("d", "d"), ("n", "n"),
    ("p", "p"), ("b", "b"), ("m", "m"),
    ("y", "y"), ("r", "r"), ("l", "l"), ("v", "v"), ("w", "v"),
    ("s", "s"), ("h", "h"), ("'", "'"), ("’", "'"),
]


def _table_tokenize(s: str, table: list[tuple[str, str]]) -> str:
    """Greedy longest-match transliteration using an ordered (src, dst) table."""
    keys = sorted({k for k, _ in table}, key=len, reverse=True)
    lookup = dict(table)
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        for k in keys:
            if s.startswith(k, i):
                out.append(lookup[k]); i += len(k); break
        else:
            out.append(s[i]); i += 1              # passthrough (space, digit, |)
    return "".join(out)


def _iast_to_slp1(s: str) -> str:
    s = unicodedata.normalize("NFC", s).lower()
    return _table_tokenize(s, _IAST_MAP)


# ---- Harvard-Kyoto -> SLP1 (best effort) -----------------------------------
_HK_MAP = [
    ("lRR", "X"), ("RR", "F"), ("lR", "x"),
    ("kh", "K"), ("gh", "G"), ("ch", "C"), ("jh", "J"),
    ("Th", "W"), ("Dh", "Q"), ("th", "T"), ("dh", "D"),
    ("ph", "P"), ("bh", "B"), ("ai", "E"), ("au", "O"),
    ("A", "A"), ("I", "I"), ("U", "U"), ("R", "f"),
    ("G", "N"), ("J", "Y"), ("T", "w"), ("D", "q"), ("N", "R"),
    ("z", "S"), ("S", "z"), ("M", "M"), ("H", "H"),
    ("k", "k"), ("g", "g"), ("c", "c"), ("j", "j"),
    ("t", "t"), ("d", "d"), ("n", "n"), ("p", "p"), ("b", "b"),
    ("m", "m"), ("y", "y"), ("r", "r"), ("l", "l"), ("v", "v"),
    ("s", "s"), ("h", "h"), ("a", "a"), ("i", "i"),
    ("u", "u"), ("e", "e"), ("o", "o"), ("'", "'"),
]


def _hk_to_slp1(s: str) -> str:
    return _table_tokenize(s, _HK_MAP)


# ---- scheme detection ------------------------------------------------------
_IAST_DIACRITICS = set("āīūṛṝḷḹṃṁḥṅñṭḍṇśṣḻ")


def detect_scheme(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    for ch in t:
        if "ऀ" <= ch <= "ॿ":
            return "devanagari"
    low = t.lower()
    if any(ch in _IAST_DIACRITICS for ch in low):
        return "iast"
    # SLP1 vs HK/loose-romanization: SLP1 uses lone f/w/q/x/z/R/Y/N as
    # consonants and never uses digraphs. HK leans on capitals for retroflex
    # (T,D,N) + 'RR'/'lR'.
    if any(sub in text for sub in ("RR", "lR", "lRR")):
        return "hk"
    slp1_signals = set("fFxXwWqQzYL")
    if any(ch in slp1_signals for ch in text):
        return "slp1"
    # Loose romanization hallmarks: aspirate digraphs and ai/au diphthongs.
    # A real search box gets far more ITRANS/HK-style romanization than raw
    # SLP1, so treat these as HK (which handles Ch+h aspirates and ai/au).
    if re.search(r"(kh|gh|ch|jh|th|dh|ph|bh|sh|ai|au)", low):
        return "hk"
    # capital retroflex without SLP1 signals looks like HK
    if any(ch in "TDN" for ch in text):
        return "hk"
    return "slp1"                                  # plain ASCII, assume SLP1/typed


def to_slp1(text: str, scheme: str | None = None) -> str:
    """Convert `text` in `scheme` (or auto-detected) to canonical SLP1."""
    scheme = scheme or detect_scheme(text)
    if scheme == "devanagari":
        return _deva_to_slp1(text)
    if scheme == "iast":
        return _iast_to_slp1(text)
    if scheme == "hk":
        return _hk_to_slp1(text)
    return text                                    # already SLP1


# convenience: SLP1 -> Devanagari, for rendering results back to the reader.
# keep the FIRST (standard) mapping for each SLP1 value, so e/o render with the
# standard matras (े/ो) rather than the southern short-vowel signs (ॆ/ॊ).
def _first_reverse(m: dict) -> dict:
    out: dict = {}
    for k, v in m.items():
        out.setdefault(v, k)
    return out


_SLP1_TO_DEVA_CONS = {v: k for k, v in _DEVA_CONS.items()
                      if len(k) == 1 and v in set("kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzshL")}
_SLP1_TO_DEVA_VOWEL = _first_reverse(_DEVA_INDEP_VOWEL)
_SLP1_TO_DEVA_MATRA = _first_reverse(_DEVA_MATRA)
_SLP1_SIGN = {"M": "ं", "H": "ः", "~": "ँ", "'": "ऽ"}
_VOWELS = set("aAiIuUfFxXeEoO")


def slp1_to_deva(s: str) -> str:
    out: list[str] = []
    i, n = 0, len(s)
    prev_was_cons = False
    while i < n:
        ch = s[i]
        if ch in _SLP1_TO_DEVA_CONS:
            if prev_was_cons:
                out.append(_DEVA_VIRAMA)           # cluster: kill previous inherent a
            out.append(_SLP1_TO_DEVA_CONS[ch]); prev_was_cons = True; i += 1
        elif ch in _VOWELS:
            if prev_was_cons:
                if ch != "a":
                    out.append(_SLP1_TO_DEVA_MATRA.get(ch, ""))
                # 'a' after consonant = inherent, nothing to add
            else:
                out.append(_SLP1_TO_DEVA_VOWEL.get(ch, ch))
            prev_was_cons = False; i += 1
        elif ch in _SLP1_SIGN:
            out.append(_SLP1_SIGN[ch]); prev_was_cons = False; i += 1
        else:
            if prev_was_cons:
                out.append(_DEVA_VIRAMA)
            out.append(ch); prev_was_cons = False; i += 1
    if prev_was_cons:
        pass  # trailing inherent a is fine
    return "".join(out)
