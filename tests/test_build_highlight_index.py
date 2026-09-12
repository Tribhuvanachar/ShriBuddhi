"""tools/build_highlight_index.py — the shape of the word-presence index the
reader's धातु/कोश highlighting reads.

The one thing that MUST hold here is that the Python side and the JavaScript
side agree on the lookup key. A word is written into a shard under a
normalised spelling and looked up under a normalised spelling computed
independently in dge/js/highlight-words.js; if the two ever disagree about,
say, a trailing danda, every word at the end of a pāda silently stops being
marked and nothing errors. So normalise() and the bucketing are pinned here,
and the JS copies are pinned against the same cases in the browser check.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import build_highlight_index as b  # noqa: E402


class Normalise(unittest.TestCase):
    def test_strips_the_danda_a_verse_final_word_carries(self):
        self.assertEqual(b.normalise("भवति।"), "भवति")
        self.assertEqual(b.normalise("भवति॥"), "भवति")

    def test_strips_latin_punctuation_a_commentary_carries(self):
        self.assertEqual(b.normalise("गच्छति,"), "गच्छति")
        self.assertEqual(b.normalise("(गच्छति)"), "गच्छति")

    def test_drops_avagraha(self):
        # ऽ is elision, not part of the word being looked up.
        self.assertEqual(b.normalise("सोऽपि"), "सोपि")

    def test_leaves_a_bare_word_alone(self):
        self.assertEqual(b.normalise("रामः"), "रामः")

    def test_empty_and_none_are_safe(self):
        self.assertEqual(b.normalise(None), "")
        self.assertEqual(b.normalise("   "), "")


class DevanagariOnly(unittest.TestCase):
    """The marks only ever land on Devanagari text, so anything else in the
    source lists is noise that would sit in the index forever unmatched."""

    def test_a_latin_key_is_not_a_word(self):
        self.assertFalse(b.is_devanagari("shardCount"))
        self.assertFalse(b.is_devanagari("_readme"))

    def test_devanagari_and_its_vedic_extensions_are(self):
        self.assertTrue(b.is_devanagari("भवति"))
        self.assertTrue(b.is_devanagari("अ\u1cd0"))   # Vedic tone mark

    def test_the_form_index_manifest_is_not_read_as_forms(self):
        # The regression this guards: verb_forms() walked every *.json in the
        # directory, and manifest.json's own keys ('_readme', 'shardCount')
        # became indexed "words" with their own shards.
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "manifest.json"), "w", encoding="utf-8") as fh:
                json.dump({"_readme": "x", "shardCount": 3}, fh)
            with open(os.path.join(tmp, "092d.json"), "w", encoding="utf-8") as fh:
                json.dump({"भवति": [{"c": "01.0001"}]}, fh, ensure_ascii=False)
            self.assertEqual(b.verb_forms(tmp, krt_dir=None), {"भवति"})


class Bucketing(unittest.TestCase):
    def test_prefix_is_the_first_two_codepoints_in_hex(self):
        self.assertEqual(b.prefix_of("भवति", 2), "092d0935")

    def test_a_one_letter_word_pads_rather_than_truncating(self):
        # Fixed width matters: the shard NAME is what the client computes, and
        # a variable-length name would collide 'क' with 'कि'.
        self.assertEqual(len(b.prefix_of("क", 2)), 8)
        self.assertTrue(b.prefix_of("क", 2).endswith("0000"))

    def test_depth_three_is_the_same_scheme_one_character_further(self):
        self.assertEqual(b.prefix_of("भवति", 3), "092d0935" + "0924")


class Build(unittest.TestCase):
    def test_a_word_in_both_lists_carries_both_marks(self):
        marks = b.build({"गम्"}, {"गम्"})
        self.assertEqual(marks["गम्"], b.MARK_KOSHA | b.MARK_DHATU)

    def test_single_letter_words_are_dropped(self):
        # Marking every अ and च on a page is noise, not information.
        self.assertNotIn("च", b.build({"च"}, set()))

    def test_kosha_only_and_dhatu_only_stay_distinct(self):
        marks = b.build({"रामः"}, {"भवति"})
        self.assertEqual(marks["रामः"], b.MARK_KOSHA)
        self.assertEqual(marks["भवति"], b.MARK_DHATU)


class Sharding(unittest.TestCase):
    def test_words_land_in_the_shard_named_by_their_prefix(self):
        buckets, deep = b.shard({"भवति": b.MARK_DHATU})
        self.assertEqual(deep, [])
        self.assertIn("092d0935", buckets)
        self.assertEqual(buckets["092d0935"], {"d": "भवति"})

    def test_the_three_masks_are_three_separate_runs(self):
        buckets, _ = b.shard({
            "भवति": b.MARK_DHATU,
            "भवनम्": b.MARK_KOSHA,
            "भवः": b.MARK_KOSHA | b.MARK_DHATU,
        })
        shard = buckets[b.prefix_of("भवति", 2)]
        # Same first two characters for all three, so one shard holds all of
        # them and the run keys are what separates them.
        self.assertEqual(shard["d"], "भवति")
        self.assertEqual(shard["k"], "भवनम्")
        self.assertEqual(shard["b"], "भवः")

    def test_an_oversized_bucket_is_split_a_character_deeper_and_declared(self):
        marks = {"भव" + chr(0x0915 + (i % 20)) + str(i): b.MARK_DHATU for i in range(400)}
        marks.update({"भवि" + str(i): b.MARK_KOSHA for i in range(400)})
        buckets, deep = b.shard(marks, cap=200)
        self.assertIn("092d0935", deep)
        self.assertNotIn("092d0935", buckets)
        # Every word must still be reachable: the client walks down to depth 3
        # for a declared prefix, so a depth-3 shard has to exist for each.
        for word in marks:
            self.assertIn(b.prefix_of(word, 3), buckets)

    def test_a_split_bucket_is_the_only_thing_deep_reports(self):
        buckets, deep = b.shard({"भवति": b.MARK_DHATU, "रामः": b.MARK_KOSHA}, cap=10 ** 6)
        self.assertEqual(deep, [])
        self.assertEqual(len(buckets), 2)


class Manifest(unittest.TestCase):
    def test_manifest_counts_and_bucket_list_match_what_was_written(self):
        marks = {"भवति": b.MARK_DHATU, "रामः": b.MARK_KOSHA, "गम्": b.MARK_KOSHA | b.MARK_DHATU}
        buckets, deep = b.shard(marks)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = b.write(buckets, deep, marks, tmp)
            self.assertEqual(manifest["words"], 3)
            self.assertEqual(manifest["kosha_words"], 2)
            self.assertEqual(manifest["dhatu_words"], 2)
            self.assertEqual(manifest["buckets"], sorted(buckets))
            on_disk = json.load(open(os.path.join(tmp, "manifest.json"), encoding="utf-8"))
            self.assertEqual(on_disk["marks"], {"kosha": 1, "dhatu": 2})
            for name in buckets:
                self.assertTrue(os.path.exists(os.path.join(tmp, name + ".json")))

    def test_a_rebuild_clears_shards_the_new_run_no_longer_produces(self):
        # A stale shard is worse than a missing one: it answers confidently
        # with words a later rebuild deliberately dropped.
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "deadbeef.json"), "w").write("{}")
            buckets, deep = b.shard({"भवति": b.MARK_DHATU})
            b.write(buckets, deep, {"भवति": b.MARK_DHATU}, tmp)
            self.assertFalse(os.path.exists(os.path.join(tmp, "deadbeef.json")))


class ClientAgreement(unittest.TestCase):
    """dge/js/highlight-words.js recomputes the lookup key and the shard name
    independently. Neither side errors when they drift -- words simply stop
    being marked -- so the shared constants are pinned against the JS source
    itself rather than against a comment describing it."""

    def setUp(self):
        path = os.path.join(os.path.dirname(__file__), "..", "dge", "js", "highlight-words.js")
        with open(path, encoding="utf-8") as fh:
            self.js = fh.read()

    def test_the_punctuation_both_sides_strip_is_the_same_set(self):
        import re
        m = re.search(r"var STRIP_CHARS = '(.*)';", self.js)
        self.assertIsNotNone(m, "STRIP_CHARS not found in highlight-words.js")
        js_chars = m.group(1).replace("\\'", "'")
        self.assertEqual(set(js_chars), set(b.STRIP),
                         "STRIP differs between the builder and the reader")

    def test_the_mark_bits_are_the_same_numbers(self):
        self.assertIn("var MARK_KOSHA = %d;" % b.MARK_KOSHA, self.js)
        self.assertIn("var MARK_DHATU = %d;" % b.MARK_DHATU, self.js)

    def test_the_client_reads_the_directory_this_writes(self):
        self.assertIn("'data/_highlight'", self.js)
        self.assertTrue(b.OUT_DIR.endswith(os.path.join("dge", "data", "_highlight")))

    def test_the_client_walks_down_for_a_declared_deep_prefix(self):
        # prefix_of(word, 3) on the Python side; the JS must ask for depth 3
        # on exactly the prefixes the manifest lists, or a split bucket's
        # words become unreachable.
        self.assertIn("m.deep.indexOf(name) !== -1", self.js)
        self.assertIn("prefixOf(word, 3)", self.js)

    def test_the_client_expands_the_same_three_run_keys(self):
        for key in ("'k'", "'d'", "'b'"):
            self.assertIn(key, self.js)


class MultiScriptClient(unittest.TestCase):
    """The marks have to appear whatever script the reader is displaying. The
    index stays Devanagari-keyed; the client carries the word back to it."""

    def setUp(self):
        base = os.path.join(os.path.dirname(__file__), "..", "dge")
        with open(os.path.join(base, "js", "highlight-words.js"), encoding="utf-8") as fh:
            self.js = fh.read()
        self.base = base

    def test_the_client_transliterates_before_looking_up(self):
        self.assertIn("toDevanagari", self.js)
        self.assertIn("window.Sanscript.t(word, scheme, 'devanagari')", self.js)

    def test_every_script_the_reader_can_pick_has_a_scheme(self):
        # A script id present in the picker but missing from SCRIPT_SCHEME
        # makes the marks stand down in that script with nothing to say why —
        # which is exactly what Hindi and Marathi did when this was written.
        import re
        with open(os.path.join(self.base, "js", "config.js"), encoding="utf-8") as fh:
            config = fh.read()
        block = config.split("const SCRIPT_OPTIONS = [", 1)[1].split("];", 1)[0]
        ids = re.findall(r"id:\s*'([a-z0-9_]+)'", block)
        self.assertGreaterEqual(len(ids), 8, "SCRIPT_OPTIONS did not parse")
        table = self.js.split("var SCRIPT_SCHEME = {", 1)[1].split("};", 1)[0]
        keys = set(re.findall(r"([a-z0-9_]+)\s*:", table))
        for script in ids:
            self.assertIn(script, keys, "no transliteration scheme for script %r" % script)

    def test_sanscript_is_vendored_not_fetched_from_a_cdn(self):
        # The marks and the reader's own script setting both depend on it; a
        # CDN that does not answer must not be able to turn either off.
        vendored = os.path.join(self.base, "js", "vendor", "sanscript-1.3.3.min.js")
        self.assertTrue(os.path.exists(vendored))
        self.assertGreater(os.path.getsize(vendored), 50000)

    def test_no_page_still_loads_sanscript_from_a_cdn(self):
        import glob as _glob
        offenders = []
        for path in _glob.glob(os.path.join(self.base, "**", "*.html"), recursive=True):
            if "node_modules" in path:
                continue
            with open(path, encoding="utf-8") as fh:
                html = fh.read()
            for line in html.splitlines():
                if "sanscript" in line and ("cdn.jsdelivr.net" in line or "unpkg.com" in line):
                    offenders.append(os.path.relpath(path, self.base))
                    break
        self.assertEqual(offenders, [])

    def test_a_lossy_script_expands_candidates_rather_than_trusting_one(self):
        # Devanagari → any script is a function; the way back is not. Tamil
        # writes क ख ग घ with one letter and has no anusvāra, so the plain
        # back-reading is the right word only 11.5% of the time. The fix is to
        # treat it as a pattern and let the index choose — the same
        # generate-and-validate the sandhi splitter runs on.
        self.assertIn("devanagariCandidates", self.js)
        self.assertIn("CANDIDATE_CAP", self.js)
        self.assertIn("window.dgeDevanagariCandidates", self.js)

    def test_the_back_table_is_derived_not_hand_written(self):
        # A hand-listed Tamil table is a table that drifts out of step with
        # Sanscript. This probes the library for what each unit becomes.
        self.assertIn("function backTable(scheme)", self.js)
        self.assertIn("S.t(u, 'devanagari', scheme)", self.js)
        # म् is two codepoints; a single-character probe cannot see it collide
        # with ं, and misses every word carrying a nasal.
        self.assertIn("String.fromCharCode(c) + '्'", self.js)

    def test_a_resolved_reading_is_named_to_the_reader(self):
        # Where the matched reading is not the one on the page, the mark says
        # so rather than presenting a homograph as "this word".
        self.assertIn("read here as", self.js)

    def test_the_word_tools_look_up_the_devanagari_reading(self):
        # Every index they consult is Devanagari-keyed, so in Kannada or IAST
        # they answered "not found" for words plainly in the data.
        with open(os.path.join(self.base, "js", "ai.js"), encoding="utf-8") as fh:
            ai = fh.read()
        self.assertIn("function dgeLookupWordText()", ai)
        self.assertEqual(ai.count("const word = dgeLookupWordText();"), 4)
        self.assertIn("window.dgeToDevanagariWord", self.js)


class ScriptRoundTrip(unittest.TestCase):
    """Runs the shipped highlight-words.js against the shipped index under
    node, because the claim being made is behavioural: a reader in Kannada or
    Tamil sees marks. Skipped where node is absent."""

    WORDS = ["भवति", "कृत्वा", "गच्छति", "नमो", "रामः", "विशताम्"]

    @classmethod
    def setUpClass(cls):
        import shutil
        if not shutil.which("node"):
            raise unittest.SkipTest("node not available")
        if not os.path.exists(os.path.join(b.OUT_DIR, "manifest.json")):
            raise unittest.SkipTest("highlight index not built")

    def resolve(self, scheme, words):
        """{devanagari word: the reading the marking pass would settle on}."""
        import json as _json
        import subprocess
        repo = os.path.join(os.path.dirname(__file__), "..")
        # r-string: the JS below contains its own escapes, and letting
        # Python interpret them turns a \n inside a JS string literal into a
        # real newline and the script into a syntax error.
        script = r"""
