#!/usr/bin/env python3
"""
build_wordnet.py — the Sanskrit WordNet, as a lookup layer for the reader.

IndoWordNet (CFILT, IIT Bombay) holds 37,757 Sanskrit synsets. A synset is a
set of words that mean the same thing, with a definition and a usage example
— and, unusually for a machine-readable resource, BOTH ARE IN SANSKRIT:

    खण्डमोदकः, खण्डः, उपला, शुक्तोपला, शर्करा, सिताखण्डः, दृढगात्रिका
    माक्षीककृता शर्करा।
    सः खण्डमोदकान् अत्ति।

That is a Sanskrit definition of a Sanskrit word, which the rest of this
library does not have. The koshas gloss Sanskrit in English or Kannada; the
reverse-dictionary groups that tools/build_synonyms.py extracts are bound by
an ENGLISH sense. This is the only source here where the definition is in the
language being read.

It is also the only source where a synonym set is asserted rather than
inferred. build_synonyms.py inverts a bilingual dictionary, so its groups mix
true synonyms with words that merely shared a gloss — which is why the reader
is shown the English sense and asked to judge. A WordNet synset is a lexicog-
rapher's claim that these words denote one concept. The two belong in the
popover as separate sections, under their own names, and are kept apart here
for exactly that reason.

WHAT THIS SCRIPT HAS TO GET RIGHT

  1. THE HEADWORD ENDINGS. IndoWordNet lists nominal members inflected —
     खण्डमोदकः, मिष्टान्नम् — while Vidyut's analysis (dge/data/_morph) and the
     koshas both key on the stem: खण्डमोदक, मिष्टान्न. A reader who taps a word
     arrives with a stem. Indexing only what the file says would mean a lookup
     that almost never fires, so every member is also indexed under its stem
     with the nominative -ः / -म् taken off. Stripping the ending does not
     change the first two SLP1 characters, so both keys land in one bucket.

  2. THE DUPLICATED PART-OF-SPEECH COLUMN. 146 of the 37,757 lines carry the
     pos twice — `adjective:""	noun` — and the two do not always agree. The
     first one is taken: on the lines where they differ it is the one that
     matches the entry (दीनवत्सल "kind to the poor" is an adjective, and the
     trailing column says noun). pyiwn's own regex reads the LAST column and
     folds the stray `:""` into the gloss; this parser splits on tabs instead,
     which is why it also keeps the 4 six-column lines that regex mangles.

  3. HYPERNYMS ARE CROSS-LINGUAL. IndoWordNet's relation files are stated
     between synset IDs, not words, and the IDs are shared by all eighteen
     languages. So hypernymy.noun covers Sanskrit synsets even though nothing
     in it is Sanskrit — 19,322 of them have one. Each entry carries the head
     word of its hypernym synset, which is what turns a synonym list into
     "…, a kind of मिष्टान्नम्".

  Kannada equivalents ride the same shared IDs (--languages), which is worth
  having in a library whose readers are largely Kannada-speaking, and whose
  koshas already gloss in Kannada. They are the KANNADA WORDNET'S words for
  that synset, not a translation of the Sanskrit one, and the two are not
  always the same sense: synset 117 is भक्तिः "ईश्वरं प्रति अनुरागः" in Sanskrit
  and ಭಕ್ತ, the devotee rather than the devotion, in Kannada. Spot checks put
  that in a minority — जल/ನೀರು, मोक्षः/ಮೋಕ್ಷ, गुरुः/ಗುರು all line up — but it is
  a defect in the source that this script cannot detect, and PENDING.md
  carries it as an open question. `--languages ""` drops the column.

SOURCE AND LICENCE

  The data is the IndoWordNet dump distributed with pyiwn (CFILT, IIT Bombay),
  fetched from the URL in pyiwn/constants.py. The pyiwn distribution carries
  CC BY-SA 4.0. Attribution — "IndoWordNet, CFILT, IIT Bombay" — is stamped
  into the manifest so it travels with the data, the way the koshas carry
  theirs. IndoWordNet's own site frames the data as for research use; whether
  that and CC BY-SA agree is a question for the project lead, and PENDING.md
  records it as an open one rather than this script deciding it.

USAGE

    python3 tools/build_wordnet.py --download        # fetches ~30 MB once
    python3 tools/build_wordnet.py --src ~/iwn_data  # already extracted

Output: dge/data/_wordnet/<bucket>.json plus manifest.json, bucketed by the
first two SLP1 characters exactly as _morph and _synonyms are, so the client
uses one bucketing rule for all three.
"""

