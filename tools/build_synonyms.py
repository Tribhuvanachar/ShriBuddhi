#!/usr/bin/env python3
"""
build_synonyms.py — "what else means this?", from the reverse dictionary.

Monier-Williams' English-Sanskrit dictionary is a thesaurus read backwards.
Its entry for "again" lists पुनर्, पुनरपि, भूयस्, मुहुस्, असकृत् — a synonym set
that nothing else in the corpus states outright. Inverting the whole
dictionary gives, for any Sanskrit word, the other words that stand for the
same idea, with the English sense that binds them.

The one thing worth getting right is SENSE SPLITTING. A single entry covers
several distinct meanings, separated by em-dashes and parenthetical labels:

    AGAIN, adv. पुनर्, पुनरपि, भूयस्
    — (Moreover) अन्यच्च, किञ्च
    — (Repeatedly) मुहुस्, पुनःपुनर्, असकृत्

Harvesting that as one bag would make किञ्च a synonym of असकृत्, which is
wrong and would show a reader nonsense. Each dash-separated run becomes its
own group instead, carrying its own label.

    python3 tools/build_synonyms.py

Output: dge/data/_synonyms/<bucket>.json plus manifest.json, sharded by the
first two SLP1 characters exactly as dge/data/_morph is, so the client uses
one bucketing rule for both.
"""

import argparse
import collections
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'dge', 'data')
REVERSE = os.path.join(DATA, 'kosha', 'reverse')
OUT = os.path.join(DATA, '_synonyms')

DEVA_RUN = re.compile(r'[ऀ-ॿ]+')
# Grammatical tails Monier-Williams appends to a headword rather than to the
# sense: "विरुद्धः -द्धा -द्धं" is one word in three genders, not three words.
TAIL = re.compile(r'^-')
LABEL = re.compile(r'\(([^)]{2,40})\)')
# A parenthetical that is conjugation apparatus rather than a sense name:
# "(c. 1. -चāmati -चamituM)". Using it as a label would put grammar where the
# reader expects a meaning.
APPARATUS = re.compile(r'^(c\.|cl\.|\d|[ऀ-ॿ])|\bc\.\s*\d')
# Devanagari that is really punctuation or a citation, never a synonym.
NOISE = {'इति', 'च', 'वा', 'तु', 'अपि', 'एव', 'हि', 'ind', 'indec'}

MIN_GROUP = 2      # a "group" of one is not a synonym set
MAX_GROUP = 14     # a reader cannot use forty words at once
MAX_GROUPS = 6     # per word


def sense_chunks(gloss):
    """One entry, split into its distinct senses."""
    # The dash is the sense separator; newlines inside a sense are wrapping.
    flat = gloss.replace('\n', ' ')
    parts = re.split(r'\s*[—–]\s*', flat)
    for part in parts:
        if not part.strip():
            continue
        m = LABEL.search(part)
        label = m.group(1).strip() if m else ''
        if label and APPARATUS.search(label):
            label = ''
        yield label, part


def words_in(chunk):
    """The synonyms in one sense, and nothing else that happens to be Devanagari.

    Two things in the source look like words and are not:

      "विरुद्धः -द्धा -द्धं"   one word in three genders. The hyphenated tails
                              are continuations of the headword, and listing
                              them as synonyms produces gibberish like "ल्या".

      "(c. 1. -चामति -चमितुं)" the conjugation apparatus, which sits in
                              parentheses alongside the sense label.

    Both are removed before anything is extracted, which is why this works on
    the raw chunk rather than on DEVA_RUN's output — by then the hyphen and
    the bracket that identify them are gone.
    """
    chunk = re.sub(r'\([^)]*\)', ' ', chunk)          # grammatical notes
    chunk = re.sub(r'[-‑–]\s*[ऀ-ॿ]+', ' ', chunk)      # gender/stem tails
    out, seen = [], set()
    for tok in DEVA_RUN.findall(chunk):
        w = tok.strip('।॥,.;:')
        if len(w) < 2 or w in NOISE or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def bucket_of(slp):
    b = (slp + '__')[:2]
    return ''.join(c + '_' if c.isupper() else (c if c.isalnum() else 'x') for c in b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dict', default='mw-english-sanskrit')
    args = ap.parse_args()

    src = os.path.join(REVERSE, args.dict, 'e')
    if not os.path.isdir(src):
        print(f'no reverse dictionary at {src}', file=sys.stderr)
        return 1
    try:
        from vidyut import lipi
        from vidyut.lipi import Scheme
    except ImportError:
        print('vidyut is needed for the SLP1 bucketing. pip install vidyut', file=sys.stderr)
        return 1

    print('reading the reverse dictionary...')
    # word -> list of (english label, other words in that sense)
    related = collections.defaultdict(list)
    entries = groups = 0
    for path in sorted(glob.glob(os.path.join(src, '*.json'))):
        try:
            with open(path, encoding='utf-8') as fh:
                shard = json.load(fh)
        except (OSError, ValueError):
            continue
        for _, recs in shard.items():
            for rec in recs:
                head = rec.get('headword', '')
                entries += 1
                for sense in rec.get('senses', []):
                    for label, chunk in sense_chunks(sense.get('gloss', '')):
                        members = words_in(chunk)
                        if len(members) < MIN_GROUP:
                            continue
                        members = members[:MAX_GROUP]
                        groups += 1
                        name = f'{head} ({label})' if label else head
                        for w in members:
                            others = [x for x in members if x != w]
                            if others:
                                related[w].append([name, others])

    print(f'  {entries} entries, {groups} sense groups, {len(related)} words with relations')

    print('sharding...')
    buckets = collections.defaultdict(dict)
    for word, rels in related.items():
        # A word that appears in many senses gets the tightest groups first:
        # a three-word sense is a sharper statement than a fourteen-word one.
        rels.sort(key=lambda r: len(r[1]))
        slp = lipi.transliterate(word, Scheme.Devanagari, Scheme.Slp1)
        buckets[bucket_of(slp)][word] = rels[:MAX_GROUPS]

    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        os.remove(os.path.join(OUT, old))
    total = 0
    for name, entries_ in sorted(buckets.items()):
        p = os.path.join(OUT, name + '.json')
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(entries_, fh, ensure_ascii=False, separators=(',', ':'))
        total += os.path.getsize(p)

    manifest = {
        '_readme': 'Synonym groups inverted from the reverse (English-Sanskrit) '
                   'dictionary by tools/build_synonyms.py. Each entry is '
                   '[[english sense, [other words in that sense]], ...]. Bucketed by '
                   'the first two SLP1 characters, same rule as _morph. '
                   'Senses are split on the dictionary\'s own em-dashes so that words '
                   'from unrelated senses of one English headword are never presented '
                   'as synonyms of each other.',
        'v': 1,
        'source': args.dict,
        'buckets': sorted(buckets),
        'words': len(related),
        'groups': groups,
    }
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f'  {len(buckets)} buckets, {len(related)} words, {total / 1024 / 1024:.1f} MB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
