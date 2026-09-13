#!/usr/bin/env python3
"""Ingest the remaining Dvaita maṭha successions from the project lead's
genealogical sheet (batch 9 — companion to ingest_ashta_matha_sheet.py).

Covers the smaller / regional maṭhas the sheet carries that were absent or
skeletal in parampara.json:

  Kukke Subramaṇya · Bhandarakeri (Barkur) · Bheemanakatte · Majjigehalli ·
  Kudli Ārya-Akṣobhya · Baligaru Ārya-Akṣobhya · Hunasihole Kāṇva ·
  Sagarakatte · Odampalli · Madhva-Prayāg · Madhva-Nārāyaṇa Āśrama

plus a reconcile-expand of the existing Gokarṇa Partagali line (3 → full
chain). Kāśī Maṭha (already a curated 20-node chain) and Chitrapura (Advaita
/ Smārta, excluded from this Dvaita lineage) are deliberately skipped.

Modeling: where a column opens on the shared pre-split trunk (Padmanābha /
Akṣobhya / Mādhava), those leading rows are ANCHORED onto the existing core
node rather than duplicated (respecting the project convention that shared
ancestors appear once on the core trunk); the first maṭha-specific pontiff
then hangs off that anchor. Columns founded by a direct disciple (Kukke,
Bhandarakeri, Bheemanakatte …) root at Madhvācārya. Confidence 'traditional'
(single-source); provenance recorded in sources[]/note. --dry-run to preview.
"""
import csv, io, re, json, sys, unicodedata

PARA = 'dge/guru-parampara/data/parampara.json'
RAW = 'tools/guru_harvest/sources/guru_parampara_sheet_raw.txt'
SHEET_SOURCE = ('Guru Paramparā genealogical table (Madhva Vaishnava '
                'Sampradaya), community-compiled spreadsheet supplied by the '
                'project lead')

# col -> (label, display, town, root, reconcile)
#   root: 'madhva' | 'anchor' (attach to matching leading core node) | <node id>
COLS = {
    14: ('kukke',        'Kukke Subramaṇya',        'Kukke Subramanya', 'madhva',     False),
    15: ('bhandarakeri', 'Bhandarakeri (Barkur)',   'Barkur',           'madhva',     False),
    16: ('bheemanakatte','Bheemanakatte',           'Bheemanakatte',    'madhva',     False),
    17: ('majjigehalli', 'Majjigehalli',            'Majjigehalli',     'anchor',     False),
    18: ('kudli',        'Kudli Ārya Akṣobhya',     'Kudli',            'anchor',     False),
    19: ('baligaru',     'Baligaru Ārya Akṣobhya',  'Baligaru',         'anchor',     False),
    20: ('hunasihole',   'Hunasihole Kāṇva',        'Hunasihole',       'anchor',     False),
    22: ('gokarna',      'Gokarna Partagali',       'Gokarna',          'palimaru_h', True),
    23: ('sagarakatte',  'Sagarakatte',             'Sagarakatte',      'madhva',     False),
    25: ('odampalli',    'Odampalli',               'Odampalli',        'madhva',     False),
    27: ('prayag',       'Madhva Prayāg',           'Prayagraj',        'madhva',     False),
    28: ('aashrama',     'Madhva-Nārāyaṇa Āśrama',  'Udupi',            'madhva',     False),
}
NEW_LABELS = {
    'kukke': 'Kukke Subramaṇya Maṭha', 'bhandarakeri': 'Bhandarakeri Maṭha (Barkur)',
    'bheemanakatte': 'Bheemanakatte Maṭha', 'majjigehalli': 'Majjigehalli Maṭha',
    'kudli': 'Kudli Ārya Akṣobhya Maṭha', 'baligaru': 'Baligaru Ārya Akṣobhya Maṭha',
    'hunasihole': 'Hunasihole Madhva Kāṇva Maṭha', 'sagarakatte': 'Sagarakatte Maṭha',
    'odampalli': 'Odampalli Maṭha', 'prayag': 'Madhva Prayāg Maṭha',
    'aashrama': 'Madhva-Nārāyaṇa Āśrama',
}


