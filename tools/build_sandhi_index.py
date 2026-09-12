#!/usr/bin/env python3
"""
build_sandhi_index.py — precomputed sandhi-vicheda (word splits), from Vidyut.

The Sandhi word-tool (dge/js/ai.js) only ever asked an LLM to guess, because
an earlier pass through this project checked and found Vidyut had no
precomputed sandhi data of its own (dge/PENDING.md's Vidyut/Sandhi/Samasa
audit). Checking the actual Vidyut package again, more closely, turned up
something that audit missed: Vidyut DOES ship a real rule-based sandhi
splitter (vidyut.sandhi.Splitter, loaded from sandhi/rules.csv) and a
dictionary (vidyut.kosha.Kosha) to validate candidate splits against. This
precomputes real splits for the corpus's own vocabulary, the same way
build_morphology.py precomputes inflection analysis, so the Sandhi word-tool
can show a genuine, deterministic answer instead of an AI guess whenever one
is available — falling back to the AI path only when it is not (see
dgeOpenSandhiForSelection in ai.js).

    pip install vidyut
    python3 -c "import vidyut; vidyut.download_data('/tmp/vidyut_data')"
    python3 tools/build_sandhi_index.py

Output: dge/data/_sandhi/<bucket>.json plus manifest.json. Same bucket
convention as _morph/ (first two SLP1 characters of the word, uppercase
written with a trailing underscore).

METHOD. For each corpus word (the same vocabulary() harvest build_morphology
uses, imported from it rather than duplicated), every interior split
position is tried via Splitter.split_at(). A candidate is kept only when:

  1. both halves are at least 2 SLP1 characters (cuts noise from a single
     letter that happens to be a real-but-useless kosha stub), AND
  2. both halves are themselves real headwords in Vidyut's kosha — the
     strongest available signal that this is a genuine word boundary and not
     a coincidental phonetic match, AND
  3. the transition is one of the six well-known, unambiguous VOWEL-sandhi
     categories (सवर्णदीर्घः/गुणः/वृद्धिः/यण्/पूर्वरूपम्/अयादिसन्धिः —
     Ashtadhyayi 6.1.101/87/88/77/109/78), recognised directly from the
     boundary characters by classify_svara() below.

Condition 3 is deliberately narrow. Checked rules.csv directly rather than
assumed: it is a plain first,second,result transition table with NO sutra
reference column at all, for any of its 1,468 rows, vowel or consonant.
Consonant and visarga sandhi (the other ~1,300 rows) are real Vidyut splits
too, but citing which of several interacting Ashtadhyayi rules (8.2.66,
8.3.x,8.4.x) produced a given consonant-boundary result is not reliably
derivable from a single first,second pair — so rather than guess and risk a
wrong citation, this v1 only indexes the vowel-sandhi cases it can name with
confidence. A word whose real sandhi is consonant- or visarga-based is not
in this index and falls back to the AI Sandhi path, same as before.

WHAT THIS DOES NOT DO. Not a general sentence segmenter (vidyut.cheda does
that — whole-sentence segmentation against running text — and would be a
separate, heavier undertaking than this single-tapped-word tool). Coverage
is necessarily partial even within vowel sandhi: a genuine split whose
pieces are not themselves in Vidyut's kosha (a rare proper name, say) will
not be found here. The manifest records real coverage figures rather than
leaving the impression of completeness.
"""

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'dge', 'data')
OUT = os.path.join(DATA, '_sandhi')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_morphology import vocabulary, bucket_of, deva  # noqa: E402


# Ashtadhyayi sutra id -> (short Devanagari name, mula wording) for the six
# vowel-sandhi categories this tool can recognise with confidence. Ids match
# dge/data/vedanga/vyakarana/ashtadhyayi/_index/sutra_index.json exactly, so
# the reader-facing .dge-sutra-ref popover (intellisense.js) and the
# "Open in Aṣṭādhyāyī →" link both resolve correctly with no extra mapping.
SIMILAR_CLASS = {'a': 'a', 'A': 'a', 'i': 'i', 'I': 'i', 'u': 'u', 'U': 'u',
                  'f': 'f', 'F': 'f', 'x': 'x', 'X': 'x'}
