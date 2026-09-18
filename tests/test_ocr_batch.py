"""ocr_batch.py: the checks that stand between a plan and a bill."""

import datetime, io, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import ocr_batch as B  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
TODAY = datetime.date.today().isoformat()


def plan(tmp, rows):
    p = os.path.join(tmp, "plan.tsv")
    io.open(p, "w", encoding="utf-8").write("".join("%s\t%s\t%s\n" % r for r in rows))
    return p


class Preflight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def rows(self, *r):
        return B.read_plan(plan(self.tmp, r))

    def test_two_works_sharing_a_slug_is_refused(self):
        """They would share one staging branch and overwrite each other.

        Three Aitareya Upanisad items share a 44-character prefix; truncating to a
        slug gave all three the same branch.
        """
        rows = self.rows(("same", "http://a.pdf", "1-10"), ("same", "http://b.pdf", "1-10"))
        bad = B.preflight(rows, "sarvam", TODAY, ROOT)
        self.assertTrue(any("different PDFs" in p for p in bad), bad)

    def test_a_chunk_over_the_engine_cap_is_refused(self):
        rows = self.rows(("w", "http://a.pdf", "1-400"))
        self.assertTrue(any("over the sarvam cap" in p for p in B.preflight(rows, "sarvam", TODAY, ROOT)))

    def test_no_pilot_today_means_no_batch(self):
        """A dry run is not a pilot: it never calls the paid API and never commits."""
        rows = self.rows(("w", "http://a.pdf", "1-10"))
        bad = B.preflight(rows, "sarvam", "1999-01-01", ROOT)
        self.assertTrue(any("pilot recorded" in p for p in bad), bad)

    def test_it_reads_the_real_workflow_and_demands_the_two_fixes(self):
        """These are checked against the workflow file, not a copy of it.

        A range-scoped concurrency key and a retrying push are what the 18 Sep
        batch lacked; between them they lost 7,800 unattempted and 3,474 billed
        pages. If someone reverts either, the next batch must not dispatch.
        """
        rows = self.rows(("w", "http://a.pdf", "1-10"))
        bad = B.preflight(rows, "sarvam", TODAY, ROOT)
        self.assertFalse([p for p in bad if "concurrency key" in p], bad)
        self.assertFalse([p for p in bad if "retry a rejected push" in p], bad)

    def test_a_workflow_missing_the_push_retry_is_refused(self):
        broken = os.path.join(self.tmp, ".github", "workflows")
        os.makedirs(broken)
        io.open(os.path.join(broken, "ocr-sarvam.yml"), "w", encoding="utf-8").write(
            "concurrency:\n  group: ocr-sarvam-${{ inputs.pages }}\ngit push -q\n")
        rows = self.rows(("w", "http://a.pdf", "1-10"))
        bad = B.preflight(rows, "sarvam", TODAY, self.tmp)
        self.assertTrue(any("retry a rejected push" in p for p in bad), bad)


class Reconcile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_it_counts_pages_not_runs(self):
        """55 of 130 runs succeeding was 47% of the pages.

        Counting runs would have said 42% and counting conclusions would have
        said nothing about how many pages were actually readable.
        """
        rows = B.read_plan(plan(self.tmp, (("w", "u", "1-100"), ("w", "u", "101-200"))))
        out = B.reconcile(rows, {"w": set(range(1, 101))})
        self.assertEqual(200, out["requested"])
        self.assertEqual(100, out["staged"])
        self.assertEqual(100, out["missing"])

    def test_a_complete_batch_reports_nothing_incomplete(self):
        rows = B.read_plan(plan(self.tmp, (("w", "u", "1-50"),)))
        out = B.reconcile(rows, {"w": set(range(1, 51))})
        self.assertEqual([], out["incomplete"])
        self.assertEqual(0, out["missing"])


if __name__ == "__main__":
    unittest.main()
