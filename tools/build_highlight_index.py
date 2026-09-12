#!/usr/bin/env python3
"""
build_highlight_index.py — the word-presence index behind the reader's
highlighting: which words in a verse or a commentary are ones we can actually
say something about.

WHY THIS AND NOT THE INDEXES WE ALREADY HAVE. The project lead asked (9 Sep
2026) for "dhatus in the sloka highlighted with a special background color"
and for "matched koshas in the commentary" to carry the same mark. Both
answers already exist in this repo, but neither in a shape a renderer can
consult:

  prakriya/formindex/       204,970 tiṅanta forms, and prakriya/krtindex/
  prakriya/krtindex/        48,886 kṛdantas, both bucketed by FIRST LETTER
                            ONLY — the अ shard alone is 3.5 MB. Fetching it
                            to decide the colour of one word is absurd.
  kosha/<cat>/<dict>/e/     the dictionaries themselves, 54 MB of glosses,
                            of which highlighting needs precisely the
                            headword list and nothing else.

So this reduces both to the one bit each that highlighting needs — "is this
word a verb form", "is this word a कोश headword" — and shards them two
characters deep, which is what turns a 3.5 MB fetch into a ~10 KB one. The
gloss, the paradigm, the root: all still come from the full indexes, but
only once the reader actually taps the word.

COVERAGE IS DELIBERATELY CONSERVATIVE. The कोश headwords here come from the
dictionaries shipped IN THIS REPO; at runtime the reader's tap resolves
against appConfig.koshaDataBase, a larger mirror on a CDN. That asymmetry is
the safe direction: every word this marks is one the tap can answer, and
words only the CDN set knows go unmarked rather than marked-and-empty. If
the two are ever brought level, rebuild from whichever is the superset.

WHAT A MARK MEANS, AND WHAT IT DOES NOT. A highlight is a promise that
tapping gets you somewhere, not a claim of analysis. A कोश mark means the
written form IS a headword — an inflected form in a commentary generally is
not, and is honestly left unmarked rather than guessed at. Nothing here
does morphology; that is what tapping the word is for.

    python3 tools/build_highlight_index.py

Output: dge/data/_highlight/<bucket>.json  {"k"|"d"|"b": newline-joined words}
        k = कोश headword, d = verb form, b = both; plus manifest.json
"""

import argparse
import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KOSHA_DIR = os.path.join(REPO, 'dge', 'data', 'kosha')
FORM_DIR = os.path.join(REPO, 'dge', 'data', 'vedanga', 'vyakarana', 'prakriya', 'formindex')
KRT_DIR = os.path.join(REPO, 'dge', 'data', 'vedanga', 'vyakarana', 'prakriya', 'krtindex')
OUT_DIR = os.path.join(REPO, 'dge', 'data', '_highlight')

# Sanskrit-headword categories. `reverse/` is MW English-Sanskrit, whose
# headwords are English words and would mark nothing in a Devanagari text.
KOSHA_CATEGORIES = ('sanskrit_english', 'sanskrit_kannada', 'sanskrit_sanskrit')

MARK_KOSHA = 1
MARK_DHATU = 2

# Punctuation a word carries in running text. The renderer strips the same
# set before looking a word up, so the two sides have to agree exactly.
STRIP = '।॥॰,.;:!?"\'()[]{}—–-…*' + '​‌‍⁠'


# Devanagari proper, plus the Vedic extensions a corpus word may carry.
DEVANAGARI = tuple(range(0x0900, 0x0980)) + tuple(range(0xA8E0, 0xA900)) + tuple(range(0x1CD0, 0x1D00))
DEVANAGARI = frozenset(chr(c) for c in DEVANAGARI)


def normalise(word):
    """The lookup key: a bare Devanagari word, punctuation and avagraha off."""
    w = (word or '').strip().strip(STRIP)
    w = w.replace('ऽ', '')
    return w.strip(STRIP)


def is_devanagari(word):
    """Marks only ever land on Devanagari text, so a word carrying no
    Devanagari at all cannot be one. This is not pedantry: the verb form
    index ships a manifest.json alongside its shards, and reading its keys
    as forms put '_readme' and 'shardCount' into the index."""
    return any(c in DEVANAGARI for c in word)


def prefix_of(word, depth):
    """The first `depth` codepoints in hex. Two characters deep is what keeps a
    shard small: one character leaves अ holding a fifth of the whole index."""
    return ''.join('%04x' % ord(c) for c in word[:depth]).ljust(depth * 4, '0')


def kosha_headwords(kosha_dir=KOSHA_DIR):
    """Every Devanagari headword the shipped dictionaries actually carry.

    Read from the entry shards rather than _index/, because _index/ holds
    only the buckets imported so far — it answers for क but not for भ, and a
    highlight that appears for half the alphabet is worse than none."""
    out = set()
    for cat in KOSHA_CATEGORIES:
        cat_dir = os.path.join(kosha_dir, cat)
        if not os.path.isdir(cat_dir):
            continue
        for dict_slug in sorted(os.listdir(cat_dir)):
            edir = os.path.join(cat_dir, dict_slug, 'e')
            if not os.path.isdir(edir):
                continue
            for path in sorted(glob.glob(os.path.join(edir, '*.json'))):
                with open(path, encoding='utf-8') as fh:
                    shard = json.load(fh)
                for items in shard.values():
                    for item in items:
                        w = normalise(item.get('headword'))
                        if w and is_devanagari(w):
                            out.add(w)
    return out


