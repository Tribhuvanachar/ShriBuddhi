#!/usr/bin/env python3
"""Where is each Ashtadhyayi sutra actually used in the library?

Scans the grantha corpus (darshana -- which now includes DvaitaVedanta,
nested under darshana/vedanta/dvaita/ since the 23 Aug 2026 restructure --
kavya, itihasa, purana, smriti, stotra, DvaitaVedanta/Itara/DasaSahitya, ... -- everything
EXCEPT vedanga/vyakarana's
own commentary layers, whose citing of sutras is their whole job, and the
non-text datasets kosha/_morph/_synonyms) for real usages of Panini's
sutras, two ways:

  quote   the sutra's own words verbatim inside a text or its commentary
          (Jayatirtha citing कर्तृकरणयोस्तृतीया). Detected with an
          Aho-Corasick automaton over whitespace/punctuation-normalized
          text; only the 3,534 sutras whose normalized text is >= 8
          Devanagari characters participate -- the short ones (शे, ओत्,
          डति च ...) are substring-coincidence factories, measured, and a
          wrong "usage" in the middle of someone's tika is worse than an
          absent one. Two further guards, both added after the FIRST build
          of this index was inspected rather than trusted:
            * word boundaries -- the character before and after the match
              in the ORIGINAL text must not be a Devanagari letter
              ("तस्य तात्" 7.1.44 was matching inside every तस्य तात्पर्यम्);
            * a citation signal for short sutras -- a sutra under 14
              normalized characters must be followed by इति, or sit in
              quote marks, or have a cue word (सूत्र/पाणिनि/अष्टाध्यायी)
              within reach. Otherwise प्रत्ययः 3.1.1 "matches" every
              philosophical use of the word pratyaya (694 of them, all
              noise). A >= 14-character exact sequence is specific enough
              to stand alone.
  ref     an explicit numeric citation -- digits in the sutra shape with a
          cue word (अष्टाध्यायी / पाणिनि / सूत्र) within the preceding 40
          characters. Bare a.b.c numbers withOUT a cue are verse
          references in most granthas and are deliberately not counted.

Ranking is this project's own priority, not frequency: the Madhva lineage
first --

  rank 0  सर्वमूलम् (darshana/vedanta/dvaita/Anandamakaranda)
  rank 1  the wider Dvaita corpus (darshana/vedanta/dvaita/DvaitaVedantaIn/**:
          Sumadhva Vijaya, Yuktimallika, Nyaya Sudha, the later acharyas' works)
  rank 2  DvaitaVedanta/Itara/DasaSahitya (Vyasakuta/Haridasa works)
  rank 3  everything else (itihasa, kavya, purana, smriti, ...)

Output: data/vedanga/vyakarana/ashtadhyayi/prayoga_index/a<N>.json, one
per adhyaya:  {sutra_id: {"n": total_found, "e": [[slug, unit, kind, rank,
snippet], ...]}} with at most MAX_PER_SUTRA entries kept per sutra (lowest
rank first), and manifest.json with counts. The sutra page's
साहित्ये प्रयोगाः panel (js/ashtadhyayi.js) reads these.

Rerun whenever grantha content changes -- .github/workflows/interlink.yml
does this automatically on push.

    pip install pyahocorasick
    python3 tools/build_sutra_prayoga_index.py
"""
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import ahocorasick

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / 'data'
SUTRAPATHA = DATA / 'vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json'
OUT = DATA / 'vedanga/vyakarana/ashtadhyayi/prayoga_index'

SCAN_TOPDIRS = ['darshana', 'DvaitaVedanta/Itara/DasaSahitya', 'itihasa',
                'kavya_alankara', 'purana', 'smriti_dharma', 'stotra',
                'nitishastra', 'upaveda', 'agama', 'vedas']
MIN_QUOTE_NORM = 8
FREESTANDING_NORM = 14   # this long an exact sequence needs no extra signal
MAX_PER_SUTRA = 60
SNIPPET = 70

