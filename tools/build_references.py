#!/usr/bin/env python3
"""
build_references.py — where does a commentary actually CITE something?

Runs the three context-aware detectors in reference_detect.py over every
commentary in the library and stores the hits, so the reader can mark them
without shipping the dhātupāṭha, the sūtrapāṭha and a kośa registry to the
browser and re-deciding on every render.

WHAT THIS REPLACES. The generic word-marking pass (highlight-words.js, flag
showWordMarks) marked any word that existed in a database. One Sanskrit
surface form is a noun, a verb form and a dictionary headword at once, so most
of those marks were false: तन्त्राणि and भावः were "dhātus", विश्व was a
kośa. This tool marks nothing on presence. A span is written only where
reference_detect.py finds a citation FRAME around it — a root beside its own
traditional artha, a lexicon named after इति, a sūtra's own words in quotation
— and only where the thing cited is then found in the authoritative list.

OUTPUT — data/_references/<slug with __ for />.json

    {"slug": ..., "tool": "tools/build_references.py",
     "units": {"<verse id>": {"<commentary key>": [ref, ...]}}}

    ref = {"t": "sutra" | "kosha" | "dhatu",
           "w": [first token, last token + 1],   # for rendering
           "s": [char start, char end],          # the ORIGINAL characters
           "x": surface text,
           "i": authoritative id (dhātu code / sūtra id / kośa slug),
           "l": human label,
           "c": "high" | "medium",
           "r": why it was detected}

TWO COORDINATE SYSTEMS, deliberately. "s" is the source span the directive
asks every reference to keep: it points at the original Devanagari characters
and is what a debugging session or a future exporter wants. "w" is a
whitespace-token range, and it is what the reader actually renders with,
because render.js wraps each \\S+ run in its own <span class="dge-word"> and
the text may by then have been transliterated into Kannada or IAST. Character
offsets do not survive transliteration; token counts do.

Run:  python3 tools/build_references.py            # whole library
      python3 tools/build_references.py --slug DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1
      python3 tools/build_references.py --report   # counts only, writes nothing
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_detect import (DhatuDetector, KoshaDetector, SutraDetector,  # noqa: E402
                              detect_all)

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / 'data'
DHATUPATHA = DATA / 'vedanga/vyakarana/dhatupatha/data.json'
SUTRAPATHA = DATA / 'vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json'
REGISTRY = DATA / 'kosha/_citation_registry.json'
OUT = DATA / '_references'

#: The vyākaraṇa layers are excluded for the same reason
#: build_sutra_prayoga_index.py excludes them: quoting sūtras and roots is
#: their whole job, so a "reference" there carries no information a reader
#: does not already have from the page they are on.
SKIP_PREFIXES = ('vedanga/vyakarana/', 'kosha/', '_')

TOKEN = re.compile(r'\S+')


def token_starts(text):
    """Character offset of every whitespace-separated token, in order.

    render.js wraps exactly these runs in <span class="dge-word">, so the nth
    entry here is the nth word span in the rendered card."""
    return [m.start() for m in TOKEN.finditer(text)], [m.end() for m in TOKEN.finditer(text)]


def token_range(starts, ends, start, end):
    """[first token, last token + 1] covering characters [start, end).

    A citation rarely lands on token boundaries — दीप्ताविति is one written
    word carrying the end of an artha and an इति — so the range is widened to
    whole tokens. Marking a whole word is right anyway: half a Devanagari word
    with a box drawn round it reads as a typo."""
    first = None
    last = None
    for i, (s, e) in enumerate(zip(starts, ends)):
        if e <= start:
            continue
        if s >= end:
            break
        if first is None:
            first = i
        last = i
    if first is None:
        return None
    return [first, last + 1]


def commentary_units(doc):
    """(unit id, commentary key, text) for every plain-string commentary.

    Gold-Standard commentaries (format gold_v2_2) are dicts and are skipped:
    they carry a verified word-by-word mapping and their own citation data,
    and a detector's guess layered over that would fight it (this is the same
    rule render.js applies when it declines to word-wrap a gold block)."""
    shlokas = doc.get('shlokas')
    if not isinstance(shlokas, dict):
        return
    for uid, sh in shlokas.items():
        if not isinstance(sh, dict):
            continue
        for ckey, ctext in (sh.get('commentaries') or {}).items():
            if isinstance(ctext, str) and ctext.strip():
                yield str(uid), ckey, ctext


def slug_of(path):
    return str(path.parent.relative_to(DATA)).replace('\\', '/')


def load_detectors():
    dhatus = json.loads(DHATUPATHA.read_text(encoding='utf-8'))
    sutras = json.loads(SUTRAPATHA.read_text(encoding='utf-8'))
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    return (DhatuDetector(dhatus.get('items') or dhatus),
            KoshaDetector(registry.get('names') or {}),
            SutraDetector(sutras.get('items') or sutras))


def references_for(text, dhatu, kosha, sutra):
    starts, ends = token_starts(text)
    out = []
    for ref in detect_all(text, dhatu=dhatu, kosha=kosha, sutra=sutra):
        w = token_range(starts, ends, ref['start'], ref['end'])
        if not w:
            continue
        out.append({
            't': ref['type'],
            'w': w,
            's': [ref['start'], ref['end']],
            'x': ref['surface'],
            'i': ref['ref_id'],
            'l': ref['label'],
            'c': ref['confidence'],
            'r': ref['reason'],
        })
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--slug', help='build one grantha only')
    ap.add_argument('--report', action='store_true', help='count, write nothing')
    args = ap.parse_args()

    t0 = time.time()
    dhatu, kosha, sutra = load_detectors()

    files = sorted(DATA.rglob('data.json'))
    written = 0
    totals = {'dhatu': 0, 'kosha': 0, 'sutra': 0}
    conf = {'high': 0, 'medium': 0}
    passages = 0
    chars = 0
    for path in files:
        slug = slug_of(path)
        if args.slug and slug != args.slug:
            continue
        if any(slug.startswith(p) for p in SKIP_PREFIXES):
            continue
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        units = {}
        for uid, ckey, ctext in commentary_units(doc):
            passages += 1
            chars += len(ctext)
            refs = references_for(ctext, dhatu, kosha, sutra)
            if not refs:
                continue
            for r in refs:
                totals[r['t']] = totals.get(r['t'], 0) + 1
                conf[r['c']] = conf.get(r['c'], 0) + 1
            units.setdefault(uid, {})[ckey] = refs
        if not units:
            continue
        written += 1
        if args.report:
            continue
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / (slug.replace('/', '__') + '.json')).write_text(
            json.dumps({'slug': slug, 'tool': 'tools/build_references.py',
                        'units': units}, ensure_ascii=False, separators=(',', ':')) + '\n',
            encoding='utf-8')

    print('%d passages, %d chars, %.1fs' % (passages, chars, time.time() - t0))
    print('dhatu %d  kosha %d  sutra %d   (high %d, medium %d)'
          % (totals['dhatu'], totals['kosha'], totals['sutra'],
             conf['high'], conf['medium']))
    print('%s %d grantha files' % ('would write' if args.report else 'wrote', written))
    if not args.report and OUT.exists():
        kb = sum(p.stat().st_size for p in OUT.glob('*.json')) // 1024
        print('%s (%d KB)' % (OUT, kb))
    return 0


if __name__ == '__main__':
    sys.exit(main())
