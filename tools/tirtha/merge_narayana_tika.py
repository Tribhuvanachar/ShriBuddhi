#!/usr/bin/env python3
"""Merge Śrī Nārāyaṇācārya's vyākhyā (the Pradīpa edition ṭīkā) into the
Tīrthaprabandha reader as a per-verse commentary — from the clean source
files, no OCR needed.

The four `dge/pradeepasimha/teerthaprabhandha-tika/*prabandha*` files in the
repo were the SAME source but mis-saved as UTF-8, which destroyed them. The
project lead re-supplied the intact originals: UTF-16, 82-83 % clean
Devanāgarī, zero data loss, each verse's ṭīkā bracketed by `<p-v>…</p-v>`
anchors (p = prabandha 1-4, v = verse) that align 1:1 with the mula
(Paścima 99 · Uttara 46 · Pūrva 43 · Dakṣiṇa 47).

This tool (a) rewrites the repo's corrupt files with the clean UTF-8 text and
(b) parses each `<p-v>` block — heading (kṣetra) + mula pratīka + the vyākhyā
prose, with %pratīka% word-markers — and writes the vyākhyā into
items[*].commentaries['narayana_vyakhya'] of the four prabandha data.json.
Idempotent; run --write to apply.
"""
import json, os, re, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UP = os.environ.get('TP_TIKA_DIR',
                    '/root/.claude/uploads/e8a5c83c-760f-5d7b-9fbc-3df8440bd264')
REPO_TIKA = os.path.join(ROOT, 'dge/pradeepasimha/teerthaprabhandha-tika')
FAM = os.path.join(ROOT, 'dge/data/darshana/vedanta/dvaita/SarvaMula/kavya/tirtha_prabandha')
KEY = 'narayana_vyakhya'
LABEL = 'श्री नारायणाचार्य व्याख्या'

# prabandha number in the <p-v> anchors -> (folder slug, id code, clean filename)
PRA = {
    1: ('paschima_prabandha', 'PAS', 'paschimaprabandha_1'),
    2: ('uttara_prabandha',   'UTT', 'uttaraprabandha_2'),
    3: ('purva_prabandha',    'PUR', 'purvaprabandha_3'),
    4: ('dakshina_prabandha', 'DAK', 'dakshinaprabandha_4'),
}


def find_upload(prab_word):
    hits = glob.glob(os.path.join(UP, '*%s*' % prab_word))
    if not hits:
        raise SystemExit('missing upload for %s in %s' % (prab_word, UP))
    return hits[0]


def clean_block(blk):
    """A <p-v> block -> the vyākhyā commentary string: heading (if any) +
    prose after the mula verse, with %pratīka% markers unwrapped and anchor
    tags gone. Falls back to the whole block if no mula verse-number marker
    is found."""
    b = re.sub(r'</?\d+-\d+>', '', blk)          # any stray anchor tags
    b = b.replace('\r', '')
    lines = [ln.strip() for ln in b.split('\n')]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ''
    heading = ''
    # a short first line with no danda / verse number is the kṣetra heading
    if len(lines[0]) <= 40 and '।' not in lines[0] and not re.search(r'\d', lines[0]):
        heading = lines[0]
        lines = lines[1:]
    text = '\n'.join(lines)
    # split off the leading mula verse: everything after its own "।। N ।।"
    m = re.search(r'।।\s*[०-९0-9]+\s*।।', text)
    vyakhya = text[m.end():].strip() if m else text
    if heading:
        vyakhya = heading + '\n' + vyakhya
    vyakhya = re.sub(r'%(.*?)%', r'\1', vyakhya, flags=re.S)   # unwrap pratīka markers
    vyakhya = vyakhya.replace('%', '')             # drop any unpaired survivors
    vyakhya = re.sub(r'[ \t]+', ' ', vyakhya)
    vyakhya = re.sub(r'\n{3,}', '\n\n', vyakhya).strip()
    return vyakhya


def main():
    mode = '--write' if '--write' in sys.argv else '--dry-run'
    os.makedirs(REPO_TIKA, exist_ok=True)
    report = {}
    for pnum, (slug, code, fname) in PRA.items():
        up = find_upload(fname.split('_')[0])       # e.g. 'paschimaprabandha'
        raw = open(up, 'rb').read().decode('utf-16')
        # (a) rewrite the repo's corrupt file with clean UTF-8
        if mode == '--write':
            with open(os.path.join(REPO_TIKA, fname), 'w', encoding='utf-8') as fh:
                fh.write(raw)
        # (b) parse blocks -> {verse: commentary}
        blocks = dict(
            (int(v), clean_block(body))
            for v, body in re.findall(r'<%d-(\d+)>(.*?)</%d-\1>' % (pnum, pnum), raw, re.S)
        )
        # merge into the prabandha data.json
        dj = os.path.join(FAM, slug, 'data.json')
        data = json.load(open(dj, encoding='utf-8'))
        av = data.setdefault('availableCommentaries', {})
        av[KEY] = LABEL
        n_set = 0
        for it in data['items']:
            v = int(it['id'].rsplit('_', 1)[1])
            c = blocks.get(v)
            if c:
                it.setdefault('commentaries', {})[KEY] = c
                n_set += 1
        if mode == '--write':
            json.dump(data, open(dj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        report[slug] = (len(blocks), len(data['items']), n_set)

    print('=== Nārāyaṇācārya vyākhyā merge (%s) ===' % mode)
    for slug, (nb, ni, ns) in report.items():
        print('  %-20s blocks=%3d items=%3d commentary-set=%3d' % (slug, nb, ni, ns))
    if mode != '--write':
        print('(dry-run: nothing written)')


if __name__ == '__main__':
    main()
