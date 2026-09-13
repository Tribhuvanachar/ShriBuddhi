#!/usr/bin/env python3
"""Build the Mahābhārata-Tātparya-Nirṇaya multi-commentary ṭīkā layers from the
Vishwa Madhwa Maha Parishat critical edition (Uttarādi Maṭha), OCR'd by
archive.org.

Source: four archive.org scans (adhyāyas 1-3 / 4-9 / 10-17 / 18-21), whose
`_text.pdf` already carries a good Devanāgarī OCR layer (~92-96%). This tool
reads the pre-extracted page text (pdftotext form-feed dumps — the multi-MB
PDFs are never committed, per the repo's size rule), and for each adhyāya
splits the running apparatus into its individual NAMED sub-commentaries
(Janārdanīya, Varadarājīya, Vādirāja, Vyāsatīrtha's Bhāvapañcikā, Chaṭṭī,
Anantabhaṭṭīya, …) using tools/mbtn/mbtn_labels.py's OCR-tolerant matcher.

Each commentary becomes one lazy-loaded sibling layer (tika_<key>/data.json)
on the existing MBTN mula spine, with one item per adhyāya it covers, keyed to
that adhyāya's mula item id so dge/js/layer-stitch.js joins them and the reader
can select a single commentary and read just that one. Also writes the
library.json catalog entries. Re-run tools/build_layer_manifest.py afterwards.

Usage:
  python3 tools/mbtn/build_tika_layers.py --textdir <dir-with-mbtn_volN_ff.txt> [--write]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mbtn_labels import canon, LABEL_OF, SECTION_MARKERS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAM = os.path.join(ROOT, 'dge/data/darshana/vedanta/dvaita/DvaitaVedanta/'
                         'itihasa_prasthana/mahabharata_tatparya_nirnaya')
LIB = os.path.join(ROOT, 'dge/data/library.json')
GRANTHA_TITLE = 'महाभारततात्पर्यनिर्णयः'
SOURCE_URL = 'https://archive.org/details/mahabharata-tatparya-nirnaya-1-3-adhyaya-10-tippani-vol-1'
SOURCE_NOTE = ('Vishwa Madhwa Maha Parishat critical edition (Sri Jayateertha '
               'Vidyapeetha, Uttaradi Math, Bengaluru), OCR-digitised from the '
               'archive.org scans. Modern critical apparatus; the mula and the '
               'medieval commentaries are public-domain texts. Used with '
               'case-by-case permission granted by the project lead on '
               '2026-09-04 for non-commercial, educational dharma-prachara use. '
               'OCR (~92-96%), not yet proofread.')
VOL_TEXT = {1: ('mbtn_vol1_ff.txt', range(1, 4)),
            2: ('mbtn_vol2_ff.txt', range(4, 10)),
            3: ('mbtn_vol3_ff.txt', range(10, 18)),
            4: ('mbtn_vol4_ff.txt', range(18, 22))}
DEV = {c: i for i, c in enumerate('०१२३४५६७८९')}
BOUNDARY = re.compile(r'(?:^|\n)\s*([ऀ-ॿ]{2,20})[-–—]{1,3}\s')
VERSE_END = re.compile(r'।।\s*[०-९]+\s*।।|॥\s*[०-९]+\s*॥')


def dnum(s):
    n = 0
    for ch in s:
        if ch in DEV:
            n = n * 10 + DEV[ch]
        else:
            return None
    return n


def page_adhyaya(pg, aset):
    """The adhyāya a page belongs to = the mode of the first number across all
    'N-M' verse markers on the page, restricted to this volume's adhyāya set.
    Robust to the header sitting at top OR bottom, and to the odd footnote
    citation ('भा.ता. १-१९') that names a different adhyāya."""
    from collections import Counter
    nums = Counter()
    for m in re.finditer(r'([०-९]+)-[०-९]+', pg):
        n = dnum(m.group(1))
        if n in aset:
            nums[n] += 1
    return nums.most_common(1)[0][0] if nums else None


def strip_header(pg):
    out = []
    for l in pg.split('\n'):
        s = l.strip()
        if not s:
            continue
        if re.match(r'^[०-९]+-[०-९]+\s*$', s):
            continue
        if re.match(r'^[०-९]+-[०-९]+\s+', s) and 'ध्याय' in s:
            continue
        if re.match(r'^\S*ऽ?ध्यायः?\s*$', s) and 'ध्याय' in s and len(s) < 20:
            continue
        if re.match(r'^[०-९0-9]{1,3}\s*$', s):
            continue
        if 'तात्पर्यनिर्णयः' in s and len(s) < 40:
            continue
        out.append(s)
    return '\n'.join(out)


def adhyaya_texts(vol_text, adhyaya_set):
    """-> {adhyaya: cleaned running text} using contiguous header-derived ranges."""
    pages = vol_text.split('\f')
    aset = set(adhyaya_set)
    seq = [page_adhyaya(p, aset) for p in pages]
    # first-occurrence-in-order start page for each adhyaya in the set
    starts = {}
    want = list(adhyaya_set)
    i = 0
    for a in want:
        while i < len(pages) and seq[i] != a:
            i += 1
        if i >= len(pages):
            break
        starts[a] = i
    out = {}
    keys = sorted(starts)
    for j, a in enumerate(keys):
        lo = starts[a]
        hi = starts[keys[j + 1]] if j + 1 < len(keys) else len(pages)
        body = '\n'.join(strip_header(pages[k]) for k in range(lo, hi))
        body = re.sub(r'[ \t]+', ' ', body)
        body = re.sub(r'\n{3,}', '\n\n', body).strip()
        out[a] = body
    return out


def split_commentaries(text):
    """-> {comm_key: text} for one adhyāya, concatenating each commentary's
    labelled segments in document order."""
    bounds = []  # (pos, key)
    for m in BOUNDARY.finditer(text):
        k = canon(m.group(1))
        if k:
            bounds.append((m.start(1), m.end(), k))
    segs = {}
    for idx, (s0, e0, key) in enumerate(bounds):
        end = bounds[idx + 1][0] if idx + 1 < len(bounds) else len(text)
        seg = text[e0:end].strip()
        if seg:
            segs.setdefault(key, []).append(seg)
    return {k: '\n\n'.join(v).strip() for k, v in segs.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--textdir', required=True)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    mula = json.load(open(os.path.join(FAM, 'mula/data.json'), encoding='utf-8'))
    adhyaya_id = {i + 1: it['id'] for i, it in enumerate(mula['items'])}

    # comm_key -> {adhyaya: text}
    layers = {}
    for vol, (fname, aset) in VOL_TEXT.items():
        path = os.path.join(args.textdir, fname)
        vtext = open(path, encoding='utf-8', errors='replace').read()
        atexts = adhyaya_texts(vtext, aset)
        for a, atext in atexts.items():
            for key, ctext in split_commentaries(atext).items():
                layers.setdefault(key, {})[a] = ctext

    report = []
    for key in sorted(layers):
        label = LABEL_OF.get(key, key)
        items = []
        for a in sorted(layers[key]):
            items.append({
                'id': adhyaya_id[a],
                'reference': '%s > %s > अध्यायः %d' % (GRANTHA_TITLE, label, a),
                'unit_title': 'अध्यायः %d' % a,
                'sanskrit_text': layers[key][a],
                'tags': [], 'references': [],
                'breadcrumb': ['इतिहासप्रस्थानम्', '2. श्रीमहाभारततात्पर्यनिर्णय:',
                               label, 'अध्यायः %d' % a],
                'tika_title': label,
                'source': {'layer': label},
            })
        folder = 'tika_%s' % key
        data = {'schema': 'grantha_mula_text',
                'default_author': label,
                'title': '%s — %s' % (GRANTHA_TITLE, folder),
                'source_url': SOURCE_URL, 'source_note': SOURCE_NOTE,
                'items': items}
        total = sum(len(it['sanskrit_text']) for it in items)
        report.append((folder, label, len(items), total))
        if args.write:
            d = os.path.join(FAM, folder)
            os.makedirs(d, exist_ok=True)
            json.dump(data, open(os.path.join(d, 'data.json'), 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)

    # library.json entries
    if args.write:
        lib = json.load(open(LIB, encoding='utf-8'))
        rel = 'dge/data/darshana/vedanta/dvaita/DvaitaVedanta/itihasa_prasthana/mahabharata_tatparya_nirnaya'
        have = {e['path'] for e in lib['granthas']}
        for folder, label, _n, _t in report:
            p = '%s/%s/data.json' % (rel, folder)
            if p in have:
                continue
            lib['granthas'].append({
                'path': p, 'populated': True,
                'title': '%s — %s' % (GRANTHA_TITLE, folder),
                'addedAt': '2026-09-04',
                'source': {'source_url': SOURCE_URL},
                'facets': {'default_author': label},
            })
        json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('=== MBTN ṭīkā layers (%s) ===' % ('write' if args.write else 'dry-run'))
    for folder, label, n, total in report:
        print('  %-22s adhyāyas=%2d  %6.0f KB  %s' % (folder, n, total / 1024, label))
    print('  %d commentary layers, %.1f MB total'
          % (len(report), sum(t for *_, t in report) / 1024 / 1024))


if __name__ == '__main__':
    main()
