"""
reference_resolution — local-first citation/quotation resolver for the DGE corpus.

Context: this exists because of a reviewed AI-architecture proposal (see
dge/PENDING.md, "Reference Resolution Engine") whose central point is that
Gemini must not be asked to invent or guess citations the corpus can already
confirm. This module IS the "search DGE" step that proposal calls for. It
never calls Gemini and makes no network calls -- callers (e.g.
tools/gemini_enrich.py) feed it Gemini's candidate references and get back a
confidence-tiered verdict grounded in the corpus actually on disk.

Resolution-priority ladder this module implements:

  1. Exact DGE canonical match -- an explicit {target_slug, unit_id} hint,
     the same shape the corpus's own `references: [{target, unit_id, note}]`
     schema field already uses (see dge/data/schemas.json).
  2. DGE lexical match -- quoted text found near-verbatim (SLP1/phonetic key)
     in a scoped search.
  3. Fuzzy DGE match -- quoted text found via trigram/edit-distance
     similarity, below the lexical-match threshold.

Priorities 4 (Gemini's own proposed reference) and 6-7 (external search,
human review) are the caller's responsibility; priority 5 ("search DGE using
Gemini's proposal") is just `resolve_text()` with `hint_slugs` derived from
Gemini's free-text guess -- see `resolve()`.

Scope: `DEFAULT_SEARCH_SCOPE` is a small, curated set of texts likely to be
quoted (Bhagavad Gita chapters today), not the full ~1 GB corpus. Building an
in-memory SanskritIndex over every populated grantha on every run does not
scale; a corpus-wide version of this should reuse the prebuilt static trigram
index under dge/search_index/ (today queried only from dge/js/dge-search.js --
see dge/SEARCH_ARCHITECTURE.md) instead of re-indexing from scratch. That is
tracked as a follow-up, not solved here.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DGE_DIR = _REPO_ROOT / "dge"
if str(_DGE_DIR) not in sys.path:
    sys.path.insert(0, str(_DGE_DIR))

from search_toolkit_pkg.index import SanskritIndex  # noqa: E402

DEFAULT_SEARCH_SCOPE = tuple(
    f"itihasa/bhagavad_gita/adhyaya_{n:02d}" for n in range(1, 19)
) + (
    "vedanga/vyakarana/ashtadhyayi/sutrapatha",
)


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Quote-mark and stray edge punctuation a caller's "verbatim quoted span"
# may include (e.g. a real Gemini run returning `'कर्तृकरणयोस्तृतीया'`
# rather than just the sutra text) -- none of this appears in the corpus's
# own stored text, so left in, it only dilutes the match against a clean
# corpus string. Observed directly in a real (non-mock) enrichment run: an
# exact sutra quote wrapped in quote marks scored 0.517 ("possible")
# instead of 1.0 ("verified") until this stripping was added.
_EDGE_PUNCT = "‘’“”'\"।॥.,;:!? \t\n"


def _normalize_query(s: str) -> str:
    return s.strip(_EDGE_PUNCT)


def _iter_units(data: dict):
    """Yield (unit_id, primary_text) pairs, covering both corpus data shapes:
    catalog ({schema, items:[...]}, flat or with nested per-verse `shlokas`)
    and legacy ({metadata, shlokas:{n:{...}}})."""
    items = data.get("items")
    if isinstance(items, list):
        for item in items:
            uid = item.get("id")
            if not uid:
                continue
            shlokas = item.get("shlokas")
            if isinstance(shlokas, list):
                # itihasa/purana shape: one item per adhyaya/skandha, verses nested
                for sh in shlokas:
                    n = sh.get("number")
                    if n is None:
                        continue
                    text = sh.get("sanskrit_text") or ""
                    if text:
                        yield f"{uid}:{n}", text
                continue
            text = item.get("sanskrit_text") or item.get("samhita_patha") or item.get("sa") or ""
            if text:
                yield uid, text
        return
    shlokas = data.get("shlokas")
    if isinstance(shlokas, dict):
        for n, sh in shlokas.items():
            text = sh.get("sanskrit_text") or sh.get("sa") or ""
            if text:
                yield str(n), text


@dataclass(frozen=True)
class GranthaInfo:
    slug: str
    path: Path
    title: str
    populated: bool


class GranthaRegistry:
    """Slug <-> data.json path lookup, built from dge/data/library.json.

    `slug` is the grantha's folder path relative to dge/data/ (no trailing
    /data.json) -- the same convention `references[].target` already uses
    elsewhere in the corpus.
    """

    def __init__(self, data_root: Optional[Path] = None, library_path: Optional[Path] = None):
        self.data_root = Path(data_root) if data_root is not None else (_DGE_DIR / "data")
        self.library_path = Path(library_path) if library_path is not None else (self.data_root / "library.json")
        self._by_slug: dict[str, GranthaInfo] = {}
        self._load()

    def _load(self) -> None:
        lib = _load_json(self.library_path)
        prefix = "dge/data/"
        suffix = "/data.json"
        for g in lib.get("granthas", []):
            raw_path = g.get("path", "")
            slug = raw_path
            has_prefix = slug.startswith(prefix)
            if has_prefix:
                slug = slug[len(prefix):]
            if slug.endswith(suffix):
                slug = slug[: -len(suffix)]
            # Resolve relative to THIS registry's data_root (so a synthetic
            # library.json under a tempdir resolves within that tempdir, not
            # against the real repo) rather than assuming dge/data/ always
            # means the real corpus on disk.
            resolved_path = self.data_root / slug / "data.json" if has_prefix else _REPO_ROOT / raw_path
            self._by_slug[slug] = GranthaInfo(
                slug=slug,
                path=resolved_path,
                title=g.get("title", ""),
                populated=bool(g.get("populated")),
            )

    def get(self, slug: str) -> Optional[GranthaInfo]:
        return self._by_slug.get(slug)

    def find_by_title(self, title_fragment: str) -> list[GranthaInfo]:
        """Loose title search -- turns a Gemini free-text guess like 'Bhagavad
        Gita' into a candidate slug list to search first (priority 5)."""
        needle = title_fragment.strip().lower()
        if not needle:
            return []
        return [info for info in self._by_slug.values() if needle in info.title.lower()]