DEVA = re.compile(r'[ऀ-ॿ]')
STRIP = re.compile(r'[।॥\s‌‍\-]+')  # danda, space, zwj/zwnj, hyphen
# A Devanagari LETTER for boundary purposes: the block minus danda (0964-65)
# and digits (0966-6F). Avagraha counts as a letter (a sandhi-fused form is
# not the sutra's own wording).
LETTER = re.compile(r'[ऀ-ॣ॰-ॿ]')
# Panini-SPECIFIC cues only. Bare सूत्र is worse than no cue in THIS
# corpus: the numeric refs the first build found were almost all
# Brahmasutra citations (ब्र.सू. १.३.२०  "तदाह सूत्रे ..."), plus one
# Kamasutra -- inspected, not assumed. Likewise सूत्रकारस्य/सूत्राणाम् in
# running Vedanta prose says nothing about Panini.
CUE = re.compile(r'(अष्टाध्यायी|पाणिन|पा\s*[.।॰०]\s*सू|व्याकरणसूत्र)')
NOT_PANINI = re.compile(r'(ब्र|व्र)\s*[.।॰०]?\s*सू|ब्रह्मसूत्र|काम\s*-?\s*सूत्र|म\s*[.।]\s*भा|भागवत|गीता')
ITI = re.compile(r'^[\s।॥\'"’”»›]*(इति|इत्य)')
OPENQ = '\'"‘“«‹'
NUMREF = re.compile(r'([१-८1-8])\s*[.।,]\s*([१-४1-4])\s*[.।,]\s*([०-९0-9]{1,3})')
DEVDIG = {ord(a): str(i) for i, a in enumerate('०१२३४५६७८९')}


def rank_of(slug):
    if slug.startswith('darshana/vedanta/dvaita/Anandamakaranda'):
        return 0
    if slug.startswith('darshana/vedanta/dvaita/DvaitaVedantaIn'):
        return 1
    if slug.startswith('DvaitaVedanta/Itara/DasaSahitya'):
        return 2
    return 3


def norm_with_map(text):
    """Normalized string + map from normalized index -> original index."""
    out, omap = [], []
    for i, ch in enumerate(text):
        if STRIP.match(ch):
            continue
        out.append(ch)
        omap.append(i)
    return ''.join(out), omap


def units_of(doc):
    """Yield (unit_id, text) for every piece of text a grantha carries --
    flat items and nested shlokas, mula and per-verse bhashya alike."""
    for it in doc.get('items') or []:
        uid = str(it.get('id') or it.get('reference') or '')
        base = it.get('sanskrit_text') or it.get('samhita_patha') or \
            it.get('sa') or it.get('text') or ''
        if base:
            yield uid, base
        for sh in it.get('shlokas') or []:
            suid = uid + ('#' + str(sh.get('number')) if sh.get('number') is not None else '')
            st = sh.get('sanskrit_text') or sh.get('sa') or ''
            if st:
                yield suid, st
            for b in sh.get('bhashya') or []:
                bt = b.get('text') or ''
                if bt:
                    yield suid, bt


