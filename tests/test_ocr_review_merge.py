"""tools/ocr_review_merge.py — a reviewer's STRUCTURE reaches the library.

The bug this pins, fixed 11 Sep 2026: Sarvam Document AI is run precisely
because it keeps a page's headings, paragraphs and indentation, and
admin/ocr-review.html showed that structure faithfully — but the edit surface
was a flat textarea and the merge stored only a string. So the entire reason
for running a layout-preserving engine was discarded at the last step, and a
प्रतीक a scholar had bolded came out as plain text.

A decision may now carry `html`, and that lands in the item as
`sanskrit_html` BESIDE the plain `sanskrit_text` every existing consumer
reads — the structure is additive, so a reader that has never heard of it
cannot break.
"""

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools')
sys.path.insert(0, TOOLS)

import ocr_review_merge as orm  # noqa: E402

SARVAM = {
    "engine": "sarvam-docai", "format": "html",
    "source": {"pdf": "mbtn.pdf", "pages": [1]},
    "pages": [{"page": 1, "ok": True, "html":
               "<h2>प्रथमोऽध्यायः</h2><p>नारायणं नमस्कृत्य ।</p>"
               "<blockquote>इति प्रथमोऽध्यायः ।</blockquote>"}],
}


def args_for(staged_path, target):
    return SimpleNamespace(
        staged=staged_path, target=target, schema='grantha_tika_text',
        title='MBTN', title_devanagari='', author='', id_prefix='',
        mode='write', include_undecided=False,
        decisions=os.path.join(os.path.dirname(staged_path), 'review', 'd.json'),
        dry_run=False)


