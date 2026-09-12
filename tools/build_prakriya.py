#!/usr/bin/env python3
"""
build_prakriya.py — the derivation viewer's data, from Vidyut.

dge/js/dhatu.js has shipped two buttons per root, प्रक्रिया · तिङन्त and
कृदन्त forms, pointing at prakriya.html and krdanta.html. Neither page ever
existed, so both 404 on tap; the code calls them a "Stage-2 hook". This
builds what they were always meant to show.

For every root in the Dhātupāṭha:

  forms   the tiṅanta paradigm — 8 lakāras × 3 puruṣa × 3 vacana, the word
          only. Cheap, so it is complete.
  steps   the full derivation of each form, every step naming the
          Aṣṭādhyāyī sūtra that fired. All 8 lakāras, since 19 Aug 2026
          (see below) — was 2 (Lat/Lot) before that.
  krt     the common kṛdanta forms, likewise derived step by step.

WHY THIS ONCE SHIPPED ONLY TWO LAKĀRAS STEP BY STEP, AND WHY THAT CHANGED.
Steps are written in Devanagari, three bytes a character, so all eight
lakāras run 256 MB across the 2,229 roots (measured directly, not the
116 MB once estimated for a lighter --lakaras run) -- against a site that
was already about 640 MB toward GitHub Pages' documented "recommended"
1 GB. Two lakāras (64 MB) was the size-conscious default; --lakaras always
existed to widen it when there was room. The project lead explicitly
authorized importing at whatever size is needed (with a later
split-to-another-repo fallback if it becomes a real problem, and after
confirming 1 GB is GitHub's own recommendation rather than a hard block),
so the shipped data now runs --lakaras with all 8 lakāras. Rerun with the
narrower default if the space is needed back.

Each root is its own file, so the reader fetches ~29 KB for the root in front
of it and nothing else.

    pip install vidyut
    python3 -c "import vidyut; vidyut.download_data('/tmp/vidyut_data')"
    python3 tools/build_prakriya.py

The sūtra code on every step is the same id dge/js/intellisense.js already
resolves, so each step in the viewer opens the rule that produced it.
"""

import argparse
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'dge', 'data', 'vedanga', 'vyakarana', 'prakriya')
DHATUPATHA = os.path.join(REPO, 'dge', 'data', 'vedanga', 'vyakarana',
                          'dhatupatha', 'data.json')

# The two a learner conjugates first. The rest of the paradigm still ships as
# forms; --lakaras widens this. See the note in the module docstring on why it
# is not all eight.
STEP_LAKARAS = ['Lat', 'Lot']
ALL_LAKARAS = ['Lat', 'Lit', 'Lut', 'Lrt', 'Lot', 'Lan', 'VidhiLin', 'Lun']

