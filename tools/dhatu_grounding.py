"""dhatu_grounding.py -- looks up REAL source text for a dhatu (root) from
two places, for gemini_dhatu_lexicon.py to ground its generation in instead
of asking Gemini to invent content from scratch:

  1. This repo's own dge/data/vedanga/vyakarana/vritti/<id>.json (already
     integrated, GPL-2.0 from samsaadhanii/scl) -- real quoted text from
     Madhaviya Dhatuvritti, Kshiratarangini, Dhatupradipa. Uses the
     "relevant" (root-form-matching) nodes tools/build_vritti_nodes.py
     already tagged, same filter dhatu.js's UI defaults to, capped in
     length since a handful of roots (bhu especially) carry a 90KB+ wall
     of general shastra discussion alongside the actually-relevant part.

  2. A local build of bhumandala-kosha-data's dictionary corpus (built via
     that repo's own build_koshas.py against the indic-dict source repos --
     NOT checked into this repo, matching that project's own reasoning for
     keeping the corpus out of the 1GB app repo budget). Pass its build
     root via --kosha-build. Looks up macdonell/capeller/mw-1872/apte-1957
     (concise real dictionary senses) plus the same three vritti works in
     their headword-keyed form (a second, independently-digitized copy of
     the same underlying texts -- used as a fallback when this repo's own
     vritti/ has no entry for a root, or when its samsaadhanii/scl copy is
     itself missing that specific vritti).

No network calls -- everything here is local file lookup.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

VRITTI_LABELS = {
    "madhaviya": "Mādhavīya Dhātuvṛtti (Sāyaṇa)",
    "kshira": "Kṣīrataraṅgiṇī (Kṣīrasvāmin)",
    "dhatupradipa": "Dhātupradīpa (Maitreyarakṣita)",
}
KOSHA_VRITTI_SLUGS = {
    "madhaviya": "madhaviya-dhatu-vritti",
    "kshira": "kshiratarangini",
    "dhatupradipa": "dhatupradipa",
}
KOSHA_DICT_LABELS = {
    "macdonell": "Macdonell's Sanskrit-English Dictionary",
    "capeller-sanskrit-english": "Capeller's Sanskrit-English Dictionary",
    "mw-1872": "Monier-Williams Sanskrit-English Dictionary (1872)",
    "apte-1957": "Apte's Practical Sanskrit-English Dictionary (1957)",
}

VRITTI_CAP = 4000       # chars per vritti source fed into one prompt
DICT_CAP = 1500         # chars per dictionary sense fed into one prompt

_MARKERS = re.compile(r"[~\\^]|\d")


def strip_markers(slp1: str) -> str:
    """Drops SLP1 accent/it-marker punctuation (~, \\, ^, digits) so a
    dhatupatha citation form and a dictionary headword can be compared."""
    return _MARKERS.sub("", slp1 or "")


def _fold(slp1: str) -> str:
    """Mirrors bhumandala-kosha-data's kosha_core.fold() -- long vowels to
    short, sibilants merged, anusvara/anunasika merged, doubled letters
    collapsed -- so a lookup survives minor headword-vs-citation spelling
    differences the same way that corpus's own cross-dictionary index does."""
    t = (slp1 or "").replace("'", "")
    for a, b in (("A", "a"), ("I", "i"), ("U", "u"), ("F", "f"), ("X", "x")):
        t = t.replace(a, b)
    for s in ("S", "z"):
        t = t.replace(s, "s")
    t = t.replace("M", "n").replace("~", "n")
    return re.sub(r"(.)\1+", r"\1", t)


def load_vritti_relevant(vritti_dir: Path, dhatu_id: str) -> dict[str, str]:
    """Returns {source: text} for this repo's own already-integrated vritti
    file, preferring the relevant-node-filtered text (same default view as
    dhatu.js) and capping length. Empty dict if the file doesn't exist."""
    fp = vritti_dir / f"{dhatu_id}.json"
    if not fp.exists():
        return {}
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out = {}
    for v in data.get("vrittis", []):
        source = v.get("source")
        text = v.get("text", "")
        nodes = v.get("nodes") or []
        if nodes:
            relevant = [text[n[0]:n[1]] for n in nodes if "r" in (n[2] or "")]
            text = "\n".join(relevant) if relevant else text
        text = text.strip()
        if text:
            out[source] = text[:VRITTI_CAP]
    return out


class KoshaIndex:
    """Loads a handful of bhumandala-kosha-data dictionary shards into
    memory, keyed by marker-stripped, folded SLP1 headword. Built once per
    run (tools/gemini_dhatu_lexicon.py's --kosha-build), reused per-root."""

    def __init__(self, build_root: Path | None, slugs: list[str]):
        self.by_key: dict[str, list[tuple[str, str]]] = {}
        if not build_root:
            return
        for slug in slugs:
            self._load_slug(build_root, slug)

    def _load_slug(self, build_root: Path, slug: str) -> None:
        for cat_dir in ("sanskrit_sanskrit", "sanskrit_english"):
            e_dir = build_root / "data" / "koshas" / cat_dir / slug / "e"
            if not e_dir.is_dir():
                continue
            for shard in e_dir.glob("*.json"):
                try:
                    shard_data = json.loads(shard.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                for entries in shard_data.values():
                    for entry in entries:
                        hw_slp1 = entry.get("headword_slp1", "")
                        key = _fold(strip_markers(hw_slp1))
                        if not key:
                            continue
                        senses = entry.get("senses") or []
                        if not senses:
                            continue
                        gloss = senses[0].get("gloss", "").strip()
                        if gloss:
                            self.by_key.setdefault(key, []).append((slug, gloss[:DICT_CAP]))
            return  # found the category that has this slug; don't scan the other

    def lookup(self, dhatu_slp: str) -> list[tuple[str, str]]:
        key = _fold(strip_markers(dhatu_slp))
        return self.by_key.get(key, [])


def build_grounding(entry: dict, vritti_dir: Path, kosha_vritti: KoshaIndex | None,
                     kosha_dict: KoshaIndex | None) -> tuple[str, list[str]]:
    """Returns (grounding_text, sources_used) for one dhatupatha entry.
    grounding_text is "" if nothing real was found for this root -- callers
    should fall back to ungrounded generation in that case, not claim a
    source that isn't there."""
    parts = []
    sources_used = []

    own_vritti = load_vritti_relevant(vritti_dir, entry["id"])
    for source, text in own_vritti.items():
        label = VRITTI_LABELS.get(source, source)
        parts.append(f"--- {label} (real quoted text) ---\n{text}")
        sources_used.append(label)

    if kosha_vritti:
        for source, slug in KOSHA_VRITTI_SLUGS.items():
            if source in own_vritti:
                continue  # already have this one from our own integrated copy
            hits = [g for s, g in kosha_vritti.lookup(entry.get("dhatu_slp", "")) if s == slug]
            if hits:
                label = VRITTI_LABELS[source]
                parts.append(f"--- {label} (real quoted text) ---\n{hits[0][:VRITTI_CAP]}")
                sources_used.append(label)

    if kosha_dict:
        seen_slugs = set()
        for slug, gloss in kosha_dict.lookup(entry.get("dhatu_slp", "")):
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            label = KOSHA_DICT_LABELS.get(slug, slug)
            parts.append(f"--- {label} (real dictionary entry) ---\n{gloss}")
            sources_used.append(label)

    return ("\n\n".join(parts), sources_used)
