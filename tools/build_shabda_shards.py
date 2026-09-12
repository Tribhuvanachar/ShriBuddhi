#!/usr/bin/env python3
"""Shard the Shabdapatha by first akshara, for the reader's instant lookup.

The full shabdapatha (dge/data/vedanga/vyakarana/shabdapatha/data.json,
7.6 MB, 9,007 words) is fine for its own browser page but far too heavy to
pull into the main reader just to answer "what is this one word". Sanskrit
declension is suffixal -- a form's first akshara is its stem's first
akshara (the one systematic exception, the vocative's हे, is a separate
particle the looker-up strips) -- so sharding the entries by the word's
first character lets the reader fetch one ~130 KB shard (~25 KB over the
wire) chosen from the queried form's own first character, and scan only
that.

Output: dge/data/vedanga/vyakarana/shabdapatha/by_akshara/u0905.json ...
(one per first-codepoint, named by hex), each {"items": [entries...]} with
entries copied verbatim from data.json, plus an index.json listing the
shards. Rerun whenever data.json changes.

    python3 tools/build_shabda_shards.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / 'dge/data/vedanga/vyakarana/shabdapatha/data.json'
OUT = REPO / 'dge/data/vedanga/vyakarana/shabdapatha/by_akshara'


def main():
    d = json.loads(SRC.read_text(encoding='utf-8'))
    shards = {}
    for it in d['items']:
        w = (it.get('word') or '').strip()
        if not w:
            continue
        shards.setdefault(w[0], []).append(it)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob('u*.json'):
        old.unlink()
    index = {}
    total = 0
    for ch, items in shards.items():
        name = 'u%04x.json' % ord(ch)
        p = OUT / name
        p.write_text(json.dumps({'items': items}, ensure_ascii=False,
                                separators=(',', ':')), encoding='utf-8')
        index[ch] = {'file': name, 'count': len(items)}
        total += p.stat().st_size
    (OUT / 'index.json').write_text(json.dumps({
        '_readme': ('Shabdapatha sharded by the headword\'s first character, '
                    'built by tools/build_shabda_shards.py for the reader\'s '
                    'instant word-lookup modal (js/shabda-modal.js). Entries '
                    'are verbatim copies of data.json items.'),
        'shards': index,
    }, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    sizes = sorted((p.stat().st_size for p in OUT.glob('u*.json')), reverse=True)
    print(f'{len(index)} shards, {total/1024/1024:.1f} MB total, '
          f'largest {sizes[0]//1024} KB, median {sizes[len(sizes)//2]//1024} KB')


if __name__ == '__main__':
    main()