def main():
    sutras = json.loads(SUTRAPATHA.read_text(encoding='utf-8'))['items']
    by_id = {}
    A = ahocorasick.Automaton()
    quotable = 0
    for it in sutras:
        n, _ = norm_with_map(it['sanskrit_text'])
        by_id[it['id']] = it
        if len(n) >= MIN_QUOTE_NORM:
            # several sutras can normalize identically? keep a list per key
            if n in A:
                A.get(n).append(it['id'])
            else:
                A.add_word(n, [it['id']])
            quotable += 1
    A.make_automaton()
    print(f'{quotable} sutras quotable (norm >= {MIN_QUOTE_NORM}), '
          f'{len(sutras) - quotable} short ones reachable via cued refs only')

    found = defaultdict(list)   # sutra_id -> [(rank, slug, unit, kind, snippet)]
    files = units = 0
    t0 = time.time()
    for top in SCAN_TOPDIRS:
        for fp in sorted((DATA / top).rglob('data.json')):
            slug = str(fp.parent.relative_to(DATA))
            try:
                doc = json.loads(fp.read_text(encoding='utf-8'))
            except Exception:
                continue
            files += 1
            r = rank_of(slug)
            title = str(doc.get('title') or doc.get('title_devanagari') or '')
            for uid, text in units_of(doc):
                units += 1
                ntext, omap = norm_with_map(text)
                seen_here = set()
                for end, ids in A.iter(ntext):
                    start = end  # inclusive index of the match's last char
                    for sid in ids:
                        if sid in seen_here:
                            continue
                        nlen = len(norm_with_map(by_id[sid]['sanskrit_text'])[0])
                        n0 = start - (nlen - 1)
                        o0 = omap[max(0, n0)]
                        o1 = omap[min(len(omap) - 1, start)]
                        # word boundaries in the ORIGINAL text, both sides
                        if o0 > 0 and LETTER.match(text[o0 - 1]):
                            continue
                        if o1 + 1 < len(text) and LETTER.match(text[o1 + 1]):
                            continue
                        # short sutras need a citation signal, not bare presence
                        if nlen < FREESTANDING_NORM:
                            after = text[o1 + 1:o1 + 12]
                            before = text[max(0, o0 - 3):o0]
                            around = text[max(0, o0 - 50):min(len(text), o1 + 30)]
                            quoted = any(q in before for q in OPENQ)
                            cued = CUE.search(around)
                            # a following इति counts only for MULTI-word
                            # sutras: single ordinary words close statements
                            # with इति constantly (मम प्रयोजनम् इति भावः --
                            # 39 such non-citations of 5.1.108 in the first
                            # build), while a multi-word sequence + इति is a
                            # quotation in practice.
                            multiword = ' ' in by_id[sid]['sanskrit_text'].strip()
                            if not (quoted or cued or (multiword and ITI.match(after))):
                                continue
                        seen_here.add(sid)
                        s0 = max(0, o0 - SNIPPET)
                        s1 = min(len(text), o1 + SNIPPET)
                        snip = ('…' if s0 else '') + text[s0:s1].strip() + ('…' if s1 < len(text) else '')
                        found[sid].append((r, slug, uid, 'quote', snip, title))
                for m in NUMREF.finditer(text):
                    pre = text[max(0, m.start() - 40):m.start()]
                    if not CUE.search(pre) or NOT_PANINI.search(pre):
                        continue
                    sid = '.'.join(g.translate(DEVDIG) for g in m.groups())
                    sid = re.sub(r'\.0+(\d)', r'.\1', sid)
                    if sid not in by_id or sid in seen_here:
                        continue
                    s0 = max(0, m.start() - SNIPPET)
                    s1 = min(len(text), m.end() + SNIPPET)
                    snip = ('…' if s0 else '') + text[s0:s1].strip() + ('…' if s1 < len(text) else '')
                    found[sid].append((r, slug, uid, 'ref', snip, title))
    print(f'scanned {files} files / {units} units in {time.time() - t0:.0f}s; '
          f'{len(found)} sutras have usages, '
          f'{sum(len(v) for v in found.values())} usages total')

    OUT.mkdir(parents=True, exist_ok=True)
    per_adhyaya = defaultdict(dict)
    for sid, entries in found.items():
        entries.sort(key=lambda e: (e[0], e[1], e[2]))
        per_adhyaya[sid.split('.')[0]][sid] = {
            'n': len(entries),
            'e': [[e[1], e[2], e[3], e[0], e[4], e[5]] for e in entries[:MAX_PER_SUTRA]],
        }
    for a in map(str, range(1, 9)):
        (OUT / f'a{a}.json').write_text(
            json.dumps(per_adhyaya.get(a, {}), ensure_ascii=False,
                       separators=(',', ':')), encoding='utf-8')
    (OUT / 'manifest.json').write_text(json.dumps({
        '_readme': ('Sutra -> usages across the grantha corpus, built by '
                    'tools/build_sutra_prayoga_index.py (its docstring records '
                    'the detection rules and the lineage-first ranking). '
                    'Entry: [slug, unit, quote|ref, rank, snippet, title]. '
                    'rank: 0 sarvamula, 1 dvaitavedanta, 2 DvaitaVedanta/Itara/DasaSahitya, 3 rest.'),
        'v': 1,
        'sutrasWithUsages': len(found),
        'usages': sum(len(v) for v in found.values()),
        'quotableSutras': quotable,
        'minQuoteNorm': MIN_QUOTE_NORM,
        'maxPerSutra': MAX_PER_SUTRA,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    total = sum((OUT / f'a{a}.json').stat().st_size for a in map(str, range(1, 9)))
    print(f'wrote {OUT} ({total // 1024} KB across 8 shards)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
