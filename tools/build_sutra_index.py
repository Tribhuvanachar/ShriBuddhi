#!/usr/bin/env python3
"""
build_sutra_index.py — the lookup index behind sutra intellisense.

The full sutrapatha is 4 MB. A reading page must not load that on the chance
that a commentary mentions a rule, so this splits it in two:

  _index/sutra_index.json        id, mula text, a normalised key and the
                                 topic, for all 3,962 sutras. Parallel arrays
                                 rather than objects — same data, a third of
                                 the bytes, and the client rebuilds the maps
                                 in one pass. Loaded once, lazily, the first
                                 time a page turns out to mention a sutra.

  _index/sutra_detail_<N>.json   padaccheda, anvaya, anuvritti, type and the
                                 English gloss, one file per adhyaya. Fetched
                                 only when a popover actually opens, so
                                 reading Adhyaya 1 never downloads the other
                                 seven.

The normalised key is what makes identification by NAME work. "namah svasti
svaha", नमः स्वस्ति स्वाहा and ನಮಃ ಸ್ವಸ್ತಿ ಸ್ವಾಹಾ all fold to the same ASCII
string, so a reader who half-remembers a rule's name can still find it.

    python3 tools/build_sutra_index.py
"""

import json
import os
import re
import sys
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'dge/data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json')
OUT = os.path.join(REPO, 'dge/data/vedanga/vyakarana/ashtadhyayi/_index')

# Devanagari -> a rough ASCII skeleton. Not a transliteration scheme: vowel
# length, aspiration, retroflexion and anusvara are all deliberately collapsed,
# because the point is to match what someone half-remembers. "namah svasti
# svaha" should find नमःस्वस्तिस्वाहा even though neither is spelled the way
# the other would be transliterated.
DEVA_VOWEL = {
    'अ': 'a', 'आ': 'a', 'इ': 'i', 'ई': 'i', 'उ': 'u', 'ऊ': 'u',
    'ऋ': 'r', 'ॠ': 'r', 'ऌ': 'l', 'ॡ': 'l',
    'ए': 'e', 'ऐ': 'e', 'ओ': 'o', 'औ': 'o',
}
DEVA_CONS = {
    'क': 'k', 'ख': 'k', 'ग': 'g', 'घ': 'g', 'ङ': 'n',
    'च': 'c', 'छ': 'c', 'ज': 'j', 'झ': 'j', 'ञ': 'n',
    'ट': 't', 'ठ': 't', 'ड': 'd', 'ढ': 'd', 'ण': 'n',
    'त': 't', 'थ': 't', 'द': 'd', 'ध': 'd', 'न': 'n',
    'प': 'p', 'फ': 'p', 'ब': 'b', 'भ': 'b', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
    'श': 's', 'ष': 's', 'स': 's', 'ह': 'h', 'ळ': 'l',
}
DEVA_MATRA = {
    'ा': 'a', 'ि': 'i', 'ी': 'i', 'ु': 'u', 'ू': 'u', 'ृ': 'r', 'ॄ': 'r',
    'ॢ': 'l', 'ॣ': 'l', 'े': 'e', 'ै': 'e', 'ो': 'o', 'ौ': 'o',
}
VIRAMA = '्'

LATIN = str.maketrans({
    'ā': 'a', 'ī': 'i', 'ū': 'u', 'ṛ': 'r', 'ṝ': 'r', 'ḷ': 'l', 'ḹ': 'l',
    'ṅ': 'n', 'ñ': 'n', 'ṭ': 't', 'ḍ': 'd', 'ṇ': 'n', 'ś': 's', 'ṣ': 's',
    'ṃ': 'm', 'ṁ': 'm', 'ḥ': 'h', 'ḻ': 'l', 'ĕ': 'e', 'ŏ': 'o',
})


# The Indic blocks are laid out in parallel with Devanagari for the letters
# that matter here, so a fixed offset converts them. Crude next to a real
# transliterator, and exactly right for a lookup that is about to throw away
# vowel length and aspiration anyway. Tamil is left out: its alphabet does not
# distinguish voicing or aspiration, so the offset does not hold.
INDIC_BLOCKS = [
    (0x0C80, 0x0CFF, 0x0380),   # Kannada
    (0x0C00, 0x0C7F, 0x0300),   # Telugu
    (0x0D00, 0x0D7F, 0x0400),   # Malayalam
    (0x0980, 0x09FF, 0x0080),   # Bengali
    (0x0A80, 0x0AFF, 0x0180),   # Gujarati
]


def to_devanagari(s):
    out = []
    for ch in s:
        cp = ord(ch)
        for lo, hi, off in INDIC_BLOCKS:
            if lo <= cp <= hi:
                ch = chr(cp - off)
                break
        out.append(ch)
    return ''.join(out)


