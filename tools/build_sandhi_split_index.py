#!/usr/bin/env python3
"""
build_sandhi_split_index.py — sandhi-vicheda for the corpus's own compounds,
using sanskrit_parser's rule-based Sandhi splitter, validated against the
word lists this repo already ships.

WHY A SECOND SANDHI INDEX. build_sandhi_index.py (Vidyut) deliberately
indexes only the six vowel-sandhi categories it can name an Ashtadhyayi
sutra for, and its output lives on a CDN rather than in the repo — which is
why the Sandhi word-tool does nothing on a local checkout. The project lead
asked (9 Sep 2026) for "local sandhi splitting using the open-source
sanskrit_parser library's Sandhi class, specifically the split_all method",
integrated with the dhatu data so matches can be highlighted. That library
splits consonant and visarga boundaries too, so this covers cases the
Vidyut pass skips, and the output is committed so it works offline.

    pip install sanskrit_parser
    python3 tools/build_sandhi_split_index.py --min-count 20

THE PROBLEM WITH split_all, AND THE FIX. It returns EVERY phonetically
possible split, not the right one: तच्छ्रुत्वा yields 20, among them
'g' + 'acCati'-style noise and 'rAH' + 'masyEva'. Raw output is unusable in
a reader. So each candidate is validated against word lists already in this
repo, and only splits whose BOTH halves are real words survive:

  _morph/                     93,143 inflected forms Vidyut resolved for
                              this corpus (nominal and verbal)
  prakriya/formindex/        204,970 inflected VERB forms, every root
  upasarga_artha.json         the 22 upasargas, first-half only

तच्छ्रुत्वा then keeps exactly तत् + श्रुत्वा (and its तद् variant), and
रामस्यैव keeps रामस्य + एव. That validation is also what makes the
highlighting the lead asked for possible: each half records WHICH list
recognised it, so the reader's popup can mark a half that is a real verb
form — a dhatu — differently from one that is merely a known nominal.

SCOPE, AND WHY IT IS CAPPED. split_all costs ~0.39 s per word single-core.
The corpus has 5,001,516 distinct forms; even the 388,122 seen five times
or more would be days of compute. Two filters cut that to something
honest: a word _morph ALREADY resolves is not a sandhi compound needing a
split, and a word shorter than --min-len cannot usefully be one. What
remains at --min-count 20 is ~40k words. The manifest records the real
figures rather than implying the corpus is covered; a word not in the index
falls back exactly as it does today.

NOT A SENTENCE SEGMENTER, and only ONE boundary per word: a three-member
compound is not recursively split. Both would cost far more compute and are
a separate undertaking.
"""

import argparse
import glob
import json
import logging
import os
import sys
from multiprocessing import Pool

logging.disable(logging.CRITICAL)  # the library logs every attempted split at DEBUG

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'dge', 'data')
OUT_DIR = os.path.join(DATA, '_sandhi_local')

# Which list recognised a half. The reader shows 'v' differently: that half is
# a real verb form, so it links to a dhatu.
SRC_VERB, SRC_NOMINAL, SRC_UPASARGA = 'v', 'n', 'u'

_STATE = {}


def load_recognisers():
    morph, verbs = set(), set()
    for path in glob.glob(os.path.join(DATA, '_morph', '*.json')):
        if path.endswith('manifest.json'):
            continue
        try:
            with open(path, encoding='utf-8') as fh:
                morph |= set(json.load(fh))
        except (OSError, ValueError):
            pass
    for path in glob.glob(os.path.join(DATA, 'vedanga', 'vyakarana', 'prakriya',
                                       'formindex', '*.json')):
        if path.endswith('manifest.json'):
            continue
        try:
            with open(path, encoding='utf-8') as fh:
                verbs |= set(json.load(fh))
        except (OSError, ValueError):
            pass
    # upasarga_artha.json is keyed by root code, each value a list of
    # [upasarga, gloss] pairs -- the same 22 prefixes recurring, so a set of
    # the first elements is the whole list.
    upasargas = set()
    try:
        with open(os.path.join(DATA, 'vedanga', 'vyakarana', 'upasarga_artha.json'),
                  encoding='utf-8') as fh:
            for pairs in (json.load(fh).get('items') or {}).values():
                for pair in (pairs or []):
                    if isinstance(pair, (list, tuple)) and pair and pair[0]:
                        upasargas.add(str(pair[0]).strip())
    except (OSError, ValueError, AttributeError):
        pass
    return morph, verbs, upasargas


def init_worker(morph, verbs, upasargas, min_half):
    from sanskrit_parser.parser.sandhi import Sandhi
    _STATE['sandhi'] = Sandhi()
    _STATE['morph'] = morph
    _STATE['verbs'] = verbs
    _STATE['upasargas'] = upasargas
    _STATE['min_half'] = min_half


def _source_of(deva, first):
    if deva in _STATE['verbs']:
        return SRC_VERB
    if deva in _STATE['morph']:
        return SRC_NOMINAL
    if first and deva in _STATE['upasargas']:
        return SRC_UPASARGA
    return None


