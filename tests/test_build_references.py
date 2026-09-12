"""tools/build_references.py — the storage layer for context-aware citations.

What is being pinned here is the coordinate contract. The build step stores
every reference twice: character offsets into the ORIGINAL Devanagari (so the
source location is never lost) and a whitespace-token range (so the mark
survives transliteration into Kannada, Telugu or IAST, where character offsets
do not). If those two ever disagree the reader marks the wrong words, silently.
"""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

import build_references as br  # noqa: E402


class TokenCoordinates(unittest.TestCase):

    def test_token_starts_are_the_runs_render_js_wraps(self):
        # render.js's dgeWrapWordsForTap wraps /(\S+)/g. Same runs, same order.
        text = 'कान्ताय   रमणीयाय ।\nकल्याणाः शोभनाः'
        starts, ends = br.token_starts(text)
        toks = [text[s:e] for s, e in zip(starts, ends)]
        self.assertEqual(toks, ['कान्ताय', 'रमणीयाय', '।', 'कल्याणाः', 'शोभनाः'])

    def test_range_covers_whole_tokens_a_citation_only_partly_fills(self):
        # दीप्ताविति is one written word carrying the artha's end and an इति.
        text = 'ज्वल दीप्ताविति लट्'
        starts, ends = br.token_starts(text)
        start = text.index('ज्वल')
        end = text.index('दीप्ता') + len('दीप्ता')   # stops mid-token
        self.assertEqual(br.token_range(starts, ends, start, end), [0, 2])

    def test_range_is_none_when_the_span_touches_no_token(self):
        text = 'अ   ब'
        starts, ends = br.token_starts(text)
        self.assertIsNone(br.token_range(starts, ends, 1, 3))   # the gap only

    def test_range_is_half_open_like_python_slicing(self):
        text = 'क ख ग घ'
        starts, ends = br.token_starts(text)
        w = br.token_range(starts, ends, text.index('ख'), text.index('ग') + 1)
        self.assertEqual(w, [1, 3])


class UnitExtraction(unittest.TestCase):

    def test_plain_string_commentaries_are_yielded(self):
        doc = {'shlokas': {'1': {'sa': 'x', 'commentaries': {'a': 'क', 'b': 'ख'}}}}
        self.assertEqual(sorted(br.commentary_units(doc)),
                         [('1', 'a', 'क'), ('1', 'b', 'ख')])

    def test_gold_standard_commentaries_are_skipped(self):
        # A gold_v2_2 commentary is a dict carrying its own verified mapping;
        # render.js declines to word-wrap it and this declines to mark it.
        doc = {'shlokas': {'1': {'commentaries': {
            'g': {'format': 'gold_v2_2', 'commentary_markdown': 'क'},
            'p': 'ख'}}}}
        self.assertEqual(list(br.commentary_units(doc)), [('1', 'p', 'ख')])

    def test_empty_and_whitespace_commentaries_are_skipped(self):
        doc = {'shlokas': {'1': {'commentaries': {'a': '', 'b': '   '}}}}
        self.assertEqual(list(br.commentary_units(doc)), [])

    def test_a_grantha_with_no_shloka_map_yields_nothing(self):
        self.assertEqual(list(br.commentary_units({'items': [{'id': 1}]})), [])


