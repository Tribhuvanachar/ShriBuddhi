#!/usr/bin/env python3
"""Build the Tīrthaprabandha mūla into the DGE Library under
SarvaMula → Kāvya, with each verse linked to the project's Tīrtha page.

Source of the digitised Devanāgarī mūla (235 ślokas, 4 directional
prabandhas): tirthaprabandha.wordpress.com (a verse-by-verse transcription
of Śrī Vādirāja Tīrtha's 16th-c. work). Only the mūla ślokas — public-domain
text — are imported; the blogger's own English notes are NOT copied. The
Pradīpa-Siṁha ṭīkā is a separate later layer (added per verse under
`commentaries` once a clean/OCR'd source exists).

Emits four grantha_mula_text data.json files (one per prabandha), registers
them in library.json, and adds the taxonomy nodes. Each verse item carries:
  reference   "<Kṣetra> · <n>"      (context; not shown in list view but kept)
  breadcrumb  [work, prabandha, kṣetra]   (section-navigator grouping)
  tirtha_link "tirtha/index.html?q=<kṣetra>"  (rendered as a 📍 chip)
"""
import json, os, re, unicodedata, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARSED = os.path.join(ROOT, 'tools/tirtha/sources/tirthaprabandha_mula_parsed.json')
TIRTHA = os.path.join(ROOT, 'dge/tirtha/data.json')
LIB = os.path.join(ROOT, 'dge/data/library.json')
TAX = os.path.join(ROOT, 'dge/data/taxonomy.json')
BASE = 'dge/data/darshana/vedanta/dvaita/SarvaMula/kavya/tirtha_prabandha'

PRA = [
    ('paschima', 'paschima_prabandha', 'Paścima', 'PAS', 'तीर्थप्रबन्धः — पश्चिमप्रबन्धः (पश्चिमदिक्)'),
    ('uttara',   'uttara_prabandha',   'Uttara',  'UTT', 'तीर्थप्रबन्धः — उत्तरप्रबन्धः (उत्तरदिक्)'),
    ('purva',    'purva_prabandha',    'Pūrva',   'PUR', 'तीर्थप्रबन्धः — पूर्वप्रबन्धः (पूर्वदिक्)'),
    ('dakshina', 'dakshina_prabandha', 'Dakṣiṇa', 'DAK', 'तीर्थप्रबन्धः — दक्षिणप्रबन्धः (दक्षिणदिक्)'),
]
# posts that are not a linkable tīrtha place
NO_PLACE = {'Mangalacharana and Prarthana', 'Upasamhara and Mangala'}

SRC = {
    'source': 'tirthaprabandha.wordpress.com (verse-by-verse Devanāgarī transcription of the mūla)',
    'source_url': 'https://tirthaprabandha.wordpress.com/',
    'licence': 'Mūla text is public domain (Śrī Vādirāja Tīrtha, 16th c.); only the ślokas are reproduced, none of the transcriber’s own notes/translation.',
}


def clean_q(kshetra):
    """Query string for the Tīrtha-page filter: drop parentheticals and the
    generic 'nadee/Kshetra/Tirtha/sangama' tail so the substring match lands."""
    k = re.sub(r'\(.*?\)', '', kshetra).strip()
    k = re.sub(r'\b(nadee|Kshetra|Tirtha|sangama|parvata|Matha)\b', '', k, flags=re.I).strip()
    return k or kshetra


def main():
    data = json.load(open(PARSED, encoding='utf-8'))
    lib = json.load(open(LIB, encoding='utf-8'))
    tax = json.load(open(TAX, encoding='utf-8'))
    today = datetime.date.today().isoformat()

    # taxonomy: SarvaMula -> kavya -> tirtha_prabandha -> 4 prabandhas
    sm = tax['darshana']['vedanta']['dvaita']['SarvaMula']
    kav = sm.setdefault('kavya', {})
    kav.setdefault('_schema', 'grantha_mula_text')
    kav.setdefault('_default_author', 'Sri Vadiraja Tirtha')
    tp = kav.setdefault('tirtha_prabandha', {})

    existing_paths = {g['path'] for g in lib['granthas']}
    new_granthas = []
    totals = {}

    for key, slug, disp, code, title in PRA:
        tp[slug] = {}
        items = []
        for kobj in data[key]:
            kshetra = kobj['kshetra']
            linkable = kshetra not in NO_PLACE
            for vn, vtext in kobj['verses']:
                items.append({
                    'id': '%s_%s_%03d' % ('TP', code, vn),
                    'reference': '%s · %d' % (kshetra, vn),
                    'sanskrit_text': vtext,
                    'tags': ['verse', 'kavya'],
                    'notes': '',
                    'references': [],
                    'audio': [],
                    'breadcrumb': ['Tīrthaprabandha', disp + ' Prabandha', kshetra],
                    'tirtha_link': ('tirtha/index.html?q=' + clean_q(kshetra)) if linkable else '',
                    'commentaries': {},
                    'source': {'site': 'tirthaprabandha.wordpress.com',
                               'prabandha': disp, 'kshetra': kshetra, 'verse': vn},
                })
        out = {
            'schema': 'grantha_mula_text',
            'default_author': 'Sri Vadiraja Tirtha',
            # top-level provenance strings — audit_library.derive_source reads
            # exactly these keys, so they stay in sync with the library.json entry
            'source': SRC['source'],
            'source_url': SRC['source_url'],
            'licence': SRC['licence'],
            'source_note': SRC['licence'],
            'title': title,
            'items': items,
        }
        d = os.path.join(ROOT, BASE, slug)
        os.makedirs(d, exist_ok=True)
        json.dump(out, open(os.path.join(d, 'data.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        totals[slug] = len(items)

        gpath = '%s/%s/data.json' % (BASE, slug)
        if gpath not in existing_paths:
            new_granthas.append({
                'path': gpath, 'populated': True, 'title': title, 'addedAt': today,
                'source': dict(SRC), 'facets': {'default_author': 'Sri Vadiraja Tirtha'},
            })

    lib['granthas'].extend(new_granthas)
    json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(tax, open(TAX, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('wrote 4 prabandha data.json:', totals, '(total %d verses)' % sum(totals.values()))
    print('registered %d new granthas; taxonomy SarvaMula/kavya/tirtha_prabandha added' % len(new_granthas))


if __name__ == '__main__':
    main()
