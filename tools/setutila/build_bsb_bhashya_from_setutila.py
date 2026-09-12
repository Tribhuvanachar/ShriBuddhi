#!/usr/bin/env python3
"""Rebuild the brahma_sutra v2 `bhashya` layer from the Setu Tila edition.

The DvaitaVedanta bhashya layer (grantha.html reader) had plain paragraphs
and no structural headings. The Setu Tila edition (setutila.in, imported
under dge/data/.../SetuTila/) carries, per sutra:
  * the Sarvamula bhashya text,
  * unique descriptive HEADINGS (Heading1 adhyaya · Heading2 upodghata /
    vishaya-vakya sub-sections · Heading3 adhikarana),
  * FOOTNOTES — pathantara (variant-reading) notes in data-note attrs and
    pramana (scriptural-source) citations, embedded in source_html.

This tool maps that flat item list onto the v2 layer's ref scheme (the
Mula blocks carry १/१/१ = 1.1.1, which align 1:1 with the sutra base
layer) and emits grantha_layer_v2 units that preserve headings + footnotes
as additive fields the reader renders. Output overwrites bhashya/data.json.
"""
import json, os, re, html

BSB = 'dge/data/DvaitaVedanta/SarvaMula/sutra_prasthana/brahmasutra_bhashya/data.json'
FAM = 'dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/brahma_sutra'
OUT = FAM + '/bhashya/data.json'
SUTRA = FAM + '/sutra/data.json'
DVMAP = FAM + '/_sources/dv_map.json'
ST_URL = 'https://setutila.in/brahmasutra-bhashya/'

DIG = {'०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
       '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'}

def parse_ref(text):
    m = re.search(r'([०-९]+)\s*/\s*([०-९]+)\s*/\s*([०-९]+)', text)
    if not m:
        return None
    return '.'.join(''.join(DIG.get(c, c) for c in g) for g in m.groups())


def esc(s):
    return html.escape(s or '', quote=True)



def transform(source_html):
    """Return (safe_html, footnotes[]). Stack-based so every <span> we strip
    (uuid wrappers, unknown spans) also drops its matching </span>, while the
    two spans we keep (pramana citations, kutra cross-ref labels) stay
    balanced. pathantara markers become numbered footnote sups; the raw 🔗
    source anchors are dropped. All text and attribute values are escaped."""
    notes = []
    s = source_html
    # pathantara: empty self-contained markers carrying the note in data-note
    def _fn(m):
        note = m.group(1)
        if not notes or notes[-1] != note:
            notes.append(note)
        return '\x00FN%d\x00' % len(notes)      # placeholder, restored last
    s = re.sub(r"<span class='pathantara' data-note=\"(.*?)\"></span>", _fn, s, flags=re.S)
    # drop the raw 🔗 <a class=source> anchors entirely (the kutra label stays)
    s = re.sub(r"<a[^>]*class='source'[^>]*>.*?</a>", '', s, flags=re.S)

    out, stack, pos = [], [], 0
    for m in re.finditer(r"<(/?)span([^>]*)>", s):
        out.append(esc(s[pos:m.start()]))       # escaped text between tags
        pos = m.end()
        if m.group(1):                           # </span>
            if stack.pop() if stack else False:
                out.append('</span>')
        else:                                    # <span ...>
            attrs = m.group(2)
            cm = re.search(r"class='([^']*)'", attrs)
            cls = cm.group(1) if cm else ''
            if 'pramana' in cls:
                sm = re.search(r"data-source='(.*?)'", attrs)
                im = re.search(r"data-pramana-info='(.*?)'", attrs)
                title = ' · '.join(x for x in (sm and sm.group(1), im and im.group(1)) if x)
                out.append('<span class="g2-pramana"' +
                           (' title="' + esc(title) + '"' if title else '') + '>')
                stack.append(True)
            elif 'kutra' in cls:
                out.append('<span class="g2-kutra">')
                stack.append(True)
            else:                                # uuid wrapper / anything else
                stack.append(False)
    out.append(esc(s[pos:]))
    res = ''.join(out)
    res = re.sub(r'\x00FN(\d+)\x00', lambda x: '<sup class="g2-fn">' + x.group(1) + '</sup>', res)
    return re.sub(r'\s+', ' ', res).strip(), notes


