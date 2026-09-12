#!/usr/bin/env python3
"""
build_morphology.py — precomputed word analysis, from Vidyut.

Tapping a word in a text should say what it is: which root or stem it comes
from, and what case, number, person or tense it is standing in. Vidyut can
answer that, but it answers from a 75 MB kosha and a Rust binary — neither of
which belongs in a browser on a static site.

So the answer is computed here, once, for the words the corpus actually uses,
and shipped as small sharded JSON the reader fetches one bucket at a time.

    pip install vidyut
    python3 -c "import vidyut; vidyut.download_data('/tmp/vidyut_data')"
    python3 tools/build_morphology.py

Output: dge/data/_morph/<bucket>.json plus manifest.json.

WHAT THIS DOES NOT DO, stated plainly because the gap is visible to a reader.
Vidyut resolves inflected forms, not sandhi-joined ones. Coverage is about
75% of word OCCURRENCES at the common end of the vocabulary and falls away
into the tail, where most entries are compounds that were never separate
words. A form with no analysis simply shows none — the popover still gives
the kosha senses and where else the word appears. The manifest records the
real coverage figures rather than leaving the impression of completeness.
"""

import argparse
import collections
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'dge', 'data')
OUT = os.path.join(DATA, '_morph')

DEVA_RUN = re.compile(r'[ऀ-ॿ]+')
PUNCT = re.compile(r'[।॥]')
TEXT_KEYS = {'sanskrit_text', 'text', 'mula', 'sa', 'line', 'content', 'value'}

# Short codes on the wire, expanded to Sanskrit by dge/js/intellisense.js.
# Keyed on what str() of Vidyut's enums actually yields — the SLP1 Sanskrit
# term (puM, saptamI, la~w), NOT the Python enum name. repr() shows
# "Linga.Pum" and str() shows "puM"; keying on the first writes empty codes
# into every entry, which is exactly what a first pass here did.
LINGA = {'puM': 'p', 'strI': 's', 'napuMsaka': 'n'}
VIBHAKTI = {'praTamA': '1', 'dvitIyA': '2', 'tftIyA': '3', 'caturTI': '4',
            'paYcamI': '5', 'zazWI': '6', 'saptamI': '7', 'samboDanam': '8'}
VACANA = {'eka': '1', 'dvi': '2', 'bahu': '3'}
PURUSHA = {'praTama': '3', 'maDyama': '2', 'uttama': '1'}
LAKARA = {'la~w': 'lat', 'li~w': 'lit', 'lu~w': 'lut', 'lf~w': 'lrt',
          'le~w': 'let', 'lo~w': 'lot', 'la~N': 'lan', 'viDili~N': 'vlin',
          'ASIrli~N': 'alin', 'lu~N': 'lun', 'lf~N': 'lrn'}
PRAYOGA = {'kartari': 'k', 'karmaRi': 'km', 'BAve': 'b'}


def enum_name(v):
    return str(v)


def harvest(node, counts):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str) and (k in TEXT_KEYS or k.startswith('sanskrit')):
                for w in DEVA_RUN.findall(PUNCT.sub(' ', v)):
                    if len(w) > 1:
                        counts[w] += 1
            else:
                harvest(v, counts)
    elif isinstance(node, list):
        for v in node:
            harvest(v, counts)


def vocabulary(min_count):
    counts = collections.Counter()
    files = 0
    for root, _, names in os.walk(DATA):
        if os.path.basename(root) == '_morph':
            continue
        for n in names:
            if n != 'data.json':
                continue
            files += 1
            try:
                with open(os.path.join(root, n), encoding='utf-8') as fh:
                    harvest(json.load(fh), counts)
            except (OSError, ValueError):
                pass
    print(f'  {files} data.json files, {len(counts)} distinct forms')
    keep = {w: c for w, c in counts.items() if c >= min_count}
    print(f'  {len(keep)} appear at least {min_count}x '
          f'({sum(keep.values())} of {sum(counts.values())} occurrences)')
    return keep, counts


def deva(slp1, _cache={}):
    """Vidyut speaks SLP1; a reader does not.

    Lemmas are converted here rather than in the browser so the shipped file
    is already readable, and so the client needs no SLP1 table of its own.
    Cached because the same few thousand stems recur across 93,000 forms.
    """
    if slp1 not in _cache:
        from vidyut import lipi
        from vidyut.lipi import Scheme
        try:
            _cache[slp1] = lipi.transliterate(slp1, Scheme.Slp1, Scheme.Devanagari)
        except Exception:
            _cache[slp1] = slp1
    return _cache[slp1]