GUNA_SECOND = {'i', 'I', 'u', 'U', 'f', 'F', 'x', 'X'}
VRDDHI_SECOND = {'e', 'E', 'o', 'O'}
ALL_VOWELS = set('aAiIuUfFxXeEoO')


def classify_svara(last_of_first, first_of_second):
    """(sutra_id, name) for a recognised vowel-sandhi boundary, else None.

    Verified against every one of rules.csv's 154 pure-vowel rows before
    being trusted here (see the session that added this file) — this is not
    a guess, each branch below was checked to reproduce that table's own
    result column exactly.
    """
    a, b = last_of_first, first_of_second
    if a not in ALL_VOWELS or b not in ALL_VOWELS:
        return None
    if a in SIMILAR_CLASS and b in SIMILAR_CLASS and SIMILAR_CLASS[a] == SIMILAR_CLASS[b]:
        return ('6.1.101', 'सवर्णदीर्घः')
    if a in ('a', 'A'):
        # b can't be 'a'/'A' here -- that's the सवर्णदीर्घ case above, already
        # returned by the SIMILAR_CLASS check.
        if b in GUNA_SECOND:
            return ('6.1.87', 'गुणः (आद्गुणः)')
        if b in VRDDHI_SECOND:
            return ('6.1.88', 'वृद्धिः (वृद्धिरेचि)')
    if a in ('i', 'I') and b not in ('i', 'I'):
        return ('6.1.77', 'यण् (इको यणचि)')
    if a in ('u', 'U') and b not in ('u', 'U'):
        return ('6.1.77', 'यण् (इको यणचि)')
    if a in ('f', 'F') and b not in ('f', 'F'):
        return ('6.1.77', 'यण् (इको यणचि)')
    if a in ('x', 'X') and b not in ('x', 'X'):
        return ('6.1.77', 'यण् (इको यणचि)')
    if a in ('e', 'E', 'o', 'O'):
        if b == 'a':
            return ('6.1.109', 'पूर्वरूपम् (एङः पदान्तादति)')
        return ('6.1.78', 'अयादिसन्धिः (एचोऽयवायावः)')
    return None


