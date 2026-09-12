#!/usr/bin/env python3
"""Strip a literal "$adhyaya$pada$sutra" suffix that leaked into the
Ashtadhyayi reader's visible अधिकारः (adhikara) text -- and, in one case,
its अन्वयः (anvaya) text.

ashtadhyayi.com's own sutraani/data.txt uses "$" as an internal field
delimiter within several of its columns (padaccheda's "pc", anuvritti's
"an", sutra_type's "type" all do this, and importers/ashtadhyayi_layers.py
parses all three correctly). Its "ad" (adhikara) column follows the same
convention -- e.g. "आकडारात् एका संज्ञा$1$4$1", the adhikara text plus the
adhyaya.pada.sutra of the rule that first states it, and a sutra can carry
more than one at once, "##"-joined ("...$1$4$1##कारके$1$4$23") -- but the
importer stored the raw value unparsed, so the reader showed the literal
digits, dollar signs and "##" markers after every adhikara heading:
"अनभिहिते$2$3$1". Fixed at the source in importers/ashtadhyayi_layers.py
(parse_adhikara(), same commit as this script); this is the one-off pass to
clean what an earlier import already wrote to
dge/data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json (3,467 sutras
carried the suffix on "adhikara", 2,780 of those with more than one
"##"-joined heading; one, 6.2.142, carried the identical single-segment
pattern on "anvaya" instead -- a different, much rarer artifact whose root
cause was not tracked down, but showing raw "$6$2$111" to a reader is
wrong regardless of which field it landed in, so it is cleaned the same
way here).

Each "##"-separated segment is stripped of its own trailing
"$<digits>$<digits>$<digits>" (optionally with a trailing "$"), then the
cleaned segments are rejoined with " · " for display. A segment that
doesn't match that exact shape -- with or without the numeric suffix -- is
left untouched and the whole field reported, not guessed at.

    python3 tools/clean_adhikara_suffix.py           # report only
    python3 tools/clean_adhikara_suffix.py --apply   # rewrite data.json

Rebuild the reader's index afterwards:

    python3 tools/build_sutra_index.py
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'dge/data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json')

FIELDS = ('adhikara', 'anvaya')
# A single "##"-joined segment: its own text, optionally its own
# $adhyaya$pada$sutra reference (optionally trailed by a bare "$").
SEGMENT = re.compile(r'^(?P<text>[^$]*?)(\$[0-9]+\$[0-9]+\$[0-9]+)?\$?$')


def clean(value):
    """Returns the cleaned display string, or None if any "##"-segment
    doesn't match the expected shape (left untouched in that case)."""
    segs = []
    for tok in value.split('##'):
        m = SEGMENT.match(tok)
        if not m:
            return None
        text = m.group('text').strip()
        if text:
            segs.append(text)
    return ' · '.join(segs)


def main():
    apply_it = '--apply' in sys.argv
    doc = json.load(open(SRC, encoding='utf-8'))
    items = doc['items']

    cleaned = 0
    unmatched = []
    for it in items:
        for field in FIELDS:
            v = it.get(field)
            if not isinstance(v, str) or '$' not in v:
                continue
            text = clean(v)
            if text is None:
                unmatched.append((it['id'], field, v))
                continue
            cleaned += 1
            if apply_it:
                if text:
                    it[field] = text
                else:
                    it.pop(field, None)

    print('Ashtadhyayi adhikara/anvaya $-suffix cleanup')
    print('  sutras                        %d' % len(items))
    print('  suffix stripped               %d' % cleaned)
    print('  left with an unrecognised $   %d' % len(unmatched))
    if unmatched:
        print('\n  not touched, needs a human look:')
        for sid, field, v in unmatched[:20]:
            print('    %-8s %-9s %s' % (sid, field, v))

    if not apply_it:
        print('\nReport only. Re-run with --apply to rewrite the file, then run'
              '\n  python3 tools/build_sutra_index.py')
        return 0

    json.dump(doc, open(SRC, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\nWrote %s' % SRC)
    return 0


if __name__ == '__main__':
    sys.exit(main())
