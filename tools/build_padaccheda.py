#!/usr/bin/env python3
"""
build_padaccheda.py — run the offline segmenter (tools/padaccheda.py) over the
corpus and store what it finds, so a reader pays nothing at read time.

TWO TIERS, AND THEY ARE NOT THE SAME THING.

  Tier A  a padaccheda a human editor made, already in the text's own JSON
          (the Aṣṭādhyāyī sūtrapāṭha ships 3,941 of these). Authoritative.
          This tool copies it through untouched and never second-guesses it.

  Tier B  this repository's own segmenter, for the verses nobody has split by
          hand. Useful, and NOT authoritative — see the numbers below.

WHAT TIER B IS WORTH, MEASURED. Scored against those 3,941 editor padacchedas,
counting the editor's own compound hyphens as boundaries so the comparison is
fair, and offering only splits that clear the confidence gate:

    offered 284 of 1,230 · exact 40% · wrong 59% · declined the rest

That is the honest figure and it is why nothing here is written into a text's
`padaccheda` field, which means "an editor said so". It goes to a sidecar,
labelled `source: "engine"`, and the reader shows it as analysis rather than
as the text. The Aṣṭādhyāyī is also the hardest possible test set — it is
Pāṇini's metalanguage, full of pratyāhāras (अच्, हल्, ङः) that are not words
in any lexicon — so ordinary verse does better; how much better is not known,
because there is no ordinary-verse ground truth in this repository to measure
against. Saying "probably better" and leaving it unmeasured is the honest
position, not a claim of accuracy.

    python3 tools/build_padaccheda.py --paths kavya_alankara,stotra
    python3 tools/build_padaccheda.py --evaluate     (re-run the scoring above)

Output: dge/data/_padaccheda/<slug>.json
        {unit_id: [[piece, piece, …], …]} — one list per written token that
        was split, in the order the tokens appear; a token with no analysis is
        absent rather than echoed.
"""

import argparse
import collections
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from padaccheda import Segmenter, strip_punct, is_devanagari   # noqa: E402
from sanskrit_text import protected_spans                     # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'dge', 'data')
OUT_DIR = os.path.join(DATA, '_padaccheda')
HIGHLIGHT = os.path.join(DATA, '_highlight')
MORPH = os.path.join(DATA, '_morph')

DEVA_WORD = re.compile(r'[ऀ-ॣ०-ॿ]+')
TRAIL = re.compile(r'[।॥०-९\s]+$')


def load_morphology():
    """(stems, avyaya, inflected, verbs) from _morph's own records.

    A samāsa's non-final members are prātipadikas — bare stems with no case
    ending — while two words joined by sandhi are each complete. That is the
    whole difference between a hyphen and a plus, and _morph's subanta records
    name the lemma each form came from, so it can be read off the data instead
    of guessed from the shape of the word."""
    stems, avyaya, inflected, verbs = set(), set(), set(), set()
    for path in glob.glob(os.path.join(MORPH, '*.json')):
        if os.path.basename(path) == 'manifest.json':
            continue
        with open(path, encoding='utf-8') as fh:
            shard = json.load(fh)
        for form, records in shard.items():
            if not isinstance(records, list):
                continue
            for rec in records:
                if not isinstance(rec, list) or not rec:
                    continue
                if rec[0] == 's':
                    if len(rec) > 1:
                        stems.add(rec[1])
                    if len(rec) >= 4 and rec[3]:
                        inflected.add(form)
                elif rec[0] == 'a':
                    avyaya.add(form)
                elif rec[0] == 't':
                    inflected.add(form)
                    verbs.add(form)
    return stems, avyaya, inflected, verbs


def load_vocab():
    """Every word this library can recognise: कोश headwords and verb forms from
    the highlight index, plus the declined nominal forms only _morph carries.

    _morph matters more here than anywhere else. Without it रामस्यैव has no
    analysis at all — रामस्य is a declension, and declensions are exactly what
    the other indexes do not hold."""
    vocab = set()
    for path in glob.glob(os.path.join(HIGHLIGHT, '*.json')):
        if os.path.basename(path) == 'manifest.json':
            continue
        with open(path, encoding='utf-8') as fh:
            raw = json.load(fh)
        for key in ('k', 'd', 'b'):
            if raw.get(key):
                vocab.update(raw[key].split('\n'))
    n_index = len(vocab)
    for path in glob.glob(os.path.join(MORPH, '*.json')):
        with open(path, encoding='utf-8') as fh:
            for word in json.load(fh):
                if not word.startswith('_'):
                    vocab.add(word)
    return vocab, n_index


