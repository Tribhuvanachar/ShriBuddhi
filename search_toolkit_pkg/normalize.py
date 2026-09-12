"""
normalize.py — the heart of Sanskrit-aware fuzzy search.

Strategy (validated by VedaWeb, DCS, Ambuda): do the Sanskrit-specific work at
INDEX time by folding known equivalence classes into a canonical key, so that by
the time the search engine sees the text, the only remaining "fuzziness" is
ordinary typos — which any engine handles natively.

We produce THREE representations of every unit of text, in decreasing strictness:

  1. slp1   — exact canonical SLP1 (diacritics preserved). Exact/near-exact hits.
  2. pkey   — "phonetic key": folds the SAFE equivalence classes that reflect how
              the same word is legitimately spelled/pronounced differently
              (anusvara<->nasal, sibilants, vowel length, avagraha, gemination,
              visarga). High precision.
  3. ckey   — "coarse key": pkey PLUS lossy folds (retroflex->dental, aspiration,
              voicing). High recall, lower precision — used as a fallback tier.

Rank matches: exact slp1 > pkey > ckey. Store all three; search all three.
"""
from __future__ import annotations
import re

# ---- character classes in SLP1 ---------------------------------------------
_NASALS = set("MNYRnm~")          # anusvara, candrabindu, and the five class nasals
_SIBILANTS = set("Szs")           # ś ṣ s
_LONG_TO_SHORT = str.maketrans({"A": "a", "I": "i", "U": "u", "F": "f", "X": "x"})
# vocalic r/l -> plain r/l: users overwhelmingly type 'r'/'l' for ṛ/ḷ
_VOCALIC_FOLD = str.maketrans({"f": "r", "x": "l"})
# retroflex -> dental (lossy)
_RETRO_TO_DENTAL = str.maketrans({"w": "t", "W": "T", "q": "d", "Q": "D", "R": "n", "z": "s"})
# aspiration fold (lossy): remove the aspirate distinction
_DEASPIRATE = str.maketrans({"K": "k", "G": "g", "C": "c", "J": "j",
                             "W": "w", "Q": "q", "T": "t", "D": "d",
                             "P": "p", "B": "b"})
# voicing fold (very lossy): collapse voiced/unvoiced stops
_DEVOICE = str.maketrans({"g": "k", "j": "c", "q": "w", "d": "t", "b": "p"})

_DOUBLE = re.compile(r"(.)\1+")


def _collapse_geminates(s: str) -> str:
    return _DOUBLE.sub(r"\1", s)


def phonetic_key(slp1: str) -> str:
    """pkey — safe folds only. Two spellings a scholar would call 'the same word'
    collapse to the same key; genuinely different words stay distinct."""
    s = slp1
    s = s.replace("'", "")                 # avagraha marks elided initial 'a'
    s = s.translate(_LONG_TO_SHORT)        # vowel length is often inconsistent
    s = s.translate(_VOCALIC_FOLD)         # ṛ/ḷ (f/x) -> r/l
    s = "".join("n" if c in _NASALS else c for c in s)   # nasal class -> n
    s = "".join("s" if c in _SIBILANTS else c for c in s)  # ś/ṣ/s -> s
    s = s.replace("H", "")                 # visarga often dropped in casual input
    s = _collapse_geminates(s)             # -tt- / -kk- gemination
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def coarse_key(slp1: str) -> str:
    """ckey — pkey plus lossy folds. Casts a wide net for high recall."""
    s = phonetic_key(slp1)
    s = s.translate(_RETRO_TO_DENTAL)      # retroflex -> dental
    s = s.translate(_DEASPIRATE)           # drop aspiration
    s = s.translate(_DEVOICE)              # collapse voicing
    s = _collapse_geminates(s)             # folds may create new doubles
    return s


def trigrams(s: str, n: int = 3) -> set[str]:
    """Character n-grams over a padded string. On SLP1 these are *phonemic*
    n-grams (1 char = 1 phoneme), which is why they work so well here."""
    s = s.replace(" ", "")
    if not s:
        return set()
    padded = f"{'^'}{s}{'$'}"
    if len(padded) < n:
        return {padded}
    return {padded[i:i + n] for i in range(len(padded) - n + 1)}


def keys_for(slp1: str) -> dict:
    """Bundle all searchable representations for a unit of text."""
    pk = phonetic_key(slp1)
    ck = coarse_key(slp1)
    return {
        "slp1": slp1,
        "pkey": pk,
        "ckey": ck,
        "pkey_trigrams": trigrams(pk),
        "ckey_trigrams": trigrams(ck),
    }
