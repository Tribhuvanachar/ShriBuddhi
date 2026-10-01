import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from watch import triage_reports as T  # noqa: E402


def R(i, cat="wrong-text", msg="the second line is missing a word", subject="1.4", path="p/q", **kw):
    d = {"id": i, "category": cat, "message": msg, "subject": subject, "path": path, "uid": "u" + i}
    d.update(kw)
    return d


def test_queues_follow_the_category():
    got = {r["id"]: r["queue"] for r in T.classify([
        R("a", "wrong-text", subject="a", path="a"), R("b", "missing-text", subject="b", path="b"),
        R("c", "wrong-mapping", subject="c", path="c"), R("d", "wrong-form", subject="d", path="d"),
        R("e", "not-resolving", subject="e", path="e"), R("f", "wrong-split", subject="f", path="f"),
        R("g", "other", subject="g", path="g")])}
    assert got == {"a": "proofreader", "b": "content", "c": "content", "d": "linguistics",
                   "e": "linguistics", "f": "linguistics", "g": "admin"}


def test_priorities():
    reps = [R("1"), R("2"), R("3")]                       # same subject three times
    assert {r["priority"] for r in T.classify(reps)} == {"P1"}
    two = T.classify([R("1"), R("2")])
    assert {r["priority"] for r in two} == {"P2"}
    one = T.classify([R("1", subject="", path="", msg="a short but real complaint")])
    assert one[0]["priority"] == "P3"
    assert T.classify([R("1", msg="typo")])[0]["priority"] == "P4"
    assert T.classify([R("1", selected="a selected passage", subject="x", path="y")])[0]["priority"] == "P2"


def test_staff_reports_are_p1():
    got = T.classify([R("1", subject="solo", path="solo")], roles={"u1": "admin"})
    assert got[0]["priority"] == "P1"


def test_digest_groups_by_queue_then_priority_and_hides_p4_detail():
    items = T.classify([R("1", "missing-text", subject="s1", path="s1"), R("2", "wrong-text", msg="typo", subject="s2", path="s2")])
    subject, body = T.digest(items)
    assert subject.startswith("Reader reports: 2 new")
    assert body.index("CONTENT queue") < body.index("PROOFREADER queue")
    assert "typo" not in body.split("PROOFREADER queue")[1].split("report id")[0].replace("[P4]", "")
    assert T.digest([])[0] == "No new reader reports."


def test_resolved_notice_carries_the_note():
    subject, body = T.resolved_notice({"subject": "Typo in Gita 2.47", "resolution": "Fixed in the text."})
    assert "resolved" in subject.lower() or "dealt with" in subject
    assert "Typo in Gita 2.47" in body and "Fixed in the text." in body


def test_resolved_notice_without_note():
    _, body = T.resolved_notice({"title": "x"})
    assert "What was done" not in body
