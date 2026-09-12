"""
index.py — an in-memory reference index that ties the pieces together.

It demonstrates the retrieval model you'd implement on top of Typesense/
Meilisearch/Postgres in production; the Sanskrit intelligence lives in the
normalizer, so the "engine" here is deliberately simple and boring.

Retrieval model
---------------
Documents are indexed at three granularities of key (slp1 / pkey / ckey) plus
trigram sets of pkey and ckey. A query is normalized the SAME way, then:

  1. candidate generation — any doc sharing >=1 pkey/ckey trigram with the query
     (this is the cheap recall step a search engine's inverted index gives you).
  2. scoring — a weighted blend of:
       * exact slp1 substring / whole-field match          (strongest signal)
       * pkey equality or bounded Damerau-Levenshtein       (safe fuzzy)
       * ckey equality / distance                           (loose fuzzy)
       * trigram Jaccard similarity                         (partial / OCR noise)
  3. cross-references — each hit carries its typed edges (comments_on, parallel_to,
     quotes, ...) so the UI can show "← commentary on X" / "‖ parallel in Y".

Every citable unit has a stable CTS-URN-style id, so cross-references are edges
between ids and survive edition changes.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from .translit import to_slp1, slp1_to_deva
from .normalize import keys_for, phonetic_key, coarse_key, trigrams


# ---- edit distance ---------------------------------------------------------
def damerau_levenshtein(a: str, b: str, max_d: int | None = None) -> int:
    """Optimal string alignment distance (handles adjacent transpositions).
    `max_d` enables early exit for speed."""
    la, lb = len(a), len(b)
    if abs(la - lb) > (max_d if max_d is not None else max(la, lb)):
        return (max_d or max(la, lb)) + 1
    prev2 = list(range(lb + 1))
    prev = None
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        row_min = cur[0]
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(cur[j - 1] + 1, prev2[j] + 1, prev2[j - 1] + cost)
            if (i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]):
                # transposition — needs the row two back; approximate with prev
                cur[j] = min(cur[j], (prev[j - 2] if prev else prev2[j - 1]) + 1)
            row_min = min(row_min, cur[j])
        if max_d is not None and row_min > max_d:
            return max_d + 1
        prev, prev2 = prev2, cur
    return prev2[lb]


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---- data model ------------------------------------------------------------
@dataclass
class Doc:
    id: str                     # CTS-URN-style, e.g. urn:dge:rv.1.1:1
    text: str                   # original text (any scheme)
    scheme: str                 # source scheme of `text`
    work: str                   # human label, e.g. "Rigveda"
    unit: str                   # citation label, e.g. "1.1.1"
    kind: str = "mula"          # mula | commentary | sutra | kosha
    slp1: str = ""
    pkey: str = ""
    ckey: str = ""
    pkey_trigrams: set = field(default_factory=set)
    ckey_trigrams: set = field(default_factory=set)

    def deva(self) -> str:
        return slp1_to_deva(self.slp1)


@dataclass
class Edge:
    src: str                    # doc id
    dst: str                    # doc id
    type: str                   # comments_on | parallel_to | quotes | attributed_to
    confidence: float = 1.0
    evidence: str = ""


@dataclass
class Hit:
    doc: Doc
    score: float
    matched_field: str          # slp1 | pkey | ckey | trigram
    detail: str = ""
    cross_refs: list = field(default_factory=list)   # list[(Edge, Doc)]


class SanskritIndex:
    def __init__(self) -> None:
        self.docs: dict[str, Doc] = {}
        self.edges: list[Edge] = []
        # inverted indexes: trigram -> set(doc_id)
        self._pk_inv: dict[str, set] = {}
        self._ck_inv: dict[str, set] = {}

    # ---- ingest ----
    def add(self, id: str, text: str, work: str, unit: str,
            kind: str = "mula", scheme: str | None = None) -> Doc:
        sch = scheme or "auto"
        slp1 = to_slp1(text, None if sch == "auto" else sch)
        k = keys_for(slp1)
        doc = Doc(id=id, text=text, scheme=sch, work=work, unit=unit, kind=kind,
                  slp1=k["slp1"], pkey=k["pkey"], ckey=k["ckey"],
                  pkey_trigrams=k["pkey_trigrams"], ckey_trigrams=k["ckey_trigrams"])
        self.docs[id] = doc
        for g in doc.pkey_trigrams:
            self._pk_inv.setdefault(g, set()).add(id)
        for g in doc.ckey_trigrams:
            self._ck_inv.setdefault(g, set()).add(id)
        return doc

    def link(self, src: str, dst: str, type: str,
             confidence: float = 1.0, evidence: str = "") -> None:
        self.edges.append(Edge(src, dst, type, confidence, evidence))

    def _refs_for(self, doc_id: str):
        out = []
        for e in self.edges:
            if e.src == doc_id and e.dst in self.docs:
                out.append((e, self.docs[e.dst], "out"))
            elif e.dst == doc_id and e.src in self.docs:
                out.append((e, self.docs[e.src], "in"))
        return out

    # ---- search ----
    def search(self, query: str, scheme: str | None = None,
               limit: int = 10, min_score: float = 0.15) -> list[Hit]:
        q_slp1 = to_slp1(query, scheme)
        q_pk = phonetic_key(q_slp1)
        q_ck = coarse_key(q_slp1)
        q_pk_tri = trigrams(q_pk)
        q_ck_tri = trigrams(q_ck)

        # candidate generation via shared trigrams (the inverted-index step)
        cands: set[str] = set()
        for g in q_pk_tri:
            cands |= self._pk_inv.get(g, set())
        for g in q_ck_tri:
            cands |= self._ck_inv.get(g, set())

        hits: list[Hit] = []
        for did in cands:
            doc = self.docs[did]
            score, field_name, detail = self._score(
                doc, q_slp1, q_pk, q_ck, q_pk_tri, q_ck_tri)
            if score >= min_score:
                refs = [(e, d, direction) for (e, d, direction) in self._refs_for(did)]
                hits.append(Hit(doc=doc, score=score, matched_field=field_name,
                                detail=detail, cross_refs=refs))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    def _score(self, doc, q_slp1, q_pk, q_ck, q_pk_tri, q_ck_tri):
        best = 0.0
        field_name = "trigram"
        detail = ""

        # 1) exact / substring on canonical SLP1 (strongest)
        if q_slp1 and q_slp1 == doc.slp1:
            return 1.0, "slp1", "exact SLP1"
        if q_slp1 and q_slp1 in doc.slp1:
            frac = len(q_slp1) / max(len(doc.slp1), 1)
            s = 0.85 + 0.10 * frac
            if s > best:
                best, field_name, detail = s, "slp1", "SLP1 substring"

        # 2) phonetic key — equality or bounded edit distance (safe fuzzy)
        if q_pk and doc.pkey:
            if q_pk == doc.pkey:
                s = 0.9
                if s > best:
                    best, field_name, detail = s, "pkey", "phonetic-key exact"
            elif q_pk in doc.pkey:
                s = 0.75 + 0.10 * (len(q_pk) / max(len(doc.pkey), 1))
                if s > best:
                    best, field_name, detail = s, "pkey", "phonetic-key substring"
            else:
                # compare against the closest whole word in the doc's pkey
                for word in doc.pkey.split():
                    d = damerau_levenshtein(q_pk, word, max_d=2)
                    if d <= 2:
                        s = 0.8 - 0.18 * d
                        if s > best:
                            best, field_name, detail = s, "pkey", f"phonetic-key edit dist {d}"

        # 3) coarse key — looser fallback
        if best < 0.7 and q_ck and doc.ckey:
            if q_ck in doc.ckey:
                s = 0.6 + 0.08 * (len(q_ck) / max(len(doc.ckey), 1))
                if s > best:
                    best, field_name, detail = s, "ckey", "coarse-key substring"
            else:
                for word in doc.ckey.split():
                    d = damerau_levenshtein(q_ck, word, max_d=2)
                    if d <= 2:
                        s = 0.62 - 0.16 * d
                        if s > best:
                            best, field_name, detail = s, "ckey", f"coarse-key edit dist {d}"

        # 4) trigram similarity (partial matches / OCR noise) — recall floor
        jp = jaccard(q_pk_tri, doc.pkey_trigrams)
        jc = jaccard(q_ck_tri, doc.ckey_trigrams)
        jsim = max(jp, jc)
        if jsim * 0.7 > best:
            best, field_name, detail = jsim * 0.7, "trigram", f"trigram sim {jsim:.2f}"

        return best, field_name, detail