def analyses(kosha, slp, cap):
    """Vidyut's entries for one form, deduplicated and capped.

    The kosha returns every analysis it can justify — 68 for देवानाम् — most
    of them technically available and useless to a reader. Identical readings
    are collapsed, and the rest truncated: a popover listing sixty parses is
    not an answer.
    """
    keys = [slp]
    # The official data stores word-final visarga as s or r.
    if slp.endswith('H'):
        keys += [slp[:-1] + 's', slp[:-1] + 'r']

    out, seen = [], set()
    for key in keys:
        try:
            if key not in kosha:
                continue
            entries = list(kosha.get(key))
        except Exception:
            continue
        for e in entries:
            kind = type(e).__name__
            try:
                if getattr(e, 'is_avyaya', False):
                    rec = ['a', deva(e.lemma)]
                elif kind.endswith('Tinanta'):
                    rec = ['t', deva(e.lemma),
                           LAKARA.get(enum_name(e.lakara), ''),
                           PURUSHA.get(enum_name(e.purusha), ''),
                           VACANA.get(enum_name(e.vacana), ''),
                           PRAYOGA.get(enum_name(e.prayoga), '')]
                elif kind.endswith('Subanta'):
                    rec = ['s', deva(e.lemma),
                           LINGA.get(enum_name(e.linga), ''),
                           VIBHAKTI.get(enum_name(e.vibhakti), ''),
                           VACANA.get(enum_name(e.vacana), '')]
                else:
                    continue
            except Exception:
                continue
            sig = tuple(rec)
            if sig in seen:
                continue
            seen.add(sig)
            out.append(rec)
            if len(out) >= cap:
                return out
    return out


def bucket_of(slp):
    """Two leading SLP1 characters, sanitised for a filename.

    SLP1 is case-significant — 'A' is long a, 'a' is short — so a
    case-insensitive filesystem would merge two different buckets. Uppercase
    is written with a trailing underscore to keep them apart.
    """
    b = (slp + '__')[:2]
    return ''.join(c + '_' if c.isupper() else (c if c.isalnum() else 'x') for c in b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='/tmp/vidyut_data')
    ap.add_argument('--min-count', type=int, default=2,
                    help='ignore forms rarer than this (default 2: a form seen '
                         'once is usually a sandhi accident, not a word)')
    ap.add_argument('--max-analyses', type=int, default=6)
    args = ap.parse_args()

    try:
        from vidyut.kosha import Kosha
        from vidyut import lipi
        from vidyut.lipi import Scheme
    except ImportError:
        print('vidyut is not installed. pip install vidyut', file=sys.stderr)
        return 1
    kosha_dir = os.path.join(args.data, 'kosha')
    if not os.path.isdir(kosha_dir):
        print(f'no kosha data at {kosha_dir}\n'
              f'  python3 -c "import vidyut; vidyut.download_data(\'{args.data}\')"',
              file=sys.stderr)
        return 1

    print('reading the corpus...')
    vocab, allcounts = vocabulary(args.min_count)

    print('analysing...')
    kosha = Kosha(kosha_dir)
    buckets = collections.defaultdict(dict)
    resolved = resolved_occ = 0
    total_occ = sum(vocab.values())
    for i, (word, count) in enumerate(sorted(vocab.items(), key=lambda kv: -kv[1])):
        if i and i % 50000 == 0:
            print(f'    {i}/{len(vocab)}  ({100 * resolved / i:.0f}% resolved so far)')
        slp = lipi.transliterate(word, Scheme.Devanagari, Scheme.Slp1)
        got = analyses(kosha, slp, args.max_analyses)
        if not got:
            continue
        resolved += 1
        resolved_occ += count
        buckets[bucket_of(slp)][word] = got

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
        '_readme': 'Precomputed morphology from Vidyut, built by '
                   'tools/build_morphology.py. Buckets are keyed by the first two '
                   'SLP1 characters of the form (uppercase written with a trailing '
                   'underscore, since SLP1 is case-significant). Each entry is a '
                   'list of analyses: ["s",lemma,linga,vibhakti,vacana] for a '
                   'subanta, ["t",lemma,lakara,purusha,vacana,prayoga] for a '
                   'tinanta, ["a",lemma] for an avyaya.',
        'v': 1,
        'buckets': sorted(buckets),
        'coverage': {
            'formsInCorpus': len(allcounts),
            'formsConsidered': len(vocab),
            'formsResolved': resolved,
            'occurrencesConsidered': total_occ,
            'occurrencesResolved': resolved_occ,
            'note': 'Vidyut resolves inflected forms, not sandhi-joined ones. '
                    'An unresolved word shows no analysis; the rest of the '
                    'popover still works.',
        },
    }
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f'\n  {len(buckets)} buckets, {resolved} forms, '
          f'{total_bytes / 1024 / 1024:.1f} MB total')
    print(f'  coverage: {100 * resolved / len(vocab):.0f}% of considered forms, '
          f'{100 * resolved_occ / total_occ:.0f}% of their occurrences')
    biggest = max(buckets.items(), key=lambda kv: len(kv[1]))
    print(f'  largest bucket: {biggest[0]} with {len(biggest[1])} forms')
    return 0


if __name__ == '__main__':
    sys.exit(main())
