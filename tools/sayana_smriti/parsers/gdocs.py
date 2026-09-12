"""
gdocs.py — reader for the UT-Austin / Olivelle Dharmaśāstra transcriptions,
which are published as public Google Docs.

Hub: https://sites.utexas.edu/sanskrit/resources/dharmasastra/

This is the single highest-value route for Sanskrit commentaries that exist
nowhere else as e-text: Medhātithi, Kullūka, Govindarāja, Mitākṣarā,
Viśvarūpa's Bālakrīḍā, Haradatta, and — the one that matters most for this
project — the **Parāśara-Mādhavīya**, i.e. Sāyaṇa-Mādhava's own commentary on
the Parāśara Smṛti.

Fetch pattern (verified):
    https://docs.google.com/document/d/{ID}/export?format=txt
    -> 302 to doc-XX-XX-docstext.googleusercontent.com; follow redirects.

Format: plain UTF-8 IAST. Mūla verses close with "|| 1.1 ||"; the commentary
is unmarked prose between verses. The colour-coding that distinguishes mūla
from bhāṣya in the original document is LOST in format=txt — if you need that
split, fetch format=html and look at the span styles instead.

Caveat carried through from the source: UT-Austin states that "almost none of
the transcriptions on this site have been proofread." Everything imported from
here is tagged provenance="ut-austin-draft" so it can be re-sourced later.
"""

from __future__ import annotations

import re
from typing import Dict, List

from common import clean

EXPORT = "https://docs.google.com/document/d/{doc_id}/export?format={fmt}"

# "|| 1.1 ||" / "॥ 1.1 ॥" / "|| 1.1cd ||"
VERSE_TAG = re.compile(r"[|॥]{1,2}\s*(\d+)\s*\.\s*(\d+)\s*[a-z]{0,2}\s*[|॥]{1,2}")


def export_url(doc_id: str, fmt: str = "txt") -> str:
    return EXPORT.format(doc_id=doc_id, fmt=fmt)


def parse(text: str) -> List[Dict]:
    """-> [{'chapter', 'verse', 'text'}] where `text` is everything between the
    previous verse tag and this one (mūla + its commentary, undifferentiated)."""
    out: List[Dict] = []
    prev = 0
    for m in VERSE_TAG.finditer(text or ""):
        body = clean(text[prev:m.start()])
        prev = m.end()
        if body:
            out.append({"chapter": int(m.group(1)), "verse": int(m.group(2)), "text": body})
    return out


def split_mula_and_commentary(block: str):
    """Heuristic split for a `parse()` block. The mūla is the leading metrical
    portion — typically the first 1–3 lines, ending at a daṇḍa. Anything after
    is commentary. Returns (mula, commentary); commentary may be ''."""
    b = clean(block)
    if not b:
        return "", ""
    m = re.search(r"[|॥।]\s*\n", b)
    if m:
        return clean(b[:m.end()]), clean(b[m.end():])
    lines = b.split("\n")
    if len(lines) > 2:
        return clean("\n".join(lines[:2])), clean("\n".join(lines[2:]))
    return b, ""
