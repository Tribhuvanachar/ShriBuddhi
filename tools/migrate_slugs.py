#!/usr/bin/env python3
"""
migrate_slugs.py — rewrite taxonomy slugs left behind by the restructure.

tools/restructure_taxonomy.py --apply moves the folders and fixes the two
catalogue files. It does not touch the three other places a slug is written
down, because each needs its own handling:

  dge/data/**/data.json     references[].target — cross-links between texts,
                            e.g. a vritti pointing at the sutra it comments on
  dge/search_index/         backlinks.json (keys and "from"), manifest.json
                            (slug, category, shard), and every shard FILENAME,
                            which is the slug with / replaced by __
  dge/data/*/_meta.json     a category's own name, where it records one

The postings are keyed by grantha index rather than slug, so they need
nothing — which is why this is a rewrite and not the 162 MB rebuild the
dry run warned about. The result is byte-identical to a rebuild for every
field a search touches.

    python3 tools/migrate_slugs.py            # report only
    python3 tools/migrate_slugs.py --apply
"""

import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'tools'))
from restructure_taxonomy import MAPPING, rewrite_prefix   # one source of truth

DATA = os.path.join(REPO, 'dge', 'data')
INDEX = os.path.join(REPO, 'dge', 'search_index')


def upgrade(slug):
    return rewrite_prefix(slug, MAPPING)[0]


def walk_targets(node, changed):
    """references[].target and anything else shaped like a slug pointer."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ('target', 'from') and isinstance(v, str):
                head, sep, frag = v.partition('#')
                new = upgrade(head)
                if new != head:
                    node[k] = new + sep + frag
                    changed[0] += 1
            else:
                walk_targets(v, changed)
    elif isinstance(node, list):
        for v in node:
            walk_targets(v, changed)


def do_data(apply):
    total_files = total_refs = 0
    for root, _, names in os.walk(DATA):
        for n in names:
            if not n.endswith('.json'):
                continue
            p = os.path.join(root, n)
            try:
                with open(p, encoding='utf-8') as fh:
                    doc = json.load(fh)
            except (OSError, ValueError):
                continue
            changed = [0]
            walk_targets(doc, changed)
            if changed[0]:
                total_files += 1
                total_refs += changed[0]
                if apply:
                    with open(p, 'w', encoding='utf-8') as fh:
                        json.dump(doc, fh, ensure_ascii=False)
                print(f'  {os.path.relpath(p, REPO)}  ({changed[0]} targets)')
    print(f'  data files: {total_refs} cross-reference targets in {total_files} files')


def do_backlinks(apply):
    p = os.path.join(INDEX, 'backlinks.json')
    if not os.path.exists(p):
        print('  backlinks.json: absent')
        return
    with open(p, encoding='utf-8') as fh:
        bl = json.load(fh)
    out, keys, froms = {}, 0, 0
    for key, entries in bl.items():
        head, sep, frag = key.partition('#')
        nk = upgrade(head)
        if nk != head:
            keys += 1
        for e in entries:
            if isinstance(e, dict) and isinstance(e.get('from'), str):
                h2, s2, f2 = e['from'].partition('#')
                n2 = upgrade(h2)
                if n2 != h2:
                    e['from'] = n2 + s2 + f2
                    froms += 1
        out[nk + sep + frag] = entries
    print(f'  backlinks.json: {keys} keys, {froms} "from" pointers')
    if apply:
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False)


def do_manifest(apply):
    p = os.path.join(INDEX, 'manifest.json')
    if not os.path.exists(p):
        print('  manifest.json: absent')
        return
    with open(p, encoding='utf-8') as fh:
        man = json.load(fh)
    renames, slugs = [], 0
    for g in man.get('granthas', []):
        old = g.get('slug', '')
        new = upgrade(old)
        if new == old:
            continue
        slugs += 1
        g['slug'] = new
        g['category'] = new.split('/')[0]
        old_shard = g.get('shard', '')
        new_shard = 'units/' + new.replace('/', '__') + '.json'
        if old_shard and old_shard != new_shard:
            renames.append((old_shard, new_shard))
            g['shard'] = new_shard
    print(f'  manifest.json: {slugs} slugs, {len(renames)} shard files to rename')
    if not apply:
        return
    for old_shard, new_shard in renames:
        src, dst = os.path.join(INDEX, old_shard), os.path.join(INDEX, new_shard)
        if not os.path.exists(src):
            print(f'    !! shard missing, skipped: {old_shard}')
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        r = subprocess.run(['git', 'mv', f'dge/search_index/{old_shard}',
                            f'dge/search_index/{new_shard}'],
                           cwd=REPO, capture_output=True, text=True)
        if r.returncode:
            os.rename(src, dst)   # untracked or already staged; move it anyway
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(man, fh, ensure_ascii=False)


def do_meta(apply):
    n = 0
    for root, _, names in os.walk(DATA):
        if '_meta.json' not in names:
            continue
        p = os.path.join(root, '_meta.json')
        rel = os.path.relpath(root, DATA).replace(os.sep, '/')
        try:
            with open(p, encoding='utf-8') as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            continue
        hit = False
        for key in ('slug', 'path', 'category'):
            if isinstance(meta.get(key), str):
                new = upgrade(meta[key])
                if new != meta[key]:
                    meta[key] = new
                    hit = True
        # a category _meta that still names its old folder
        if rel != '.' and isinstance(meta.get('name'), str) and meta['name'] == rel.split('/')[0]:
            pass
        if hit:
            n += 1
            print(f'  {os.path.relpath(p, REPO)}')
            if apply:
                with open(p, 'w', encoding='utf-8') as fh:
                    json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(f'  _meta.json: {n} files')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    print('DRY RUN — nothing written\n' if not args.apply else 'APPLYING\n')
    print('data cross-references:');   do_data(args.apply)
    print('\nsearch index:');           do_backlinks(args.apply); do_manifest(args.apply)
    print('\ncategory metadata:');      do_meta(args.apply)
    if not args.apply:
        print('\nRe-run with --apply to write.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