class StructuredMerge(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.staged_path = os.path.join(self.tmp.name, 'sarvam_pages1-1.json')
        with open(self.staged_path, 'w', encoding='utf-8') as fh:
            json.dump(SARVAM, fh, ensure_ascii=False)
        self.units = orm.units_of(SARVAM)[1]

    def tearDown(self):
        self.tmp.cleanup()

    def _items(self, decisions):
        target = os.path.join(self.tmp.name, 'out', 'data.json')
        orm.build_layer(SARVAM, decisions, args_for(self.staged_path, target))
        with open(target, encoding='utf-8') as fh:
            return json.load(fh)['items']

    def test_an_edited_structure_reaches_the_layer(self):
        uid = self.units[0]['id']
        edited = '<h2>प्रथमोऽध्यायः</h2><p><b>नारायणं</b> नमस्कृत्य ।</p>'
        items = self._items({uid: {'decision': 'edit', 'text': 'नारायणं नमस्कृत्य ।',
                                   'html': edited, 'by': 'SVG', 'at': '2026-09-11'}})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['sanskrit_html'], edited)
        self.assertIn('<b>', items[0]['sanskrit_html'], 'the bolded प्रतीक must survive')
        self.assertIn('<h2>', items[0]['sanskrit_html'], 'the heading must survive')

    def test_the_plain_text_is_still_written_beside_it(self):
        """Additive, never a replacement — every existing reader keeps working."""
        uid = self.units[0]['id']
        items = self._items({uid: {'decision': 'edit', 'text': 'नारायणं नमस्कृत्य ।',
                                   'html': '<p><b>नारायणं</b> नमस्कृत्य ।</p>'}})
        self.assertEqual(items[0]['sanskrit_text'], 'नारायणं नमस्कृत्य ।')
        self.assertNotIn('<', items[0]['sanskrit_text'], 'the text field stays plain')

    def test_an_accepted_unit_keeps_the_engines_own_structure(self):
        """Accepting without editing must not throw the layout away either."""
        uid = self.units[0]['id']
        items = self._items({uid: {'decision': 'accept', 'by': 'SVG'}})
        self.assertIn('sanskrit_html', items[0])
        self.assertIn('<h2>', items[0]['sanskrit_html'])

    def test_a_rejected_unit_reaches_the_layer_at_all(self):
        uid = self.units[0]['id']
        self.assertEqual(self._items({uid: {'decision': 'reject'}}), [])

    def test_a_plain_vision_unit_carries_no_html_key(self):
        """Vision returns flat text; the item must not grow an empty field."""
        staged = {"engine": "vision", "pages": [{"page": 1, "text": "नारायणं नमस्कृत्य ।"}]}
        path = os.path.join(self.tmp.name, 'vision_pages1-1.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(staged, fh, ensure_ascii=False)
        uid = orm.units_of(staged)[1][0]['id']
        target = os.path.join(self.tmp.name, 'v', 'data.json')
        orm.build_layer(staged, {uid: {'decision': 'accept'}}, args_for(path, target))
        with open(target, encoding='utf-8') as fh:
            items = json.load(fh)['items']
        self.assertNotIn('sanskrit_html', items[0])


class ReviewerContract(unittest.TestCase):
    """Facts admin/ocr-review.html must keep true for the above to be reachable."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'admin', 'ocr-review.html')
        with open(path, encoding='utf-8') as fh:
            cls.html = fh.read()

    def test_the_rendered_layout_is_the_edit_surface(self):
        self.assertIn('contenteditable="true"', self.html)

    def test_a_decision_carries_the_edited_html(self):
        self.assertIn('rec.html = editedHtml', self.html)

    def test_bold_is_offered_because_that_is_how_a_pratika_is_marked(self):
        self.assertIn('data-cmd="bold"', self.html)

    def test_structure_only_changes_still_record_as_an_edit(self):
        # Accepting a unit whose layout was changed must not be logged as a
        # bare "accept" — the provenance would claim the engine produced it.
        self.assertIn('htmlChanged', self.html)

    def test_the_self_test_hook_is_gated_on_a_query_parameter(self):
        self.assertIn('selftest=1', self.html)


if __name__ == '__main__':
    unittest.main()


class BlockSplitting(unittest.TestCase):
    """split_html_blocks — one reviewable unit per element, markup intact."""

    def test_each_top_level_element_becomes_its_own_block(self):
        blocks = orm.split_html_blocks(
            '<h2>अध्यायः</h2><p>पद्यम् ।</p><blockquote>इति ।</blockquote>')
        self.assertEqual(len(blocks), 3)
        self.assertTrue(blocks[0][0].startswith('<h2'))
        self.assertTrue(blocks[2][0].startswith('<blockquote'))

    def test_a_block_keeps_its_own_markup_and_its_text(self):
        (frag, text), = orm.split_html_blocks('<p>क <b>ख</b> ग</p>')
        self.assertIn('<b>', frag)
        self.assertEqual(text, 'क ख ग')

    def test_nested_elements_do_not_split_their_parent(self):
        blocks = orm.split_html_blocks('<div><p>क</p><p>ख</p></div>')
        self.assertEqual(len(blocks), 1, 'the outer div is one block')
        self.assertIn('<p>क</p>', blocks[0][0])

    def test_a_self_closing_tag_does_not_unbalance_the_depth(self):
        # <br> inside a verse is the commonest tag in this corpus; if it were
        # counted as an open element every following block would be swallowed.
        blocks = orm.split_html_blocks('<p>क<br>ख</p><p>ग</p>')
        self.assertEqual(len(blocks), 2)

    def test_blocks_with_no_text_are_dropped(self):
        blocks = orm.split_html_blocks('<p></p><p>क</p><div>  </div>')
        self.assertEqual(len(blocks), 1)

    def test_empty_input_is_no_blocks_not_an_error(self):
        self.assertEqual(orm.split_html_blocks(''), [])
        self.assertEqual(orm.split_html_blocks(None), [])

    def test_the_unit_model_now_carries_html(self):
        kind, units = orm.units_of(SARVAM)
        self.assertEqual(kind, 'layer')
        self.assertEqual(len(units), 3, 'heading, verse and colophon are three units')
        self.assertTrue(all('html' in u for u in units))
        self.assertIn('<h2>', units[0]['html'])
