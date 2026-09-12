#!/usr/bin/env python3
"""Where is each dhātu form actually used in the library? (धातुप्रयोगसूची)

For every surface form the site can already name -- the 204,974 tiṅanta
forms in prakriya/formindex/ and the 48,890 kṛdanta forms in
prakriya/krtindex/, both keyed to a Dhātupāṭha code and a cell -- this walks
every verse and prose unit of the corpus, records each exact occurrence, and
writes two mirror-image indexes:

  by_dhatu/<gana>/<code>.json     code → {total, forms: {cell → {n, e:[examples]}}}
                                  (the examples a dhātu page shows under a form)
  by_grantha/<slug>.json          unit → [[word, code, cell], …]
                                  (the chips a verse card shows, linking back)
  manifest.json                   totals, per-dhātu totals for leaderboards,
                                  per-branch totals, build info

Why a stored index when intellisense.js and dhatu.js deliberately route
"other occurrences" through the global search: search is STRING-precise (it
finds the letters भवति wherever they occur), this is FORM-precise (it knows
भवति is 01.0001 भू, लट् प्रथमपुरुष एकवचन, and can therefore count, rank and
list examples per cell, per dhātu and per branch). The two answer different
questions and this one cannot be asked of a substring search at all.

Precision over recall: only exact, word-bounded matches count. A word fused
by sandhi (भवत्येव) is not found -- fine, the list is examples, not a census
-- and the very short or notoriously ambiguous forms (ते, स, मे, याति as a
noun …) are skipped by length and a small stoplist rather than counted
wrongly.

HOMOGRAPHS: COUNTED TWICE, NEVER CREDITED ONCE. A surface form does not
always name one root. कृत्वा is the ktvā of both कृ॒ञ् हिंसायाम् (05.0007,
"to injure") and डुकृ॒ञ् करणे (08.0010, "to do"), and the form indexes used
to answer with whichever root came first in Dhātupāṭha order -- so all 29,938
"having done"s in the corpus were filed under "having injured" (the project
lead, 9 Sep 2026). 12.9% of tiṅanta forms and 22% of kṛdanta forms are
ambiguous this way, so this is not a rounding error.

Both indexes now return EVERY reading, and every count here is split in two:

  n   CERTAIN   the form has exactly one reading in the whole corpus of
                forms; the occurrence is this root's, and nothing else's
  sn  SHARED    the form is a homograph; the occurrence is recorded in full
                against EVERY candidate root, and flagged as shared

Shared counts deliberately do not sum to the number of occurrences -- one
कृत्वा is counted for 05.0007 AND for 08.0010, because that is the honest
statement of what is known: one of them wrote it and we cannot say which.
Anything that ranks (the leaderboards, the chip a verse card links to) ranks
on the certain count, which is evidence rather than a guess. What is NOT done
here: splitting an ambiguous occurrence fractionally between candidates by
some assumed baseline. There is no such baseline in this repository, and a
made-up weight would give a wrong number the appearance of a measured one.

root_weights.json falls out of the certain counts: code -> certain total, the
one piece of corpus evidence available for ordering candidates when a reader
tool has to show something first. It is a ranking hint and never a count.

Run:  python3 tools/build_dhatu_prayoga_index.py        (~3 min)
"""
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / 'data'
VY = DATA / 'vedanga/vyakarana'
FORMINDEX = VY / 'prakriya/formindex'
KRTINDEX = VY / 'prakriya/krtindex'
OUT = VY / 'dhatu_prayoga'

SCAN_TOPDIRS = ['darshana', 'DvaitaVedanta/Itara/DasaSahitya', 'itihasa', 'kavya_alankara', 'purana',
                'smriti_dharma', 'stotra', 'nitishastra', 'upaveda', 'agama', 'vedas',
                'vedanga/chandas', 'vedanga/nirukta', 'vedanga/jyotisha', 'vedanga/shiksha',
                'vedanga/kalpa', 'shastra', 'misc']