@dataclass
class ResolvedReference:
    status: str  # "verified" | "possible" | "unresolved"
    confidence: float
    resolution_method: str  # "exact_canonical" | "lexical_search" | "fuzzy_search" | "unresolved"
    target_slug: Optional[str] = None
    target_title: Optional[str] = None
    target_unit_id: Optional[str] = None
    matched_text: Optional[str] = None
    score: float = 0.0
    scope_searched: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "resolution_method": self.resolution_method,
            "target_slug": self.target_slug,
            "target_title": self.target_title,
            "target_unit_id": self.target_unit_id,
            "matched_text": self.matched_text,
            "score": self.score,
            "scope_searched": self.scope_searched,
        }


class ReferenceResolver:
    """Resolves candidate references against the on-disk DGE corpus."""

    def __init__(
        self,
        registry: Optional[GranthaRegistry] = None,
        search_scope: Optional[Iterable[str]] = None,
    ):
        self.registry = registry or GranthaRegistry()
        self.search_scope = list(search_scope) if search_scope is not None else list(DEFAULT_SEARCH_SCOPE)
        self._index_cache: dict[str, Optional[SanskritIndex]] = {}

    def resolve_exact(self, target_slug: str, unit_id: str) -> ResolvedReference:
        """Priority 1: an explicit {target_slug, unit_id} hint -- confirm the
        unit actually exists in that grantha's data.json."""
        info = self.registry.get(target_slug)
        if info is None or not info.path.exists():
            return ResolvedReference(
                status="unresolved", confidence=0.0, resolution_method="exact_canonical",
                target_slug=target_slug, target_unit_id=unit_id,
            )
        data = _load_json(info.path)
        for uid, text in _iter_units(data):
            if uid == unit_id:
                return ResolvedReference(
                    status="verified", confidence=1.0, resolution_method="exact_canonical",
                    target_slug=target_slug, target_title=info.title,
                    target_unit_id=uid, matched_text=text, score=1.0,
                )
        return ResolvedReference(
            status="unresolved", confidence=0.0, resolution_method="exact_canonical",
            target_slug=target_slug, target_unit_id=unit_id,
        )

    def _index_for(self, slug: str) -> Optional[SanskritIndex]:
        if slug in self._index_cache:
            return self._index_cache[slug]
        info = self.registry.get(slug)
        idx: Optional[SanskritIndex] = None
        if info is not None and info.path.exists():
            data = _load_json(info.path)
            idx = SanskritIndex()
            for uid, text in _iter_units(data):
                idx.add(id=uid, text=text, work=info.title, unit=uid)
        self._index_cache[slug] = idx
        return idx

    def resolve_text(
        self,
        quoted_text: str,
        hint_slugs: Optional[Iterable[str]] = None,
        min_verified_score: float = 0.85,
        min_possible_score: float = 0.4,
        min_verified_length: int = 8,
    ) -> ResolvedReference:
        """Priorities 2/3/5: search for `quoted_text` verbatim or fuzzily.
        `hint_slugs` (e.g. from a title match on Gemini's free-text guess) is
        searched first; the resolver stops at the first verified hit rather
        than scanning the whole scope.

        `quoted_text` is normalized (edge quote marks/punctuation stripped)
        before searching -- see `_normalize_query`. A normalized query
        shorter than `min_verified_length` can never resolve as "verified",
        only "possible" at best, however high its score: a single short
        word (a term the commentator is glossing, not quoting -- this
        commentary style repeats one before explaining it) will coincidentally
        substring-match SOMETHING in almost any reasonably sized search scope,
        so a short match is not real evidence of a genuine citation the way a
        longer one is. Observed directly in a real enrichment run (single
        words like 'सदिति'/'नच'/'अत' resolving "verified" against essentially
        unrelated Gita verses that merely happen to contain that substring)."""
        query = _normalize_query(quoted_text)
        scopes = list(hint_slugs) if hint_slugs else []
        scopes += [s for s in self.search_scope if s not in scopes]

        best: Optional[ResolvedReference] = None
        searched: list[str] = []
        for slug in scopes:
            idx = self._index_for(slug)
            searched.append(slug)
            if idx is None:
                continue
            hits = idx.search(query, limit=1, min_score=min_possible_score)
            if not hits:
                continue
            hit = hits[0]
            info = self.registry.get(slug)
            can_verify = len(query) >= min_verified_length
            candidate = ResolvedReference(
                status="verified" if (can_verify and hit.score >= min_verified_score) else "possible",
                confidence=round(hit.score, 3),
                resolution_method="lexical_search" if hit.matched_field in ("slp1", "pkey") else "fuzzy_search",
                target_slug=slug,
                target_title=info.title if info else slug,
                target_unit_id=hit.doc.unit,
                matched_text=hit.doc.text,
                score=hit.score,
            )
            if best is None or candidate.score > best.score:
                best = candidate
            if best.status == "verified":
                break
        if best is not None:
            best.scope_searched = searched
            return best
        return ResolvedReference(
            status="unresolved", confidence=0.0, resolution_method="unresolved",
            scope_searched=searched,
        )

    def resolve(self, candidate: dict) -> ResolvedReference:
        """High-level entry point matching the full priority ladder.
        `candidate` (typically Gemini's proposal for one detected quotation) is
        one of:
          {"target_slug": ..., "unit_id": ...}                     -> priority 1
          {"quoted_text": ..., "source_guess": "Bhagavad Gita"}    -> priority 1 (if
              target_slug/unit_id also given) falling through to 2/5
          {"quoted_text": ...}                                     -> priority 2/3
        """
        target_slug = candidate.get("target_slug")
        unit_id = candidate.get("unit_id")
        exact_result: Optional[ResolvedReference] = None
        if target_slug and unit_id:
            exact_result = self.resolve_exact(target_slug, unit_id)
            if exact_result.status == "verified":
                return exact_result

        quoted_text = candidate.get("quoted_text")
        if not quoted_text:
            return exact_result or ResolvedReference(
                status="unresolved", confidence=0.0, resolution_method="unresolved",
            )

        hint_slugs = None
        source_guess = candidate.get("source_guess")
        if source_guess:
            hint_slugs = [info.slug for info in self.registry.find_by_title(source_guess)]
        return self.resolve_text(quoted_text, hint_slugs=hint_slugs)