def split_word(word):
    """(word, [{"a","b","sa","sb"}...]) — validated splits, best first."""
    from sanskrit_parser.base.sanskrit_base import SanskritImmutableString, sanscript
    try:
        obj = SanskritImmutableString(word, encoding=sanscript.DEVANAGARI)
        raw = _STATE['sandhi'].split_all(obj)
    except Exception:
        return word, []
    if not raw:
        return word, []
    out = []
    for pair in raw:
        try:
            a, b = pair
        except (TypeError, ValueError):
            continue
        if len(a) < _STATE['min_half'] or len(b) < _STATE['min_half']:
            continue
        da = SanskritImmutableString(a, encoding=sanscript.SLP1).devanagari()
        db = SanskritImmutableString(b, encoding=sanscript.SLP1).devanagari()
        sa = _source_of(da, True)
        sb = _source_of(db, False)
        if not sa or not sb:
            continue
        out.append({'a': da, 'b': db, 'sa': sa, 'sb': sb})
    # Ranked in the parent, where the corpus frequency table lives.
    return word, out


def rank_splits(splits, counts):
    """Best first. A split naming a real verb form is what a reader is most
    likely to want, and after that the halves the corpus ACTUALLY uses win.

    Frequency is what separates फलितम् + आह from फलित + माह: both halves of
    both pass the word-list check (माह is in _morph), both name a verb, and on
    balance alone the wrong one wins by a letter. The corpus uses फलितम् and
    आह constantly and माह almost never, which settles it.
    """
    def key(s):
        verbs = (s['sa'] == SRC_VERB) + (s['sb'] == SRC_VERB)
        rarest = min(counts.get(s['a'], 0), counts.get(s['b'], 0))
        return (-verbs, -rarest, abs(len(s['a']) - len(s['b'])), s['a'])
    return sorted(splits, key=key)


def bucket_of(word):
    """Same convention as _morph/ and _sandhi/: first two SLP1 characters,
    an uppercase one written with a trailing underscore so the filename is
    case-insensitive-safe."""
    from sanskrit_parser.base.sanskrit_base import SanskritImmutableString, sanscript
    slp = SanskritImmutableString(word, encoding=sanscript.DEVANAGARI).canonical()
    two = (slp + '__')[:2]
    return ''.join(c + '_' if c.isupper() else (c if c.isalnum() else 'x') for c in two)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--min-count', type=int, default=20,
                    help='only index words the corpus uses at least this often')
    ap.add_argument('--min-len', type=int, default=7,
                    help='shorter words are not worth splitting')
    ap.add_argument('--min-half', type=int, default=2,
                    help='reject a split leaving a half shorter than this (SLP1 chars)')
    ap.add_argument('--limit', type=int, default=0, help='stop after N words (testing)')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--out', default=OUT_DIR)
    args = ap.parse_args(argv)

    sys.path.insert(0, os.path.join(REPO, 'tools'))
    import build_morphology as bm

    print('harvesting corpus vocabulary')
    _, counts = bm.vocabulary(1)
    print('loading recognisers')
    morph, verbs, upasargas = load_recognisers()
    print(f'  {len(morph)} morph forms, {len(verbs)} verb forms, {len(upasargas)} upasargas')

    known = morph | verbs
    targets = [w for w, c in counts.items()
               if c >= args.min_count and len(w) >= args.min_len and w not in known]
    targets.sort(key=lambda w: -counts[w])
    if args.limit:
        targets = targets[:args.limit]
    print(f'  {len(targets)} words to split '
          f'(>= {args.min_count}x, >= {args.min_len} chars, not already resolved)')

    results = {}
    with Pool(args.jobs, initializer=init_worker,
              initargs=(morph, verbs, upasargas, args.min_half)) as pool:
        for i, (word, splits) in enumerate(
                pool.imap_unordered(split_word, targets, chunksize=64), 1):
            if splits:
                results[word] = rank_splits(splits, counts)[:4]
            if i % 2000 == 0:
                print(f'    {i}/{len(targets)} · {len(results)} with a validated split',
                      flush=True)

    init_worker(morph, verbs, upasargas, args.min_half)  # bucket_of needs the import
    shards = {}
    for word, splits in results.items():
        shards.setdefault(bucket_of(word), {})[word] = splits

    os.makedirs(args.out, exist_ok=True)
    for name, shard in shards.items():
        with open(os.path.join(args.out, name + '.json'), 'w', encoding='utf-8') as fh:
            json.dump(shard, fh, ensure_ascii=False, separators=(',', ':'), sort_keys=True)

    with_verb = sum(1 for v in results.values()
                    if any(s['sa'] == SRC_VERB or s['sb'] == SRC_VERB for s in v))
    manifest = {
        '_readme': (
            "Sandhi splits for dge/js/ai.js's Sandhi word-tool: word -> "
            '[{"a","b","sa","sb"}], best first. sa/sb say which list recognised '
            'that half — "v" a real verb form (so it links to a dhatu, and the '
            'reader highlights it), "n" a nominal form from _morph, "u" an '
            'upasarga. Built by tools/build_sandhi_split_index.py with '
            "sanskrit_parser's Sandhi.split_all, validated against this repo's "
            'own word lists; see that script for scope and its limits.'),
        'v': 1,
        'minCount': args.min_count,
        'minLen': args.min_len,
        'wordsConsidered': len(targets),
        'wordsWithSplit': len(results),
        'wordsWithVerbHalf': with_verb,
        'buckets': sorted(shards),
    }
    with open(os.path.join(args.out, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f'{len(results)} of {len(targets)} words got a validated split '
          f'({with_verb} with a verb half) across {len(shards)} buckets')
    return 0


if __name__ == '__main__':
    sys.exit(main())
