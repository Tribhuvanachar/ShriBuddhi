#!/usr/bin/env python3
"""Import Śrī Krishnacharitra Manjari (Sanskrit kāvya by Śrī Rāghavendra
Tīrtha, with the Kannada vyākhyāna of his pūrvāśrama son Śrī
Lakṣmīnārāyaṇācārya, edited by Raja S. Gururajacharya) from a local
Tesseract-Kannada OCR of the scanned edition (~95%, ₹0, no Vision/Gemini).

The edition lays each verse out as: the Sanskrit verse (Kannada script),
then labelled Kannada sections — ವಿಗ್ರಹವಾಕ್ಯ (compound analysis),
ವಿಶೇಷ ವಿಚಾರಃ (special notes), ತಾತ್ಪರ್ಯ (meaning), ಕಥಾಭಿಪ್ರಾಯ (story
purport), ಅಲಂಕಾರ (figures). Verses close with «॥ N ॥».

This is a faithful FIRST-PASS import: the text is split into verse blocks on
the sequential «॥ N ॥» markers and each block (verse + its Kannada exposition)
is stored as one item, verse-numbered, so the whole edition is navigable and
searchable. A finer verse/commentary/section split is a later refinement.
The OCR is labelled unproofread. Run with --write to apply.
"""
import argparse
import html as _html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEST = os.path.join(ROOT, 'dge/data/darshana/vedanta/dvaita/DvaitaVedanta/'
                          'later_acharyas/krishnacharitra_manjari/mula')
LIB = os.path.join(ROOT, 'dge/data/library.json')
TITLE = 'श्रीकृष्णचरित्रमञ्जरी'
SOURCE_NOTE = ('Śrī Krishnacharitra Manjari — Sanskrit kāvya of Śrī Rāghavendra '
               'Tīrtha with the Kannada vyākhyāna of Śrī Lakṣmīnārāyaṇācārya '
               '(edited by Raja S. Gururajacharya, "Śrī Gururāja Sampuṭam"). '
               'Digitised by local Tesseract Kannada OCR of the scanned edition '
               '(~95%, not yet proofread). Imported under the project lead\'s '
               'case-by-case-permission practice for non-commercial, educational '
               'dharma-prachara use.')

KD = {c: str(i) for i, c in enumerate('೦೧೨೩೪೫೬೭೮೯')}
VEND = re.compile(r'॥\s*([೦-೯0-9]+)\s*॥')
# lines that are pure page furniture (running header + page number)
FURNITURE = re.compile(r'(ಶ್ರೀಗುರುರಾಜಸಂಪುಟಮ|ಶ್ರೀಕೃಷ್ಣಚಾರಿತ್ರಮಂಜರೀ)\s*\d*\s*$')


def kn2i(s):
    return int(''.join(KD.get(c, c) for c in s))


def clean(block):
    out = []
    for l in block.split('\n'):
        s = l.strip()
        if not s or FURNITURE.match(s):
            continue
        s = re.sub(r'^\d+\s+(?=\S)', '', s)          # leading page number
        out.append(s)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--txt', required=True)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    t = open(args.txt, encoding='utf-8').read()

    # sequential ॥N॥ markers: accept a marker whose number advances by a small
    # step (real kāvya verse-ends), skipping the many quoted verses in prose.
    marks = []
    maxv = 0
    for m in VEND.finditer(t):
        n = kn2i(m.group(1))
        if maxv < n <= maxv + 3:
            marks.append((n, m.end()))
            maxv = n

    items = []
    prev = 0
    for i, (n, end) in enumerate(marks):
        block = clean(t[prev:end])
        prev = end
        if len(block) < 40:
            continue
        items.append({
            'id': 'KCM_%03d' % n,
            'reference': '%s · पद्यम् %d' % (TITLE, n),
            'unit_title': 'पद्यम् %d' % n,
            'sanskrit_text': block,
            'artha': '', 'tags': [], 'references': [],
            'breadcrumb': ['श्रीकृष्णचरित्रमञ्जरी', 'पद्यम् %d' % n],
        })

    print('=== Krishnacharitra Manjari ===')
    print('  verse blocks: %d (verses %s..%s)'
          % (len(items), items[0]['id'] if items else '-',
             items[-1]['id'] if items else '-'))
    print('  total chars: %d' % sum(len(it['sanskrit_text']) for it in items))

    if args.write:
        os.makedirs(DEST, exist_ok=True)
        data = {'schema': 'grantha_mula_text',
                'default_author': 'श्रीराघवेन्द्रतीर्थः',
                'title': TITLE, 'source_note': SOURCE_NOTE, 'items': items}
        json.dump(data, open(os.path.join(DEST, 'data.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        lib = json.load(open(LIB, encoding='utf-8'))
        p = ('dge/data/darshana/vedanta/dvaita/DvaitaVedanta/later_acharyas/'
             'krishnacharitra_manjari/mula/data.json')
        if p not in {e['path'] for e in lib['granthas']}:
            lib['granthas'].append({
                'path': p, 'populated': True, 'title': TITLE + ' — mula',
                'addedAt': '2026-09-04', 'source': {},
                'facets': {'default_author': 'श्रीराघवेन्द्रतीर्थः'}})
            json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('  wrote %d items' % len(items))


if __name__ == '__main__':
    main()