def verb_forms(form_dir=FORM_DIR, krt_dir=KRT_DIR):
    """Every verb form the reader can tap and get an answer for.

    BOTH indexes, not just the finite one. formindex holds tiṅanta forms
    (गच्छति, चकार); krtindex holds kṛdantas — कृत्वा, गत्वा, कृतम्, लब्धव्य —
    words that are verb-derived and everywhere in the corpus. Marking only the
    first meant कृत्वा, the single most common absolutive in the language, was
    left unmarked while the Śabda tool answers it perfectly. The mark is a
    promise that tapping gets you somewhere; it has to cover everything that
    does."""
    out = set()
    for d in (form_dir, krt_dir):
        if not d or not os.path.isdir(d):
            continue
        for path in sorted(glob.glob(os.path.join(d, '*.json'))):
            if os.path.basename(path) == 'manifest.json':
                continue
            with open(path, encoding='utf-8') as fh:
                shard = json.load(fh)
            for form in shard:
                w = normalise(form)
                if w and is_devanagari(w):
                    out.add(w)
    return out


def build(kosha, forms, min_len=2):
    """word -> mask. Single-letter words are dropped: they are overwhelmingly
    particles and sandhi debris, and marking every अ in a page is noise."""
    marks = {}
    for w in kosha:
        if len(w) >= min_len:
            marks[w] = marks.get(w, 0) | MARK_KOSHA
    for w in forms:
        if len(w) >= min_len:
            marks[w] = marks.get(w, 0) | MARK_DHATU
    return marks


# Two characters is right for almost every bucket and badly wrong for a few:
# वि- alone holds 8,700 words, because half the upasarga-prefixed verbs in the
# language start there. Those get split a character deeper, exactly as the
# कोश importer does with its own oversized prefixes, and the manifest names
# them so the reader knows to walk down instead of guessing.
SHARD_CAP = 48 * 1024


def encode(words_by_mask):
    """A shard is three newline-joined runs, not an object of word->number.
    The mask is one of three values, so naming it once per run rather than
    once per word takes ~30% off the wire — on 250k words that is 2 MB."""
    out = {}
    for key, mask in (('k', MARK_KOSHA), ('d', MARK_DHATU), ('b', MARK_KOSHA | MARK_DHATU)):
        run = words_by_mask.get(mask)
        if run:
            out[key] = '\n'.join(sorted(run))
    return out


def _serialise(bucket):
    return json.dumps(bucket, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def shard(marks, cap=SHARD_CAP):
    """{prefix: encoded_shard}, plus the list of 2-char prefixes that had to be
    split deeper for the client to walk down."""
    groups = {}
    for w, m in marks.items():
        groups.setdefault(prefix_of(w, 2), {}).setdefault(m, []).append(w)

    buckets, deep = {}, []
    for prefix, by_mask in sorted(groups.items()):
        encoded = encode(by_mask)
        if len(_serialise(encoded).encode('utf-8')) <= cap:
            buckets[prefix] = encoded
            continue
        deep.append(prefix)
        finer = {}
        for mask, words in by_mask.items():
            for w in words:
                finer.setdefault(prefix_of(w, 3), {}).setdefault(mask, []).append(w)
        for sub, sub_by_mask in finer.items():
            buckets[sub] = encode(sub_by_mask)
    return buckets, deep


def write(buckets, deep, marks, out_dir=OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    for stale in glob.glob(os.path.join(out_dir, '*.json')):
        os.remove(stale)
    biggest = 0
    for name, data in buckets.items():
        path = os.path.join(out_dir, name + '.json')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(_serialise(data))
        biggest = max(biggest, os.path.getsize(path))
    manifest = {
        'buckets': sorted(buckets),
        'deep': sorted(deep),
        'bucket_depth': 2,
        'marks': {'kosha': MARK_KOSHA, 'dhatu': MARK_DHATU},
        'words': len(marks),
        'kosha_words': sum(1 for m in marks.values() if m & MARK_KOSHA),
        'dhatu_words': sum(1 for m in marks.values() if m & MARK_DHATU),
        'largest_shard_bytes': biggest,
    }
    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=OUT_DIR)
    ap.add_argument('--min-len', type=int, default=2)
    args = ap.parse_args(argv)

    print('reading कोश headwords…', flush=True)
    kosha = kosha_headwords()
    print('  %d' % len(kosha))
    print('reading verb forms…', flush=True)
    forms = verb_forms()
    print('  %d' % len(forms))

    marks = build(kosha, forms, args.min_len)
    buckets, deep = shard(marks)
    manifest = write(buckets, deep, marks, args.out)
    print('%d words in %d shards, largest %.1f KB' % (
        manifest['words'], len(buckets), manifest['largest_shard_bytes'] / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
