#!/usr/bin/env python3
"""
restructure_taxonomy.py — move dge/data/ onto the recommended DGE taxonomy.

The corpus grew a folder at a time, so its top level is a mix of categories
(puranas, itihasas), single works (shankara_bhashya), and a drawer called
"ancillary" that turned out to hold the Vedangas. DGE_Shastra_Taxonomy.md
proposes a top level that a student would recognise: Veda, Vedanga, Darshana,
Itihasa, Purana, Smriti & Dharma, and so on. This moves the corpus onto it.

    python3 tools/restructure_taxonomy.py              # report only, default
    python3 tools/restructure_taxonomy.py --overrides  # write the no-move alternative
    python3 tools/restructure_taxonomy.py --apply      # actually move things

Nothing is touched without --apply. Read the report first: moving files
breaks every URL anyone has bookmarked into the library, and rebuilding the
search index is a separate 162 MB job. The report says exactly what would
move and what else would have to be rewritten to keep the site working.

vedas/ is left alone, as instructed.
"""

import argparse
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'dge', 'data')

# ---------------------------------------------------------------------------
# The mapping. Ordered longest-source-first when matched, so a mapping of a
# subfolder is never shadowed by a mapping of its parent.
#
# Each entry: (source under dge/data/, destination under dge/data/, why)
# ---------------------------------------------------------------------------
MAPPING = [
    # --- Vedanga -----------------------------------------------------------
    # "ancillary" is the Vedangas under another name: shiksha, vyakarana,
    # chandas, nirukta, jyotisha, pratishakhya. Named as such, it stops being
    # a drawer and becomes a branch of the tree.
    ('ancillary/shiksha',        'vedanga/shiksha',              'Vedanga 1'),
    ('ancillary/pratishakhya',   'vedanga/shiksha/pratishakhya', 'phonetic treatises, so under Shiksha — see DECISIONS'),
    ('ancillary/vyakarana',      'vedanga/vyakarana',            'Vedanga 2 — the grammatical schools'),
    ('vyakarana',                'vedanga/vyakarana',            'Vedanga 2 — Ashtadhyayi, Dhatupatha, Vritti; MERGES with the line above'),
    ('ancillary/chandas',        'vedanga/chandas',              'Vedanga 3'),
    ('ancillary/nirukta',        'vedanga/nirukta',              'Vedanga 4'),
    ('ancillary/jyotisha',       'vedanga/jyotisha',             'Vedanga 5 — see DECISIONS, Jyotisha is also its own branch'),
    ('sutras/kalpa_sutras',      'vedanga/kalpa',                'Vedanga 6 — Shrauta, Grhya, Dharma, Shulba'),

    # --- Darshana ----------------------------------------------------------
    ('sarvamoola_grantha',       'darshana/vedanta/dvaita/sarvamula',        'Madhva mula granthas'),
    ('shankara_bhashya',         'darshana/vedanta/advaita/shankara_bhashya', 'Advaita commentary'),

    # --- Itihasa, Purana ---------------------------------------------------
    ('itihasas',                 'itihasa',  'singular, per the taxonomy'),
    ('puranas',                  'purana',   'singular, per the taxonomy'),

    # --- Smriti & Dharma ---------------------------------------------------
    ('smritis',                  'smriti_dharma/smriti',        'Smriti & Dharma'),
    ('dharmashastra',            'smriti_dharma/dharmashastra', 'Smriti & Dharma'),

    # --- Independent branches ----------------------------------------------
    ('kavya',                    'kavya_alankara',       'Kavya & Alankara'),
    ('koshas',                   'kosha',                'Kosha / Lexicography'),
    ('stotras',                  'stotra',               'Stotra stays independent — taxonomy note 7'),
    ('pancharatra_agama',        'agama/pancharatra',    'Agama / Tantra / Mantra'),

    # --- Dasa Sahitya ------------------------------------------------------
    # Taxonomy note 6: its home is Bhakti / Dasa Sahitya, not inside Dvaita.
    # The two kutas are branches of it rather than top-level siblings.
    ('dasakuta',                 'DvaitaVedanta/Itara/DasaSahitya/dasakuta', 'the two kutas gather under Dasa Sahitya'),
    ('vyasakuta',                'DvaitaVedanta/Itara/DasaSahitya/vyasakuta', 'the two kutas gather under Dasa Sahitya'),
]

# Left where they are, deliberately.
UNTOUCHED = {
    'vedas':        'instructed to leave alone',
    'DvaitaVedanta/Itara/DasaSahitya': 'already a top-level branch in the recommended taxonomy',
}

