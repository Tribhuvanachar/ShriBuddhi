"""
translit.py -- IAST/ISO-15919-style Roman Sanskrit to Devanagari, no dependencies.

GRETIL and several other sources give the mūla in Roman (IAST). The reader, search,
padaccheda and sandhi tools all work on Devanagari, so the importer converts at the door
(`kavya.schema.set_payload`) and a Roman mūla never reaches data/.

Handles: a/ā i/ī u/ū ṛ/ṝ ḷ/ḹ e ai o au, anusvāra ṃ/ṁ/ṃ, visarga ḥ, candrabindu m̐, the
consonant table incl. ṅ ñ ṭ ḍ ṇ ś ṣ, aspirates (kh gh ... bh), avagraha ' / ’, the
slash danda ('/' -> '।', '//' -> '॥'), digits. Anything it does not know passes through
unchanged. Round-trip checked against vidyut.lipi in tests/test_kavya_translit.py.
"""
from __future__ import annotations

import re
import unicodedata

_VOWELS = {"a": ("अ", ""), "ā": ("आ", "ा"), "i": ("इ", "ि"), "ī": ("ई", "ी"),
           "u": ("उ", "ु"), "ū": ("ऊ", "ू"), "ṛ": ("ऋ", "ृ"), "ṝ": ("ॠ", "ॄ"),
           "ḷ": ("ऌ", "ॢ"), "ḹ": ("ॡ", "ॣ"), "e": ("ए", "े"), "ai": ("ऐ", "ै"),
           "o": ("ओ", "ो"), "au": ("औ", "ौ")}
_CONS = {"kh": "ख", "gh": "घ", "ch": "छ", "jh": "झ", "ṭh": "ठ", "ḍh": "ढ", "th": "थ",
         "dh": "ध", "ph": "फ", "bh": "भ",
         "k": "क", "g": "ग", "ṅ": "ङ", "c": "च", "j": "ज", "ñ": "ञ", "ṭ": "ट", "ḍ": "ड",
         "ṇ": "ण", "t": "त", "d": "द", "n": "न", "p": "प", "b": "ब", "m": "म",
         "y": "य", "r": "र", "l": "ल", "v": "व", "ś": "श", "ṣ": "ष", "s": "स", "h": "ह"}
_DIGITS = dict(zip("0123456789", "०१२३४५६७८९"))
VIRAMA = "्"

_TOKEN = re.compile("|".join(sorted(
    list(_VOWELS) + list(_CONS) + ["ṃ", "ṁ", "ḥ", "m̐", "'", "’", "ऽ"], key=lambda s: -len(s))))


def _norm(s):
    s = unicodedata.normalize("NFC", s)
    # 'ṃ' may arrive as m + U+0323 (composed above) or m + U+0307; both are composed by NFC
    # where a precomposed form exists. Fold the stragglers.
    return s.replace("ṁ", "ṃ").replace("m̐", "ṃ")


def is_roman(text):
    lat = sum(1 for c in text if c.isalpha() and ord(c) < 0x250)
    dev = sum(1 for c in text if "ऀ" <= c <= "ॿ")
    return lat > dev and lat > 0


def to_devanagari(text):
    """Convert a Roman text; lines that start with '%' are GRETIL's own metre/editorial
    annotations (Kathāsaritsāgara has thousands), not Sanskrit, and pass through unchanged."""
    if "\n" in text:
        return "\n".join(l if l.lstrip().startswith("%") else to_devanagari(l) for l in text.split("\n"))
    if text.lstrip().startswith("%"):
        return text
    s = _norm(text)
    s = re.sub(r"(?<=\w)\s+(?=['’])", "", s)   # "so 'pi" is one word, सोऽपि
    s = s.replace("//", "॥").replace(" / ", " । ")
    s = re.sub(r"/\s*$", "।", s)
    out = []
    i, n = 0, len(s)
    pending = False          # last emitted thing is a bare consonant (virama-able)
    while i < n:
        ch = s[i]
        low = ch.lower() if ch not in "ṬḌṆŚṢṚṜḶḸṂḤṄÑ" else ch.lower()
        m = _TOKEN.match(s, i) if low == ch else _TOKEN.match(s[:i] + low + s[i + 1:], i)
        tok = m.group(0) if m else None
        if tok in _VOWELS:
            ind, mat = _VOWELS[tok]
            if pending:
                out.append(mat)
            else:
                out.append(ind)
            pending = False
            i += len(tok)
        elif tok in _CONS:
            if pending:
                out.append(VIRAMA)
            out.append(_CONS[tok])
            pending = True
            i += len(tok)
        elif tok == "ṃ":
            if pending:
                pending = False
            out.append("ं")
            i += 1
        elif tok == "ḥ":
            pending = False
            out.append("ः")
            i += 1
        elif tok in ("'", "’") and (out or True):
            if pending:
                out.append(VIRAMA)
                pending = False
            out.append("ऽ")
            i += 1
        elif ch in _DIGITS:
            if pending:
                out.append(VIRAMA)
                pending = False
            out.append(_DIGITS[ch])
            i += 1
        else:
            if pending:
                out.append(VIRAMA)
                pending = False
            out.append(ch)
            i += 1
    if pending:
        out.append(VIRAMA)
    return "".join(out)
