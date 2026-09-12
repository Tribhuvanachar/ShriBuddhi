"""js/vyakarana-runtime.js — peeling an upasarga off a written verb.

The Dhatupatha stores bare roots, so a prefixed verb can never be found by a
direct index lookup however complete the index is: गम् is indexed, समागच्छति
is not. These pin the junction-sandhi inversions that recover the root, and
the recursion that handles a verb carrying two prefixes.
"""

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "js/vyakarana-runtime.js"

# The module fetches on demand; the harness answers those fetches from a small
# fixed set of verb forms rather than the real 205k-form index.
HARNESS = """
const FORMS = %s;
global.window = {};
global.fetch = (url) => {
  if (url.indexOf('formindex/') >= 0) {
    const cp = url.split('formindex/')[1].split('.json')[0];
    const shard = {};
    for (const f of FORMS) {
      if (f.codePointAt(0).toString(16).toLowerCase().padStart(4,'0') === cp) {
        shard[f] = [{c: '01.1131', k: 'Lat.00'}];
      }
    }
    return Promise.resolve({ok: true, json: () => Promise.resolve(shard)});
  }
  return Promise.resolve({ok: false});
};
require(%s);
"""


def peel(word, forms, depth=None):
    call = ("window.dgePeelUpasarga(%s%s)"
            % (json.dumps(word), "" if depth is None else ", %d" % depth))
    script = (HARNESS % (json.dumps(forms), json.dumps(str(JS)))) + """
%s.then(rows => console.log(JSON.stringify(
  rows.map(r => ({u: r.upasarga, rest: r.rest, rule: r.rule, chain: r.chain.length})))));
""" % call
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


class PlainPrefix(unittest.TestCase):
    def test_a_prefix_that_does_not_change_the_spelling(self):
        rows = peel("प्रविशति", ["विशति"])
        self.assertEqual(rows[0]["u"], "प्र")
        self.assertEqual(rows[0]["rest"], "विशति")

    def test_an_unrecognised_remainder_is_not_offered(self):
        # प्र is there, but झझझ is not a verb form, so there is nothing to show.
        self.assertEqual(peel("प्रझझझ", ["विशति"]), [])


class JunctionSandhi(unittest.TestCase):
    def test_vriddhi_recovers_the_roots_own_vowel(self):
        # उप + एति → उपैति. Without inverting the vṛddhi the root reads एति
        # nowhere in the written form.
        rows = peel("उपैति", ["एति"])
        self.assertEqual((rows[0]["u"], rows[0]["rest"]), ("उप", "एति"))
        self.assertEqual(rows[0]["rule"], "वृद्धिः")

    def test_yan_restores_an_independent_vowel_not_a_matra(self):
        # प्रति + उवाच → प्रत्युवाच. Slicing after प्रत्य leaves the DEPENDENT
        # sign ु; the index is keyed by the independent उ, so the sign has to
        # be converted back or the lookup silently misses.
        rows = peel("प्रत्युवाच", ["उवाच"])
        self.assertEqual((rows[0]["u"], rows[0]["rest"]), ("प्रति", "उवाच"))
        self.assertEqual(rows[0]["rule"], "यण्")

    def test_savarna_dirgha_tries_both_readings_of_the_long_vowel(self):
        # आ hides अ+अ, अ+आ, आ+अ and आ+आ alike; only trying both finds the आ.
        rows = peel("समागच्छति", ["आगच्छति"], depth=1)
        self.assertIn(("सम्", "आगच्छति"), [(r["u"], r["rest"]) for r in rows])


class TwoPrefixes(unittest.TestCase):
    def test_a_verb_can_carry_two_and_the_fuller_reading_wins(self):
        # समागच्छति is सम् + आ + गच्छति. Only गच्छति is a real form here --
        # आगच्छति is prefixed and so absent from the index by construction --
        # which is exactly why the recursion must not require the intermediate
        # to validate.
        rows = peel("समागच्छति", ["गच्छति"])
        self.assertEqual(rows[0]["u"], "सम् + आ")
        self.assertEqual(rows[0]["rest"], "गच्छति")
        self.assertEqual(rows[0]["chain"], 2)

    def test_a_yan_prefix_stacks_on_a_plain_one(self):
        rows = peel("व्युत्पद्यते", ["पद्यते"])
        self.assertEqual((rows[0]["u"], rows[0]["rest"]), ("वि + उत्", "पद्यते"))

    def test_depth_one_stops_at_a_single_prefix(self):
        rows = peel("समागच्छति", ["गच्छति"], depth=1)
        self.assertEqual(rows, [])

    def test_the_longer_chain_is_ranked_above_the_shorter(self):
        # Both readings are real; the one accounting for more of the written
        # word is the fuller analysis.
        rows = peel("समागच्छति", ["गच्छति", "आगच्छति"])
        self.assertEqual(rows[0]["chain"], 2)


if __name__ == "__main__":
    unittest.main()