# The kṛt pratyayas a reader meets in commentary, rather than all 128.
KRTS = ['kta', 'ktavatu', 'ktvA', 'tumun', 'Satf', 'SAnac', 'tavya', 'anIyar',
        'yat', 'Rvul', 'tfc', 'lyuw']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='/tmp/vidyut_data')
    ap.add_argument('--lakaras', default=','.join(STEP_LAKARAS),
                    help='which lakaras get full derivations (default: %(default)s)')
    ap.add_argument('--limit', type=int, default=0, help='stop after N roots (for a trial run)')
    args = ap.parse_args()

    try:
        from vidyut.prakriya import (Vyakarana, Data, Pada, Pratipadika, Krt,
                                     Prayoga, Lakara, Purusha, Vacana)
        from vidyut import lipi
        from vidyut.lipi import Scheme
    except ImportError:
        print('vidyut is not installed. pip install vidyut', file=sys.stderr)
        return 1
    pdir = os.path.join(args.data, 'prakriya')
    if not os.path.isdir(pdir):
        print(f'no prakriya data at {pdir}\n'
              f'  python3 -c "import vidyut; vidyut.download_data(\'{args.data}\')"',
              file=sys.stderr)
        return 1

    step_lakaras = [l.strip() for l in args.lakaras.split(',') if l.strip()]
    data = Data(pdir)
    v = Vyakarana()
    entries = data.load_dhatu_entries()

    # dhatu.js links prakriya.html#<id> where id is the Dhatupatha's own code,
    # which build_dhatupatha.py took from these same entries — so the two
    # agree by construction. Checked rather than assumed.
    shipped = {}
    if os.path.exists(DHATUPATHA):
        with open(DHATUPATHA, encoding='utf-8') as fh:
            shipped = {it['id']: it for it in json.load(fh)['items']}
        missing = sum(1 for e in entries if e.code not in shipped)
        print(f'  {len(entries)} roots, {len(shipped)} in the shipped Dhatupatha, '
              f'{missing} without a match')
    # The root's name, meaning and gana come from the shipped Dhatupatha rather
    # than from Vidyut, so the derivation viewer is labelled identically to the
    # Dhatupatha page the reader just came from. Vidyut's own entry carries only
    # a code, the aupadeshika and an artha that is often empty.

    dev = {}
    def to_deva(s):
        if s not in dev:
            try: dev[s] = lipi.transliterate(s, Scheme.Slp1, Scheme.Devanagari)
            except Exception: dev[s] = s
        return dev[s]

    def derive(pada):
        try: return v.derive(pada)
        except Exception: return []

    def steps_of(p):
        """(sutra code, the state of the derivation after that rule fired).

        Consecutive rules often leave the text untouched — 1.3.1, 1.3.2 and
        1.3.3 all fire on "BU + la~w" without changing it, since they only mark
        letters as it. Writing the same string out twenty times per derivation
        cost 116 MB across the Dhatupatha. A step whose result equals the one
        before it stores just its code, and the reader carries the last result
        forward. Lossless: every step is still present, in order, with its
        rule.
        """
        out, last = [], None
        for st in p.history:
            # Devanagari, not SLP1: "daD + Sap + ta" is unreadable next to
            # दध् + शप् + त, and the aupadeshika transliterates to exactly the
            # form the Dhatupatha page already shows (daDa~\ -> दधँ॒).
            r = to_deva(' + '.join(st.result))
            out.append([st.code] if r == last else [st.code, r])
            last = r
        return out

    os.makedirs(OUT, exist_ok=True)
    todo = entries[:args.limit] if args.limit else entries
    started = time.time()
    total_bytes = files = 0

    for n, e in enumerate(todo):
        if n and n % 200 == 0:
            rate = n / (time.time() - started)
            print(f'    {n}/{len(todo)}  {rate:.0f} roots/s  '
                  f'{(len(todo) - n) / rate / 60:.0f} min left')
        src = shipped.get(e.code, {})
        out = {'code': e.code,
               'dhatu': src.get('dhatu') or to_deva(e.dhatu.aupadeshika),
               'aupadeshika': e.dhatu.aupadeshika,
               'artha': src.get('artha', ''),
               'gana': src.get('gana', ''),
               'pada': src.get('pada', ''),
               'forms': {}, 'steps': {}, 'krt': []}

        for lname in ALL_LAKARAS:
            lak = getattr(Lakara, lname)
            want_steps = lname in step_lakaras
            for pi, pname in enumerate(['Prathama', 'Madhyama', 'Uttama']):
                for vi, vname in enumerate(['Eka', 'Dvi', 'Bahu']):
                    ps = derive(Pada.Tinanta(
                        dhatu=e.dhatu, prayoga=Prayoga.Kartari, lakara=lak,
                        purusha=getattr(Purusha, pname), vacana=getattr(Vacana, vname)))
                    if not ps:
                        continue
                    key = f'{lname}.{pi}{vi}'
                    out['forms'][key] = [to_deva(p.text) for p in ps]
                    if want_steps:
                        out['steps'][key] = [{'t': to_deva(p.text), 's': steps_of(p)}
                                             for p in ps]

        for kname in KRTS:
            krt = getattr(Krt, kname, None)
            if krt is None:
                continue
            try:
                pr = Pratipadika.krdanta(dhatu=e.dhatu, krt=krt)
            except Exception:
                continue
            ps = derive(pr)
            if not ps:
                continue
            out['krt'].append({'k': kname, 't': to_deva(ps[0].text),
                               's': steps_of(ps[0])})

        gana_dir = os.path.join(OUT, e.code.split('.')[0])
        os.makedirs(gana_dir, exist_ok=True)
        p = os.path.join(gana_dir, e.code + '.json')
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
        total_bytes += os.path.getsize(p)
        files += 1

    manifest = {
        '_readme': 'Derivation data for prakriya.html and krdanta.html, built by '
                   'tools/build_prakriya.py from Vidyut. One file per root, named by '
                   'its Dhatupatha code and filed under its gana. "forms" is the whole '
                   'tinanta paradigm; "steps" carries the full derivation for the '
                   'lakaras listed below, each step naming the Ashtadhyayi sutra that '
                   'fired; "krt" the common krdanta forms. Keys in forms/steps are '
                   'Lakara.<purusha index><vacana index>, both 0-based in the order '
                   'prathama/madhyama/uttama and eka/dvi/bahu.',
        'v': 1,
        'roots': files,
        'lakaras': ALL_LAKARAS,
        'lakarasWithSteps': step_lakaras,
        'krt': KRTS,
    }
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f'\n  {files} roots, {total_bytes / 1024 / 1024:.1f} MB, '
          f'{total_bytes / max(files, 1) / 1024:.0f} KB each')
    print(f'  {(time.time() - started) / 60:.1f} min')
    return 0


if __name__ == '__main__':
    sys.exit(main())