import argparse
import collections
import json
import os
import re
import sys
import tarfile
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'dge', 'data', '_wordnet')

# From pyiwn/constants.py. Roughly 30 MB, all eighteen languages.
DATA_URL = 'https://www.dropbox.com/s/t29eqq19nt5eygs/iwn_data.tar.gz?dl=1'

POS = {'noun': 'n', 'verb': 'v', 'adjective': 'a', 'adverb': 'd'}

# Relation files are named <relation>.<pos>; these are the ones that say
# "is a kind of". Meronymy and troponymy are in the dump too and are not read:
# a popover has room for one relation, and "a kind of X" is the one that
# orients a reader who does not know the word at all.
HYPERNYM_FILES = ['hypernymy.noun', 'hypernymy.verb']

MAX_SYNSETS = 6      # per word — a popover the reader can read
MAX_MEMBERS = 12     # per synset
MAX_FOREIGN = 4      # per synset, per language

DEVA = re.compile(r'[ऀ-ॿ]')

# ---------------------------------------------------------------- SLP1 ---
# Ported from dge/js/intellisense.js rather than taken from vidyut, because
# the bucket a lookup fetches is computed by that JS at runtime. If the two
# transliterations ever disagreed the client would fetch the wrong file and
# find nothing, so the rule is copied verbatim instead of reimplemented.
SLP = {'अ': 'a', 'आ': 'A', 'इ': 'i', 'ई': 'I', 'उ': 'u', 'ऊ': 'U', 'ऋ': 'f',
       'ॠ': 'F', 'ऌ': 'x', 'ॡ': 'X', 'ए': 'e', 'ऐ': 'E', 'ओ': 'o', 'औ': 'O',
       'क': 'k', 'ख': 'K', 'ग': 'g', 'घ': 'G', 'ङ': 'N', 'च': 'c', 'छ': 'C',
       'ज': 'j', 'झ': 'J', 'ञ': 'Y', 'ट': 'w', 'ठ': 'W', 'ड': 'q', 'ढ': 'Q',
       'ण': 'R', 'त': 't', 'थ': 'T', 'द': 'd', 'ध': 'D', 'न': 'n', 'प': 'p',
       'फ': 'P', 'ब': 'b', 'भ': 'B', 'म': 'm', 'य': 'y', 'र': 'r', 'ल': 'l',
       'व': 'v', 'श': 'S', 'ष': 'z', 'स': 's', 'ह': 'h', 'ळ': 'L', 'ं': 'M',
       'ः': 'H', 'ँ': '~'}
SLP_M = {'ा': 'A', 'ि': 'i', 'ी': 'I', 'ु': 'u', 'ू': 'U', 'ृ': 'f', 'ॄ': 'F',
         'ॢ': 'x', 'ॣ': 'X', 'े': 'e', 'ै': 'E', 'ो': 'o', 'ौ': 'O'}


def to_slp(word):
    out = []
    i = 0
    while i < len(word):
        ch = word[i]
        if ch in SLP and ch not in SLP_M:
            out.append(SLP[ch])
            if 'क' <= ch <= 'ह' or ch == 'ळ':
                nxt = word[i + 1] if i + 1 < len(word) else ''
                if nxt == '्':
                    i += 2
                    continue
                if nxt in SLP_M:
                    out.append(SLP_M[nxt])
                    i += 2
                    continue
                out.append('a')
            i += 1
            continue
        if ch in SLP_M:
            out.append(SLP_M[ch])
        i += 1
    return ''.join(out)


def bucket_of(slp):
    b = (slp + '__')[:2]
    return ''.join(c + '_' if c.isupper() else (c if c.isalnum() else 'x') for c in b)