def load_rows():
    raw = open(RAW, encoding='utf-8').read().strip()
    if raw.startswith('Sheet1 '):
        raw = raw[len('Sheet1 '):]
    toks = next(csv.reader(io.StringIO(raw)))
    return [[toks[87 + r * 29 + c].strip() for c in range(29)] for r in range(41)]


def norm_name(raw):
    n = re.sub(r'\s+', ' ', raw).strip()
    n = re.sub(r'\s*\?\?\s*$', '', n)
    n = re.sub(r'\s*-\\?>.*$', '', n)
    n = re.sub(r'\s*\(merged.*$', '', n, flags=re.I)
    n = re.sub(r'\s*Sripad Wader Swamiji$', '', n)
    n = re.sub(r'\bTheertha\b', 'Tirtha', n)
    n = re.sub(r'([a-z])(Tirtha)\b', r'\1 \2', n)
    n = re.sub(r'^Sri\s+', '', n).strip()
    return n


def key(name):
    k = re.sub(r'\bTirtha\b', '', norm_name(name))
    k = re.sub(r'\(.*?\)', '', k)
    k = unicodedata.normalize('NFKD', k)
    k = ''.join(c for c in k if c.isalpha()).lower()
    return re.sub(r'(.)\1+', r'\1', k.replace('h', '').replace('w', 'v'))


def slugify(name, taken):
    s = re.sub(r'\bTirtha\b', '', norm_name(name))
    s = re.sub(r'\(.*?\)', '', s)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c if c.isalnum() else '_' for c in s.lower()).strip('_')
    s = re.sub(r'_+', '_', s) or 'guru'
    cand, i = s, 2
    while cand in taken:
        cand, i = '%s_%d' % (s, i), i + 1
    taken.add(cand)
    return cand


ORD = ['1st', '2nd', '3rd'] + ['%dth' % i for i in range(4, 60)]