# Choices in the mapping above that are defensible either way, and are the
# author's to make rather than this script's.
DECISIONS = [
    ('ancillary/pratishakhya',
     'vedanga/shiksha/pratishakhya',
     'vedanga/pratishakhya',
     'The Pratishakhyas are phonetic/recitational treatises, which is Shiksha\'s\n'
     '  subject, so nesting them there reflects what they are. Listing them as a\n'
     '  seventh Vedanga sibling is easier to find but claims a status the six\n'
     '  Vedangas do not give them.'),
    ('ancillary/jyotisha',
     'vedanga/jyotisha',
     'jyotisha (its own top-level branch)',
     'The taxonomy says Jyotisha belongs in both places: originally the sixth\n'
     '  Vedanga, later a discipline of its own. What is here now is Vedanga\n'
     '  Jyotisha, so it goes under Vedanga; a top-level jyotisha/ branch can be\n'
     '  added when Siddhanta, Ganita and Hora texts arrive.'),
    ('itihasas / puranas / smritis / koshas / stotras',
     'singular: itihasa, purana, smriti, kosha, stotra',
     'keep the current plural names',
     'The taxonomy is written in the singular. Renaming is consistent but moves\n'
     '  several hundred more paths for a naming convention alone. Dropping these\n'
     '  five renames cuts the change substantially and costs nothing structural.'),
]

# Where else a path under dge/data/ is written down. Everything here has to be
# rewritten in the same commit as the move, or the site breaks.
REFERENCE_GLOBS = ['.js', '.html', '.py', '.yml', '.yaml', '.json', '.md']
SKIP_DIRS = {'.git', 'node_modules', 'dge/data', 'dge/search_index', '.github/workflows/logs'}

# Files that name these paths but are produced by a script. Regenerate them
# rather than editing them, or the next run undoes the edit.
GENERATED = {'admin/config/library-status.json'}


