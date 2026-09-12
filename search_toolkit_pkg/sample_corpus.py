"""
sample_corpus.py — a tiny multi-text, multi-scheme corpus with cross-references,
so the search behaviour can be demonstrated and tested end to end.

Texts are intentionally stored in DIFFERENT input schemes (Devanagari, IAST,
SLP1) to prove the canonicalization makes them all mutually searchable.
IDs follow a CTS-URN-style scheme: urn:dge:<work>.<section>:<unit>
"""
from __future__ import annotations
from .index import SanskritIndex


def build_sample_index() -> SanskritIndex:
    ix = SanskritIndex()

    # --- Veda: Rigveda 1.1.1 (Devanagari) ---
    ix.add("urn:dge:rv.1.1:1",
           "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम्",
           work="Rigveda", unit="1.1.1", kind="mula", scheme="devanagari")

    # --- Itihasa: Bhagavadgita 2.47 (Devanagari) ---
    ix.add("urn:dge:mbh.gita.2:47",
           "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन",
           work="Bhagavadgita", unit="2.47", kind="mula", scheme="devanagari")

    # --- Purana: a verse that quotes the Rigveda mantra (IAST, w/ variants) ---
    # note deliberate spelling variants vs the RV: 'agnimILe' spelled with plain
    # 'l', anusvara realized as class nasal, sibilant swap — all should still match.
    ix.add("urn:dge:vp.1.5:12",
           "agnim īle purohitan yajñasya devam ṛtvijam iti",
           work="Vishnupurana", unit="1.5.12", kind="mula", scheme="iast")

    # --- Grammar: Ashtadhyayi 1.1.1 and 1.1.2 (Devanagari) ---
    ix.add("urn:dge:ashta.1.1:1", "वृद्धिरादैच्",
           work="Ashtadhyayi", unit="1.1.1", kind="sutra", scheme="devanagari")
    ix.add("urn:dge:ashta.1.1:2", "अदेङ्गुणः",
           work="Ashtadhyayi", unit="1.1.2", kind="sutra", scheme="devanagari")

    # --- Commentary: Kashika on Ashtadhyayi 1.1.1 (IAST) ---
    ix.add("urn:dge:kashika.1.1:1",
           "ād aic ca vṛddhisaṃjñā bhavati",
           work="Kashika", unit="ad 1.1.1", kind="commentary", scheme="iast")

    # --- Kosha: Amarakosha-style synonym line for 'svarga' (SLP1 stored raw) ---
    ix.add("urn:dge:amara.svarga:1",
           "svar dyM divO tridivaM trIdaSAlayaH",  # SLP1
           work="Amarakosha", unit="svarga-varga", kind="kosha", scheme="slp1")

    # --- cross-references (typed edges between stable ids) ---
    ix.link("urn:dge:vp.1.5:12", "urn:dge:rv.1.1:1", "quotes",
            confidence=0.95, evidence="verbatim pada quotation of RV 1.1.1")
    ix.link("urn:dge:vp.1.5:12", "urn:dge:rv.1.1:1", "parallel_to",
            confidence=0.95)
    ix.link("urn:dge:kashika.1.1:1", "urn:dge:ashta.1.1:1", "comments_on",
            confidence=1.0, evidence="Kashikavritti gloss on the sutra")

    return ix
