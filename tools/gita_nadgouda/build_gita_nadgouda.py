#!/usr/bin/env python3
"""Import Prof. Gururao V. Nadgouda & Smt. Indira Nadgouda's English
Bhagavad-Gītā (Mādhva, srimadhvyasa.wordpress.com) as a SECOND English
translation layer on the SarvaMula Gītā-Bhāṣya mūla, alongside Boray's.

The PDF is born-digital (MS Word) but its Devanāgarī extracts with the
matras reordered (unusable), so we take only the clean English translation:
each verse is anchored by an embedded «॥C-V॥» marker, and the translation
is the run of English (Latin-script) lines that follows it, up to the next
anchor (the interleaved Devanāgarī word-glosses are dropped — the mūla
already carries the verse). Aligned to the mūla's BGB_C<NN>_V<NN> ids.

Imported under the project lead's case-by-case-permission practice,
attributed to the authors. Run with --write to apply.
"""
import argparse
import html as _html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MULA = os.path.join(ROOT, 'dge/data/darshana/vedanta/dvaita/SarvaMula/'
                          'gita_prasthana/gita_bhashya/mula/data.json')
FAM = os.path.dirname(os.path.dirname(MULA))
LIB = os.path.join(ROOT, 'dge/data/library.json')
KEY = 'english_nadgouda'
LABEL = 'English (Nadgouda)'
SOURCE_URL = 'https://srimadhvyasa.wordpress.com/'
SOURCE_NOTE = ('“Śrīmad Bhagavad-Gītā with English translation” by '
               'Prof. Gururao V. Nadgouda & Smt. Indira Nadgouda '
               '(srimadhvyasa.wordpress.com) — a Mādhva rendering. Used with '
               'case-by-case permission of the project lead for '
               'non-commercial, educational dharma-prachara use, attributed '
               'to the authors.')

ANCHOR = re.compile(r'॥\s*(\d+)-(\d+)\s*॥')
DEVA = re.compile(r'[ऀ-ॿ]')
LATIN = re.compile(r'[A-Za-z]')
DROP = re.compile(r'^(Page\s+\d+|TOC:|https?://|अथ\b|\d+\s*$)')


def english_only(seg):
    """Keep the English translation lines from a between-anchors segment,
    dropping the interleaved Devanāgarī glosses and page furniture."""
    out = []
    for l in seg.split('\n'):
        s = l.strip()
        if not s or DROP.match(s):
            continue
        if 'srimadhvyasa' in s or 'sites.google' in s:
            continue
        if len(LATIN.findall(s)) > len(DEVA.findall(s)):   # English-dominant
            out.append(s)
    eng = ' '.join(out)
    eng = re.sub(r'^\s*\d+-\d+(?:/\d+)?\s*', '', eng)      # leading "C-V" ref
    eng = re.sub(r'[ऀ-ॿ]+', '', eng)                       # strip leaked Devanāgarī glosses
    eng = re.sub(r'\(\s*[-–.,;]*\s*\)', '', eng)           # empty parens left behind
    eng = re.sub(r'\s+([.,;)])', r'\1', eng)
    return re.sub(r'\s+', ' ', eng).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--txt', required=True)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    t = open(args.txt, encoding='utf-8').read()
    mula_ids = {it['id'] for it in json.load(open(MULA, encoding='utf-8'))['items']}

    anchors = [(int(m.group(1)), int(m.group(2)), m.start(), m.end())
               for m in ANCHOR.finditer(t)]
    seen = set()
    items = []
    import collections
    cov = collections.Counter()
    for i, (c, v, s, e) in enumerate(anchors):
        if not (1 <= c <= 18 and 1 <= v <= 100):
            continue
        vid = 'BGB_C%02d_V%02d' % (c, v)
        if vid in seen or vid not in mula_ids:
            continue
        nxt = anchors[i + 1][2] if i + 1 < len(anchors) else len(t)
        eng = english_only(t[e:nxt])
        if len(eng) < 15:
            continue
        seen.add(vid)
        cov[c] += 1
        items.append({
            'id': vid,
            'reference': 'Bhagavad Gītā %d.%d — English (Nadgouda)' % (c, v),
            'unit_title': '%d.%d' % (c, v),
            'sanskrit_text': '<div class="gita-translation">%s</div>' % _html.escape(eng),
            'tags': [], 'references': [],
            'tika_title': LABEL, 'source': {'layer': LABEL},
        })

    print('=== Gita English (Nadgouda) coverage ===')
    for c in range(1, 19):
        print('  ch %2d: %3d' % (c, cov.get(c, 0)))
    print('  TOTAL: %d verses' % len(items))

    if args.write:
        d = os.path.join(FAM, 'tika_%s' % KEY)
        os.makedirs(d, exist_ok=True)
        data = {'schema': 'grantha_mula_text',
                'default_author': 'Prof. Gururao V. Nadgouda & Smt. Indira Nadgouda',
                'title': 'गीताभाष्यम् — tika_%s' % KEY,
                'source_url': SOURCE_URL, 'source_note': SOURCE_NOTE, 'items': items}
        json.dump(data, open(os.path.join(d, 'data.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        lib = json.load(open(LIB, encoding='utf-8'))
        rel = 'dge/data/darshana/vedanta/dvaita/SarvaMula/gita_prasthana/gita_bhashya'
        p = '%s/tika_%s/data.json' % (rel, KEY)
        if p not in {x['path'] for x in lib['granthas']}:
            lib['granthas'].append({
                'path': p, 'populated': True, 'title': 'गीताभाष्यम् — tika_%s' % KEY,
                'addedAt': '2026-09-04', 'source': {'source_url': SOURCE_URL},
                'facets': {'default_author': 'Prof. Gururao V. Nadgouda & Smt. Indira Nadgouda'}})
            json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('  wrote tika_%s (%d items)' % (KEY, len(items)))


if __name__ == '__main__':
    main()