def sh(*args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


def human(n):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024:
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


def tree_stats(path):
    files = total = 0
    for root, _, names in os.walk(path):
        for n in names:
            files += 1
            try:
                total += os.path.getsize(os.path.join(root, n))
            except OSError:
                pass
    return files, total


def rewrite_prefix(slug, rules):
    """Longest source prefix wins, so a mapped subfolder is not shadowed."""
    best = None
    for src, dst, _ in rules:
        if slug == src or slug.startswith(src + '/'):
            if best is None or len(src) > len(best[0]):
                best = (src, dst)
    if not best:
        return slug, False
    src, dst = best
    return dst + slug[len(src):], True


def scan_references(sources):
    """Every place outside dge/data/ that names one of the moving folders AS A
    PATH. The folder names are ordinary words — sutras, kavya, koshas — and a
    bare word match buries the real hits under prose and unrelated variables
    (`var sutras =`, "the Sanskrit koshas"). So a hit has to look like a path:
    under dge/data/, or followed by a path segment, or quoted whole the way a
    taxonomy key is written in JS."""
    names = '|'.join(re.escape(s) for s in sorted(sources, key=len, reverse=True))
    pattern = re.compile(
        r'dge/data/(?P<a>' + names + r')(?![\w])'
        r'|(?<![\w/.])(?P<b>' + names + r')/[\w*{]'
        r'|[\'"](?P<c>' + names + r')[\'"]'
    )
    hits = {}
    for root, dirs, names in os.walk(REPO):
        rel_root = os.path.relpath(root, REPO)
        if rel_root == '.':
            rel_root = ''
        dirs[:] = [d for d in dirs
                   if os.path.join(rel_root, d).replace(os.sep, '/') not in SKIP_DIRS
                   and d not in {'.git', 'node_modules'}]
        for name in names:
            if os.path.splitext(name)[1] not in REFERENCE_GLOBS:
                continue
            rel = os.path.join(rel_root, name).replace(os.sep, '/')
            try:
                with open(os.path.join(root, name), encoding='utf-8', errors='replace') as fh:
                    for i, line in enumerate(fh, 1):
                        m = pattern.search(line)
                        if m:
                            what = m.group('a') or m.group('b') or m.group('c')
                            hits.setdefault(rel, []).append((i, what, line.strip()[:110]))
            except OSError:
                pass
    return hits


def report(args):
    live = [(s, d, w) for s, d, w in MAPPING if os.path.isdir(os.path.join(DATA, s))]
    missing = [(s, d, w) for s, d, w in MAPPING if not os.path.isdir(os.path.join(DATA, s))]

    print('=' * 78)
    print('RESTRUCTURE DRY RUN — nothing has been moved')
    print('=' * 78)

    # ---- 1. the moves -----------------------------------------------------
    print('\n1. FOLDERS THAT WOULD MOVE\n')
    total_files = total_bytes = 0
    for src, dst, why in live:
        files, size = tree_stats(os.path.join(DATA, src))
        total_files += files
        total_bytes += size
        print(f'  dge/data/{src}')
        print(f'    -> dge/data/{dst}')
        print(f'       {files} files, {human(size)}   ({why})')
    print(f'\n  TOTAL: {len(live)} folders, {total_files} files, {human(total_bytes)}')

    if missing:
        print('\n  Mapped but not present (nothing to do):')
        for src, dst, _ in missing:
            print(f'    {src} -> {dst}')

    print('\n  Left where they are:')
    for name, why in sorted(UNTOUCHED.items()):
        if os.path.isdir(os.path.join(DATA, name)):
            files, size = tree_stats(os.path.join(DATA, name))
            print(f'    dge/data/{name:<22} {files} files, {human(size):>9}   ({why})')

    unmapped = sorted(
        d for d in os.listdir(DATA)
        if os.path.isdir(os.path.join(DATA, d))
        and d not in UNTOUCHED
        and not any(s == d or s.startswith(d + '/') for s, _, _ in MAPPING)
    )
    if unmapped:
        print('\n  !! NOT MAPPED — these would be left behind at the old top level:')
        for d in unmapped:
            print(f'    dge/data/{d}')

    # ---- 2. merges --------------------------------------------------------
    print('\n2. MERGES AND COLLISIONS\n')
    dests = {}
    for src, dst, _ in live:
        dests.setdefault(dst, []).append(src)
    merged = {d: s for d, s in dests.items() if len(s) > 1}
    if not merged:
        print('  None — every source lands in a destination of its own.')
    for dst, srcs in merged.items():
        print(f'  dge/data/{dst}  <-  ' + ', '.join(srcs))
        children = {}
        for s in srcs:
            for entry in os.listdir(os.path.join(DATA, s)):
                children.setdefault(entry, []).append(s)
        clash = {c: w for c, w in children.items() if len(w) > 1}
        if clash:
            print('    !! NAME CLASH — these would overwrite each other:')
            for c, w in clash.items():
                print(f'       {c}  in  ' + ' and '.join(w))
        else:
            print(f'    OK — {len(children)} children, no name used twice')

    # Parents emptied by moving their children out. ancillary/ and sutras/ each
    # keep a _meta.json describing a folder that would no longer hold anything.
    moved_children = {}
    for src, _, _ in live:
        if '/' in src:
            moved_children.setdefault(src.split('/')[0], set()).add(src.split('/', 1)[1])
    for parent, moved in sorted(moved_children.items()):
        p_abs = os.path.join(DATA, parent)
        if not os.path.isdir(p_abs):
            continue
        left = sorted(e for e in os.listdir(p_abs) if e not in moved)
        if left:
            print(f'\n  dge/data/{parent}/ would be left holding only: ' + ', '.join(left))
            print(f'    Its children have all moved, so the folder no longer describes anything.')
            print(f'    Delete it, or move what is left somewhere it belongs.')

    # also: does any destination already exist?
    existing = [d for d in dests if os.path.exists(os.path.join(DATA, d.split('/')[0]))
                and os.path.exists(os.path.join(DATA, d))]
    if existing:
        print('\n  !! DESTINATION ALREADY EXISTS:')
        for d in existing:
            print(f'     dge/data/{d}')

    # ---- 3. catalogue files ----------------------------------------------
    print('\n3. CATALOGUE AND INDEX FILES THAT WOULD NEED REWRITING\n')

    lib = json.load(open(os.path.join(DATA, 'library.json'), encoding='utf-8'))
    changed = sum(1 for g in lib.get('granthas', [])
                  if rewrite_prefix(g['path'].replace('dge/data/', ''), live)[1])
    print(f'  dge/data/library.json          {changed} of {len(lib.get("granthas", []))} grantha paths')

    tax = json.load(open(os.path.join(DATA, 'taxonomy.json'), encoding='utf-8'))
    tax_changed = [k for k in tax if rewrite_prefix(k, live)[1]]
    print(f'  dge/data/taxonomy.json         {len(tax_changed)} of {len(tax)} top-level keys')
    print(f'                                 ({", ".join(tax_changed)})')

    man_path = os.path.join(REPO, 'dge', 'search_index', 'manifest.json')
    if os.path.exists(man_path):
        man = json.load(open(man_path, encoding='utf-8'))
        gs = man.get('granthas', [])
        sc = sum(1 for g in gs if rewrite_prefix(g.get('slug', ''), live)[1])
        _, isize = tree_stats(os.path.join(REPO, 'dge', 'search_index'))
        print(f'  dge/search_index/manifest.json {sc} of {len(gs)} slugs, and the same number of')
        print(f'                                 shard FILENAMES under units/ — the slug is baked')
        print(f'                                 into each filename. {human(isize)} of index in total.')
        print(f'                                 Cleanest fix is a full rebuild:')
        print(f'                                     python3 dge/build_search_index.py')

    ov_path = os.path.join(REPO, 'admin', 'config', 'library-overrides.json')
    ov = json.load(open(ov_path, encoding='utf-8'))
    busy = {k: v for k, v in ov.items()
            if k in ('hidden', 'pinned', 'labels', 'order', 'moves') and v}
    if busy:
        print(f'  admin/config/library-overrides.json  keys in use: {", ".join(busy)}')
        print('                                 these are keyed by taxonomy path and would move too')
    else:
        print('  admin/config/library-overrides.json  empty — nothing to migrate. One less thing.')

    # ---- 4. code references ----------------------------------------------
    print('\n4. CODE AND WORKFLOWS THAT NAME A MOVING FOLDER\n')
    sources = sorted({s for s, _, _ in live} | {s.split('/')[0] for s, _, _ in live})
    hits = scan_references(sources)
    hits.pop('tools/restructure_taxonomy.py', None)   # this file talks about them by definition

    def bucket(path):
        if path in GENERATED or path.startswith('dge/search_index/'):
            return 'generated'
        return 'docs' if path.endswith('.md') else 'breaking'

    groups = {'breaking': {}, 'generated': {}, 'docs': {}}
    for p, v in hits.items():
        groups[bucket(p)][p] = v

    print('  BREAKING — the site or an importer stops working until these change:\n')
    for path in sorted(groups['breaking']):
        v = groups['breaking'][path]
        print(f'    {path}  ({len(v)})')
        for line, _, text in v[:3]:
            print(f'        {line}: {text}')
        if len(v) > 3:
            print(f'        ... and {len(v) - 3} more')
    nb = sum(len(v) for v in groups['breaking'].values())
    print(f'\n    {nb} references in {len(groups["breaking"])} files.\n')

    print('  GENERATED — regenerate rather than hand-edit:\n')
    for path in sorted(groups['generated']):
        print(f'    {path}  ({len(groups["generated"][path])} references)')
    print('    dge/search_index/**   (rebuild)')
    print('      python3 tools/gen_library_status.py')
    print('      python3 dge/build_search_index.py\n')

    nd = sum(len(v) for v in groups['docs'].values())
    print(f'  DOCUMENTATION — {nd} references in {len(groups["docs"])} .md files.')
    print('    Stale prose, not a broken site. Worth fixing, not urgent:')
    print('      ' + ', '.join(sorted(groups['docs'])[:8]) +
          (f', +{len(groups["docs"]) - 8} more' if len(groups['docs']) > 8 else ''))

    # ---- 5. decisions -----------------------------------------------------
    print('\n5. DECISIONS THIS SCRIPT MADE FOR YOU\n')
    for i, (what, chose, instead, why) in enumerate(DECISIONS, 1):
        print(f'  {i}. {what}')
        print(f'     chose:   {chose}')
        print(f'     instead: {instead}')
        print(f'  {why}\n')

    # ---- 6. the cost ------------------------------------------------------
    print('6. WHAT MOVING ACTUALLY COSTS\n')
    print('  Every URL into the library changes. Anyone holding a bookmark or a')
    print('  shared link into a grantha gets a 404, and there is no redirect layer')
    print('  on GitHub Pages to soften it.')
    print(f'  The search index ({human(tree_stats(os.path.join(REPO, "dge", "search_index"))[1])}) has the old slugs in both the')
    print('  manifest and every shard filename, so it needs a full rebuild.')
    print(f'  {nb} references in {len(groups["breaking"])} code files have to move with it, plus {nd}')
    print('  more in documentation.')
    print('  git sees renames, so history follows the files. That part is safe.')
    print('\n  There is a second way to get the same tree, in section 7.')

    # ---- 7. the alternative ----------------------------------------------
    print('\n7. THE SAME TREE WITHOUT MOVING ANYTHING\n')
    print('  dge/js/library.js already reads a "moves" map from')
    print('  admin/config/library-overrides.json: it regroups how the library tree')
    print('  DISPLAYS, keyed by the real folder, while every fetch still uses the')
    print('  real path. The reader sees Veda / Vedanga / Darshana / Itihasa; the')
    print('  files do not move, no URL breaks, the search index stays valid, and')
    print('  none of the code in section 4 is touched. It is reversible by')
    print('  deleting the file.')
    print('\n  What it does not do: the repository on disk keeps its present shape,')
    print('  so anyone browsing GitHub, and every importer, still sees the old')
    print('  names. It is a reading-room rearrangement, not a move.')
    print('\n  Run with --overrides to write that file and see it in the browser.')
    print('  If it reads right, the physical move can follow later with --apply,')
    print('  and the overrides file is deleted in the same commit.')


def write_overrides(args):
    """The display-only version of the same tree."""
    live = [(s, d, w) for s, d, w in MAPPING if os.path.isdir(os.path.join(DATA, s))]
    path = os.path.join(REPO, 'admin', 'config', 'library-overrides.json')
    ov = json.load(open(path, encoding='utf-8'))
    ov['moves'] = {src: dst for src, dst, _ in live}
    ov.setdefault('labels', {})
    ov['note'] = (ov.get('note', '').split(' -- ')[0] +
                  ' -- moves/ below regroup the tree onto the recommended DGE taxonomy '
                  '(DGE_Shastra_Taxonomy.md) for DISPLAY only; the files have not moved '
                  'and every fetch still uses the real path. Generated by '
                  'tools/restructure_taxonomy.py --overrides.')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(ov, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print(f'Wrote {len(ov["moves"])} display moves to admin/config/library-overrides.json')
    print('Open the library and check the tree. Nothing on disk has changed.')


def apply(args):
    live = [(s, d, w) for s, d, w in MAPPING if os.path.isdir(os.path.join(DATA, s))]
    dirty = sh('git', 'status', '--porcelain').stdout.strip()
    if dirty and not args.force:
        print('Working tree is not clean. Commit or stash first, or pass --force.')
        print(dirty[:600])
        return 1

    print(f'Moving {len(live)} folders with git mv...')
    for src, dst, _ in live:
        d_abs = os.path.join(DATA, dst)
        os.makedirs(os.path.dirname(d_abs), exist_ok=True)
        if os.path.exists(d_abs):
            # merging into an existing destination: move the children across
            for child in os.listdir(os.path.join(DATA, src)):
                r = sh('git', 'mv', f'dge/data/{src}/{child}', f'dge/data/{dst}/{child}')
                if r.returncode:
                    print(f'  FAILED {src}/{child}: {r.stderr.strip()}')
                    return 1
            os.rmdir(os.path.join(DATA, src))
        else:
            r = sh('git', 'mv', f'dge/data/{src}', f'dge/data/{dst}')
            if r.returncode:
                print(f'  FAILED {src}: {r.stderr.strip()}')
                return 1
        print(f'  {src} -> {dst}')

    print('Rewriting dge/data/library.json ...')
    lp = os.path.join(DATA, 'library.json')
    lib = json.load(open(lp, encoding='utf-8'))
    n = 0
    for g in lib.get('granthas', []):
        slug = g['path'].replace('dge/data/', '')
        new, moved = rewrite_prefix(slug, live)
        if moved:
            g['path'] = 'dge/data/' + new
            n += 1
    json.dump(lib, open(lp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'  {n} paths')

    print('Rewriting dge/data/taxonomy.json ...')
    tp = os.path.join(DATA, 'taxonomy.json')
    tax = json.load(open(tp, encoding='utf-8'))
    out = {}
    for k, v in tax.items():
        new, moved = rewrite_prefix(k, live)
        if not moved:
            out[k] = v
            continue
        # nest the value under the new multi-segment path, merging as we go
        node = out
        parts = new.split('/')
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        if parts[-1] in node and isinstance(node[parts[-1]], dict) and isinstance(v, dict):
            node[parts[-1]].update(v)
        else:
            node[parts[-1]] = v
    json.dump(out, open(tp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'  {len(tax)} -> {len(out)} top-level keys')

    print('\nDone. Still to do, by hand:')
    print('  - the code references in section 4 of the dry run')
    print('  - python3 dge/build_search_index.py     (the index still has old slugs)')
    print('  - the labels in DGE_PATH_LABELS, dge/js/library.js')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true', help='actually move the folders')
    ap.add_argument('--overrides', action='store_true',
                    help='write the display-only version to library-overrides.json')
    ap.add_argument('--force', action='store_true', help='allow --apply on a dirty tree')
    args = ap.parse_args()

    if args.apply and args.overrides:
        print('Pick one: --apply or --overrides.')
        return 1
    if args.overrides:
        return write_overrides(args) or 0
    if args.apply:
        return apply(args)
    report(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