MAX_PER_FORM = 20          # examples kept per (dhātu, cell); counts stay complete
# A cell whose every occurrence is shared with another root has no evidence
# behind it, only possibility -- a handful of examples makes the point, and
# twenty of them across every candidate root is how this index grew 27% for
# nothing. Certain cells keep the full twenty.
MAX_PER_SHARED_ONLY = 5
MAX_PER_UNIT = 40          # chips per verse card
SNIPPET = 45
MIN_LEN = 3                # code points; ते / स / मे are noise, not evidence
# Words that are far more often something else than the verb form the
# index knows them as (pronouns, particles, common nouns). Extend freely.
STOP = set('''ते स मे न च वा हि तु किं कः का के तत् एव इति अपि यत् यः या ये सः सा
अस्ति आसीत् अस्मि सन्ति स्म अथ इव यथा तथा नु वै आह उत उ ह ऊचुः
भवान् भवति भवत् याति यान्ति वेद वेदः वेदाः नाम काम कामः रामः कृष्णः
अर्थः अर्थ अर्थे लोकः लोके लोकाः देवः देवाः पुत्रः पुत्र गुरुः ईश ईशः'''.split())
# भवति is kept out on purpose? No -- it is the single most useful example
# of all; only the honorific भवान्/भवत् are stopped. Remove it from STOP:
STOP.discard('भवति')

DEVA_WORD = re.compile(r'[ऀ-ॣ०-ॿ]+')
TRAIL = re.compile(r'[।॥०-९0-9\s]+$')


def rank_of(slug):
    if slug.startswith('darshana/vedanta/dvaita/Anandamakaranda'):
        return 0
    if slug.startswith('darshana/vedanta/dvaita/DvaitaVedantaIn'):
        return 1
    if slug.startswith('DvaitaVedanta/Itara/DasaSahitya'):
        return 2
    return 3


def units_of(doc):
    """(unit_id, text) for every text unit a grantha carries (same walk as
    build_sutra_prayoga_index.py), plus the shlokas{} map schema."""
    sh = doc.get('shlokas')
    if isinstance(sh, dict):
        for k, v in sh.items():
            if isinstance(v, dict):
                t = v.get('sa') or v.get('sanskrit_text') or v.get('text') or ''
            else:
                t = str(v or '')
            if t:
                yield str(k), t
    for it in doc.get('items') or []:
        uid = str(it.get('id') or it.get('reference') or '')
        base = it.get('sanskrit_text') or it.get('samhita_patha') or it.get('sa') or it.get('text') or ''
        if base:
            yield uid, base
        for s in it.get('shlokas') or []:
            suid = uid + ('#' + str(s.get('number')) if s.get('number') is not None else '')
            st = s.get('sanskrit_text') or s.get('sa') or ''
            if st:
                yield suid, st


def load_forms():
    """surface → [(code, key), …], EVERY reading the form has.

    Both indexes store a list per form now; the older single-record shape is
    still read, so this keeps working against an index built before that
    change rather than silently indexing nothing (which is exactly what it did
    when formindex became a list and this still tested isinstance(rec, dict)).

    The kṛdanta reading is listed first where a form is both: स्तुतम् is the
    क्त participle far more often than लोट् मध्यम-द्विवचन of स्तु. That is an
    ordering, not a claim -- both readings are kept.
    """
    forms = {}
    for d, kind in ((KRTINDEX, 'k'), (FORMINDEX, 't')):
        for fp in sorted(d.glob('*.json')):
            if fp.name == 'manifest.json':
                continue
            for surf, rec in json.loads(fp.read_text(encoding='utf-8')).items():
                if surf == '_readme' or len(surf) < MIN_LEN or surf in STOP:
                    continue
                recs = rec if isinstance(rec, list) else [rec]
                bucket = forms.setdefault(surf, [])
                for r in recs:
                    if not isinstance(r, dict) or 'c' not in r or 'k' not in r:
                        continue
                    reading = (r['c'], r['k'] if kind == 't' else 'krt:' + r['k'])
                    if reading not in bucket:
                        bucket.append(reading)
    return {k: v for k, v in forms.items() if v}


def branch_of(slug):
    seg = slug.split('/')
    return seg[0] if seg[0] != 'vedanga' else 'vedanga/' + seg[1]


def rank_readings(readings, weights):
    """Most-attested root first.

    The only evidence in the building about which of two homographic roots a
    corpus actually uses is how often each is attested by forms that are NOT
    ambiguous. डुकृञ् करणे is written unambiguously 17,049 times (करोति,
    चकार, कुर्वन्ति); कृञ् हिंसायाम् 110. So a कृत्वा chip links to डुकृञ्
    — earned from this corpus, not assumed, and not a fractional split of the
    count between them either. Ties fall back to code order so a build is
    reproducible."""
    return sorted(readings, key=lambda ck: (-weights.get(ck[0], 0), ck[0], ck[1]))


