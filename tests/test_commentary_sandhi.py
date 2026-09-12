"""Sandhi splitting inside a commentary — the gate and the three protections.

A commentary is prose, and a wrong cut in prose reads as a claim about what
the commentator wrote. The directive this implements is explicit that false
positives cost more than missed links, so what is pinned here is mostly what
the builder REFUSES to split.
"""

import json
import os
import sys
import unittest
from pathlib import Path

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools')
sys.path.insert(0, TOOLS)

import build_padaccheda as bp  # noqa: E402
from sanskrit_text import protected_spans  # noqa: E402


class _Seg(object):
    """A segmenter stub: whatever the test puts in, plus a frequency floor.

    The real Segmenter needs 375,000 words of vocabulary and a corpus
    frequency pass; what is under test here is the gate around it."""

    def __init__(self, table, freq=None):
        self.table = table
        self.freq = freq if freq is not None else {}

    def confident_split(self, token):
        return self.table.get(token)


HIGH = {w: 99 for w in
        ('कान्ताय', 'इति', 'गुरोः', 'भक्तिः', 'सन्तः', 'अपि', 'समाः', 'गतम्',
         'कुः', 'विति', 'मन्दा', 'आक्रान्ता', 'अति', 'सः', 'जने', 'ब्रह्म',
         'आदि', 'दिश', 'अतिसर्जने', 'श्रीः', 'लक्ष्मीः')}


class Gate(unittest.TestCase):

    def rows(self, text, table, **kw):
        return bp.commentary_rows(_Seg(table, HIGH), text, **kw)

    def test_a_clitic_seam_is_shown(self):
        rows = self.rows('कान्तायेति', {'कान्तायेति': [('कान्ताय', 'गुणः'), ('इति', 'सन्धिरहितम्')]})
        self.assertEqual(rows, [['कान्तायेति', '+', 'कान्ताय', 'इति']])

    def test_a_written_visarga_seam_is_shown_without_a_clitic(self):
        # गुरोः + भक्तिः is WRITTEN गुरोर्, so the join is in the text.
        rows = self.rows('गुरोर्भक्तिः',
                         {'गुरोर्भक्तिः': [('गुरोः', 'विसर्गस्य रः'), ('भक्तिः', 'सन्धिरहितम्')]})
        self.assertEqual(len(rows), 1)

    def test_visarga_lopa_is_refused(self):
        """आः → आ leaves nothing behind, so the seam is invented.

        समागतम् is सम् + आगतम्; the segmenter offers समाः + गतम्, which is
        wrong and looks right. This is the reason विसर्गलोपः is not an
        accepted seam rule."""
        rows = self.rows('समागतम्',
                         {'समागतम्': [('समाः', 'विसर्गलोपः'), ('गतम्', 'सन्धिरहितम्')]})
        self.assertEqual(rows, [])

    def test_a_savarnadirgha_seam_needs_a_clitic(self):
        # मन्दाक्रान्ता is the name of a metre, not मन्दा + आक्रान्ता.
        rows = self.rows('मन्दाक्रान्ता',
                         {'मन्दाक्रान्ता': [('मन्दा', 'सवर्णदीर्घः'), ('आक्रान्ता', 'सन्धिरहितम्')]})
        self.assertEqual(rows, [])

    def test_three_pieces_are_refused(self):
        rows = self.rows('अतिसर्जने', {'अतिसर्जने': [
            ('अति', 'सन्धिरहितम्'), ('सः', 'विसर्गस्य रः'), ('जने', 'सन्धिरहितम्')]})
        self.assertEqual(rows, [])

    def test_a_rare_piece_is_refused(self):
        # कुर्विति -> कुः + विति clears every structural rule and is nonsense.
        # The frequency floor is what stops it.
        freq = dict(HIGH); freq['विति'] = 1
        rows = bp.commentary_rows(
            _Seg({'कुर्विति': [('कुः', 'विसर्गस्य रः'), ('विति', 'सन्धिरहितम्')]}, freq),
            'कुर्विति')
        self.assertEqual(rows, [])

    def test_a_token_with_no_confident_split_is_absent_not_echoed(self):
        self.assertEqual(self.rows('नारायणाय', {}), [])


