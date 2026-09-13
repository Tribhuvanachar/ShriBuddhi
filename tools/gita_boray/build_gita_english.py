#!/usr/bin/env python3
"""Import Dr. Giridhar Boray's English Bhagavad-Gītā (based on Śrī Rāghavendra
Tīrtha's Gītā-Vivṛti, upanishat.com, 2021) as an English translation +
commentary layer on the SarvaMula Gītā-Bhāṣya mūla.

The PDF (born-digital, no OCR) lays each verse out as:
    <topic heading>
    <Devanāgarī in a legacy non-Unicode font — mojibake, ends "&& N &&">
    <IAST transliteration, 2 or 4 lines>
    <English translation>              (C.V)
    Comments: <exposition>             — until the next verse
The Devanāgarī is discarded (the mūla already carries correct Unicode
Devanāgarī per chapter.verse); we keep the clean IAST + translation +
comments, aligned to the mūla's BGB_C<NN>_V<NN> ids.

Copyright: a living author's 2021 work with an explicit no-reproduction
clause. Imported under the project lead's case-by-case-permission practice
(their responsibility), attributed to the author, non-commercial
dharma-prachara. Run with --write to apply.
"""
import argparse
import html as _html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MULA = os.path.join(ROOT, 'dge/data/darshana/vedanta/dvaita/SarvaMula/'
                          'gita_prasthana/gita_bhashya/mula/data.json')
FAM = os.path.dirname(os.path.dirname(MULA))          # .../gita_bhashya
LIB = os.path.join(ROOT, 'dge/data/library.json')
KEY = 'english_boray'
LABEL = 'English (Boray, on Rāghavendra Tīrtha\'s Gītā-Vivṛti)'
SOURCE_URL = 'https://upanishat.com/'
SOURCE_NOTE = ('“The Bhagavad Gita”, English translation & commentary by '
               'Dr. Giridhar Boray, based on Śrī Rāghavendra Tīrtha\'s '
               'Gītā-Vivṛti and the lectures of HH Sri Vidyāsāgara Mādhava '
               'Tīrtha (Publisher: upanishat.com, ISBN 978-81-928503-4-4, '
               '© 2021 Giridhar Boray, all rights reserved). Used with '
               'case-by-case permission of the project lead for '
               'non-commercial, educational dharma-prachara use; not to be '
               'reproduced without the copyright holder\'s permission.')

IAST_DIAC = set('āīūṛṝḷḹṅñṭḍṇśṣṃḥ')


def load_body(txt_path):
    t = open(txt_path, encoding='utf-8').read()
    m = re.search(r'Chapter 1 \(\d+ verses\)', t)
    return t[m.start():]


REF = re.compile(r'\((\d+)\.(\d+)(?:\s*[-–]\s*\d+)?\)')


def verse_anchors(body):
    """Walk every '(C.V)' ref in document order and keep only the ones that
    ADVANCE the verse sequence (C rising, or same C with V rising) — this
    turns the running verse markers into clean per-verse end-anchors and
    discards the many cross-citations in the comments (which repeat earlier
    numbers out of order). -> [(c, v, ref_start, ref_end)]."""
    out = []
    curc, maxv = 1, 0
    for m in REF.finditer(body):
        c, v = int(m.group(1)), int(m.group(2))
        # Only a SMALL forward step is a real next-verse (allowing combined
        # verses to skip a few); a big jump within the chapter is a citation
        # in the comments, and at a chapter turn a real first verse is 1-3.
        if c == curc and maxv < v <= maxv + 5:
            out.append((c, v, m.start(), m.end())); maxv = v
        elif c == curc + 1 and v <= 3:
            out.append((c, v, m.start(), m.end())); curc, maxv = c, v
    return out


LEGACY = set('$©{}&Ê®°ÑîQï>ìí²^~`ª«»¬')


def is_iast_line(l):
    s = l.strip()
    if not s or len(s) < 4:
        return False
    if any(ch in LEGACY for ch in s):    # legacy-font Devanagari mojibake, not IAST
        return False
    if any(ch in IAST_DIAC for ch in s):
        low = ' ' + s.lower() + ' '
        if not re.search(r' (the|and|of|to|is|that|this|with|for|are|you) ', low):
            return True
    return False


def clean_prose(s):
    """Unwrap hard line-wraps to a flowing paragraph; drop page furniture."""
    s = re.sub(r'\bChapter \d+\b', ' ', s)
    s = re.sub(r'\bThe Bhagavad Gita\b', ' ', s)
    s = re.sub(r'(?m)^\s*\d+\s*$', ' ', s)          # bare page numbers
    s = re.sub(r'\s+', ' ', s)                        # collapse all whitespace incl newlines
    return s.strip()