# ------------------------------------------------------------- parsing ---
def parse_line(line):
    """One line of synsets/all.<language>, or None if it is not a synset.

    id \t word,word,… \t gloss:"example" \t pos [\t pos …]

    Sanskrit's own colon is the visarga ः, a different character from the
    ASCII one, so splitting the gloss from the example on the first : is safe
    here in a way it would not be in a Latin-script WordNet.
    """
    parts = line.rstrip('\n').split('\t')
    if len(parts) < 4 or not parts[0].isdigit():
        return None
    sid = int(parts[0])
    words = [w.strip() for w in parts[1].split(',') if w.strip()]
    if not words:
        return None
    pos = POS.get(parts[3].split(':')[0].strip())
    if not pos:
        return None

    field = parts[2].strip()
    gloss, _, tail = field.partition(':')
    gloss = gloss.strip()
    example = ''
    if tail:
        # The example is usually quoted and sometimes not, so the quote cannot
        # be what identifies it. Where a synset carries several, they sit
        # inside ONE pair of quotes separated by a slash — "…आधारम्। /अजीर्णे
        # जलम्…" — which is why the split happens after the quotes come off.
        # A popover shows one whole sentence; the rest are dropped rather than
        # run together.
        quoted = re.findall(r'"([^"]*)"', tail)
        example = (quoted[0] if quoted else tail).strip()
        example = example.split('/')[0].strip()
    if not gloss:
        return None
    return sid, words, gloss, example, pos


def read_synsets(path):
    out = {}
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            rec = parse_line(line)
            if rec:
                out[rec[0]] = rec[1:]
    return out


def read_relation(path, keep):
    """<synset id>\t<comma-separated synset ids>, filtered to ids we have."""
    rel = {}
    if not os.path.exists(path):
        return rel
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            src = int(parts[0])
            if src not in keep:
                continue
            for tok in parts[1].split(','):
                tok = tok.strip()
                if tok.isdigit() and int(tok) in keep and int(tok) != src:
                    rel[src] = int(tok)
                    break        # one hypernym is what the popover shows
    return rel


