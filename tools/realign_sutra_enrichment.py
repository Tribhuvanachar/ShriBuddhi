#!/usr/bin/env python3
"""Put each sutra's padaccheda, anvaya, type and gloss back on the sutra it
actually belongs to.

The enrichment in sutrapatha/data.json came from ashtadhyayi.com and was
joined to our mula text BY ID. The two sources do not agree on how many
sutras there are. Ours reads

    1.1.17  उञ ऊँ

as one sutra where the source counts two (उञः 1.1.17, ऊँ 1.1.18), so from
that point to the end of the pada every gloss sat one sutra late: our
1.1.19 दाधा घ्वदाप् carried the padaccheda and English of ईदूतौ च
सप्तम्यर्थे. It resets at each pada boundary and starts again wherever the
next disagreement is. Measured before this script existed: about 930 of
3962 sutras -- roughly a quarter of the Ashtadhyayi -- were described by
their neighbour's analysis, in the reader's padaccheda panel and in every
intellisense popover alike.

Joining by id cannot be repaired by shifting a fixed amount, because the
offset differs per pada. So this aligns the two sequences by their own
text: within each pada, our mula lines and the enrichment blocks (which
are still in source order) are matched with a Needleman-Wunsch alignment
scoring a mula line against a block's own padaccheda. Sandhi makes an
exact match impossible -- इको यणचि is split as इकः यण् अचि -- so the score
is consonant-bag overlap, which survives the vowel changes sandhi makes.

A block that aligns to nothing is dropped; a sutra that gets no block is
left with none. Both are reported. An empty panel is honest; a
confidently wrong one is not.

anuvritti references ("प्रगृह्यम् carries over from 1.1.11") are in source
numbering too, and are remapped through the same alignment.

    python3 tools/realign_sutra_enrichment.py           # report only
    python3 tools/realign_sutra_enrichment.py --apply   # rewrite data.json

Rebuild the reader's index afterwards:

    python3 tools/build_sutra_index.py
"""

import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'dge/data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json')

# The keys that came from the enrichment source and therefore travel together.
ENRICH_KEYS = ('padaccheda', 'anvaya', 'anuvritti', 'adhikara', 'sutra_type', 'english')

CONS = re.compile('[क-ह]')          # क .. ह
GAP = -0.45          # cost of leaving a mula line or a block unmatched
FLOOR = 0.34         # below this two lines are not the same sutra at all


def cons(text):
    return CONS.findall(unicodedata.normalize('NFC', text or ''))


def similarity(mula, block):
    """Consonant-bag F1 between a mula line and a block's own words."""
    words = block.get('padaccheda') or []
    other = ' '.join(words) or block.get('anvaya') or ''
    a, b = cons(mula), cons(other)
    if not a or not b:
        return 0.0
    inter = sum((Counter(a) & Counter(b)).values())
    return 2.0 * inter / (len(a) + len(b))


def align(mulas, blocks):
    """Needleman-Wunsch. Returns pairs (i, j); either may be None."""
    n, m = len(mulas), len(blocks)
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] + GAP
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] + GAP
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = similarity(mulas[i - 1], blocks[j - 1])
            diag = score[i - 1][j - 1] + (s if s >= FLOOR else GAP * 2)
            score[i][j] = max(diag, score[i - 1][j] + GAP, score[i][j - 1] + GAP)
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            s = similarity(mulas[i - 1], blocks[j - 1])
            diag = score[i - 1][j - 1] + (s if s >= FLOOR else GAP * 2)
            if abs(score[i][j] - diag) < 1e-9:
                pairs.append((i - 1, j - 1)); i -= 1; j -= 1; continue
        if i > 0 and abs(score[i][j] - (score[i - 1][j] + GAP)) < 1e-9:
            pairs.append((i - 1, None)); i -= 1; continue
        pairs.append((None, j - 1)); j -= 1
    pairs.reverse()
    return pairs


def pada_of(sid):
    a, p, _ = sid.split('.')
    return a + '.' + p


def main():
    apply_it = '--apply' in sys.argv
    doc = json.load(open(SRC, encoding='utf-8'))
    items = doc.get('items') or doc.get('sutras')
    key = 'items' if 'items' in doc else 'sutras'

    by_pada = defaultdict(list)
    for it in items:
        by_pada[pada_of(it['id'])].append(it)

    moved = kept = orphan_sutra = dropped_block = 0
    # source id -> our id, so anuvritti references can be remapped
    remap = {}
    plan = []            # (item, block or None)
    examples = []

    for pada in sorted(by_pada, key=lambda k: [int(x) for x in k.split('.')]):
        group = by_pada[pada]
        mulas = [it.get('sanskrit_text', '') for it in group]
        blocks, source_ids = [], []
        for n, it in enumerate(group, 1):
            b = {k: it[k] for k in ENRICH_KEYS if k in it}
            if b:
                blocks.append(b)
                # blocks are still in source order, so the nth block in this
                # pada is the source's nth sutra of the pada
                source_ids.append('%s.%d' % (pada, n))
        got = {}
        for i, j in align(mulas, blocks):
            if i is not None and j is not None:
                got[i] = blocks[j]
                remap[source_ids[j]] = group[i]['id']
                if source_ids[j] != group[i]['id']:
                    moved += 1
                    if len(examples) < 8:
                        examples.append((group[i]['id'], group[i].get('sanskrit_text', '')[:26],
                                         source_ids[j]))
                else:
                    kept += 1
            elif i is not None:
                orphan_sutra += 1
            else:
                dropped_block += 1
        for i, it in enumerate(group):
            plan.append((it, got.get(i)))

    print('Aṣṭādhyāyī enrichment realignment')
    print('  sutras                     %d' % len(items))
    print('  already on the right sutra %d' % kept)
    print('  moved to the right sutra   %d' % moved)
    print('  sutras left with no gloss  %d' % orphan_sutra)
    print('  glosses with no sutra here %d' % dropped_block)
    if examples:
        print('\n  for example:')
        for our, text, src in examples:
            print('    %-8s %-28s was carrying the gloss of %s' % (our, text, src))

    if not apply_it:
        print('\nReport only. Re-run with --apply to rewrite the file, then run'
              '\n  python3 tools/build_sutra_index.py')
        return 0

    fixed = 0
    for it, block in plan:
        for k in ENRICH_KEYS:
            it.pop(k, None)
        if block:
            for k in ENRICH_KEYS:
                if k in block:
                    it[k] = block[k]
            if 'anuvritti' in it:
                for ref in it['anuvritti']:
                    src = ref.get('from')
                    if src in remap:
                        if remap[src] != src:
                            fixed += 1
                        ref['from'] = remap[src]
                    elif src:
                        # the sutra it pointed at is one we do not carry
                        ref.pop('from', None)
    doc[key] = [it for it, _ in plan]
    doc.setdefault('enrichment', {})
    if isinstance(doc.get('enrichment'), dict):
        doc['enrichment']['alignment'] = (
            'Enrichment was joined by id, which the source numbers differently; '
            'realigned by text with tools/realign_sutra_enrichment.py.')
    with open(SRC, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    print('\n  anuvritti references remapped %d' % fixed)
    print('  wrote %s' % os.path.relpath(SRC, REPO))
    print('  now run: python3 tools/build_sutra_index.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