def main():
    src = json.load(open(BSB, encoding='utf-8'))
    items = src['items']
    # the base sutra layer defines the family ref universe; Setu Tila sutras
    # that the base edition splits/merges differently (e.g. 3.1.29) are snapped
    # onto the last valid base ref so the bhashya stays anchored in-universe.
    base_refs = {u['ref'] for u in json.load(open(SUTRA, encoding='utf-8'))['units']}
    units = []
    cur_ref = '0.0.0'       # everything before the first Mula = mangala
    counters = {}
    pending_heads = []      # headings buffered until the next ref
    # The base sutra layer already supplies adhikarana (Heading3) dividers, so
    # only the adhyaya (Heading1) and the unique descriptive upodghata / vishaya
    # sub-sections (Heading2) are brought over as the edition's own headings.
    KEEP_HEADINGS = {1, 2}
    # The opening invocation (narayanam gunaih … dvapare …) precedes Madhva's
    # gloss of the first sutra; it is routed to the mangala ref (0.0.0) so the
    # reader shows it as the collapsible Mangalacharana section, matching the
    # rest of the grantha family.
    mangala_active = True
    first_word = None

    # ids stay <ref>.p<n> (validate_grantha's ID_RE) — one sequence per ref
    # across all unit kinds; the `kind` field distinguishes heading/colophon.
    def nid(ref):
        counters[ref] = counters.get(ref, 0) + 1
        return '%s.p%d' % (ref, counters[ref])

    def flush_heads(ref):
        for h in pending_heads:
            units.append({'id': nid(ref), 'ref': ref, 'kind': 'heading',
                          'level': h['level'], 'text': h['text'], 'on': [ref]})
        pending_heads.clear()

    for it in items:
        tags = it.get('tags', [])
        txt = (it.get('sanskrit_text') or '').strip()
        sh = it.get('source_html') or ''
        if any(t.startswith('Heading') for t in tags):
            lvl = int(next(t[7:] for t in tags if t.startswith('Heading')))
            if lvl in KEEP_HEADINGS:
                pending_heads.append({'level': lvl, 'text': txt})
            continue
        if 'Mula' in tags:
            r = parse_ref(txt)
            if r and (r in base_refs or r == '0.0.0'):
                cur_ref = r           # a base sutra — anchor here
            # else: a Setu-Tila-only split (e.g. 3.1.29) — keep the previous
            # valid ref so its bhashya stays anchored in the family universe
            if first_word is None:
                core = re.sub(r'[ॐ०-९\[\]।॥/]', ' ', txt).split()
                first_word = core[0] if core else None
            flush_heads(cur_ref)   # headings attach to the sutra they precede
            continue
        if 'Sarvamula' in tags or 'Colophon_Sarvamula' in tags:
            target = cur_ref
            if mangala_active and 'Sarvamula' in tags:
                clean = re.sub(r'^[ॐ०-९\[\]।॥“”"\s]+', '', txt)
                if first_word and clean.startswith(first_word):
                    mangala_active = False    # Madhva's sutra-gloss has begun
                else:
                    target = '0.0.0'          # still in the opening invocation
            flush_heads(target)
            h, notes = transform(sh)
            kind = 'colophon' if 'Colophon_Sarvamula' in tags else None
            u = {'id': nid(target), 'ref': target,
                 'text': txt, 'html': h, 'on': [target]}
            if kind:
                u['kind'] = kind
            if notes:
                u['footnotes'] = notes
            units.append(u)

    out = {'schema': 'grantha_layer_v2', 'work': 'brahma_sutra', 'layer': 'bhashya',
           'source': 'Setu Tila edition (setutila.in)',
           'units': units}
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # Rewrite the bhashya provenance in _sources/dv_map.json: the layer is now
    # the Setu Tila edition, so its old dvaitavedanta.in anchors are replaced
    # with Setu Tila source refs (other layers' entries are left untouched).
    if os.path.exists(DVMAP):
        dm = json.load(open(DVMAP, encoding='utf-8'))
        mp = dm.get('map', {})
        for k in [k for k in mp if k.startswith('bhashya:')]:
            del mp[k]
        for u in units:
            mp['bhashya:' + u['id']] = {'source': 'setutila.in', 'url': ST_URL}
        json.dump(dm, open(DVMAP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    from collections import Counter
    kinds = Counter(u.get('kind', 'para') for u in units)
    fn = sum(len(u.get('footnotes', [])) for u in units)
    print('wrote %d bhashya units: %s | %d footnotes; dv_map bhashya entries refreshed'
          % (len(units), dict(kinds), fn))


if __name__ == '__main__':
    main()
