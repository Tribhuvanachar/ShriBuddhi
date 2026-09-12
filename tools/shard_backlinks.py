#!/usr/bin/env python3
"""
shard_backlinks.py — split backlinks.json so a reading page can use it.

dge/search_index/backlinks.json answers "which commentaries discuss this
verse". It is built by build_search_index.py by inverting every
references[].target in the corpus, and at 2.8 MB it is sized for an offline
tool, not for a phone opening one grantha.

This splits it by the grantha being CITED, so opening the Aṣṭādhyāyī fetches
the Aṣṭādhyāyī's backlinks and nothing else. A grantha nobody cites has no
shard, and the reader fetches nothing at all.

    python3 tools/shard_backlinks.py

Output: dge/search_index/backlinks/<slug with / as __>.json, each
{unitId: [[citing slug, unit, note], ...]}, plus an index.json naming which
granthas have one.

Coverage is whatever the corpus states. Today that is three cited texts —
the Aṣṭādhyāyī sūtrapāṭha and Kāśikā, and the Anuvyākhyāna — because those
are the only data files carrying references[].target. Adding targets to more
texts and rerunning build_search_index.py widens this with no change here.
"""

import collections
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO, 'dge', 'search_index')
SRC = os.path.join(INDEX, 'backlinks.json')
OUT = os.path.join(INDEX, 'backlinks')


def main():
    if not os.path.exists(SRC):
        print(f'no backlinks at {SRC}', file=sys.stderr)
        return 1
    with open(SRC, encoding='utf-8') as fh:
        backlinks = json.load(fh)

    # The Aṣṭādhyāyī's commentary layers are registered as layers rather than
    # as catalogue entries, so library.json has no title for them and the
    # reader would see a folder path. These are the names admin/ashtadhyayi.html
    # already uses for the same files.
    titles = {
        'vedanga/vyakarana/ashtadhyayi/kashika': 'काशिकावृत्तिः',
        'vedanga/vyakarana/ashtadhyayi/nyasa': 'न्यासः',
        'vedanga/vyakarana/ashtadhyayi/balamanorama': 'बालमनोरमा',
        'vedanga/vyakarana/ashtadhyayi/tattvabodhini': 'तत्त्वबोधिनी',
        'vedanga/vyakarana/ashtadhyayi/vasu': 'Vasu (English)',
        'vedanga/vyakarana/ashtadhyayi/sutrapatha': 'सूत्रपाठः',
        'vedanga/vyakarana/paniniya_vyakarana/mahabhashya_patanjali': 'महाभाष्यम्',
        'vedanga/vyakarana/paniniya_vyakarana/siddhanta_kaumudi': 'सिद्धान्तकौमुदी',
    }
    lib = os.path.join(REPO, 'dge', 'data', 'library.json')
    if os.path.exists(lib):
        with open(lib, encoding='utf-8') as fh:
            for g in json.load(fh).get('granthas', []):
                slug = g['path'].replace('dge/data/', '').replace('/data.json', '')
                # The catalogue wins where it has an entry; the table above
                # only fills the gaps it leaves.
                if g.get('title'):
                    titles.setdefault(slug, g['title'])

    # A commentary on sūtra 1.1.1 is filed under its own 1.1.1 and its note is
    # always "comments_on" — every one of the 18,936 pointers in the Aṣṭādhyāyī
    # is like that. Writing the slug, the unit and the note out per pointer
    # cost 1.3 MB for one grantha, most of it the same eight strings repeated.
    # Instead each shard names its citing granthas once and a unit is a list of
    # indices into that list. Anything that does NOT follow the pattern is
    # written out in full under "odd", so the compression never loses a case.
    shards = collections.defaultdict(lambda: {'sources': [], 'units': {}, 'odd': {}})
    pointers = 0
    for key, entries in backlinks.items():
        cited, _, unit = key.partition('#')
        if not cited or not unit:
            continue
        shard = shards[cited]
        srcs = shard['sources']
        plain, odd = [], []
        for e in entries:
            frm, _, funit = (e.get('from') or '').partition('#')
            if not frm:
                continue
            pointers += 1
            if frm not in srcs:
                srcs.append(frm)
            idx = srcs.index(frm)
            if funit == unit and e.get('note', '') == 'comments_on':
                plain.append(idx)
            else:
                odd.append([idx, funit, e.get('note', '')])
        if plain:
            shard['units'][unit] = plain
        if odd:
            shard['odd'][unit] = odd

    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        os.remove(os.path.join(OUT, old))

    index = {}
    total = 0
    for slug, shard in sorted(shards.items()):
        if not shard['odd']:
            del shard['odd']
        name = slug.replace('/', '__') + '.json'
        p = os.path.join(OUT, name)
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(shard, fh, ensure_ascii=False, separators=(',', ':'))
        size = os.path.getsize(p)
        total += size
        n = len(shard['units']) + len(shard.get('odd', {}))
        index[slug] = n
        print(f'  {slug}  {n} units, {size / 1024:.0f} KB')

    # Every grantha that does the citing, so the reader can name it without
    # loading the catalogue a second time.
    citing = sorted({s for shard in shards.values() for s in shard['sources']})
    with open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8') as fh:
        json.dump({
            '_readme': 'Which granthas have a backlinks shard, and the titles of the '
                       'granthas that cite them. Built by tools/shard_backlinks.py from '
                       'search_index/backlinks.json. "cited" maps a grantha slug to how '
                       'many of its units are cited; a slug absent here has no shard and '
                       'the reader fetches nothing.',
            'v': 1,
            'cited': index,
            'titles': {s: titles.get(s, '') for s in citing},
        }, fh, ensure_ascii=False, indent=1)

    print(f'\n  {len(shards)} cited granthas, {pointers} pointers, '
          f'{total / 1024 / 1024:.1f} MB (from {os.path.getsize(SRC) / 1024 / 1024:.1f} MB)')
    print(f'  {len(citing)} granthas do the citing')
    missing = [s for s in citing if not titles.get(s)]
    if missing:
        print(f'  no catalogue title for {len(missing)}: ' + ', '.join(missing[:4]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
