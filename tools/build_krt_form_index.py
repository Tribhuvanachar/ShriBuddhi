#!/usr/bin/env python3
"""
build_krt_form_index.py — reverse lookup from a kṛdanta (verb-derived word)
surface form, e.g. लभ्यः, back to (root, kṛt-pratyaya), for the reader's
word-tool "Shabda" click.

WHY THIS EXISTS. उवाच/परस्य-style deep-linking (tools/build_prakriya_form_index.py,
data/.../formindex/) already covers finite tiṅanta verb forms and nominal
declensions. It does NOT cover kṛdantas — words like लभ्यः ("obtainable",
लभ् + यत्) that are grammatically verb-derived but used AS nominals in a
sentence. A reader selecting one and tapping "Shabda" got a genuinely wrong
answer: no exact match in the Śabdapāṭha nominal-stem database (correctly —
kṛdantas are not stored there), followed by a plain substring fallback that
matched the query as a raw substring INSIDE an unrelated word's declension
table (लभ्यः is literally a substring of वलभ्यः, वलभी's own द्वितीया
बहुवचन) and silently opened that as if it were the answer. Confirmed live,
reported with a screenshot, 20 Aug 2026.

WHAT THIS INDEXES. tools/build_prakriya.py already derives each root's
kṛdanta STEMS (data/vedanga/vyakarana/prakriya/<gana>/<code>.json's
"krt" array — kta/ktavatu/ktvA/tumun/Satf/SAnac/tavya/anIyar/yat/Rvul/
tfc/lyuw). A stem is not a complete word a reader would click on in running
text; it still needs a case ending. This script is NOT a declension engine
— it generates a SMALL, deliberately limited set of the most common surface
forms per stem shape, not a full paradigm:

  - Stems ending in an implicit-अ consonant (the common case — kta, SAnac,
    tavya, anIyar, yat, Rvul, lyuw: लब्ध, लभमान, लब्धव्य, लम्भनीय, लभ्य,
    लम्भक, लम्भन) get three candidates: +ः (nom sg masc), +म् (nom/acc sg
    neut), +आ (nom sg fem, imperfect for an ī-stem feminine reading, but the
    single most common fem citation form for this stem shape).
  - tfc (ऋ-stem agent nouns like लब्धृ) additionally gets its own ऋ->आ
    nominative (लब्धृ -> लब्धा), the one irregular case worth the extra rule.
  - Already-complete stems (ktvA/tumun, genuinely indeclinable; ktavatu/Satf,
    whose own nominative is NOT a simple suffix — कृतवत् -> कृतवान्, भवत् ->
    भवन् — and irregular enough that guessing it wrong would be worse than
    not indexing it at all) are indexed ONLY as their bare stem.

AMBIGUITY: EVERY ROOT, NOT THE LOWEST-NUMBERED ONE. This used to be
first-write-wins over roots in Dhātupāṭha code order — documented as a
heuristic, and wrong in the single most common case in the language. कृत्वा
is the ktvā of both कृ॒ञ् हिंसायाम् (05.0007, "to injure") and डुकृ॒ञ् करणे
(08.0010, "to do"). Code order files it under 05.0007, so every "having done"
in the corpus was counted as an injuring: 29,938 occurrences on a root that
means the opposite of what the reader is looking at (reported by the project
lead, 9 Sep 2026).

There is no honest way to pick one here, so this picks none: a form maps to
the LIST of every (root, kṛt-pratyaya) that produces it. The readers already
know how to offer a choice — the Dhātu popup has shown all matching roots
since 8 Sep — and tools/build_dhatu_prayoga_index.py uses the list to
separate occurrences it can attribute with certainty from ones it cannot.
The same change was made to build_prakriya_form_index.py for tiṅanta forms.

Sharded by first Devanagari codepoint, same scheme as formindex/, so one
word-click fetches one small shard.

    python3 tools/build_krt_form_index.py
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRAKRIYA_DIR = os.path.join(REPO, 'data', 'vedanga', 'vyakarana', 'prakriya')
OUT_DIR = os.path.join(PRAKRIYA_DIR, 'krtindex')

# Matches KRTS in tools/build_prakriya.py.
KRT_ORDER = ['kta', 'ktavatu', 'ktvA', 'tumun', 'Satf', 'SAnac', 'tavya',
             'anIyar', 'yat', 'Rvul', 'tfc', 'lyuw']
# Stem shape -> which surface forms to generate, per the docstring above.
IMPLICIT_A_STEM = {'kta', 'SAnac', 'tavya', 'anIyar', 'yat', 'Rvul', 'lyuw'}
RI_STEM = {'tfc'}
# ktavatu, Satf: irregular nominative, not guessed -- bare stem only.
# ktvA, tumun: genuinely indeclinable -- bare stem only.


def surface_forms(stem, krt_type):
    forms = [stem]
    if krt_type in IMPLICIT_A_STEM:
        forms += [stem + 'ः', stem + 'म्', stem + 'ा']
    elif krt_type in RI_STEM and stem.endswith('ृ'):
        forms.append(stem[:-1] + 'ा')
    return forms


def main():
    if not os.path.isdir(PRAKRIYA_DIR):
        print(f'no prakriya data at {PRAKRIYA_DIR} — run tools/build_prakriya.py first', file=sys.stderr)
        return 1

    root_files = []
    for gana_dir in sorted(os.listdir(PRAKRIYA_DIR)):
        full = os.path.join(PRAKRIYA_DIR, gana_dir)
        if not os.path.isdir(full):
            continue
        for fn in sorted(os.listdir(full)):
            if fn.endswith('.json'):
                root_files.append(os.path.join(full, fn))

    if not root_files:
        print(f'no per-root files found under {PRAKRIYA_DIR}', file=sys.stderr)
        return 1

    flat = {}  # surface form -> [{"c": code, "k": krt type}, ...] (all readings)
    roots_seen = 0
    for path in root_files:
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
        code = d.get('code')
        krt = d.get('krt') or []
        if not code or not krt:
            continue
        roots_seen += 1
        by_type = {k['k']: k['t'] for k in krt if k.get('t')}
        for krt_type in KRT_ORDER:
            stem = by_type.get(krt_type)
            if not stem:
                continue
            for f in surface_forms(stem, krt_type):
                f = f.strip()
                if not f:
                    continue
                entry = {'c': code, 'k': krt_type}
                bucket = flat.setdefault(f, [])
                if entry not in bucket:
                    bucket.append(entry)

    shards = {}
    for form, hit in flat.items():
        cp = format(ord(form[0]), '04x')
        shards.setdefault(cp, {})[form] = hit

    os.makedirs(OUT_DIR, exist_ok=True)
    for cp, shard in shards.items():
        with open(os.path.join(OUT_DIR, cp + '.json'), 'w', encoding='utf-8') as fh:
            json.dump(shard, fh, ensure_ascii=False, separators=(',', ':'), sort_keys=True)

    ambiguous = sum(1 for v in flat.values() if len({e['c'] for e in v}) > 1)
    manifest = {
        '_readme': (
            'Reverse index for js/shabda.js\'s krt-form fallback (a Shabda '
            'word-tool click that misses the nominal Sabdapatha database but is '
            'actually a krdanta): surface form -> [{"c": Dhatupatha root code, '
            '"k": krt pratyaya name}, ...], one entry per root that produces the '
            'form. A single-element list is the common case; a form with several '
            'is genuinely ambiguous and callers must offer the choice rather than '
            'take the first (krtva is the ktva of BOTH 05.0007 "to injure" and '
            '08.0010 "to do"). Built by tools/build_krt_form_index.py from '
            'the per-root prakriya files\' own "krt" array. NOT a full declension '
            'engine -- see the build script\'s own docstring for exactly which '
            'surface forms are generated per stem shape and which krt types are '
            'indexed only as their bare, undeclined stem. Sharded by first '
            'Devanagari codepoint, same scheme as ../formindex/.'
        ),
        'rootsWithKrt': roots_seen,
        'distinctForms': len(flat),
        'formsWithMoreThanOneRoot': ambiguous,
        'shardCount': len(shards),
    }
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f'{roots_seen} roots with krt data -> {len(flat)} distinct surface forms across {len(shards)} shards')
    return 0


if __name__ == '__main__':
    sys.exit(main())
