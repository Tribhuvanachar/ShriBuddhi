#!/usr/bin/env python3
# Regenerate admin/config/library-status.json -- the snapshot the Library Manager
# dashboard reads. Run from the repo root (or dge/) after new data lands, or
# wire as a GitHub Action step.
#
# Counts are cross-referenced against data/library.json's granthas[] list,
# NOT derived by guessing a file path from taxonomy.json alone. Some
# taxonomy leaves nest an extra layer folder under themselves -- today just
# "mula" (the root text, leaving room for a future sibling commentary
# layer) -- used across Ramayana/Mahabharata's kanda/parva leaves, several
# monolithic Puranas, and all of Sarvamoola's real, live content. Guessing
# "<leaf>/data.json" directly misses every one of those (it lands on an
# unrelated placeholder file instead) and would keep reporting a leaf as
# empty forever even after real content is merged. library.json's own path
# per entry is already correct for every leaf either way, so it's the one
# thing this script should trust.
import json, os
from collections import defaultdict

ROOT = 'dge' if os.path.isdir('dge/data') else '.'
DATA = os.path.join(ROOT, 'data')
# The snapshot is an admin artefact, so it lands in admin/config/ while the
# corpus it describes stays under dge/data/.
OUT_DIR = 'admin/config' if os.path.isdir('admin/config') else DATA
tax = json.load(open(os.path.join(DATA, 'taxonomy.json'), encoding='utf-8'))
lib = json.load(open(os.path.join(DATA, 'library.json'), encoding='utf-8'))

def item_count(data):
    # vedic_text schema: items IS the flat verse list, len(items) is correct.
    # itihasa_purana_text schema: each item is a whole chapter with its own
    # nested shlokas[] -- len(items) would silently report chapter count
    # (e.g. ~77 for Ramayana Bala Kanda) instead of the true verse count.
    items = data.get('items', [])
    if items and isinstance(items[0], dict) and isinstance(items[0].get('shlokas'), list):
        return sum(len(it.get('shlokas', [])) for it in items)
    if items:
        return len(items)
    # vedanga_chandas_vrutta_database: a lookup table, not an items[] list --
    # real content (282 vruttas) was reporting 0 forever, which is exactly
    # why "Chandas" never appeared in the library browser (it excludes
    # unpopulated entries) despite the database having shipped weeks ago.
    if data.get('schema') == 'vedanga_chandas_vrutta_database':
        return sum(len(v) for v in data.values() if isinstance(v, list))
    return 0

def to_slug(catalog_path):
    p = catalog_path
    if p.startswith('dge/'): p = p[4:]
    if p.startswith('data/'): p = p[5:]
    if p.endswith('/data.json'): p = p[:-len('/data.json')]
    return p

# library.json's own paths are always "dge/data/...data.json" (repo-root
# relative, per its own convention) regardless of where this script is run
# from -- rebase onto whichever of "dge" / "." this script resolved ROOT to,
# the same way DATA itself was built above, so both agree on cwd.
def to_local_path(catalog_path):
    return os.path.join(ROOT, catalog_path[len('dge/'):]) if catalog_path.startswith('dge/') else catalog_path

# slug ("x/y" or "x/y/mula") -> cwd-relative file path
SLUG_TO_FILE = {to_slug(g['path']): to_local_path(g['path']) for g in lib.get('granthas', [])}

def count_leaf(leaf_path):
    # Union of two candidate files, deduped by resolved path:
    #  1) the flat "<leaf>/data.json" guess -- covers every ordinary leaf,
    #     AND leaves like vedanga/vyakarana/ashtadhyayi/* that live entirely outside
    #     library.json's catalog (Ashtadhyayi is its own standalone feature,
    #     not part of the main library.json-driven reader).
    #  2) any library.json entry at this exact slug, or exactly one layer
    #     folder below it (e.g. leaf_path + "/mula") -- covers Sarvamoola
    #     (whose "mula" IS the taxonomy leaf itself, so this coincides with
    #     #1) and Ramayana/Mahabharata/monolithic-Puranas (whose taxonomy
    #     leaf has no "mula" child at all, so #1 alone would always miss it).
    files = set()
    flat_fp = os.path.join(DATA, *leaf_path.split('/'), 'data.json')
    if os.path.exists(flat_fp):
        files.add(flat_fp)
    depth = leaf_path.count('/') + 1
    for slug, fp in SLUG_TO_FILE.items():
        if slug == leaf_path or (slug.startswith(leaf_path + '/') and slug.count('/') == depth):
            files.add(fp)
    total = 0
    for fp in files:
        if os.path.exists(fp):
            try: total += item_count(json.load(open(fp, encoding='utf-8')))
            except Exception: pass
    return total