def clean(s):
    s = re.sub(r'(?m)^\s*\d+\s*$', ' ', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def parse_block(pre, mid):
    """pre = text before a verse's (C.V) ref (heading+mojibake+IAST+translation);
    mid = text after it up to the next verse. -> {iast, translation, comments}."""
    blines = pre.split('\n')
    iast = [l.strip() for l in blines if is_iast_line(l)]
    last_iast = max((i for i, l in enumerate(blines) if is_iast_line(l)), default=-1)
    trans = [l.strip() for l in blines[last_iast + 1:]
             if l.strip() and '&&' not in l and 'Ÿ' not in l]
    cm = re.search(r'Comments\s*:\s*', mid)
    craw = mid[cm.end():] if cm else ''
    # A verse's comment ends where the NEXT verse's Sanskrit (legacy-font
    # Devanāgarī, mojibake) begins — otherwise it swallows the next verse's
    # heading + verse + IAST + translation, which sit before that verse's
    # (C.V) ref. Cut at the first mojibake line; drop a trailing short
    # heading line just above it.
    clines = craw.split('\n')
    cut = len(clines)
    for i, l in enumerate(clines):
        if ('&&' in l or 'Ÿ' in l) and any(c in l for c in LEGACY):
            cut = i
            while cut > 0 and clines[cut - 1].strip() and len(clines[cut - 1].strip()) < 45 \
                    and clines[cut - 1].strip()[-1] not in '.!?':
                cut -= 1                      # a topic heading just before the verse
            break
    comments = '\n'.join(clines[:cut])
    return {'iast': '\n'.join(clean_prose(l) for l in iast if clean_prose(l)),
            'translation': clean_prose(' '.join(trans)),
            'comments': clean_prose(comments)}


def item_html(rec):
    h = []
    if rec['iast']:
        h.append('<div class="gita-iast"><em>%s</em></div>'
                 % _html.escape(rec['iast']).replace('\n', '<br>'))
    if rec['translation']:
        h.append('<div class="gita-translation">%s</div>' % _html.escape(rec['translation']))
    if rec['comments']:
        h.append('<div class="gita-comment"><b>Comments:</b> %s</div>'
                 % _html.escape(rec['comments']))
    return '\n'.join(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--txt', required=True, help='pdftotext dump of the Boray Gita PDF')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    body = load_body(args.txt)
    declared = {int(c): int(v) for c, v in
                re.findall(r'Chapter (\d+) \((\d+) verses\)', body)}

    mula = json.load(open(MULA, encoding='utf-8'))
    mula_ids = {it['id'] for it in mula['items']}

    anchors = verse_anchors(body)
    items = []
    import collections
    cov = collections.Counter()
    for i, (c, v, s, e) in enumerate(anchors):
        pre_start = anchors[i - 1][3] if i else 0
        nxt = anchors[i + 1][2] if i + 1 < len(anchors) else len(body)
        rec = parse_block(body[pre_start:s], body[e:nxt])
        if not (rec['translation'] or rec['comments']):
            continue
        vid = 'BGB_C%02d_V%02d' % (c, v)
        if vid not in mula_ids:
            continue
        items.append({
            'id': vid,
            'reference': 'Bhagavad Gītā %d.%d — English (Boray)' % (c, v),
            'unit_title': '%d.%d' % (c, v),
            'sanskrit_text': item_html(rec),
            'tags': [], 'references': [],
            'tika_title': LABEL, 'source': {'layer': LABEL},
        })
        cov[c] += 1

    total = len(items)
    tv = sum(declared.values())
    print('=== Gita English (Boray) coverage ===')
    for c in sorted(declared):
        print('  ch %2d: %3d / %3d verses' % (c, cov.get(c, 0), declared[c]))
    print('  TOTAL: %d / %d verses (%.0f%%)' % (total, tv, 100 * total / tv))

    if args.write:
        d = os.path.join(FAM, 'tika_%s' % KEY)
        os.makedirs(d, exist_ok=True)
        data = {'schema': 'grantha_mula_text', 'default_author': 'Dr. Giridhar Boray',
                'title': 'गीताभाष्यम् — tika_%s' % KEY,
                'source_url': SOURCE_URL, 'source_note': SOURCE_NOTE, 'items': items}
        json.dump(data, open(os.path.join(d, 'data.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        lib = json.load(open(LIB, encoding='utf-8'))
        rel = 'dge/data/darshana/vedanta/dvaita/SarvaMula/gita_prasthana/gita_bhashya'
        p = '%s/tika_%s/data.json' % (rel, KEY)
        if p not in {e['path'] for e in lib['granthas']}:
            lib['granthas'].append({
                'path': p, 'populated': True, 'title': 'गीताभाष्यम् — tika_%s' % KEY,
                'addedAt': '2026-09-04', 'source': {'source_url': SOURCE_URL},
                'facets': {'default_author': 'Dr. Giridhar Boray'}})
            json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('  wrote tika_%s (%d items)' % (KEY, len(items)))


if __name__ == '__main__':
    main()
