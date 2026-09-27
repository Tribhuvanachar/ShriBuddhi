#!/usr/bin/env python3
"""The parts every staged-OCR segmenter in this repository needs.

Written after landing Rukmiṇīśa Vijaya, the Veṅkaṭeśa Māhātmya and the Vaidika
Svara Prakaraṇam, because the same four mistakes were available in each and
three of them were actually made at least once. Each is fixed HERE so the next
work inherits the fix instead of rediscovering it.

  1. THERE ARE TWO DANDA FORMS. A verse number is written ॥ N ॥ with U+0965
     DEVANAGARI DOUBLE DANDA, and also ।। N ।। with two U+0964 single dandas.
     In the Veṅkaṭeśa Māhātmya 1,280 markers are the first and 584 the second;
     matching only the first lost 31% of them and did not look like loss -- one
     adhyāya simply read as a part of the book with little commentary.

  2. A NUMBER IN PARENTHESES BELONGS TO ANOTHER TEXT. `(ಫಿಟ್ ಸೂತ್ರ-೮೫)` cites
     the Phiṭ Sūtras. The guard has to be the parentheses and not the citing
     word: `( ಫಿಟ್ ಸೂತ್ರ ) ಸೂತ್ರ - ೪೧,` is a citation carrying no number
     followed by the book's own sūtra 41, and excluding on the word lost it.

  3. A BLOCK OFTEN HOLDS SEVERAL UNITS. p456 of the Veṅkaṭeśa Māhātmya carries
     verses 5 through 11 in one 622-character block and only the last marker
     closes it, so six of the seven are unreachable without splitting.

  4. A NUMBER FAR BELOW THE RUNNING MAXIMUM IS A QUOTATION, not a restart. The
     Pāṣaṇḍakhaṇḍana quotes verses 13 and 17 again on pages 37 and 39, in the
     middle of a run that has reached 92 and 96 and goes on rising.

Digits are read in Devanāgarī, Kannada and ASCII, because the corpus has all
three and a Kannada book's numbering looks like nothing at all to a
Devanāgarī-only pattern.
"""

from __future__ import annotations

import glob
import json
import os
import re

DEV_DIGITS = "०१२३४५६७८९"
KAN_DIGITS = "೦೧೨೩೪೫೬೭೮೯"
DIGITS = str.maketrans(DEV_DIGITS + KAN_DIGITS, "0123456789" * 2)
ANY_DIGIT = f"[0-9{DEV_DIGITS}{KAN_DIGITS}]"

# BOTH danda forms -- see (1) in the module docstring.
DD = r"(?:॥|।।)"
MARKER = re.compile(DD + r"\s*(" + ANY_DIGIT + r"+)\s*" + DD)
# The closing form, which may drop the trailing danda: ...शरणं विरिञ्चम् ॥ ११
CLOSER = re.compile(DD + r"\s*(" + ANY_DIGIT + r"+)\s*" + DD + r"?\s*[।॥]?\s*$")

BLOCK = re.compile(r'<(\w+)[^>]*data-layout="([^"]+)"[^>]*>(.*?)</\1>', re.S)
# Layout kinds that are page furniture rather than text.
FURNITURE = ("page-number", "footer", "image")


def untag(html: str) -> str:
    """HTML to text, keeping <br> as the line break it stands for."""
    return re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>", "\n", html)).strip()


def flat(text: str) -> str:
    return " ".join(text.split())


def to_int(s: str) -> int:
    return int(s.translate(DIGITS))


def load_sarvam(staged_dir: str) -> dict[int, str]:
    """Every Sarvam page that came back, as layout-tagged HTML.

    Dispatch ranges overlap -- the Veṅkaṭeśa Māhātmya was fetched as 163-702
    alongside 203-402 and 403-602 -- so a page appears in several files and the
    first delivery wins. A page can be `ok` and still empty: p111 of the Vaidika
    Svara Prakaraṇam is a blank leaf, correctly returned blank.
    """
    pages: dict[int, str] = {}
    for path in sorted(glob.glob(os.path.join(staged_dir, "*.json"))):
        if "vision" in os.path.basename(path).lower():
            continue
        try:
            doc = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        for page in doc.get("pages") or []:
            html = page.get("html") or page.get("text") or ""
            if page.get("ok") and html.strip():
                pages.setdefault(page["page"], html)
    return pages