const fs=require('fs'), path=require('path');
// node -e leaves no script path in argv, so the first extra arg is argv[1].
const repo=process.argv[1], scheme=process.argv[2], words=JSON.parse(process.argv[3]);
const sans=fs.readFileSync(path.join(repo,'dge/js/vendor/sanscript-1.3.3.min.js'),'utf8');
const win={activeScript:scheme};
(new Function('window','self','globalThis','exports','module',sans)).call(win,win,win,win,undefined,undefined);
global.window=win;
global.document={addEventListener(){},querySelectorAll(){return[]},getElementById(){return null}};
global.fetch=()=>Promise.resolve({ok:false});
eval(fs.readFileSync(path.join(repo,'dge/js/highlight-words.js'),'utf8'));
const dir=path.join(repo,'dge/data/_highlight');
const index=new Set();
for(const f of fs.readdirSync(dir)){ if(f==='manifest.json') continue;
  const raw=JSON.parse(fs.readFileSync(path.join(dir,f),'utf8'));
  for(const k of ['k','d','b']) if(raw[k]) raw[k].split('\n').forEach(w=>index.add(w)); }
const out={};
for(const dev of words){
  const shown=win.Sanscript.t(dev,'devanagari',scheme);
  const cands=win.dgeDevanagariCandidates(shown)||[];
  out[dev]=cands.find(c=>index.has(c))||null;
}
console.log(JSON.stringify(out));
"""
        res = subprocess.run(["node", "-e", script, repo, scheme, _json.dumps(words)],
                             capture_output=True, text=True, cwd=repo)
        self.assertEqual(res.returncode, 0, res.stderr[-800:])
        return _json.loads(res.stdout)

    def test_the_lossless_scripts_resolve_to_the_word_itself(self):
        for scheme in ("iast", "kannada", "telugu", "malayalam", "oriya"):
            got = self.resolve(scheme, self.WORDS)
            for word in self.WORDS:
                self.assertEqual(got[word], word, "%s in %s" % (word, scheme))

    def test_tamil_recovers_the_word_despite_not_round_tripping(self):
        # Without candidate expansion every one of these comes back as a
        # different string (भवति → பவதி → भवधि) and matches nothing.
        got = self.resolve("tamil", self.WORDS)
        found = [w for w in self.WORDS if got[w] is not None]
        self.assertGreaterEqual(len(found), len(self.WORDS) - 1, got)

    def test_bengali_recovers_its_ba_va_merger(self):
        got = self.resolve("bengali", ["बभूव", "भवति"])
        self.assertEqual(got["भवति"], "भवति")
        self.assertIsNotNone(got["बभूव"])


class ShippedIndex(unittest.TestCase):
    """The committed index itself — a build that never ran is a feature that
    silently does nothing."""

    def setUp(self):
        path = os.path.join(b.OUT_DIR, "manifest.json")
        if not os.path.exists(path):
            self.skipTest("highlight index not built")
        self.manifest = json.load(open(path, encoding="utf-8"))

    def test_it_holds_both_kinds_of_word(self):
        self.assertGreater(self.manifest["kosha_words"], 10000)
        self.assertGreater(self.manifest["dhatu_words"], 100000)

    def test_krdanta_forms_are_marked_too(self):
        # कृत्वा is the commonest absolutive in the language and lives in
        # krtindex, not formindex; marking only the latter left it plain while
        # the Śabda tool answered it perfectly.
        name = b.prefix_of("कृत्वा", 2)
        shard = json.load(open(os.path.join(b.OUT_DIR, name + ".json"), encoding="utf-8"))
        words = set()
        for run in shard.values():
            words.update(run.split("\n"))
        self.assertIn("कृत्वा", words)

    def test_every_declared_bucket_exists_on_disk(self):
        for name in self.manifest["buckets"]:
            self.assertTrue(os.path.exists(os.path.join(b.OUT_DIR, name + ".json")), name)

    def test_no_declared_deep_prefix_is_also_a_shard(self):
        # The client stops walking the moment it finds a name; a prefix that is
        # both split AND present would hand back half its words.
        for name in self.manifest["deep"]:
            self.assertNotIn(name, self.manifest["buckets"], name)

    def test_a_common_verb_form_is_actually_marked(self):
        name = b.prefix_of("भवति", 2)
        shard = json.load(open(os.path.join(b.OUT_DIR, name + ".json"), encoding="utf-8"))
        words = set()
        for run in shard.values():
            words.update(run.split("\n"))
        self.assertIn("भवति", words)


if __name__ == "__main__":
    unittest.main()