class Protections(unittest.TestCase):

    def test_a_protected_phrase_is_left_alone(self):
        """इत्यर्थः is punctuation the commentary uses whole."""
        text = 'कृतानीत्यर्थः'
        table = {'कृतानीत्यर्थः': [('कृतानि', 'सन्धिरहितम्'), ('इति', 'सन्धिरहितम्')]}
        spans = protected_spans(text)
        self.assertTrue(spans, 'इत्यर्थः should be a protected span')
        self.assertEqual(bp.commentary_rows(_Seg(table, HIGH), text, protected=spans), [])

    def test_a_citation_span_is_left_alone(self):
        """दिश अतिसर्जने is a root quoted with its own artha."""
        text = 'दिश अतिसर्जने लिट्'
        table = {'अतिसर्जने': [('अति', 'सन्धिरहितम्'), ('सर्जने', 'सन्धिरहितम्')]}
        span = [(text.index('दिश'), text.index('अतिसर्जने') + len('अतिसर्जने'))]
        self.assertEqual(bp.commentary_rows(_Seg(table, HIGH), text, protected=span), [])

    def test_a_pratika_is_not_cut_through(self):
        """A word quoted verbatim from the verse is a citation unit.

        कान्ताय inside कान्तायेति may be separated from its इति; कान्ताय
        standing alone is not ours to divide."""
        table = {'कान्ताय': [('कान्त', 'सन्धिरहितम्'), ('आय', 'सन्धिरहितम्')],
                 'कान्तायेति': [('कान्ताय', 'गुणः'), ('इति', 'सन्धिरहितम्')]}
        freq = dict(HIGH); freq.update({'कान्त': 99, 'आय': 99})
        rows = bp.commentary_rows(_Seg(table, freq), 'कान्ताय कान्तायेति',
                                  pratikas={'कान्ताय'})
        self.assertEqual([r[0] for r in rows], ['कान्तायेति'])

    def test_mula_words_are_read_from_the_verse(self):
        got = bp.mula_words({'sa': 'कान्ताय कल्याणगुणैकधाम्ने ।। १ ।।'})
        self.assertIn('कान्ताय', got)
        self.assertIn('कल्याणगुणैकधाम्ने', got)
        self.assertNotIn('।।', got)


class BuiltOutput(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        out = Path(bp.COMMENTARY_OUT)
        cls.files = sorted(out.glob('*.json')) if out.exists() else []

    def test_the_index_was_built_for_sumadhva_vijaya(self):
        names = {f.name for f in self.files}
        self.assertIn('kavya_alankara__sumadhva_vijaya__sarga_1.json', names,
                      'run tools/build_padaccheda.py --commentary DvaitaVedanta/Itara/Kavya/sumadhva_vijaya')

    def test_every_row_is_a_two_piece_split_of_its_own_token(self):
        rows = 0
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8'))
            for per_key in data['units'].values():
                for lst in per_key.values():
                    for row in lst:
                        self.assertEqual(len(row), 4, row)
                        self.assertEqual(row[1], '+')
                        rows += 1
        self.assertGreater(rows, 100)

    def test_no_row_splits_a_protected_phrase(self):
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8'))
            doc = json.loads((Path(bp.DATA) / data['slug'] / 'data.json').read_text(encoding='utf-8'))
            for uid, per_key in data['units'].items():
                for ckey, lst in per_key.items():
                    text = doc['shlokas'][uid]['commentaries'][ckey]
                    guarded = protected_spans(text)
                    if not guarded:
                        continue
                    hot = {text[a:b] for a, b in guarded}
                    for row in lst:
                        for phrase in hot:
                            self.assertNotIn(phrase, row[0],
                                             '%s cut through %s' % (row[0], phrase))

    def test_every_right_hand_piece_is_a_clitic_or_the_seam_is_a_visarga(self):
        """The gate, re-checked against what actually shipped."""
        loose = []
        for f in self.files:
            data = json.loads(f.read_text(encoding='utf-8'))
            for per_key in data['units'].values():
                for lst in per_key.values():
                    for row in lst:
                        if row[3] not in bp.COMMENTARY_CLITICS and not row[2].endswith('ः'):
                            loose.append(row)
        self.assertEqual(loose, [], 'rows outside the gate')


class ReaderContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.js = (Path(__file__).resolve().parent.parent
                  / 'dge/js/commentary-sandhi.js').read_text(encoding='utf-8')

    def test_it_matches_by_word_not_by_offset(self):
        # The commentary may be showing in Kannada or IAST by then.
        self.assertIn('dgeToDevanagariWord', self.js)

    def test_it_yields_to_the_louder_marks(self):
        self.assertIn("dge-ref", self.js)
        self.assertIn("dge-pratika", self.js)

    def test_it_honours_a_feature_flag(self):
        self.assertIn('showCommentarySandhi', self.js)

    def test_a_tap_says_what_a_tooltip_would(self):
        # A title attribute is unreachable on a phone.
        self.assertIn('showToast', self.js)


if __name__ == '__main__':
    unittest.main()