def main():
    mode = '--write' if '--write' in sys.argv else '--dry-run'
    data = json.load(open(PARA, encoding='utf-8'))
    nodes = data['nodes']
    by_id = {n['id']: n for n in nodes}
    taken = set(by_id)
    core_key = {key(n['name']): n['id'] for n in nodes if n['matha'] in ('core', 'mula')}
    rows = load_rows()

    for lab, disp in NEW_LABELS.items():
        data['matha_labels'].setdefault(lab, disp)

    print('=== batch 9: smaller maṭha ingestion (%s) ===' % mode)
    for col, (matha, mdisp, town, root, reconcile) in COLS.items():
        seq = []
        for r in range(41):
            nm = norm_name(rows[r][col])
            if nm and nm.lower() != 'sri' and len(nm) >= 3:
                seq.append(nm)
        if not seq:
            continue

        existing = [n for n in nodes if n['matha'] == matha] if reconcile else []
        ex_by_key, used = {}, set()
        for n in existing:
            ex_by_key.setdefault(key(n['name']), n)

        # resolve leading anchor for 'anchor' columns
        prev_id, start = 'madhva', 0
        if root == 'anchor':
            while start < len(seq) and key(seq[start]) in core_key:
                prev_id = core_key[key(seq[start])]
                start += 1
        elif root != 'madhva':
            prev_id = root
        prev_id0 = prev_id            # the anchor, before the chain overwrites it

        founder_name = seq[start] if start < len(seq) else seq[0]
        rep = []
        for j, name in enumerate(seq[start:]):
            pos = j + 1
            k = key(name)
            ex = ex_by_key.get(k)
            if ex and ex['id'] not in used:
                used.add(ex['id'])
                ex['guru'] = prev_id
                ex['matha'] = matha
                ex.setdefault('sources', [])
                if SHEET_SOURCE not in ex['sources']:
                    ex['sources'].append(SHEET_SOURCE)
                ex['succ_index'] = pos
                prev_id = ex['id']
                rep.append('  %2d. %-30s [reuse:%s]' % (pos, name, ex['id']))
                continue
            nid = slugify(name, taken)
            base = re.sub(r'\bTirtha\b', '', name).strip()
            disp_name = '%s Tirtha (%s)' % (base, mdisp) if not name.endswith('Tirtha') \
                else '%s (%s)' % (name, mdisp)
            if pos == 1:
                contrib = ('Founding / earliest recorded pontiff of the %s in the '
                           'Madhva (Dvaita) tradition, per the community genealogical '
                           'table.' % NEW_LABELS.get(matha, mdisp))
            else:
                contrib = ('%s pontiff in the %s succession, the lineage recorded '
                           'from %s in the community genealogical table.'
                           % (ORD[pos - 1], mdisp, founder_name))
            node = {
                'id': nid, 'name': disp_name, 'guru': prev_id, 'matha': matha,
                'tag': 'acharya', 'purva': None, 'titles': [], 'period': 'unknown',
                'b': None, 'd': None, 'pont': None, 'brindavana': None, 'place': town,
                'works': [], 'contrib': contrib, 'confidence': 'traditional',
                'sources': [SHEET_SOURCE], 'note': None, 'role':
                '%s pontiff of %s (Madhva/Dvaita lineage)' % (ORD[pos - 1], mdisp),
                'contemporaries': [], 'succ_index': pos,
            }
            nodes.append(node); by_id[nid] = node
            prev_id = nid
            rep.append('  %2d. %-30s [NEW:%s]' % (pos, name, nid))
        # reconcile columns: fold any still-unplaced existing rich node into its
        # closest sheet twin (spelling variant of the same pontiff) by edit
        # distance, then drop the existing duplicate (repointing guru refs).
        def edist(a, b):
            dp = list(range(len(b) + 1))
            for i, ca in enumerate(a, 1):
                prev, dp[0] = dp[0], i
                for j, cb in enumerate(b, 1):
                    prev, dp[j] = dp[j], min(dp[j] + 1, dp[j - 1] + 1, prev + (ca != cb))
            return dp[-1]

        created = [n for n in nodes if n['matha'] == matha and n['id'] not in
                   {e['id'] for e in existing}]
        for o in [n for n in existing if n['id'] not in used]:
            ok = key(o['name'])
            best = min(created, key=lambda n: edist(ok, key(n['name'])), default=None)
            if best and edist(ok, key(best['name'])) <= 2:
                for f in ('contrib', 'b', 'd', 'pont', 'brindavana', 'place',
                          'works', 'titles', 'purva', 'note'):
                    if o.get(f) and not best.get(f):
                        best[f] = o[f]
                for n in nodes:                       # repoint any guru refs
                    if n.get('guru') == o['id']:
                        n['guru'] = best['id']
                nodes.remove(o); by_id.pop(o['id'], None)
                rep.append('  ~~ folded existing %s -> %s' % (o['id'], best['id']))

        note = ''
        if root == 'anchor' and start:
            note = ' (leading %d shared rows anchored on core %s)' % (start, prev_id0)
        elif root not in ('madhva', 'anchor'):
            note = ' (rooted at %s)' % root
        print('\n%s — %d nodes, root=%s%s' % (mdisp, len(seq) - start, root, note))
        print('\n'.join(rep))
        orph = [n for n in nodes if n['matha'] == matha and n['id'] in
                {e['id'] for e in existing} and n.get('succ_index') is None]
        if orph:
            print('  ! STILL UNPLACED:', [o['id'] for o in orph])

    data['meta']['node_count'] = len(nodes)
    if mode == '--write':
        json.dump(data, open(PARA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\nWROTE %s — %d total nodes' % (PARA, len(nodes)))
    else:
        print('\n(dry-run; total would be %d)' % len(nodes))


if __name__ == '__main__':
    main()
