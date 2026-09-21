"""The spend report must reconcile, and must not quietly invent a loss.

The cost ledger exists to answer "the top-up bought how many PDFs, and which
ones". On 21 Sep 2026 it could not: 4,850 pages were staged, real and paid
for, with no ledger row at all -- every Vision run over sandhis 2-9 of the
Harikathamrtasara among them -- understating the total by INR 949. The page
that surfaced it now has a test behind it.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    """Rebuild the report, into a temp file, and read that.

    Rebuilt rather than read from the committed copy, because a stale report
    would pass a test about a ledger it no longer describes.

    Into a TEMP file because the first version of this wrote over
    admin/config/spend_report.json, whose generated_at timestamp changes on
    every run -- so running the suite left the working tree dirty, every
    time, for everyone. A test that reports on the repository must not edit
    it.
    """
    out = tmp_path_factory.mktemp("spend") / "spend_report.json"
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "spend_report.py"),
                    "--root", ROOT, "--out", str(out)],
                   cwd=ROOT, capture_output=True, check=True)
    with open(out, encoding="utf-8") as fh:
        return json.load(fh)


def test_the_committed_report_is_not_rewritten_by_running_tests():
    """Guards the defect above: the suite must leave this file alone."""
    committed = os.path.join(ROOT, "admin", "config", "spend_report.json")
    before = os.path.getmtime(committed)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "spend_report.py"),
                    "--root", ROOT, "--out", os.devnull],
                   cwd=ROOT, capture_output=True)
    assert os.path.getmtime(committed) == before, (
        "running the spend report touched the committed copy")


def test_every_staged_page_has_a_ledger_row(report):
    r = report["reconciliation"]
    assert r["pages_unledgered"] == 0, (
        "%d page(s) are staged with no ledger row -- the total is understated. "
        "First few: %s" % (r["pages_unledgered"], r["staged_not_in_ledger"][:3]))


def test_no_ledger_row_without_a_staged_file(report):
    r = report["reconciliation"]
    assert r["pages_overledgered"] == 0, (
        "%d page(s) are charged for with nothing staged behind them: %s"
        % (r["pages_overledgered"], r["in_ledger_not_staged"][:3]))


def test_losses_are_classified_not_guessed(report):
    """Every failed page is either refused or a server error, never 'unknown'.

    A page nobody has classified is a page whose money nobody has accounted
    for, and it must not be averaged into a total that reads as confident.
    """
    unknown = [f for w in report["works"] for f in w["failures"] if f["kind"] == "unknown"]
    assert unknown == [], "unclassified failure(s): %s" % unknown[:3]


def test_confirmed_loss_stays_evidenced(report):
    """confirmed_lost_inr is 0.00 because no page was billed and not delivered.

    If that ever becomes non-zero it is a real claim against a vendor, and it
    must be backed by pages we can name -- which needs job receipts.
    """
    g = report["grand"]
    if g["confirmed_lost_inr"]:
        named = [r for w in report["works"] for r in (w.get("job_receipts") or [])]
        assert named, "a confirmed loss is claimed with no job receipt to name it"


def test_harikathamrtasara_rolls_up_to_one_book(report):
    """31 staging branches, one book. "What did the HKS cost" is the question
    actually asked, and it must have an answer without adding up 31 rows."""
    g = next((x for x in report["groups"] if x["group"].startswith("Harikathamrtasara")), None)
    assert g is not None, "the Harikathamrtasara does not roll up"
    assert len(g["works"]) >= 30, "only %d branch(es) rolled up" % len(g["works"])
    assert g["inr"] > 0 and g["pages_billed"] > 10000