def dedupe(words):
    out, seen = [], set()
    for w in words:
        w = w.strip()
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def keys_for(word):
    """The word as IndoWordNet writes it, plus the stem a reader arrives with.

    Only the two nominative endings that IndoWordNet actually uses on its
    nominal members are stripped. Anything more aggressive — taking off -ा,
    -ी, -आ — would collapse feminine stems that are already stems (अम्बादेवी,
    गोल्फक्रीडिका) onto forms that do not exist.
    """
    keys = [word]
    if word.endswith('ः') and len(word) > 2:
        keys.append(word[:-1])
    elif word.endswith('म्') and len(word) > 3:
        keys.append(word[:-2])
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', help='an extracted iwn_data/ directory')
    ap.add_argument('--download', action='store_true',
                    help='fetch and extract the IndoWordNet dump first')
    ap.add_argument('--cache', default=os.path.join(REPO, '.cache', 'iwn'),
                    help='where --download puts it')
    ap.add_argument('--languages', default='kannada',
                    help='comma-separated other IndoWordNet languages to carry '
                         'equivalents from, or "" for none')
    ap.add_argument('--no-examples', action='store_true',
                    help='drop usage sentences (roughly a third of the output)')
    args = ap.parse_args()

    src = args.src
    if args.download:
        os.makedirs(args.cache, exist_ok=True)
        tgz = os.path.join(args.cache, 'iwn_data.tar.gz')
        if not os.path.exists(tgz):
            print(f'fetching {DATA_URL}')
            urllib.request.urlretrieve(DATA_URL, tgz)
        with tarfile.open(tgz) as tf:
            # A tarball off the internet is not trusted to stay inside the
            # directory it is extracted into. `filter='data'` is Python 3.12's
            # default and 3.11's opt-in; older ones get the unguarded call.
            try:
                tf.extractall(args.cache, filter='data')
            except TypeError:
                tf.extractall(args.cache)
        src = os.path.join(args.cache, 'iwn_data')
    if not src:
        print('need --src <iwn_data dir> or --download', file=sys.stderr)
        return 1
    sa_path = os.path.join(src, 'synsets', 'all.sanskrit')
    if not os.path.exists(sa_path):
        print(f'no Sanskrit synsets at {sa_path}', file=sys.stderr)
        return 1

    print('reading the Sanskrit synsets...')
    synsets = read_synsets(sa_path)
    print(f'  {len(synsets)} synsets')

    print('reading hypernyms...')
    hyper = {}
    for name in HYPERNYM_FILES:
        hyper.update(read_relation(os.path.join(src, 'synset_relations', name), synsets))
    print(f'  {len(hyper)} synsets have one')

    langs = [l.strip() for l in args.languages.split(',') if l.strip()]
    foreign = {}
    for lang in langs:
        p = os.path.join(src, 'synsets', 'all.' + lang)
        if not os.path.exists(p):
            print(f'  no {lang} synsets, skipping', file=sys.stderr)
            continue
        other = read_synsets(p)
        # IndoWordNet writes multiword members with underscores and repeats a
        # member outright in places (synset 117's Kannada side lists
        # ಆರಾಧನೆ_ಮಾಡುವವನು twice), neither of which should reach a reader.
        shared = {sid: dedupe(w.replace('_', ' ') for w in rec[0])[:MAX_FOREIGN]
                  for sid, rec in other.items() if sid in synsets}
        foreign[lang] = shared
        print(f'  {len(shared)} synsets also in {lang}')

    print('sharding...')
    # Within a bucket a synset is stored ONCE and its words point at it by
    # index. Written the obvious way — the whole record inlined under every
    # word it contains — the same gloss and example are repeated for each of
    # the synset's members and again for each member's stem key, and the
    # output comes to 40 MB instead of the 12 it needs to be. Only the
    # word->index map is per-word; a synset still repeats across buckets when
    # its members start with different letters, which is the price of a
    # lookup that fetches exactly one file.
    buckets = collections.defaultdict(lambda: {'s': [], 'w': collections.defaultdict(list)})
    seen = {}
    for sid, (words, gloss, example, pos) in sorted(synsets.items()):
        members = words[:MAX_MEMBERS]
        head = synsets[hyper[sid]][0][0] if sid in hyper else ''
        langvals = [foreign[l].get(sid, []) for l in langs if l in foreign]
        rec = [pos, gloss, '' if args.no_examples else example, members, head] + langvals
        for word in members:
            if not DEVA.search(word):
                continue
            slp = to_slp(word)
            if not slp:
                continue
            b = bucket_of(slp)
            bucket = buckets[b]
            at = seen.get((b, sid))
            if at is None:
                at = seen[(b, sid)] = len(bucket['s'])
                bucket['s'].append(rec)
            for key in keys_for(word):
                if at not in bucket['w'][key]:
                    bucket['w'][key].append(at)

    # Senses are kept in ascending synset id, which is why the loop above runs
    # sorted. The ids run oldest-first: IndoWordNet was seeded from a core
    # vocabulary and extended outwards, so the earliest synset a word belongs
    # to is reliably its central sense — भक्तिः is "ईश्वरं प्रति अनुरागः" at 117
    # and a metrical foot at 31253. Ordering by how many words a synset holds
    # instead, as the reverse-dictionary groups are ordered, would open अश्वः
    # on the chess piece: that synset has one member and the horse has six.
    words_total = 0
    for bucket in buckets.values():
        for ids in bucket['w'].values():
            del ids[MAX_SYNSETS:]
        words_total += len(bucket['w'])

    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        os.remove(os.path.join(OUT, old))
    total = 0
    for name, bucket in sorted(buckets.items()):
        p = os.path.join(OUT, name + '.json')
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump({'s': bucket['s'], 'w': bucket['w']}, fh,
                      ensure_ascii=False, separators=(',', ':'))
        total += os.path.getsize(p)

    manifest = {
        '_readme':
            'The Sanskrit WordNet, built by tools/build_wordnet.py from the '
            'IndoWordNet dump distributed with pyiwn. A bucket is '
            '{s: [synset, ...], w: {word: [indices into s]}} — the synsets a '
            'word belongs to, most specific first, stored once per bucket '
            'rather than once per member. A synset is '
            '[pos, gloss, example, [all its words], hypernym, [' +
            ', '.join(langs) + ']]; the word being looked up is among its own '
            'words and the caller drops it. pos is n/v/a/d. The gloss and the example '
            'are Sanskrit, which is what this source has that the koshas do '
            'not. Words are indexed both as IndoWordNet writes them '
            '(inflected: खण्डमोदकः) and as a reader arrives at them (stem: '
            'खण्डमोदक). Bucketed by the first two SLP1 characters, same rule '
            'as _morph and _synonyms.',
        'v': 1,
        'source': 'IndoWordNet (CFILT, IIT Bombay), via the pyiwn data dump',
        'source_url': DATA_URL,
        'licence': 'CC BY-SA 4.0 per the pyiwn distribution; attribution required',
        'attribution': 'IndoWordNet, CFILT, IIT Bombay',
        'languages': langs,
        'synsets': len(synsets),
        'words': words_total,
        'hypernyms': len(hyper),
        'examples': not args.no_examples,
        'buckets': sorted(buckets),
    }
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f'  {len(buckets)} buckets, {words_total} words, {total / 1024 / 1024:.1f} MB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
