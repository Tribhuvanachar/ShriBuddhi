"""sync_check.py: the diff must name real change and refuse to invent it."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "tools", "dvaitavedanta"))

import sync_check  # noqa: E402


def census_entry(ids, title="ग्रन्थः", section="later_acharyas", slug="g"):
    return {"ok": True, "title": title, "section": section, "slug": slug,
            "ids": sorted(str(i) for i in ids),
            "urls": {str(i): f"https://x/{i}" for i in ids}}


def state_with(key, ids):
    return {"granthas": {key: {"ids": sorted(str(i) for i in ids),
                               "discovered": len(ids)}}}


class DiffCensus(unittest.TestCase):
    KEY = "later_acharyas/g"

    def test_first_sighting_is_baseline_not_a_flood_of_additions(self):
        rows, changed, unreadable = sync_check.diff_census(
            {}, {self.KEY: census_entry([1, 2, 3])})
        self.assertEqual(rows[0]["status"], "baseline")
        self.assertEqual(changed, [])
        self.assertEqual(unreadable, [])

    def test_identical_census_reports_same(self):
        rows, changed, _ = sync_check.diff_census(
            state_with(self.KEY, [1, 2, 3]), {self.KEY: census_entry([1, 2, 3])})
        self.assertEqual(rows[0]["status"], "same")
        self.assertEqual(changed, [])

    def test_new_ids_are_named_exactly(self):
        _, changed, _ = sync_check.diff_census(
            state_with(self.KEY, [1, 2]), {self.KEY: census_entry([1, 2, 9, 10])})
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["added"], ["10", "9"])
        self.assertEqual(changed[0]["removed"], [])

    def test_removed_ids_are_named_exactly(self):
        _, changed, _ = sync_check.diff_census(
            state_with(self.KEY, [1, 2, 3]), {self.KEY: census_entry([1, 2])})
        self.assertEqual(changed[0]["removed"], ["3"])

    def test_failed_seed_is_unreadable_not_a_deletion(self):
        rows, changed, unreadable = sync_check.diff_census(
            state_with(self.KEY, [1, 2, 3]),
            {self.KEY: {"ok": False, "why": "bot-challenge page", "title": "t"}})
        self.assertEqual(rows[0]["status"], "unreadable")
        self.assertEqual(changed, [])
        self.assertEqual(len(unreadable), 1)

    def test_shrunken_sidebar_is_suspect_not_a_mass_deletion(self):
        _, changed, unreadable = sync_check.diff_census(
            state_with(self.KEY, range(100)), {self.KEY: census_entry([1, 2])})
        self.assertEqual(changed, [])
        self.assertEqual(unreadable[0]["status"], "suspect")

    def test_moderate_shrink_is_still_a_real_removal(self):
        # 10 -> 7 is above the guard: report it, don't second-guess it.
        _, changed, unreadable = sync_check.diff_census(
            state_with(self.KEY, range(10)), {self.KEY: census_entry(range(7))})
        self.assertEqual(len(changed), 1)
        self.assertEqual(unreadable, [])
        self.assertEqual(len(changed[0]["removed"]), 3)


class NextState(unittest.TestCase):
    KEY = "later_acharyas/g"

    def test_readable_census_replaces_memory(self):
        state = sync_check.next_state(state_with(self.KEY, [1]),
                                      {self.KEY: census_entry([1, 2])}, "T")
        self.assertEqual(state["granthas"][self.KEY]["ids"], ["1", "2"])

    def test_failed_read_never_overwrites_memory(self):
        state = sync_check.next_state(
            state_with(self.KEY, [1, 2, 3]),
            {self.KEY: {"ok": False, "why": "seed fetch failed", "title": "t"}}, "T")
        self.assertEqual(state["granthas"][self.KEY]["ids"], ["1", "2", "3"])


class ReportAndMain(unittest.TestCase):
    KEY = "later_acharyas/g"

    def test_changed_rows_carry_the_grep_marker(self):
        rows, changed, unreadable = sync_check.diff_census(
            state_with(self.KEY, [1]), {self.KEY: census_entry([1, 2])})
        report = sync_check.render_report(rows, changed, unreadable,
                                          {self.KEY: census_entry([1, 2])})
        self.assertIn("| **later_acharyas/g**", report)
        self.assertIn("scope=`later_acharyas` granthas=`g`", report)

    def test_quiet_report_has_no_marker(self):
        rows, changed, unreadable = sync_check.diff_census(
            state_with(self.KEY, [1]), {self.KEY: census_entry([1])})
        report = sync_check.render_report(rows, changed, unreadable, {})
        self.assertNotIn("| **", report)

    def test_nyaya_sudha_advice_names_the_long_timeout(self):
        key = "later_acharyas/nyaya_sudha"
        rows, changed, unreadable = sync_check.diff_census(
            state_with(key, [1]),
            {key: census_entry([1, 2], slug="nyaya_sudha")})
        report = sync_check.render_report(rows, changed, unreadable, {})
        self.assertIn("job_timeout=350", report)

    def test_main_end_to_end_with_injected_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            jout = os.path.join(tmp, "changes.json")
            fake = {self.KEY: census_entry([1, 2])}
            argv = ["--state", state, "--json-out", jout, "--write-state"]
            sync_check.main(argv, discover_fn=lambda gs: fake)
            with open(jout) as handle:
                first = json.load(handle)
            self.assertEqual(first["changed"], {})           # baseline run
            self.assertEqual(first["baseline"], [self.KEY])
            fake2 = {self.KEY: census_entry([1, 2, 3])}
            sync_check.main(argv, discover_fn=lambda gs: fake2)
            with open(jout) as handle:
                second = json.load(handle)
            self.assertEqual(second["changed"], {"later_acharyas": ["g"]})


if __name__ == "__main__":
    unittest.main()
