"""point_search_index.py: rewrite one key, never its neighbours."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import point_search_index as point  # noqa: E402

BASE = "https://storage.googleapis.com/sarvamula/search_index/abc123def456"

CONFIG = '''
  koshaDataBase: "data/kosha",
  wordnetDataBase: "search_index/_wordnet",
  kavyaDataBase: "search_index",
  searchIndexBase: "search_index",
'''


class RewriteOnlyTheIndexBase(unittest.TestCase):
    def test_the_search_index_base_is_rewritten(self):
        out, n = point.point(CONFIG, BASE)
        self.assertEqual(n, 1)
        self.assertIn('searchIndexBase: "%s"' % BASE, out)

    def test_the_other_three_bases_are_untouched(self):
        out, _ = point.point(CONFIG, BASE)
        self.assertIn('koshaDataBase: "data/kosha"', out)
        self.assertIn('wordnetDataBase: "search_index/_wordnet"', out)
        self.assertIn('kavyaDataBase: "search_index"', out)

    def test_the_global_search_fallback_is_rewritten_too(self):
        out, n = point.point("  var CDN_INDEX = 'search_index';", BASE)
        self.assertEqual(n, 1)
        self.assertIn(BASE, out)

    def test_a_jsdelivr_pin_left_over_from_the_old_design_is_replaced(self):
        old = '  searchIndexBase: "https://cdn.jsdelivr.net/gh/X/y@' + "0" * 40 + '",'
        out, n = point.point(old, BASE)
        self.assertEqual(n, 1)
        self.assertNotIn("jsdelivr", out)

    def test_running_twice_changes_nothing_the_second_time(self):
        once, first = point.point(CONFIG, BASE)
        twice, second = point.point(once, BASE)
        self.assertEqual((first, second), (1, 0))
        self.assertEqual(once, twice)

    def test_single_quotes_survive_as_single_quotes(self):
        out, _ = point.point("searchIndexBase: 'search_index',", BASE)
        self.assertIn("searchIndexBase: '%s'," % BASE, out)


if __name__ == "__main__":
    unittest.main()
