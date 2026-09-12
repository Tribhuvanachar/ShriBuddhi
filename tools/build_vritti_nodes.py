#!/usr/bin/env python3
"""Structure the dhatuvrittis into classified nodes — "relevant text only".

The three vrittis (Madhaviya, Kshiratarangini, Dhatupradipa) arrive as one
continuous prose string per dhatu. Median entry is 122 characters and fine
as-is; the long ones are walls of text — भू's Madhaviya entry alone is
94 KB, and much of it is general shastra discussion (it-samjna debates,
karika threads) that belongs to the work's opening, not to भू
specifically. On a phone that reads as a dump.

This tool splits each long vritti into NODES (danda-bounded chunks) and
classifies every node, deterministically — no AI, no rewriting, and the
node boundaries are byte offsets into the untouched original text, so
nothing can be fabricated or lost:

  r  रूपाणि        the node contains this dhatu's own forms — matched
                   against the root's OWN generated paradigm (the vidyut
                   prakriya/dhatuforms data already in this repo: every
                   tinanta across 8 lakaras, krt forms, sanadi forms),
                   plus root-prefixed words (भूत्वा, भूमिः) for roots of
                   2+ characters
  s  सूत्रनिर्देशाः  cites sutras numerically (n.n.n / n/n/n)
  m  आचार्यमतानि    quotes named authorities (हरिः, कैयटः, हेलाराजः,
                   न्यासः, भाष्यम्, क्षीरस्वामी, मैत्रेयः ...)
  g  सामान्यचर्चा    none of the above — general discussion, the part a
                   reader asking "what does this vritti say about THIS
                   dhatu" usually wants folded away

Output is written IN PLACE, additively: each vritti object longer than
NODE_MIN_TEXT gains  "nodes": [[start, end, "rs"], ...]  (offset pairs +
category letters). The text field is never modified. dhatu.js renders
nodes as cards with a "धातुविशिष्टम् / सर्वम्" toggle when they exist and
falls back to the plain text when they don't.

    python3 tools/build_vritti_nodes.py            # report only
    python3 tools/build_vritti_nodes.py --apply    # write

Rerun after regenerating vritti/ or prakriya/ data;
.github/workflows/interlink.yml is the natural home once vrittis change
in CI at all.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VRITTI = REPO / 'dge/data/vedanga/vyakarana/vritti'
PRAKRIYA = REPO / 'dge/data/vedanga/vyakarana/prakriya'
DHATUFORMS = REPO / 'dge/data/vedanga/vyakarana/dhatuforms'

NODE_MIN_TEXT = 600      # vrittis shorter than this stay as-is
NODE_TARGET = 400        # aim for chunks around this size, on danda bounds

SUTRA_REF = re.compile(r'[१-९0-9]\s*[./।]\s*[१-९0-9]\s*[./।]\s*[०-९0-9]{1,3}')
ACHARYAS = re.compile(r'(हरिः|हेलाराज|कैयट|न्यास|काशिका|भाष्य|क्षीरस्वामी|मैत्रेय|'
                      r'आत्रेय|वामन|नन्दी|सुधाकर|पुरुषकार|वृत्तिकार|स्वामी|दुर्ग)')
WORD = re.compile(r'[ऀ-ॣॱ-ॿ]+')


def forms_of(code):
    """Every surface form this repo has generated for the root."""
    out = set()
    p = PRAKRIYA / code.split('.')[0] / (code + '.json')
    if p.exists():
        d = json.loads(p.read_text(encoding='utf-8'))
        for arr in (d.get('forms') or {}).values():
            out.update(arr)
        for k in d.get('krt') or []:
            if k.get('t'):
                out.add(k['t'])
        root = d.get('dhatu') or ''
    else:
        root = ''
    df = DHATUFORMS / (code + '.json')
    if df.exists():
        d = json.loads(df.read_text(encoding='utf-8'))
        for grp in (d.get('forms') or {}).values():
            for pada in grp.values():
                for cells in pada.values():
                    for cell in str(cells).split(';'):
                        for alt in cell.split(','):
                            a = alt.strip()
                            if a:
                                out.add(a)
    out.discard('')
    return out, root


def chunk(text):
    """Danda-bounded chunks of roughly NODE_TARGET chars, as (start, end).

    Long danda-less stretches exist in this OCR'd source (भू's Madhaviya
    text runs 32 KB between two dandas at one point) — a chunk that danda
    boundaries alone would leave over ~3x the target is subdivided at
    spaces instead, so no node is ever a wall of its own."""
    bounds = [m.end() for m in re.finditer(r'[।॥](?:[।॥\s]*)', text)]
    if not bounds or bounds[-1] < len(text):
        bounds.append(len(text))
    coarse, start = [], 0
    for b in bounds:
        if b - start >= NODE_TARGET:
            coarse.append((start, b))
            start = b
    if start < len(text):
        coarse.append((start, len(text)))
    nodes = []
    for s, e in coarse:
        while e - s > NODE_TARGET * 3:
            cut = text.rfind(' ', s + NODE_TARGET, s + NODE_TARGET * 2)
            if cut == -1:
                cut = s + NODE_TARGET * 2
            nodes.append((s, cut))
            s = cut
        nodes.append((s, e))
    return nodes or [(0, len(text))]


def classify(seg, forms, root):
    cats = ''
    words = WORD.findall(seg)
    hit = any(w in forms for w in words)
    if not hit and root and len(root) >= 2:
        hit = any(w.startswith(root) for w in words)
    if hit:
        cats += 'r'
    if SUTRA_REF.search(seg):
        cats += 's'
    if ACHARYAS.search(seg):
        cats += 'm'
    if not cats:
        cats = 'g'
    return cats


def main():
    apply_it = '--apply' in sys.argv
    files = noded = nodes_total = general = 0
    for fp in sorted(VRITTI.glob('*.json')):
        if fp.name.startswith('_'):
            continue
        d = json.loads(fp.read_text(encoding='utf-8'))
        code = d.get('code') or fp.stem
        forms = root = None
        changed = False
        for v in d.get('vrittis') or []:
            text = v.get('text') or ''
            if len(text) < NODE_MIN_TEXT:
                if 'nodes' in v:
                    del v['nodes']
                    changed = True
                continue
            if forms is None:
                forms, root = forms_of(code)
            ns = []
            for s, e in chunk(text):
                cats = classify(text[s:e], forms, root)
                ns.append([s, e, cats])
                nodes_total += 1
                if cats == 'g':
                    general += 1
            v['nodes'] = ns
            noded += 1
            changed = True
        files += 1
        if apply_it and changed:
            fp.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')),
                          encoding='utf-8')
    print(f'{files} vritti files; {noded} long vrittis noded, '
          f'{nodes_total} nodes ({general} general-discussion, '
          f'{nodes_total - general} dhatu-relevant/cited)')
    if not apply_it:
        print('report only — rerun with --apply to write')
    return 0


if __name__ == '__main__':
    sys.exit(main())
