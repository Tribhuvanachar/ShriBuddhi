"""
sanskrit_search — a dependency-free reference implementation of Sanskrit-aware,
sandhi/variant-tolerant corpus-wide search with typed cross-references, for the
DGE project (item #9).

Public API:
    to_slp1(text, scheme=None)      canonicalize any scheme -> SLP1
    phonetic_key(slp1)              safe phonetic fold (pkey)
    coarse_key(slp1)                lossy fold (ckey)
    SanskritIndex                   the in-memory index (.add/.link/.search)
    build_sample_index()            a demo corpus
"""
from .translit import to_slp1, slp1_to_deva, detect_scheme
from .normalize import phonetic_key, coarse_key, keys_for, trigrams
from .index import SanskritIndex, Doc, Edge, Hit, damerau_levenshtein
from .sample_corpus import build_sample_index

__all__ = [
    "to_slp1", "slp1_to_deva", "detect_scheme",
    "phonetic_key", "coarse_key", "keys_for", "trigrams",
    "SanskritIndex", "Doc", "Edge", "Hit", "damerau_levenshtein",
    "build_sample_index",
]