def load_vision(staged_dir: str) -> dict[int, str]:
    """The Vision pass -- plain `text`, no `ok` -- for checking a doubtful
    reading against a second witness."""
    out: dict[int, str] = {}
    for path in sorted(glob.glob(os.path.join(staged_dir, "*vision*.json"))):
        try:
            doc = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        for page in doc.get("pages") or []:
            if (page.get("text") or "").strip():
                out.setdefault(page["page"], page["text"])
    return out


def paren_spans(text: str) -> list[tuple[int, int]]:
    """The (…) ranges in a string -- see (2) in the module docstring."""
    out, start = [], None
    for i, ch in enumerate(text):
        if ch in "(（[":
            start = i
        elif ch in ")）]" and start is not None:
            out.append((start, i))
            start = None
    return out


def markers(text: str, skip_parenthesised: bool = True) -> list[tuple[int, int, int]]:
    """Every ॥ N ॥ in the text as (start, end, number), citations left out."""
    spans = paren_spans(text) if skip_parenthesised else []
    return [(m.start(), m.end(), to_int(m.group(1)))
            for m in MARKER.finditer(text)
            if not any(a < m.start() < b for a, b in spans)]


def closing_number(text: str) -> int | None:
    """The number that CLOSES this block, if any."""
    m = CLOSER.search(text.rstrip())
    return to_int(m.group(1)) if m else None


def split_at_markers(text: str, low: int = 10, high: int = 700) -> list[str] | None:
    """Cut a block holding several units at its internal markers -- see (3).

    Returns None when the block holds at most one unit, or when a piece would
    fall outside `low`..`high`, in which case it is left whole: a block that
    does not split into unit-shaped pieces is not a run of units.
    """
    cuts = markers(text)
    if len(cuts) < 2 and not (
            len(cuts) == 1 and cuts[0][1] < len(text.rstrip()) - 2):
        return None
    spans, prev = [], 0
    for start, end, _ in cuts:
        spans.append(text[prev:end])
        prev = end
    tail = text[prev:].strip()
    if tail:
        spans.append(tail)
    pieces = [s.strip() for s in spans if s.strip()]
    if not all(low <= len(s) <= high for s in pieces[:len(cuts)]):
        return None
    return pieces


def is_quotation(number: int, running_max: int, tolerance: int = 1) -> bool:
    """Whether a number is a quotation rather than this text's own -- see (4).

    A text's numbering rises. One that drops far below the highest reached so
    far, in a run that then carries on rising, is the commentary quoting an
    earlier verse. `tolerance` allows the ordinary case of a verse and its
    commentary both closing on the same number.
    """
    return number < running_max - tolerance


def page_report(pages: dict[int, str]) -> dict:
    """Pages delivered, their range, and any gap in it."""
    if not pages:
        return {"pages": 0, "page_range": [], "page_gaps": []}
    lo, hi = min(pages), max(pages)
    return {"pages": len(pages), "page_range": [lo, hi],
            "page_gaps": [n for n in range(lo, hi + 1) if n not in pages]}


def read_stream(pages: dict[int, str], keep: tuple[str, ...] | None = None,
                skip: tuple[str, ...] = FURNITURE,
                first_page: int = 0) -> list[dict]:
    """The book as one ordered list of text blocks."""
    out: list[dict] = []
    for page in sorted(pages):
        if page < first_page:
            continue
        for m in BLOCK.finditer(pages[page]):
            kind, body = m.group(2), untag(m.group(3))
            if kind in skip or not body:
                continue
            if keep is not None and kind not in keep:
                continue
            out.append({"page": page, "kind": kind, "text": flat(body)})
    return out
