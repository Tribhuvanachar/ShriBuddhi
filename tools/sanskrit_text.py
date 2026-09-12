#!/usr/bin/env python3
"""
sanskrit_text.py — the one place Sanskrit text is normalised, so that every
detector asks the same question of the same string.

WHY ONE PLACE. Before this there were at least six normalisers in the tree —
build_sutra_prayoga_index's norm_with_map, build_sutra_index's fold,
build_highlight_index's normalise, padaccheda's strip_punct, and two more in
JavaScript — each correct for its own job and none agreeing with the others
about anusvāra, avagraha or a danda. A reference detector that normalises one
way and validates against an index built another way misses silently, which
is the worst way for a matcher to fail.

TWO THINGS ARE KEPT APART THROUGHOUT, and this is the load-bearing design
decision: the SOURCE text is never rewritten, and every normalised string
carries a map back to the offsets it came from. A reference found in the
normalised form has to be highlightable in the original characters the reader
is actually looking at, and normalisation moves those offsets around.

PARASAVARṆA (8.4.58 अनुस्वारस्य ययि परसवर्णः). An anusvāra before a stop is a
written stand-in for that stop's own nasal, and which nasal depends on which
varga follows:

    ं + क ख ग घ ङ  →  ङ्      अं + क  →  अङ्क
    ं + च छ ज झ ञ  →  ञ्      अं + च  →  अञ्च
    ं + ट ठ ड ढ ण  →  ण्      अं + ट  →  अण्ट
    ं + त थ द ध न  →  न्      अं + त  →  अन्त
    ं + प फ ब भ म  →  म्      अं + ब  →  अम्ब

A blanket ं → म् is wrong for four of those five rows. Before श ष स ह, before
a semivowel, and at the end of a word with nothing following, the anusvāra
stays as it is — except word-finally, where it IS a written म् (प्रसूनं is
प्रसूनम्) and is restored so the lexicon can recognise the word. That one
line is why प्रसूनं was being split as प्र + सूनं.
"""

import re
import unicodedata

# --- the vargas, in the order the nasal rule needs them ---------------------
VARGA_NASAL = {}
for _letters, _nasal in (
        ('कखगघङ', 'ङ'),
        ('चछजझञ', 'ञ'),
        ('टठडढण', 'ण'),
        ('तथदधन', 'न'),
        ('पफबभम', 'म'),
):
    for _c in _letters:
        VARGA_NASAL[_c] = _nasal

ANUSVARA = 'ं'
VISARGA = 'ः'
CANDRABINDU = 'ँ'
VIRAMA = '्'
AVAGRAHA = 'ऽ'

DEVA_LETTER = re.compile(r'[ऀ-ॿ]')
#: Marks that carry no lexical content and are dropped from the canonical form.
DROP = re.compile(
    r'[॑-॔᳐-᳿꣠-ꣿ]'      # vedic accents
    r'|[​-‍⁠﻿]'                    # zero-width joiners
    r'|[।॥॰|]'                                         # dandas
    r'|[,.;:!?"\'()\[\]{}—–\-…*‘’“”`]'                 # punctuation and quotes
    r'|\s+'
)

#: Expressions the Gold-Standard contract protects: they are the marks OF a
#: citation, never the thing cited, and must not be broken apart by sandhi
#: splitting or swallowed into a reference span. Part 0.4 of the contract
#: (FOSSILIZED CLITIC DENYLIST) plus the reference forms the project lead
#: named on 10 Sep 2026.
PROTECTED = (
    'इत्यर्थः', 'इति भावः', 'इतिभावः', 'इत्याह', 'इत्यत आह', 'इत्यताह',
    'इति चेत्', 'इतिचेत्', 'इति चेन्न', 'इतिचेन्न', 'तथाहि', 'यद्वा', 'किञ्च',
    'इत्येवमादि', 'इत्यतः', 'इत्युक्ते', 'इत्युक्तम्', 'इत्यादि', 'इत्यादिना',
    'इति यावत्', 'इतियावत्', 'इत्यनेन', 'इत्येतत्',
)
#: Vowel signs an इति-initial expression's own इ fuses into when it follows a
#: word: मुख्याश्रयाय + इत्यर्थः is written मुख्याश्रयायेत्यर्थः, and a
#: matcher looking only for the unfused spelling finds none of them — which is
#: most of them, because that is how commentaries actually write.
#: …and the avagraha (or the apostrophe print uses for it), which marks the
#: same elision from the other side: the project lead's own example
#: अरुर्द्विषदि'त्यादिना is अरुर्द्विषदि + इत्यादिना with the इ elided.
_FUSED_SIGNS = 'ेैीोौाऽ\''