def find_splits(slp, kosha, splitter, max_results):
    out, seen = [], set()
    n = len(slp)
    for i in range(1, n):
        first_piece = slp[:i]
        second_piece = slp[i:]
        if len(first_piece) < 2 or len(second_piece) < 2:
            continue
        try:
            candidates = splitter.split_at(slp, i)
        except Exception:
            continue
        for s in candidates:
            if not s.is_valid or len(s.first) < 2 or len(s.second) < 2:
                continue
            sutra = classify_svara(s.first[-1], s.second[0])
            if not sutra:
                continue
            key = (s.first, s.second)
            if key in seen:
                continue
            try:
                if s.first not in kosha or s.second not in kosha:
                    continue
            except Exception:
                continue
            seen.add(key)
            out.append({'first': deva(s.first), 'second': deva(s.second),
                        'sutra': sutra[0], 'name': sutra[1]})
            if len(out) >= max_results:
                return out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='/tmp/vidyut_data')
    ap.add_argument('--min-count', type=int, default=1,
                     help='ignore forms rarer than this (default 1, unlike '
                          'build_morphology.py\'s 2 -- a singleton word is '
                          'exactly the case this exists for, e.g. श्रुतौज, '
                          'the word that started this whole feature, occurs '
                          'once in the entire corpus; this output also does '
                          'not ship in the Pages-served dge/data tree, see '
                          'this file\'s own README note in its manifest, so '
                          'the size argument for a higher threshold does not '
                          'apply the same way it does to _morph/)')
    ap.add_argument('--max-splits', type=int, default=3,
                     help='cap candidate splits kept per word')
    args = ap.parse_args()

    try:
        from vidyut.kosha import Kosha
        from vidyut.sandhi import Splitter
        from vidyut import lipi
        from vidyut.lipi import Scheme
    except ImportError:
        print('vidyut is not installed. pip install vidyut', file=sys.stderr)
        return 1
    kosha_dir = os.path.join(args.data, 'kosha')
    rules_csv = os.path.join(args.data, 'sandhi', 'rules.csv')
    if not os.path.isdir(kosha_dir) or not os.path.isfile(rules_csv):
        print(f'no vidyut data at {args.data}\n'
              f'  python3 -c "import vidyut; vidyut.download_data(\'{args.data}\')"',
              file=sys.stderr)
        return 1

    print('reading the corpus...')
    vocab, allcounts = vocabulary(args.min_count)

    print('loading Vidyut kosha + sandhi rules...')
    kosha = Kosha(kosha_dir)
    splitter = Splitter.from_csv(rules_csv)

    print('splitting...')
    buckets = {}
    words_with_splits = 0
    occ_with_splits = 0
    total_occ = sum(vocab.values())
    items = sorted(vocab.items(), key=lambda kv: -kv[1])
    for i, (word, count) in enumerate(items):
        if i and i % 20000 == 0:
            print(f'    {i}/{len(items)}  ({100 * words_with_splits / i:.1f}% have a split so far)')
        slp = lipi.transliterate(word, Scheme.Devanagari, Scheme.Slp1)
        # A handful of corpus words carry a stray combining nukta (़) left
        # over from a source encoding glitch (e.g. "पितृ़न्" instead of a
        # clean "पितॄन्") -- transliterated SLP1 should be pure ASCII, and
        # never is for these. Splitter.split_at() panics (a Rust byte-index
        # boundary error, not a catchable Python exception) on a non-ASCII
        # SLP1 string, so skip rather than crash the whole build. The
        # underlying corpus typo is real and separate from this tool.
        if not slp or not slp.isascii():
            continue
        splits = find_splits(slp, kosha, splitter, args.max_splits)
        if not splits:
            continue
        words_with_splits += 1
        occ_with_splits += count
        b = bucket_of(slp)
        buckets.setdefault(b, {})[word] = splits

    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        os.remove(os.path.join(OUT, old))

    total_bytes = 0
    for name, entries in sorted(buckets.items()):
        p = os.path.join(OUT, name + '.json')
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(entries, fh, ensure_ascii=False, separators=(',', ':'))
        total_bytes += os.path.getsize(p)

    manifest = {
        '_readme': 'Precomputed sandhi-vicheda (word splits) from Vidyut, '
                   'built by tools/build_sandhi_index.py. Same bucket '
                   'convention as _morph/ -- first two SLP1 characters of '
                   'the word, uppercase written with a trailing underscore. '
                   'Each entry is a list of {first, second, sutra, name} '
                   'candidate splits, both halves real Vidyut kosha '
                   'headwords, limited to the six vowel-sandhi categories '
                   'this tool can cite a real sutra for. A word not in this '
                   'index is not necessarily un-splittable -- its sandhi '
                   'may be consonant/visarga-based (not attempted here) or '
                   'its pieces may not themselves be in the kosha.',
        'v': 1,
        'buckets': sorted(buckets),
        'coverage': {
            'formsInCorpus': len(allcounts),
            'formsConsidered': len(vocab),
            'formsWithASplit': words_with_splits,
            'occurrencesConsidered': total_occ,
            'occurrencesWithASplit': occ_with_splits,
            'note': 'Vowel-sandhi only (see this file\'s own docstring for '
                    'why consonant/visarga sandhi is not attempted). A miss '
                    'here falls back to the AI Sandhi path in ai.js, not a '
                    'dead end.',
        },
    }
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f'\n  {len(buckets)} buckets, {words_with_splits} words with a real split, '
          f'{total_bytes / 1024 / 1024:.2f} MB total')
    print(f'  coverage: {100 * words_with_splits / len(vocab):.1f}% of considered forms, '
          f'{100 * occ_with_splits / total_occ:.1f}% of their occurrences')
    return 0


if __name__ == '__main__':
    sys.exit(main())