def unit_texts(doc):
    """(unit_id, devanagari text) for every unit a grantha carries."""
    shlokas = doc.get('shlokas')
    if isinstance(shlokas, dict):
        for key, val in shlokas.items():
            if isinstance(val, dict):
                text = val.get('sa') or val.get('sanskrit_text') or ''
                if isinstance(text, str) and text:
                    yield str(key), text
    for item in doc.get('items') or []:
        if not isinstance(item, dict):
            continue
        uid = str(item.get('id') or item.get('reference') or '')
        base = item.get('sanskrit_text') or item.get('samhita_patha') or item.get('sa') or ''
        if isinstance(base, str) and base:
            yield uid, base
        for sub in item.get('shlokas') or []:
            if not isinstance(sub, dict):
                continue
            sid = uid + ('#' + str(sub.get('number')) if sub.get('number') is not None else '')
            text = sub.get('sanskrit_text') or sub.get('sa') or ''
            if isinstance(text, str) and text:
                yield sid, text


def corpus_frequency(paths=None):
    """How often the corpus actually writes each word.

    This is what stops the search preferring a chain of rare-but-real words
    over the obvious reading: नवद्युनाथप्रतिमप्रभाय parses into six lexicon
    entries and into nothing at all, and frequency is what makes it choose
    nothing."""
    freq = collections.Counter()
    for path in iter_data_files(paths):
        try:
            with open(path, encoding='utf-8') as fh:
                doc = json.load(fh)
        except Exception:
            continue
        texts = []
        shlokas = doc.get('shlokas')
        if isinstance(shlokas, dict):
            for val in shlokas.values():
                if not isinstance(val, dict):
                    continue
                if isinstance(val.get('sa'), str):
                    texts.append(val['sa'])
                for com in (val.get('commentaries') or {}).values():
                    if isinstance(com, str):
                        texts.append(com)
        for _uid, text in unit_texts(doc):
            texts.append(text)
        for text in texts:
            for match in DEVA_WORD.finditer(text.replace('<br>', ' ')):
                word = TRAIL.sub('', match.group(0))
                if len(word) >= 2:
                    freq[word] += 1
    return freq


def iter_data_files(paths=None):
    for path in sorted(glob.glob(os.path.join(DATA, '**', 'data.json'), recursive=True)):
        if 'ocr_staging' in path:
            continue
        if paths:
            rel = os.path.relpath(path, DATA)
            if not any(rel.startswith(p) for p in paths):
                continue
        yield path


def split_text(seg, text, vigraha=False):
    """[[token, seams, piece, …], …] for the tokens that have an analysis.

    `seams` is one character per join, in order: '+' where two words were
    fused by sandhi, '-' where a compound's members were written together.
    Two different operations, and a reader should be able to tell which is
    which at a glance — नारायणाय + अखिल-कारणाय is a sandhi join whose second
    half is itself a compound."""
    out = []
    for match in DEVA_WORD.finditer(text.replace('<br>', ' ')):
        token = TRAIL.sub('', match.group(0))
        if not token or not is_devanagari(token):
            continue
        if vigraha:
            got = seg.analyse(token)
            if got:
                out.append([got['token'], ''.join(got['seams'])] + got['pieces'])
        else:
            got = seg.confident_split(token)
            if got:
                pieces = [w for w, _rule in got]
                out.append([token, '+' * (len(pieces) - 1)] + pieces)
    return out


COMMENTARY_OUT = os.path.join(DATA, '_commentary_sandhi')

#: The only right-hand pieces a commentary split is allowed to end in, unless
#: the seam is one of the unambiguous visarga rules below. Every one of these
#: is an indeclinable that cannot be anything else, so "X + इति" is a claim
#: about where the join is and not about what either side means.
COMMENTARY_CLITICS = frozenset(
    ('इति', 'अपि', 'इव', 'एव', 'च', 'वा', 'हि', 'तु', 'उत', 'चेत्',
     'एतत्', 'अयम्', 'इदम्', 'अस्ति'))

#: Seams a two-piece commentary split may stand on without a clitic. All of
#: them turn a visarga into something visibly different (गुरोः + भक्तिः is
#: written गुरोर्भक्तिः), so the seam is written in the text rather than
#: inferred. विसर्गलोपः is deliberately NOT here: आः → आ leaves nothing behind,
#: so समागतम् "splits" into समाः + गतम्, which is wrong and looks right.
COMMENTARY_SEAM_RULES = frozenset(
    ('विसर्गस्य रः', 'विसर्गः (उत्वम्)', 'श्चुत्वम्', 'ष्टुत्वम्', 'विसर्गस्य सः'))

