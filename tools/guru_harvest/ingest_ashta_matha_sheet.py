#!/usr/bin/env python3
"""Ingest the Udupi Aṣṭa Maṭha full paryāya successions from the project
lead's genealogical sheet (Guru Parampara.xlsx) into parampara.json.

The eight Aṣṭa Maṭhas carried only a sparse "founder + famous + current head"
skeleton (2-4 nodes each, guru links skipping ~28 intermediate pontiffs). The
sheet supplies the complete ordered succession per maṭha. This tool rebuilds
each of the eight columns as a full guru->disciple chain, RECONCILING the
existing rich nodes (their prose, dates, brindavana, works, and — crucially —
their ids, so contemporaries/guru references survive) into their correct
position by name-key match, and creating factual role-line nodes for the rest.

Source: "Guru Parampare - Genealogical Table of Apostolic Institutions of
Madhva Vaishnava Sampradaya" (project-lead-provided spreadsheet, compiled by
a community researcher). Anglicised spellings are carried from the source;
confidence is 'traditional' (single-source succession list). Run with
--dry-run to preview; --write to apply.
"""
import csv, io, re, json, sys, unicodedata

PARA = 'dge/guru-parampara/data/parampara.json'
RAW = 'tools/guru_harvest/sources/guru_parampara_sheet_raw.txt'
SHEET_SOURCE = ('Guru Paramparā genealogical table (Madhva Vaishnava '
                'Sampradaya), community-compiled spreadsheet supplied by the '
                'project lead')

# sheet column index (1-based within the 28-lineage grid) -> matha label
ASHTA = {
    6:  'palimaru',
    7:  'adamaru',
    8:  'krishnapura',
    9:  'puttige',
    10: 'shirur',
    11: 'sode',
    12: 'kaniyooru',
    13: 'pejawara',
}
MATHA_TOWN = {
    'palimaru': 'Udupi', 'adamaru': 'Udupi', 'krishnapura': 'Udupi',
    'puttige': 'Udupi', 'shirur': 'Udupi', 'sode': 'Udupi',
    'kaniyooru': 'Udupi', 'pejawara': 'Udupi',
}
MATHA_DISP = {
    'palimaru': 'Palimaru', 'adamaru': 'Adamaru', 'krishnapura': 'Krishnapura',
    'puttige': 'Puttige', 'shirur': 'Shirur', 'sode': 'Sode',
    'kaniyooru': 'Kaniyooru', 'pejawara': 'Pejawara',
}


def load_grid():
    raw = open(RAW, encoding='utf-8').read().strip()
    if raw.startswith('Sheet1 '):
        raw = raw[len('Sheet1 '):]
    toks = next(csv.reader(io.StringIO(raw)))
    rows = []
    start = 87
    for r in range(41):
        base = start + r * 29
        rows.append([toks[base + c].strip() for c in range(29)])
    return rows


def norm_name(raw):
    """Display-normalise a sheet cell: drop 'Sri ' prefix, uncertainty and
    schism annotations, split run-together 'Tirtha', collapse whitespace."""
    n = re.sub(r'\s+', ' ', raw).strip()
    n = re.sub(r'\s*\?\?\s*$', '', n)                 # trailing ?? = doubt marker
    n = re.sub(r'\s*-\\?>.*$', '', n)                 # schism arrow annotations
    n = re.sub(r'\s*\(merged.*$', '', n, flags=re.I)
    n = re.sub(r'\bTheertha\b', 'Tirtha', n)
    n = re.sub(r'([a-z])(Tirtha)\b', r'\1 \2', n)     # KavindraTirtha -> Kavindra Tirtha
    n = re.sub(r'^Sri\s+', '', n).strip()
    n = re.sub(r'\s+Sripad Wader Swamiji$', '', n).strip()
    return n


def key(name):
    """Match-key for reconciling anglicised spellings. Strip honorific/tirtha,
    keep ascii letters, lowercase, then drop every 'h' and collapse doubled
    letters so variant transliterations of one name collapse together
    (Janardhana/Janardana, Vidhyadeesha/Vidyadheesha, Vibhudapriya/
    Vibudhapriya). Applied symmetrically to sheet and existing names."""
    k = norm_name(name)
    k = re.sub(r'\bTirtha\b', '', k)
    k = re.sub(r'\(.*?\)', '', k)
    k = unicodedata.normalize('NFKD', k)
    k = ''.join(c for c in k if c.isalpha()).lower()
    k = k.replace('h', '').replace('w', 'v')
    k = re.sub(r'(.)\1+', r'\1', k)          # collapse doubled letters
    return k


def slugify(name, taken):
    s = re.sub(r'\bTirtha\b', '', norm_name(name))
    s = re.sub(r'\(.*?\)', '', s)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c if c.isalnum() else '_' for c in s.lower()).strip('_')
    s = re.sub(r'_+', '_', s)
    base = s or 'guru'
    cand = base
    i = 2
    while cand in taken:
        cand = '%s_%d' % (base, i)
        i += 1
    taken.add(cand)
    return cand