def chip_for(word, readings, weights):
    """The verse-card chip for one word.

    Three elements exactly as before when there is nothing to choose between,
    so a reader built against the old shape is unaffected. Where there IS a
    choice, the fourth element is the NUMBER of roots that write this spelling
    (it used to be a bare 0/1 flag, which could not tell a reader how much
    doubt there is) and the fifth lists the runners-up."""
    ranked = rank_readings(readings, weights)
    code, key = ranked[0]
    others = [c for c, _ in ranked[1:] if c != code]
    if not others:
        return [word, code, key]
    return [word, code, key, len(others) + 1, others[:6]]


def main():
    t0 = time.time()
    forms = load_forms()
    print(f'{len(forms):,} dhātu forms indexed (after length/stoplist filters)')
    # Certain and shared are tracked apart everywhere, never added together:
    # a shared occurrence is recorded in full against every candidate root, so
    # the shared columns deliberately over-count the corpus.
    by_form = defaultdict(lambda: [0, 0, []])       # (code,key) -> [certain, shared, examples]
    by_grantha = {}                                 # slug -> {unit: [[word,code,key,amb,alts]]}
    per_dhatu = defaultdict(lambda: [0, 0, set()])  # code -> [certain, shared, cells]
    per_branch = defaultdict(int)
    files = units = hits = shared_hits = 0
    for top in SCAN_TOPDIRS:
        root = DATA / top
        if not root.exists():
            continue
        for fp in sorted(root.rglob('data.json')):
            if 'ocr_staging' in fp.parts:
                continue
            slug = str(fp.parent.relative_to(DATA))
            try:
                doc = json.loads(fp.read_text(encoding='utf-8'))
            except Exception:
                continue
            files += 1
            r = rank_of(slug)
            title = str(doc.get('title') or doc.get('title_devanagari') or
                        (doc.get('metadata') or {}).get('title') or '')
            gmap = {}
            for uid, text in units_of(doc):
                if isinstance(text, dict):        # dasa_pada_text keeps {kannada, devanagari, …}
                    text = text.get('devanagari') or text.get('sa') or ''
                    if isinstance(text, list):
                        text = ' '.join(str(x) for x in text)
                if not isinstance(text, str) or not text:
                    continue
                units += 1
                text = text.replace('<br>', ' ').replace('<br/>', ' ')
                chips = []
                seen = set()
                for m in DEVA_WORD.finditer(text):
                    w = TRAIL.sub('', m.group(0))
                    if len(w) < MIN_LEN or w in seen:
                        continue
                    readings = forms.get(w)
                    if not readings:
                        continue
                    seen.add(w)
                    roots = {c for c, _ in readings}
                    certain = len(roots) == 1
                    hits += 1
                    if not certain:
                        shared_hits += 1
                    s0 = max(0, m.start() - SNIPPET)
                    s1 = min(len(text), m.end() + SNIPPET)
                    snip = ('…' if s0 else '') + text[s0:s1].strip() + ('…' if s1 < len(text) else '')
                    # Every candidate is credited. One कृत्वा is an occurrence
                    # for 05.0007 AND for 08.0010; which of them the author
                    # meant is not knowable from the spelling, and picking one
                    # is how 29,938 "having done"s became injuries.
                    for code, key in readings:
                        ent = by_form[(code, key)]
                        ent[0 if certain else 1] += 1
                        # Examples: certain ones always (up to the cap), shared
                        # ones only while a cell has none, so a purely
                        # ambiguous cell still shows the reader something
                        # rather than an empty list -- flagged when it does.
                        room = MAX_PER_FORM * 4 if certain else MAX_PER_FORM
                        if len(ent[2]) < room:
                            ent[2].append((r, slug, uid, w, snip, title, 0 if certain else 1))
                        per_dhatu[code][0 if certain else 1] += 1
                        per_dhatu[code][2].add(key)
                    per_branch[branch_of(slug)] += 1
                    if len(chips) < MAX_PER_UNIT:
                        # The chip's own code is resolved after the scan, once
                        # the certain counts exist to order candidates by.
                        chips.append([w, readings])
                if chips:
                    gmap[uid] = chips
            if gmap:
                by_grantha[slug] = gmap
    print(f'{files} files, {units:,} units, {hits:,} occurrences '
          f'({shared_hits:,} of them on a form more than one root can write), '
          f'{len(by_form):,} distinct (dhātu, cell) pairs, {len(per_dhatu)} dhātus attested '
          f'in {time.time() - t0:.0f}s')

    # ---- rank the candidates of an ambiguous chip ----
    weights = {code: v[0] for code, v in per_dhatu.items()}
    for slug, gmap in by_grantha.items():
        for uid, chips in gmap.items():
            gmap[uid] = [chip_for(w, readings, weights) for w, readings in chips]

    # ---- write ----
    if OUT.exists():
        for p in OUT.rglob('*.json'):
            p.unlink()
    (OUT / 'by_dhatu').mkdir(parents=True, exist_ok=True)
    (OUT / 'by_grantha').mkdir(parents=True, exist_ok=True)
    per_code = defaultdict(dict)
    for (code, key), (n, sn, ex) in by_form.items():
        # Certain examples first, then by source rank: a reader looking at a
        # cell should see the occurrences we can stand behind at the top.
        ex.sort(key=lambda e: (e[6], e[0], e[1], e[2]))
        keep = MAX_PER_FORM if n else MAX_PER_SHARED_ONLY
        cell = {'n': n, 'e': [list(e[1:6]) for e in ex[:keep]]}
        if sn:
            cell['sn'] = sn                     # occurrences shared with another root
            cell['amb'] = 1                     # kept: older readers test this flag
        per_code[code][key] = cell
    for code, cells in per_code.items():
        gana = code.split('.')[0]
        d = OUT / 'by_dhatu' / gana
        d.mkdir(parents=True, exist_ok=True)
        (d / f'{code}.json').write_text(json.dumps(
            {'code': code,
             # `total` stays the certain count, so nothing that already reads
             # it starts reporting an inflated number; the shared figure is a
             # new field beside it rather than folded in.
             'total': per_dhatu[code][0],
             'shared': per_dhatu[code][1],
             'cells': len(cells), 'forms': cells},
            ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    for slug, gmap in by_grantha.items():
        (OUT / 'by_grantha' / (slug.replace('/', '__') + '.json')).write_text(
            json.dumps(gmap, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    ambiguous_forms = sum(1 for v in forms.values() if len({c for c, _ in v}) > 1)
    manifest = {
        'builtAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'tool': 'tools/build_dhatu_prayoga_index.py',
        'formsIndexed': len(forms), 'files': files, 'units': units, 'occurrences': hits,
        'sharedOccurrences': shared_hits,
        'ambiguousForms': ambiguous_forms,
        'dhatusAttested': len(per_dhatu), 'formCellsAttested': len(by_form),
        'maxPerForm': MAX_PER_FORM, 'maxPerUnit': MAX_PER_UNIT,
        'counting': ('n/total = occurrences of forms only this root can write. '
                     'sn/shared = occurrences of a form several roots can write, '
                     'recorded in full against each of them, so these deliberately '
                     'over-count the corpus and must never be added to n. Ranking '
                     'uses n alone.'),
        'byBranch': dict(sorted(per_branch.items(), key=lambda kv: -kv[1])),
        # code -> [certain occurrences, shared occurrences, distinct cells attested]
        'byDhatu': {c: [v[0], v[1], len(v[2])] for c, v in sorted(per_dhatu.items(), key=lambda kv: -kv[1][0])},
        'granthas': sorted(by_grantha.keys()),
    }
    (OUT / 'root_weights.json').write_text(json.dumps(
        {'_readme': ('code -> occurrences of forms ONLY this root can write. A '
                     'ranking hint for a reader tool that must show one of several '
                     'homographic readings first (कृत्वा is both 05.0007 and '
                     '08.0010); never a count of anything on its own.'),
         'builtAt': manifest['builtAt'],
         'weights': dict(sorted(weights.items()))},
        ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    total_bytes = sum(p.stat().st_size for p in OUT.rglob('*.json'))
    print(f'wrote {OUT.relative_to(REPO)}: {len(per_code)} by_dhatu files, {len(by_grantha)} by_grantha files, '
          f'{total_bytes / 1e6:.1f} MB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