# Same file resolution as count_leaf() above, but for the admin tracker's
# "sources" column -- so admin/library.html can show where a leaf's text
# came from without the browser fetching every leaf's full data.json (some
# run tens of thousands of lines) just to read a source/source_url field.
def leaf_source(leaf_path):
    files = set()
    flat_fp = os.path.join(DATA, *leaf_path.split('/'), 'data.json')
    if os.path.exists(flat_fp):
        files.add(flat_fp)
    depth = leaf_path.count('/') + 1
    for slug, fp in SLUG_TO_FILE.items():
        if slug == leaf_path or (slug.startswith(leaf_path + '/') and slug.count('/') == depth):
            files.add(fp)
    for fp in sorted(files):
        if not os.path.exists(fp):
            continue
        try:
            data = json.load(open(fp, encoding='utf-8'))
        except Exception:
            continue
        source = {}
        for key in ('source', 'source_url', 'licence', 'license'):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                source['licence' if key == 'license' else key] = value.strip()
        if source:
            return source
    return None

# Self-heal library.json's own populated flags while we're here. This is
# the ONE thing core.js actually gates a fetch on (entry.populated===false
# short-circuits straight to "Not Yet Available" without even trying) --
# an importer can write a perfectly good data.json and this script can
# correctly count its verses, and the content is still completely
# invisible on the live site until this flag catches up. Confirmed for
# real, twice, in one day: every ingest here today needed this as a
# separate manual follow-up commit. Auto-syncing it here means the next
# one won't.
changed = False
for g in lib.get('granthas', []):
    fp = to_local_path(g['path'])
    if not os.path.exists(fp):
        continue
    try:
        n = item_count(json.load(open(fp, encoding='utf-8')))
    except Exception:
        continue
    if n > 0 and not g.get('populated'):
        g['populated'] = True
        changed = True
        print(f"  populated:true -> {g['path']} ({n} items)")
if changed:
    json.dump(lib, open(os.path.join(DATA, 'library.json'), 'w', encoding='utf-8'),
               ensure_ascii=False, indent=2)
    open(os.path.join(DATA, 'library.json'), 'a', encoding='utf-8').write('\n')

leaves = {}
leaf_sources = {}
def walk(node, pre):
    ch = {k: v for k, v in node.items() if not k.startswith('_')}
    if not ch:
        p = '/'.join(pre)
        leaves[p] = count_leaf(p)
        source = leaf_source(p)
        if source:
            leaf_sources[p] = source
        return
    for k, v in ch.items():
        walk(v if isinstance(v, dict) else {}, pre + [k])

for k, v in tax.items():
    if not k.startswith('_'):
        walk(v if isinstance(v, dict) else {}, [k])

# Candidate scanned/e-text sources for taxonomy leaves that are STILL empty
# (admin/config/pending_pdf_sources.json -- a hand-maintained research log,
# not derived from anything on disk, so it's merged in here rather than
# computed). Dotted keys there (matching taxonomy.json's own nesting) get
# converted to the same slash-joined form 'leaves'/'leaf_sources' already
# use. Only kept for leaves that are STILL actually empty -- once a leaf
# gets populated (by importing one of these candidates, or anything else)
# it silently drops out here rather than needing separate cleanup.
pending_sources = {}
pending_path = os.path.join(OUT_DIR, 'pending_pdf_sources.json')
if os.path.exists(pending_path):
    pending_raw = json.load(open(pending_path, encoding='utf-8'))
    for k, v in pending_raw.items():
        if k == '_readme':
            continue
        p = k.replace('.', '/')
        if leaves.get(p, 0) == 0:
            pending_sources[p] = v

sec = defaultdict(lambda: {'total': 0, 'loaded': 0, 'items': 0})
for p, n in leaves.items():
    s = p.split('/')[0]
    sec[s]['total'] += 1
    if n > 0:
        sec[s]['loaded'] += 1
        sec[s]['items'] += n

out = {
    'generated_note': 'DGE library load status. Regenerate with tools/gen_library_status.py.',
    'totals': {
        'leaves': len(leaves),
        'loaded': sum(1 for n in leaves.values() if n > 0),
        'items': sum(leaves.values()),
    },
    'sections': {k: dict(v) for k, v in sorted(sec.items())},
    'leaves': {p: n for p, n in sorted(leaves.items())},
    'leaf_sources': {p: leaf_sources[p] for p in sorted(leaf_sources)},
    'pending_sources': {p: pending_sources[p] for p in sorted(pending_sources)},
}
json.dump(out, open(os.path.join(OUT_DIR, 'library-status.json'), 'w', encoding='utf-8'),
           ensure_ascii=False, indent=1)
print('wrote', os.path.join(OUT_DIR, 'library-status.json'), '|', out['totals'])