def main():
    mode = '--write' if '--write' in sys.argv else '--dry-run'
    data = json.load(open(PARA, encoding='utf-8'))
    nodes = data['nodes']
    by_id = {n['id']: n for n in nodes}
    taken_ids = set(by_id)
    grid = load_grid()

    ORD = ['1st', '2nd', '3rd'] + ['%dth' % i for i in range(4, 60)]
    summary = []

    for col, matha in ASHTA.items():
        # existing nodes in this matha, keyed for reconciliation
        existing = [n for n in nodes if n['matha'] == matha]
        ex_by_key = {}
        for n in existing:
            ex_by_key.setdefault(key(n['name']), n)
        used_existing = set()

        # ordered succession from the sheet (skip blank cells)
        seq = []
        for r in range(41):
            cell = grid[r][col]
            if norm_name(cell):
                seq.append((r + 1, norm_name(cell)))   # (sheet row no, name)

        founder_name = norm_name(grid[seq[0][0] - 1][col]) if seq else ''
        chain_ids = []
        prev_id = 'madhva'          # Aṣṭa founders are direct disciples of Madhva
        col_report = []
        for pos, (rowno, name) in enumerate(seq, start=1):
            k = key(name)
            ex = ex_by_key.get(k)
            role = '%s pontiff of %s Maṭha (Udupi Aṣṭa Maṭha) in the Madhva succession' % (
                ORD[pos - 1], MATHA_DISP[matha])
            if ex and ex['id'] not in used_existing:
                used_existing.add(ex['id'])
                node = ex
                node['guru'] = prev_id
                node['matha'] = matha
                node.setdefault('sources', [])
                if SHEET_SOURCE not in node['sources']:
                    node['sources'].append(SHEET_SOURCE)
                node['role'] = node.get('role') or role
                # record succession index in a machine field without clobbering prose
                node['succ_index'] = pos
                tag = 'reuse:%s' % node['id']
            else:
                nid = slugify(name, taken_ids)
                disp = '%s Tirtha' % re.sub(r'\bTirtha\b', '', name).strip() \
                    if not name.endswith('Tirtha') else name
                disp = '%s (%s)' % (disp, MATHA_DISP[matha])
                if pos == 1:
                    contrib = ('Founding pontiff of the %s Maṭha, one of the '
                               'eight Udupi Aṣṭa Maṭhas established by Madhvācārya '
                               'for the daily worship of Śrī Kṛṣṇa at Udupi.'
                               % MATHA_DISP[matha])
                else:
                    contrib = ('%s pontiff in the %s Maṭha succession (Udupi '
                               'Aṣṭa Maṭha), the paryāya lineage descending from '
                               'Madhvācārya’s disciple %s.'
                               % (ORD[pos - 1], MATHA_DISP[matha], founder_name))
                node = {
                    'id': nid, 'name': disp, 'guru': prev_id, 'matha': matha,
                    'tag': 'acharya', 'purva': None, 'titles': [],
                    'period': 'unknown', 'b': None, 'd': None, 'pont': None,
                    'brindavana': None, 'place': MATHA_TOWN.get(matha),
                    'works': [], 'contrib': contrib, 'confidence': 'traditional',
                    'sources': [SHEET_SOURCE], 'note': None,
                    'role': role, 'contemporaries': [], 'succ_index': pos,
                }
                nodes.append(node)
                by_id[nid] = node
                tag = 'NEW:%s' % nid
            chain_ids.append(node['id'])
            col_report.append('  %2d. %-32s [%s]' % (pos, name, tag))
            prev_id = node['id']

        # existing rich nodes not placed by the sheet chain
        orphans = [n for n in existing if n['id'] not in used_existing]
        summary.append((matha, len(seq), len(orphans), orphans, col_report))

    # ---- report ----
    total_new = sum(1 for n in nodes if n.get('succ_index') and n['id'] not in {e['id'] for m in ASHTA.values() for e in []})
    print('=== Aṣṭa Maṭha ingestion (%s) ===' % mode)
    for matha, nseq, norph, orphans, rep in summary:
        print('\n%s — %d pontiffs' % (MATHA_DISP[matha], nseq))
        print('\n'.join(rep))
        if orphans:
            print('  ! UNPLACED existing nodes (spelling mismatch?):')
            for o in orphans:
                print('     - %s (%s)' % (o['name'], o['id']))

    data['meta']['node_count'] = len(nodes)
    if mode == '--write':
        json.dump(data, open(PARA, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('\nWROTE %s — %d total nodes' % (PARA, len(nodes)))
    else:
        print('\n(dry-run: no file written; total nodes would be %d)' % len(nodes))


if __name__ == '__main__':
    main()