def fold(text):
    """The same skeleton for the same rule, whatever script it arrived in.

    A Devanagari consonant carries an inherent 'a' unless a vowel sign or a
    virama says otherwise — without that, नमः folds to "nmh" and can never
    meet "namah" coming the other way, which is exactly the lookup this is
    for. Aspiration, vowel length, retroflexion and sibilant class are all
    collapsed on purpose: a reader half-remembering a rule's name will not
    have got those right either.
    """
    if not text:
        return ''
    s = to_devanagari(unicodedata.normalize('NFC', text))
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in DEVA_CONS:
            out.append(DEVA_CONS[ch])
            nxt = s[i + 1] if i + 1 < len(s) else ''
            if nxt == VIRAMA:
                i += 2
                continue
            if nxt in DEVA_MATRA:
                out.append(DEVA_MATRA[nxt])
                i += 2
                continue
            out.append('a')               # the inherent vowel
            i += 1
            continue
        if ch in DEVA_VOWEL:
            out.append(DEVA_VOWEL[ch])
        elif ch == 'ं' or ch == 'ँ':
            out.append('m')
        elif ch == 'ः':
            out.append('h')
        elif 'ऀ' <= ch <= 'ॿ':
            pass                          # nukta, avagraha, digits, other marks
        else:
            out.append(ch.lower())
        i += 1

    t = ''.join(out).translate(LATIN)
    # Latin diphthongs, so "vrddhiradaic" and वृद्धिरादैच् (…ादैच् -> …adec)
    # agree. Done after the table above so ai/au survive to be seen here.
    t = t.replace('ai', 'e').replace('au', 'o')
    t = re.sub(r'[^a-z]', '', t)
    # Aspiration written as a digraph. The Devanagari side already lost it —
    # ध and द both fold to 'd' — so "vrddhi" has to lose it too, or the two
    # spellings of the same word can never meet. Only after a consonant: the
    # h of ह, and the h standing in for visarga, are not aspiration.
    t = re.sub(r'(?<=[kgcjtdpbs])h', '', t)
    # A doubled consonant in one spelling and a single one in another are the
    # same rule to a reader; collapse runs so they compare equal.
    return re.sub(r'(.)\1+', r'\1', t)


def skeleton(folded):
    """The folded key with its vowels removed.

    The fallback when the vowels themselves disagree — "vriddhi" against
    वृद्धि, where one spelling inserts an i the other does not have. Consonants
    are what survive a half-remembered name; matching on them alone finds the
    rule where the full key misses.
    """
    return re.sub(r'[aeiou]', '', folded)


def main():
    if not os.path.exists(SRC):
        print(f'sutrapatha not found at {SRC}', file=sys.stderr)
        return 1
    with open(SRC, encoding='utf-8') as fh:
        items = json.load(fh)['items']

    os.makedirs(OUT, exist_ok=True)

    ids, mula, keys, topics = [], [], [], []
    details = {}
    for it in items:
        sid = it.get('id') or it.get('reference')
        if not sid:
            continue
        text = it.get('sanskrit_text', '')
        ids.append(sid)
        mula.append(text)
        keys.append(fold(text))
        st = it.get('sutra_type') or {}
        topics.append(st.get('topic', ''))

        adhyaya = sid.split('.')[0]
        d = {}
        if it.get('padaccheda'):  d['p'] = it['padaccheda']
        if it.get('anvaya'):      d['a'] = it['anvaya']
        if it.get('anuvritti'):   d['v'] = [[x.get('word', ''), x.get('from', '')]
                                            for x in it['anuvritti']]
        if it.get('english'):     d['e'] = it['english']
        if it.get('adhikara'):    d['k'] = it['adhikara']
        if st.get('label'):       d['t'] = st['label']
        if st.get('label_dev'):   d['td'] = st['label_dev']
        if d:
            details.setdefault(adhyaya, {})[sid] = d

    index = {
        '_readme': 'Lookup index for sutra intellisense. Built by '
                   'tools/build_sutra_index.py from the sutrapatha; do not hand-edit. '
                   'Parallel arrays: ids[i], mula[i], keys[i], topics[i] describe one sutra. '
                   'keys[i] is a script-agnostic ASCII skeleton for name matching.',
        'v': 1,
        'count': len(ids),
        'ids': ids, 'mula': mula, 'keys': keys, 'topics': topics,
    }
    p = os.path.join(OUT, 'sutra_index.json')
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(',', ':'))
    print(f'  {os.path.relpath(p, REPO)}  {len(ids)} sutras, '
          f'{os.path.getsize(p) / 1024:.0f} KB')

    for adhyaya in sorted(details):
        p = os.path.join(OUT, f'sutra_detail_{adhyaya}.json')
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(details[adhyaya], fh, ensure_ascii=False, separators=(',', ':'))
        print(f'  {os.path.relpath(p, REPO)}  {len(details[adhyaya])} sutras, '
              f'{os.path.getsize(p) / 1024:.0f} KB')

    # A key that two different sutras share would make name lookup ambiguous.
    seen, dupes = {}, 0
    for i, k in enumerate(keys):
        if k in seen:
            dupes += 1
        seen.setdefault(k, i)
    print(f'\n  {len(set(keys))} distinct keys, {dupes} collisions '
          f'(shown to the reader as a list when one is hit)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