def _protected_pattern():
    alts = []
    for expr in sorted(PROTECTED, key=len, reverse=True):
        alts.append(re.escape(expr))
        if expr.startswith('इ') and len(expr) > 2:
            alts.append('[' + _FUSED_SIGNS + ']' + re.escape(expr[1:]))
    return re.compile('|'.join(alts))


PROTECTED_RE = _protected_pattern()


def parasavarna(text):
    """Anusvāra rewritten as the nasal the following consonant calls for.

    Not a global ं → म्: that is right only before the प-varga and wrong
    before the other four. Anything the rule does not cover — an anusvāra
    before श ष स ह or a semivowel — is left exactly as written."""
    if ANUSVARA not in text:
        return text
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        if ch != ANUSVARA:
            out.append(ch)
            continue
        nxt = text[i + 1] if i + 1 < n else ''
        nasal = VARGA_NASAL.get(nxt)
        if nasal:
            out.append(nasal + VIRAMA)
        elif not DEVA_LETTER.match(nxt or ' '):
            # End of a word: the anusvāra IS a written म्, and restoring it is
            # what lets the lexicon recognise प्रसूनं as प्रसूनम्.
            out.append('म' + VIRAMA)
        else:
            out.append(ch)
    return ''.join(out)


def normalize(text, apply_parasavarna=True):
    """The canonical form: NFC, accents and punctuation gone, anusvāra
    resolved. Loses offsets — use normalize_with_map when they matter."""
    return normalize_with_map(text, apply_parasavarna)[0]


def normalize_with_map(text, apply_parasavarna=True):
    """(normalized, offsets) where offsets[i] is the index in `text` that
    normalized[i] came from.

    Every character the canonical form emits is traceable to a source
    character, including the ones parasavarṇa invents: ं becomes two
    characters (न and ्) and both point back at the single ं they replaced,
    so a span found in the normalised string still lands on the right
    characters of the text the reader can see."""
    if not text:
        return '', []
    text = unicodedata.normalize('NFC', text)
    out, offsets = [], []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if DROP.match(ch):
            i += 1
            continue
        if ch == AVAGRAHA:
            i += 1
            continue
        if apply_parasavarna and ch == ANUSVARA:
            nxt = text[i + 1] if i + 1 < n else ''
            nasal = VARGA_NASAL.get(nxt)
            if nasal is None and not DEVA_LETTER.match(nxt or ' '):
                nasal = 'म'
            if nasal:
                out.append(nasal)
                offsets.append(i)
                out.append(VIRAMA)
                offsets.append(i)
                i += 1
                continue
        out.append(ch)
        offsets.append(i)
        i += 1
    return ''.join(out), offsets


def protected_spans(text):
    """[(start, end), …] over the source text for every expression the
    Gold-Standard contract keeps intact.

    A detector consults this before claiming a span: इत्यर्थः is where a
    citation ENDS, and a matcher that swallows it has mistaken the punctuation
    for the sentence."""
    return [(m.start(), m.end()) for m in PROTECTED_RE.finditer(text or '')]


def is_protected(text, start, end):
    """True if [start, end) overlaps an expression the contract protects."""
    for p0, p1 in protected_spans(text):
        if start < p1 and p0 < end:
            return True
    return False


#: Distinctions that separate two spellings of the same word in practice:
#: vowel length, the three sibilants, and the nasals. Used ONLY to retrieve
#: candidates — never to decide a match, which is checked against the exact
#: normalised form afterwards.
_FOLD = {
    'ी': 'ि', 'ू': 'ु', 'ॄ': 'ृ', 'ॣ': 'ॢ', 'आ': 'अ', 'ई': 'इ', 'ऊ': 'उ',
    'ॠ': 'ऋ', 'ॡ': 'ऌ',
    'ष': 'श', 'स': 'श', 'ण': 'न', 'ङ': 'न', 'ञ': 'न', 'ं': 'न',
    'ब': 'व', 'ळ': 'ल',
}


def fold(text):
    """A coarse key for finding candidates when a citation is spelled slightly
    differently from the corpus.

    संज्ञायां भॄतॄ is quoted for 3.2.46 संज्ञायां भृतॄवृजि…, differing only in
    the length of one vowel. An exact matcher finds nothing; a fuzzy matcher
    finds too much. Folding the distinctions that actually vary in print —
    vowel length, sibilants, nasals, ब/व — retrieves the right candidate and
    leaves the deciding to the exact comparison.

    Strictly one character in, one character out, so a span found in the
    folded string maps through normalize_with_map's offsets unchanged. A fold
    that deleted characters would silently misplace every highlight."""
    out = normalize(text)
    return ''.join(_FOLD.get(c, c) for c in out)


def strip_marks(word):
    """A single word reduced to its canonical form, offsets discarded."""
    return normalize(word)
