import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from watch import scheduler as S  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def utc(s):
    return dt.datetime.fromisoformat(s)


def test_sunday_2am_ist_is_saturday_2030_utc():
    assert S.due("0 2 * * 0", utc("2026-10-03T20:31:00"))        # Sun 02:01 IST
    assert not S.due("0 2 * * 0", utc("2026-10-03T23:30:00"))    # Sun 05:00 IST, outside the window
    assert not S.due("0 2 * * 0", utc("2026-10-02T20:31:00"))    # a Saturday IST


def test_monthly_and_daily():
    assert S.due("0 3 2 * *", utc("2026-10-01T21:40:00"))        # 2 Oct 03:10 IST
    assert not S.due("0 3 2 * *", utc("2026-10-02T21:40:00"))
    assert S.due("0 23 * * *", utc("2026-10-01T17:35:00"))


def test_next_runs_in_ist():
    nxt = S.next_runs("0 2 * * 0", utc("2026-10-01T00:00:00"), 2)
    assert [t.strftime("%a %H:%M") for t in nxt] == ["Sun 02:00", "Sun 02:00"]
    assert nxt[0].day == 4


def test_config_is_valid_and_points_at_real_workflows():
    jobs = S.load()
    ids = [j["id"] for j in jobs]
    assert len(ids) == len(set(ids))
    for j in jobs:
        S.parse_cron(j["cron"])
        assert os.path.exists(os.path.join(ROOT, ".github", "workflows", j["workflow"])), j["workflow"]
        text = open(os.path.join(ROOT, ".github", "workflows", j["workflow"]), encoding="utf-8").read()
        assert "workflow_dispatch" in text and "\n  schedule:" not in text, j["workflow"]


def test_only_scheduler_has_a_native_cron():
    wf = os.path.join(ROOT, ".github", "workflows")
    for f in os.listdir(wf):
        if f.endswith(".yml") and f != "scheduler.yml":
            for line in open(os.path.join(wf, f), encoding="utf-8"):
                assert not line.strip().startswith("- cron:"), f