class BuiltOutput(unittest.TestCase):
    """The files that are actually committed."""

    @classmethod
    def setUpClass(cls):
        cls.out = br.OUT
        cls.files = sorted(cls.out.glob('*.json')) if cls.out.exists() else []

    def test_the_index_was_built(self):
        self.assertTrue(self.files, 'run python3 tools/build_references.py')

    def test_every_reference_spans_the_characters_it_claims(self):
        """The stored surface must BE the text at the stored offsets.

        This is the directive's "preserve source text" requirement, checked
        against the real data rather than asserted: a drifted offset would put
        the reader's mark on a neighbouring word with nothing to notice it."""
        checked = 0
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8'))
            doc = json.loads((br.DATA / data['slug'] / 'data.json').read_text(encoding='utf-8'))
            texts = {(u, c): t for u, c, t in br.commentary_units(doc)}
            starts_cache = {}
            for uid, per_key in data['units'].items():
                for ckey, refs in per_key.items():
                    text = texts[(uid, ckey)]
                    if (uid, ckey) not in starts_cache:
                        starts_cache[(uid, ckey)] = br.token_starts(text)
                    starts, ends = starts_cache[(uid, ckey)]
                    for ref in refs:
                        s, e = ref['s']
                        self.assertEqual(text[s:e], ref['x'],
                                         '%s %s/%s' % (f.name, uid, ckey))
                        # and the token range must contain that span
                        a, b = ref['w']
                        self.assertLessEqual(starts[a], s)
                        self.assertGreaterEqual(ends[b - 1], e)
                        checked += 1
        self.assertGreater(checked, 500, 'suspiciously few references to check')

    def test_every_reference_carries_the_metadata_the_ui_renders(self):
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8'))
            for per_key in data['units'].values():
                for refs in per_key.values():
                    for ref in refs:
                        self.assertIn(ref['t'], ('dhatu', 'kosha', 'sutra'))
                        self.assertIn(ref['c'], ('high', 'medium'))
                        self.assertTrue(ref['i'], 'a link needs an authoritative id')
                        self.assertTrue(ref['r'], 'a link needs a recorded reason')

    def test_no_two_references_in_one_passage_overlap(self):
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8'))
            for uid, per_key in data['units'].items():
                for ckey, refs in per_key.items():
                    last = -1
                    for ref in sorted(refs, key=lambda r: r['s'][0]):
                        self.assertGreaterEqual(ref['s'][0], last,
                                                '%s %s/%s' % (f.name, uid, ckey))
                        last = ref['s'][1]

    def test_dhatu_ids_exist_in_the_dhatupatha(self):
        ids = {d['id'] for d in json.loads(br.DHATUPATHA.read_text(encoding='utf-8'))['items']}
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8'))
            for per_key in data['units'].values():
                for refs in per_key.values():
                    for ref in refs:
                        if ref['t'] == 'dhatu':
                            self.assertIn(ref['i'], ids)

    def test_sutra_ids_exist_in_the_sutrapatha(self):
        ids = {s['id'] for s in json.loads(br.SUTRAPATHA.read_text(encoding='utf-8'))['items']}
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8'))
            for per_key in data['units'].values():
                for refs in per_key.values():
                    for ref in refs:
                        if ref['t'] == 'sutra':
                            self.assertIn(ref['i'], ids)

    def test_kosha_ids_are_registry_slugs(self):
        reg = json.loads(br.REGISTRY.read_text(encoding='utf-8'))
        slugs = set(reg['names'].values())
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8'))
            for per_key in data['units'].values():
                for refs in per_key.values():
                    for ref in refs:
                        if ref['t'] == 'kosha':
                            self.assertIn(ref['i'], slugs)

    def test_no_vyakarana_layer_was_indexed(self):
        # Quoting sūtras is that corpus's whole job; a mark there says nothing.
        for f in self.files:
            slug = json.loads(f.read_text(encoding='utf-8'))['slug']
            self.assertFalse(slug.startswith('vedanga/vyakarana/'), f.name)


class ReaderContract(unittest.TestCase):
    """Facts js/reference-links.js depends on, checked in its source."""

    @classmethod
    def setUpClass(cls):
        cls.js = (Path(__file__).resolve().parent.parent
                  / 'js/reference-links.js').read_text(encoding='utf-8')

    def test_it_renders_from_the_token_range_not_char_offsets(self):
        # Char offsets do not survive transliteration; token counts do.
        self.assertIn("ref.w", self.js)

    def test_it_still_puts_the_source_span_in_the_dom(self):
        self.assertIn("data-ref-span", self.js)

    def test_it_carries_the_metadata_the_directive_asks_for(self):
        for attr in ('data-ref-type', 'data-ref-id', 'data-ref-confidence'):
            self.assertIn(attr, self.js)

    def test_a_kosha_the_library_does_not_hold_is_not_linked(self):
        # medini / dhananjaya / vishvakosha / halayudha are named in
        # commentaries but are not lexicons this library carries.
        reg = json.loads(br.REGISTRY.read_text(encoding='utf-8'))
        for slug in reg['unresolved']:
            if slug.startswith('_'):
                continue
            self.assertNotIn(slug + ':', self.js,
                             '%s has no page to open' % slug)

    def test_it_honours_a_feature_flag(self):
        self.assertIn('showReferenceLinks', self.js)


if __name__ == '__main__':
    unittest.main()