#: A commentary word has to be commoner than a verse word before its split is
#: shown. The corpus of commentary is large and its vocabulary is ordinary
#: prose, so a rare "word" in a split is far likelier to be a bad cut than a
#: real hapax. (padaccheda.CONFIDENT_MIN_FREQ is 3; this is the same idea,
#: tightened for the place where the wrong cut costs more.)
COMMENTARY_MIN_FREQ = 8


def mula_words(shloka):
    """The verse's own written words — the pratīkas a commentary may quote.

    Gold Standard Part 0: a pratīka is a citation unit. Cutting through one
    (कान्ताय inside कान्तायेति is fine; कान्ताय itself is not ours to divide)
    destroys the very thing the commentary is pointing at, and pratika.js's
    verse↔commentary link is keyed on the written form."""
    text = (shloka.get('sa') or shloka.get('sanskrit_text') or '') if isinstance(shloka, dict) else ''
    out = set()
    for match in DEVA_WORD.finditer(text.replace('<br>', ' ')):
        token = TRAIL.sub('', match.group(0))
        if len(token) >= 2:
            out.add(token)
    return out


def reference_spans(slug):
    """{unit id: {commentary key: [(start, end), …]}} already claimed as a
    citation by tools/build_references.py.

    A sūtra quoted verbatim, a root beside its artha, a lexicon's name: those
    are the source's own words and are not ours to re-spell. दिश अतिसर्जने is
    the case that made this necessary — the segmenter reads अतिसर्जने as
    अति + सः + जने, which is nonsense, and it is nonsense sitting inside a
    correctly identified dhātu citation."""
    path = os.path.join(DATA, '_references', slug.replace('/', '__') + '.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return {}
    out = {}
    for uid, per_key in (data.get('units') or {}).items():
        for ckey, refs in per_key.items():
            out.setdefault(uid, {})[ckey] = [(r['s'][0], r['s'][1]) for r in refs]
    return out


def commentary_rows(seg, text, protected=(), pratikas=frozenset()):
    """Sandhi splits in one commentary passage — only the ones worth showing.

    Three protections and one gate, in that order. The protections are the
    Gold Standard's: a clitic phrase the commentary uses as a unit
    (इत्यर्थः, इति भावः), a span already identified as a scholarly citation,
    and a pratīka quoted from the verse are all left exactly as written. The
    gate is precision: two pieces, and either a closed-class clitic on the
    right or a visarga seam that is visible in the writing."""
    rows = []
    guarded = list(protected)
    for match in DEVA_WORD.finditer(text.replace('<br>', ' ')):
        start, end = match.start(), match.end()
        if any(start < b and a < end for a, b in guarded):
            continue
        token = TRAIL.sub('', match.group(0))
        if not token or not is_devanagari(token) or token in pratikas:
            continue
        got = seg.confident_split(token)
        if not got or len(got) != 2:
            continue
        (left, left_rule), (right, _r) = got
        if right not in COMMENTARY_CLITICS and left_rule not in COMMENTARY_SEAM_RULES:
            continue
        if seg.freq and min(seg.freq.get(left, 0), seg.freq.get(right, 0)) < COMMENTARY_MIN_FREQ:
            continue
        rows.append([token, '+', left, right])
    return rows


def build_commentary(seg, doc, slug):
    """{unit id: {commentary key: rows}} for one grantha."""
    refs = reference_spans(slug)
    shlokas = doc.get('shlokas')
    if not isinstance(shlokas, dict):
        return {}
    out = {}
    for uid, shloka in shlokas.items():
        if not isinstance(shloka, dict):
            continue
        pratikas = mula_words(shloka)
        for ckey, ctext in (shloka.get('commentaries') or {}).items():
            if not isinstance(ctext, str) or not ctext.strip():
                continue
            guarded = list(protected_spans(ctext))
            guarded += refs.get(str(uid), {}).get(ckey, [])
            rows = commentary_rows(seg, ctext, guarded, pratikas)
            if rows:
                out.setdefault(str(uid), {})[ckey] = rows
    return out


def evaluate(seg):
    """Score against the editor padacchedas the repository already ships."""
    path = os.path.join(DATA, 'vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json')
    if not os.path.exists(path):
        print('no ground-truth file to evaluate against', file=sys.stderr)
        return 1
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    exact = same = wrong = declined = 0
    for item in doc.get('items') or []:
        pc = item.get('padaccheda')
        text = item.get('sanskrit_text') or ''
        if not pc or not isinstance(pc, list) or not text:
            continue
        # The editor writes compound seams as '-' inside a piece; those are
        # boundaries too, and counting them as mismatches would score the
        # segmenter down for agreeing.
        editor = [p for x in pc for p in strip_punct(x).split('-') if p]
        if len(editor) < 2:
            continue
        tokens = [strip_punct(t) for t in text.split() if is_devanagari(t)]
        if len(tokens) != 1:
            continue
        got = seg.confident_split(tokens[0])
        if not got:
            declined += 1
            continue
        ours = [w for w, _ in got]
        if ours == editor:
            exact += 1
        elif set(ours) <= set(editor) or set(editor) <= set(ours):
            same += 1
        else:
            wrong += 1
    offered = exact + same + wrong
    print(f'ground truth: {offered + declined} single-token sutras with an editor padaccheda')
    print(f'  offered  {offered}')
    print(f'  exact    {exact} ({100 * exact / max(1, offered):.0f}% of offered)')
    print(f'  same pieces, different depth {same}')
    print(f'  wrong    {wrong} ({100 * wrong / max(1, offered):.0f}% of offered)')
    print(f'  declined {declined}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--paths', default='', help='comma-separated data/ prefixes to build (default: all)')
    ap.add_argument('--evaluate', action='store_true', help='score against the shipped editor padacchedas and stop')
    ap.add_argument('--limit', type=int, default=0, help='stop after this many granthas (for a quick look)')
    ap.add_argument('--vigraha', default='', help='comma-separated data/ prefixes to ALSO break compounds in')
    ap.add_argument('--commentary', default='', help='comma-separated data/ prefixes to ALSO split sandhi in the commentary of')
    ap.add_argument('--out', default=OUT_DIR)
    args = ap.parse_args(argv)
    paths = [p.strip() for p in args.paths.split(',') if p.strip()]
    vigraha_paths = [p.strip() for p in args.vigraha.split(',') if p.strip()]
    commentary_paths = [p.strip() for p in args.commentary.split(',') if p.strip()]

    t0 = time.time()
    vocab, n_index = load_vocab()
    stems, avyaya, inflected, verbs = load_morphology()
    print(f'{len(vocab):,} words of vocabulary '
          f'({n_index:,} from the highlight index, {len(vocab) - n_index:,} declensions from _morph)')
    print(f'{len(stems):,} stems, {len(avyaya):,} indeclinables, {len(verbs):,} verb forms')
    print('counting corpus frequencies…', flush=True)
    freq = corpus_frequency(paths)
    print(f'  {len(freq):,} distinct written words')
    seg = Segmenter(vocab, freq, stems, avyaya, inflected, verbs)

    if args.evaluate:
        return evaluate(seg)

    os.makedirs(args.out, exist_ok=True)
    files = units = splits = commentary_splits = 0
    for path in iter_data_files(paths):
        try:
            with open(path, encoding='utf-8') as fh:
                doc = json.load(fh)
        except Exception:
            continue
        slug = os.path.relpath(os.path.dirname(path), DATA)
        found = {}

        want_vigraha = bool(vigraha_paths) and any(slug.startswith(v) for v in vigraha_paths)
        for uid, text in unit_texts(doc):
            units += 1
            rows = split_text(seg, text, want_vigraha)
            if rows:
                found[uid] = rows
                splits += len(rows)
        # सन्धिच्छेदः in the commentary itself, on request. Separate file and
        # separate gate: a commentary is prose and a wrong cut there is read
        # as an assertion about the commentator's words.
        if commentary_paths and any(slug.startswith(c) for c in commentary_paths):
            crows = build_commentary(seg, doc, slug)
            if crows:
                os.makedirs(COMMENTARY_OUT, exist_ok=True)
                cname = slug.replace('/', '__') + '.json'
                with open(os.path.join(COMMENTARY_OUT, cname), 'w', encoding='utf-8') as fh:
                    json.dump({'slug': slug, 'source': 'engine',
                               'tool': 'tools/build_padaccheda.py --commentary',
                               'units': crows},
                              fh, ensure_ascii=False, separators=(',', ':'))
                commentary_splits += sum(len(r) for per in crows.values() for r in per.values())
        if not found:
            continue
        files += 1
        name = slug.replace('/', '__') + '.json'
        with open(os.path.join(args.out, name), 'w', encoding='utf-8') as fh:
            json.dump({'slug': slug, 'source': 'engine',
                       'tool': 'tools/build_padaccheda.py',
                       'vigraha': want_vigraha,
                       'units': found},
                      fh, ensure_ascii=False, separators=(',', ':'))
        if args.limit and files >= args.limit:
            break
    print(f'{files} granthas, {units:,} units, {splits:,} tokens split '
          f'in {time.time() - t0:.0f}s -> {os.path.relpath(args.out, REPO)}')
    if commentary_paths:
        print(f'{commentary_splits:,} commentary tokens split '
              f'-> {os.path.relpath(COMMENTARY_OUT, REPO)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
