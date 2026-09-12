"""Shared helpers for the DGE Kavya importers.

No third-party imports: this module must run inside a bare GitHub Actions
python step as well as inside Colab.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata

# --------------------------------------------------------------------------
# Devanagari / IAST
# --------------------------------------------------------------------------

DEVA_DIGITS = "०१२३४५६७८९"
_DEVA_DIGIT_MAP = {d: str(i) for i, d in enumerate(DEVA_DIGITS)}

DEVA_RANGE = (0x0900, 0x097F)


def deva_to_ascii_digits(s: str) -> str:
    """'१.१' -> '1.1'. Leaves non-Devanagari digits alone."""
    return "".join(_DEVA_DIGIT_MAP.get(ch, ch) for ch in s)


def ascii_to_deva_digits(s: str) -> str:
    return "".join(DEVA_DIGITS[int(ch)] if ch.isdigit() else ch for ch in s)


def has_devanagari(s: str) -> bool:
    return any(DEVA_RANGE[0] <= ord(ch) <= DEVA_RANGE[1] for ch in s)


def strip_danda(s: str) -> str:
    return s.replace("॥", " ").replace("।", " ")


_HWS = re.compile(r"[^\S\n]+")     # horizontal whitespace only
_NL = re.compile(r"\n{2,}")


def norm_ws(s: str) -> str:
    """Collapse horizontal whitespace but PRESERVE line breaks.

    Verse padas arrive as separate lines and the reader renders the mula with
    white-space:pre-wrap, so flattening newlines here would silently run the
    padas of every sloka together.
    """
    s = _HWS.sub(" ", (s or ""))
    s = _NL.sub("\n", s)
    return "\n".join(line.strip() for line in s.split("\n")).strip()


def fingerprint(s: str) -> str:
    """Whitespace/punctuation-insensitive fingerprint used for dedup and for
    the substring-repair check in merge.py."""
    s = unicodedata.normalize("NFC", s or "")
    s = strip_danda(s)
    return re.sub(r"[\s​‌‍.,;:'\"()\[\]{}|/\\-]+", "", s)


# --------------------------------------------------------------------------
# Ids and slugs
# --------------------------------------------------------------------------

_SLUG_BAD = re.compile(r"[^a-z0-9]+")


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = _SLUG_BAD.sub("_", s.lower()).strip("_")
    return s or "untitled"


def make_unit_id(*parts) -> str:
    """Canonical DGE unit id: dotted ASCII numerals, e.g. '1.1' or '2.14.3'."""
    out = []
    for p in parts:
        if p is None or p == "":
            continue
        p = deva_to_ascii_digits(str(p)).strip()
        p = p.strip(".")
        if p:
            out.append(p)
    return ".".join(out)


def split_ref(ref: str):
    """'1.164.1' -> ('1','164','1'). Tolerates Devanagari digits and commas
    (GRETIL writes 'ChUp_1,1.1')."""
    ref = deva_to_ascii_digits(ref or "")
    ref = ref.replace(",", ".")
    return tuple(p for p in ref.split(".") if p != "")


# --------------------------------------------------------------------------
# IO
# --------------------------------------------------------------------------

def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj, indent=1):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=indent)
        fh.write("\n")
    os.replace(tmp, path)


def log(msg):
    print(msg, flush=True)
