#!/usr/bin/env python3
"""Structural validation of dge/data/**/data.json for the DGE reader.

The library has TWO on-disk shapes:
  * the catalog shape  {schema, default_author, items:[...]}  (all importers here)
  * a legacy stotra-viewer shape  {metadata, shlokas:{...}}   (pns, some Purana
    placeholders) read by render.js, not by the itihasa/purana reader.

This tool validates the catalog shape strictly (and FAILS CI on a real error in
one of those), while skipping the legacy shape so it never fails on pre-existing
files unrelated to an import. Uses schemas.json for the schema-name vocabulary.
"""
import json, os, glob, sys

ROOT = 'dge' if os.path.isdir('dge/data') else '.'
DATA = os.path.join(ROOT, 'data')
schemas = json.load(open(os.path.join(DATA, 'schemas.json'), encoding='utf-8'))
SCHEMA_NAMES = {k for k in schemas if not k.startswith('_')}

errors, warns, catalog, legacy = [], [], 0, 0

for fp in sorted(glob.glob(os.path.join(DATA, '**', 'data.json'), recursive=True)):
    try:
        d = json.load(open(fp, encoding='utf-8'))
    except Exception as e:
        errors.append(f"{fp}: invalid JSON ({e})"); continue
    if not isinstance(d, dict):
        errors.append(f"{fp}: top-level is not an object"); continue
    if 'items' not in d:
        if d.get('schema') in ('grantha_layer_v2', 'grantha_work_v2'):
            # the v2 architecture (tools/reports/grantha_data_architecture.md)
            # keeps paragraph units under 'units'; its own deep validator is
            # tools/validate_grantha.py
            legacy += 1
        # legacy stotra-viewer shape or an empty placeholder -> skip, don't fail
        elif 'metadata' in d or 'shlokas' in d:
            legacy += 1
        else:
            warns.append(f"{fp}: no 'items' and not legacy shape (empty placeholder?)")
        continue
    catalog += 1
    sc = d.get('schema')
    if sc == 'vyakarana_corpus_v1':
        # the small sutra-corpora imported from ashtadhyayi.com
        # (tools/vyakarana/import_ashtadhyayi_corpora.py) keep the source's
        # own field names verbatim ('i'/'ind'/'id' + corpus fields) plus a
        # mandatory attribution block — that block IS the check here.
        if not isinstance(d.get('items'), list) or not d['items']:
            errors.append(f"{fp}: corpus has no items")
        if not isinstance(d.get('attribution'), dict) or not d['attribution'].get('source_url'):
            errors.append(f"{fp}: vyakarana corpus missing attribution.source_url")
        continue
    if sc and sc not in SCHEMA_NAMES:
        warns.append(f"{fp}: unknown schema '{sc}'")
    items = d.get('items', [])
    if not isinstance(items, list):
        errors.append(f"{fp}: 'items' is not a list"); continue
    for it in items:
        if not isinstance(it, dict) or 'id' not in it:
            errors.append(f"{fp}: item without 'id'"); break
        for sh in it.get('shlokas', []) or []:
            if 'number' not in sh or 'sanskrit_text' not in sh:
                warns.append(f"{fp}: shloka missing number/sanskrit_text (id={it.get('id')})"); break
            for b in sh.get('bhashya', []) or []:
                if not isinstance(b, dict) or 'text' not in b:
                    warns.append(f"{fp}: malformed bhashya (id={it.get('id')})"); break

print(f"validate_data: {catalog} catalog files, {legacy} legacy skipped, "
      f"{len(errors)} errors, {len(warns)} warnings")
for w in warns[:40]: print("  WARN", w)
for e in errors[:40]: print("  ERR ", e)
if errors:
    sys.exit(1)
