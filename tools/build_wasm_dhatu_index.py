#!/usr/bin/env python3
"""Build the two small data files the in-browser vidyut-prakriya engine needs.

dge/rupasiddhi.html derives arbitrary upasarga + sanadi + lakara paradigms
on-device via vidyut-prakriya compiled to WebAssembly (dge/wasm/vidyut/).
The wasm takes a root as (aupadeshika, gana, antargana?) -- exact SLP1 with
accents and anubandhas -- so:

  dge/data/vedanga/vyakarana/dhatu_wasm_index.json
      {code: [aupadeshika, Gana, Antargana?]} straight from vidyut's own
      dhatupatha (pip install vidyut; the same source build_prakriya.py
      uses), so codes match dhatupatha/data.json by construction.

  dge/data/vedanga/vyakarana/upasarga_artha.json
      {code: [[upasarga_devanagari, meaning_hindi], ...]} -- the documented
      upasarga+dhatu meanings from ashtadhyayi-com/data's dhatu/data.txt
      `upasargas` field (184 roots, ~674 pairs; meanings are in Hindi, as
      the source has them). Attribution: that repo's README requires credit;
      the page carries it once.

    python3 tools/build_wasm_dhatu_index.py --vidyut-data /path --ashcom /path/to/clone
"""
import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_IDX = REPO / 'dge/data/vedanga/vyakarana/dhatu_wasm_index.json'
OUT_UPA = REPO / 'dge/data/vedanga/vyakarana/upasarga_artha.json'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vidyut-data', required=True)
    ap.add_argument('--ashcom', required=True)
    args = ap.parse_args()

    from vidyut.prakriya import Data
    d = Data(str(Path(args.vidyut_data) / 'prakriya'))
    idx = {}
    for e in d.load_dhatu_entries():
        dh = e.dhatu
        ent = [dh.aupadeshika, dh.gana.name]
        if dh.antargana is not None:
            ent.append(dh.antargana.name)
        idx[e.code] = ent
    OUT_IDX.write_text(json.dumps({
        '_readme': ('Per-root arguments for the in-browser vidyut-prakriya engine '
                    '(dge/wasm/vidyut/): [aupadeshika (SLP1, with accents/anubandhas), '
                    'gana, antargana?]. Built by tools/build_wasm_dhatu_index.py from '
                    "vidyut's own dhatupatha, so the codes match dhatupatha/data.json "
                    'by construction.'),
        'items': idx,
    }, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'wrote {OUT_IDX} ({OUT_IDX.stat().st_size // 1024} KB, {len(idx)} roots)')

    rows = json.loads((Path(args.ashcom) / 'dhatu/data.txt').read_text(encoding='utf-8'))['data']
    upa = {}
    pairs = 0
    for r in rows:
        us = r.get('upasargas') or []
        code = r.get('baseindex') or ''
        if us and code:
            upa[code] = [[u.get('name', ''), u.get('artha_hindi', '')] for u in us]
            pairs += len(us)
    OUT_UPA.write_text(json.dumps({
        '_readme': ('Documented upasarga+dhatu meanings (Hindi), keyed by Dhatupatha '
                    'code: [[upasarga, meaning], ...]. From ashtadhyayi-com/data '
                    'dhatu/data.txt `upasargas` (used with credit per its README). '
                    'Built by tools/build_wasm_dhatu_index.py.'),
        'items': upa,
    }, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'wrote {OUT_UPA} ({OUT_UPA.stat().st_size // 1024} KB, '
          f'{len(upa)} roots, {pairs} pairs)')


if __name__ == '__main__':
    main()
