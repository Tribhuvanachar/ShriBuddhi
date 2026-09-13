#!/usr/bin/env python3
"""Rebuild the Tīrthaprabandha reader data from the Pradīpa edition text
(the authoritative source), replacing the earlier wordpress-derived mula.

For each <p-v> block in dge/pradeepasimha/teerthaprabhandha-tika/*:
  * category — a tab-indented heading line (kṣetra / deity). Verses with no
    heading inherit the previous one, so e.g. Bhāgīrathī (Gaṅgā) covers its
    8 ślokas and Śrīraṅgam its run. Headings are the reader's filter facet.
  * mula — the verse pādas exactly as the edition lays them out (each pāda on
    its own line, single daṇḍa at pāda-ends, "।। N ।।" at the verse end), so a
    2-line or 4-line verse renders with its own metre's line breaks.
  * vyākhyā — Śrī Nārāyaṇācārya's commentary (kept as the narayana_vyakhya
    layer), with %pratīka% markers unwrapped and the F.N. footnote apparatus
    retained.

Preserves each verse's existing tirtha_link. Idempotent; --write to apply.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TIKA = os.path.join(ROOT, 'dge/pradeepasimha/teerthaprabhandha-tika')
FAM = os.path.join(ROOT, 'dge/data/darshana/vedanta/dvaita/SarvaMula/kavya/tirtha_prabandha')
KEY = 'narayana_vyakhya'
LABEL = 'श्री नारायणाचार्य व्याख्या'
PRA = {
    1: ('paschima_prabandha', 'PAS', 'Paścima', 'paschimaprabandha_1'),
    2: ('uttara_prabandha',   'UTT', 'Uttara',  'uttaraprabandha_2'),
    3: ('purva_prabandha',    'PUR', 'Pūrva',   'purvaprabandha_3'),
    4: ('dakshina_prabandha', 'DAK', 'Dakṣiṇa', 'dakshinaprabandha_4'),
}
VERSE_END = re.compile(r'।।\s*[०-९0-9]+\s*।।')


def leading_tabs(line):
    return line[:len(line) - len(line.lstrip())].count('\t')


def is_heading(line):
    t = line.strip()
    if not t or '।' in t or '॥' in t or re.search(r'[०-९]', t):
        return False
    if t.startswith(('---', 'F.N', '(', '"', '॒')):
        return False
    return leading_tabs(line) >= 2 and len(t) <= 40


def linkify_footnotes(vy, vid):
    """Split the vyākhyā into main prose + the trailing F.N. apparatus, and
    return one HTML string where each inline (N)/(*) marker in the prose is a
    superscript link to its footnote, and each footnote back-links (↩) to its
    marker. Pure in-card anchors — no reader JS. If there is no F.N. block the
    prose is returned unchanged (markers left as plain text)."""
    m = re.search(r'(^|\n)\s*F\.N\.?\s*\n', vy)
    if not m:
        return vy
    prose, fnraw = vy[:m.start()].strip(), vy[m.end():]
    # footnote definitions: a line opening "(<key>. " with balanced parens
    defs = []                                     # (key, text)
    tokens = re.split(r'\n(?=\(\s*(?:\d+|\*+)\.)', fnraw)
    for tok in tokens:
        dm = re.match(r'\(\s*(\d+|\*+)\.\s*(.*)', tok, re.S)
        if not dm:
            continue
        key = dm.group(1)
        text = dm.group(2).strip().rstrip(')').strip()
        text = re.sub(r'\s+', ' ', text)
        defs.append((key, text))
    if not defs:
        return prose
    star_seen = [0]

    def ref2(mo):
        k = mo.group(1)
        if k.isdigit():
            sub = k
        else:
            star_seen[0] += 1
            sub = 's%d' % star_seen[0]
        return ('<sup class="tp-fnref" id="tpref-%s-%s"><a href="#tpfn-%s-%s">%s</a></sup>'
                % (vid, sub, vid, sub, k))
    prose_html = re.sub(r'\((\d+|\*+)\)', ref2, prose)
    items = []
    star_out = [0]
    for key, text in defs:
        if key.isdigit():
            sub = key
        else:
            star_out[0] += 1
            sub = 's%d' % star_out[0]
        items.append('<div class="tp-fnote" id="tpfn-%s-%s"><a class="tp-fnback" '
                     'href="#tpref-%s-%s">%s.</a> %s</div>'
                     % (vid, sub, vid, sub, key, text))
    return prose_html + '<div class="tp-fnotes">' + ''.join(items) + '</div>'


def parse_block(body, vnum):
    """-> (heading_or_None, mula_str, vyakhya_str)."""
    raw_lines = [ln for ln in body.split('\n') if ln.strip()]
    heading = None
    i = 0
    if raw_lines and is_heading(raw_lines[0]):
        heading = raw_lines[0].strip()
        i = 1
    # mula: from here up to and including the first verse-end marker
    mula, j = [], i
    while j < len(raw_lines):
        t = raw_lines[j].strip()
        mula.append(t)
        if VERSE_END.search(t):
            j += 1
            break
        j += 1
    vy_lines = [ln.strip() for ln in raw_lines[j:]]
    vy = '\n'.join(vy_lines)
    vy = re.sub(r'%(.*?)%', r'\1', vy, flags=re.S).replace('%', '')
    vy = re.sub(r'[ \t]+', ' ', vy)
    vy = re.sub(r'\n{3,}', '\n\n', vy).strip()
    return heading, '\n'.join(mula).strip(), vy


def main():
    mode = '--write' if '--write' in sys.argv else '--dry-run'
    report = {}
    for pnum, (slug, code, disp, fname) in PRA.items():
        raw = open(os.path.join(TIKA, fname), encoding='utf-8').read()
        blocks = {}
        cur_cat = None
        for v, body in re.findall(r'<%d-(\d+)>(.*?)</%d-\1>' % (pnum, pnum), raw, re.S):
            h, mula, vy = parse_block(body, int(v))
            if h:
                cur_cat = h
            blocks[int(v)] = {'category': cur_cat, 'mula': mula, 'vyakhya': vy}

        dj = os.path.join(FAM, slug, 'data.json')
        data = json.load(open(dj, encoding='utf-8'))
        data.setdefault('availableCommentaries', {})[KEY] = LABEL
        n_mula = n_cat = 0
        cats = []
        for it in data['items']:
            v = int(it['id'].rsplit('_', 1)[1])
            b = blocks.get(v)
            if not b:
                continue
            if b['mula']:
                it['sanskrit_text'] = b['mula']
                n_mula += 1
            if b['category']:
                it['category'] = b['category']
                # length-4 breadcrumb so layer-stitch.js's section navigator
                # (groups on crumbs[2:-1]) builds a category dropdown; the leaf
                # is the verse itself.
                it['breadcrumb'] = ['Tīrthaprabandha', disp + ' Prabandha',
                                    b['category'], str(v)]
                n_cat += 1
                if not cats or cats[-1] != b['category']:
                    cats.append(b['category'])
            if b['vyakhya']:
                it.setdefault('commentaries', {})[KEY] = linkify_footnotes(b['vyakhya'], it['id'])
        if mode == '--write':
            json.dump(data, open(dj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        report[slug] = (len(data['items']), n_mula, n_cat, len(cats))

    print('=== rebuild from Pradīpa (%s) ===' % mode)
    for slug, (ni, nm, nc, ncat) in report.items():
        print('  %-20s items=%3d mula-set=%3d cat-set=%3d categories=%3d'
              % (slug, ni, nm, nc, ncat))
    if mode != '--write':
        print('(dry-run)')


if __name__ == '__main__':
    main()
