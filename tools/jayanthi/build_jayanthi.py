#!/usr/bin/env python3
"""Import the JAYANTĪ NIRṆAYA (Śrī Madhvācārya / Ānandatīrtha) — the
Kannada-script edition published by the Śrīpādarāja Maṭha, Muḷabāgilu, with
the word-by-word Kannada anvaya-artha and nine tātparya prose sections of
Śrī Agrahāra Nārāyaṇa Tantri — into the DGE static library.

Source: a clean, user-supplied JSON transcription (no OCR / no API, ₹0).
The transform here is reproducible and reviewable: it reads that JSON and
emits one grantha data.json plus a library.json entry and a taxonomy.json
node.

MODEL (schema grantha_mula_text, read by dge/js/core.js's generic-items
branch):
  * each item's `sanskrit_text` is the primary body the reader shows;
  * the Kannada anvaya rides in item.commentaries.kannada_anvaya — the
    reader turns every commentaries{} key into a selectable layer and
    labels it from core.js's KNOWN_COMMENTARY_LABELS (a matching label
    entry is added there);
  * `category` drives the section navigator's filter dropdown
    (layer-stitch.js MODE A), so invocation / śloka / tātparya / colophon
    become browsable groups.

Item layout (24 items):
  JN_INV                 invocation (maṅgalācaraṇa)                       1
  JN_001 … JN_015_017    the 17 mūla ślokas as 13 items (ranges kept as
                         one item, e.g. "10-11" -> JN_010_011)           13
  JN_T1 … JN_T9          the nine tātparya prose sections                 9
  JN_COL                 colophon                                         1

STAGE 1 OF 2. The project lead's decision (5 Sep 2026) is that this Kannada
edition belongs on the EXISTING Jayantī Nirṇaya — which already carries the
Devanagari mula and the Jayatirtha tika slot — as a *commentary layer*, not as
a second mula. So this script no longer writes into the library tree: it emits
the parsed edition to tools/jayanthi/jayanthi_kannada_parsed.json, and
tools/jayanthi/build_jayanthi_tika.py (stage 2) re-keys that onto the mula's
own verse ids to produce tika_kannada/. Library + taxonomy entries belong to
stage 2's placement and are not written here.

Run with --write to apply.
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEST_REL = 'tools/jayanthi'
DEST = os.path.join(ROOT, DEST_REL)
DATA_REL = DEST_REL + '/jayanthi_kannada_parsed.json'

DEFAULT_SRC = os.path.join(
    ROOT, '..',  # not used; real default passed on CLI
)

GRANTHA = 'ಜಯಂತೀ ನಿರ್ಣಯ'
TITLE = 'ಜಯಂತೀ ನಿರ್ಣಯ (Jayantī Nirṇaya) — Kannada edition (anvaya + tātparya)'
DEFAULT_AUTHOR = 'Sri Madhvacharya'
ANVAYA_KEY = 'kannada_anvaya'

# short provenance line (read by tools/audit_library.derive_source) + long note
SOURCE_LINE = ('Śrīpādarāja Maṭha, Muḷabāgilu edition (Kannada script), with '
               'the Kannada anvaya & tātparya of Śrī Agrahāra Nārāyaṇa Tantri; '
               'user-supplied transcription.')
SOURCE_NOTE = (
    'Jayantī Nirṇaya of Śrī Madhvācārya (Ānandatīrtha Bhagavatpādācārya), one '
    'of the Sarvamūla nirṇaya-prakaraṇas. This is the Kannada-script devotional '
    'edition of the Śrī Jagadguru Madhvācārya Mūla Mahāsaṃsthāna, Śrī '
    'Śrīpādarāja Maṭha, Muḷabāgilu, carrying the word-by-word Kannada '
    'anvaya-artha and nine tātparya prose sections of Śrī Agrahāra Nārāyaṇa '
    'Tantri. Digitised from a clean user-supplied transcription (no OCR, no '
    'API). The mūla is kept verbatim in Kannada script, editorial variant '
    'readings preserved in parentheses exactly as printed. Imported under the '
    "project lead's case-by-case-permission practice for non-commercial, "
    'educational dharma-prachāra use. NB: a separate 16-verse Devanagari '
    'recension of this work (from anandamakaranda.in) already lives in the '
    'sibling mula/ folder; the two are independent editions.')

CAT_INV = 'ಮಂಗಳಾಚರಣೆ (Invocation)'
CAT_MULA = 'ಶ್ಲೋಕ (Mūla)'
CAT_TAT = 'ತಾತ್ಪರ್ಯ (Tātparya)'
CAT_COL = 'ಸಮಾಪ್ತಿ (Colophon)'


def verse_id_and_ref(vnum):
    """'1' -> ('JN_001', '1');  '10-11' -> ('JN_010_011', '10–11')."""
    vnum = vnum.strip()
    if '-' in vnum:
        a, b = (p.strip() for p in vnum.split('-', 1))
        return 'JN_%03d_%03d' % (int(a), int(b)), '%s–%s' % (a, b)
    return 'JN_%03d' % int(vnum), vnum


def build_items(src):
    items = []

    # 1. invocation
    items.append({
        'id': 'JN_INV',
        'reference': CAT_INV,
        'sanskrit_text': src['invocation'].strip(),
        'category': CAT_INV,
        'breadcrumb': [GRANTHA, 'ಮಂಗಳಾಚರಣೆ'],
        'tags': ['invocation', 'mangalacharana'],
        'notes': '', 'references': [], 'audio': [],
    })

    # 2. the mula verses, with the Kannada anvaya as a commentary layer
    for v in src['verses']:
        vid, ref = verse_id_and_ref(v['verse_number'])
        anvaya = (v.get('artha') or '').strip()
        for i, fn in enumerate(v.get('footnotes') or [], 1):
            fn = (fn or '').strip()
            if fn:
                anvaya += '\n\n★ ಟಿಪ್ಪಣಿ %d: %s' % (i, fn)
        commentaries = {ANVAYA_KEY: anvaya} if anvaya else {}
        items.append({
            'id': vid,
            'reference': ref,
            'sanskrit_text': v['mula'].strip(),
            'category': CAT_MULA,
            'breadcrumb': [GRANTHA, 'ಶ್ಲೋಕ ' + ref],
            'commentaries': commentaries,
            'tags': ['verse', 'shloka'],
            'notes': '', 'references': [], 'audio': [],
        })

    # 3. the nine tatparya prose sections as trailing prose items
    for s in src['tatparya']:
        num = str(s['section_number']).strip()
        title = (s.get('title') or '').strip()
        items.append({
            'id': 'JN_T%s' % num,
            'reference': 'ತಾತ್ಪರ್ಯ %s — %s' % (num, title),
            'sanskrit_text': s['content'].strip(),
            'category': CAT_TAT,
            'breadcrumb': [GRANTHA, 'ತಾತ್ಪರ್ಯ', title],
            'tags': ['tatparya', 'prose', 'commentary'],
            'notes': '', 'references': [], 'audio': [],
        })

    # 4. colophon
    items.append({
        'id': 'JN_COL',
        'reference': CAT_COL,
        'sanskrit_text': src['colophon'].strip(),
        'category': CAT_COL,
        'breadcrumb': [GRANTHA, 'ಸಮಾಪ್ತಿ'],
        'tags': ['colophon'],
        'notes': '', 'references': [], 'audio': [],
    })
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='path to jayanthi_nirnaya_source.json')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    src = json.load(open(args.src, encoding='utf-8'))
    items = build_items(src)

    verses = [it for it in items if it['category'] == CAT_MULA]
    with_anvaya = sum(1 for it in verses if it.get('commentaries'))
    tat = [it for it in items if it['category'] == CAT_TAT]
    print('=== Jayantī Nirṇaya (Kannada edition) ===')
    print('  dest: %s' % DATA_REL)
    print('  items: %d  (1 invocation + %d verse-items + %d tatparya + 1 colophon)'
          % (len(items), len(verses), len(tat)))
    print('  verse-items with Kannada anvaya: %d/%d' % (with_anvaya, len(verses)))
    print('  total body chars: %d' % sum(len(it['sanskrit_text']) for it in items))

    if not args.write:
        print('\n(dry run — pass --write to apply)')
        return

    data = {
        'schema': 'grantha_mula_text',
        'default_author': DEFAULT_AUTHOR,
        'title': {'kannada': src['title']['kannada'],
                  'transliteration': src['title']['transliteration']},
        'source': SOURCE_LINE,
        'source_note': SOURCE_NOTE,
        'publisher': src.get('publisher', ''),
        'kannada_commentary_by': src.get('kannada_commentary_by', ''),
        'items': items,
    }
    os.makedirs(DEST, exist_ok=True)
    with open(os.path.join(ROOT, DATA_REL), 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    print('  wrote %s' % DATA_REL)
    print('  next: python3 tools/jayanthi/build_jayanthi_tika.py  (stage 2)')


if __name__ == '__main__':
    main()
