"""The weekly watch tooling: report, mail fallback, landing, destination map, clean-up plan."""
import json
import os
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from watch import build_destinations, compose_report, dump_to_parabuddhi, land_raw, send_report  # noqa: E402


def test_both_watchers_run_sunday_2am_ist():
    """The timing lives in config/schedules.json (IST) and is started by scheduler.yml."""
    import json
    jobs = {j["id"]: j for j in json.loads((REPO / "config/schedules.json").read_text(encoding="utf-8"))["jobs"]}
    for name in ("watch-sources", "watch-indowordnet"):
        assert jobs[name]["cron"] == "0 2 * * 0" and jobs[name]["enabled"], name


def test_stitch_ashtadhyayi_never_runs_by_itself():
    wf = yaml.safe_load((REPO / ".github/workflows/stitch-ashtadhyayi.yml").read_text(encoding="utf-8"))
    on = wf.get("on") or wf.get(True)
    assert "schedule" not in on


def test_watch_matrix_covers_the_sources_the_lead_named():
    wf = yaml.safe_load((REPO / ".github/workflows/watch-sources.yml").read_text(encoding="utf-8"))
    names = {m["name"] for m in wf["jobs"]["watch"]["strategy"]["matrix"]["include"]}
    for want in ("gretil", "ambuda", "sanskritsahitya", "ashtadhyayi", "dcs", "scl", "dvaitavedanta", "setutila",
                 "anandamakaranda", "srivaishnavan", "advaitasharada", "vishvasa"):
        assert want in names, want
    assert wf["jobs"]["watch"]["strategy"]["max-parallel"] == 1      # every job pushes to ParaBuddhi


def test_compose_report_lists_changes_and_landing(tmp_path, capsys):
    (tmp_path / "result-a.json").write_text(json.dumps({
        "changed": [{"id": "setutila", "what": "CHANGED (was ab)", "detail": {"total": "50"}, "importer": "x"}],
        "unchanged": ["gretil"], "failed": [{"id": "dcs", "error": "HTTP 404"}]}))
    (tmp_path / "landed-a.json").write_text(json.dumps({"landed": {"setutila": "recorded evidence"}, "failed": {}}))
    compose_report.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert "1 changed" in out and "**setutila**" in out and "ParaBuddhi: recorded evidence" in out
    assert "dcs" in out and "IST" in out


def test_mail_falls_back_when_not_configured(monkeypatch):
    monkeypatch.delenv("SUPERADMIN_EMAILS", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    ok, why = send_report.send_mail("s", "b")
    assert not ok and "SUPERADMIN_EMAILS" in why
    monkeypatch.setenv("SUPERADMIN_EMAILS", "a@example.org, b@example.org")
    ok, why = send_report.send_mail("s", "b")
    assert not ok and "SMTP_HOST" in why


def test_mail_is_sent_through_smtp_when_configured(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=0): sent["host"] = (host, port)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context=None): sent["tls"] = True
        def login(self, u, p): sent["login"] = u
        def send_message(self, m): sent["to"] = m["To"]; sent["subject"] = m["Subject"]

    monkeypatch.setattr(send_report.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SUPERADMIN_EMAILS", "a@example.org;b@example.org")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("SMTP_USER", "u")
    ok, why = send_report.send_mail("Weekly", "body")
    assert ok and sent["to"] == "a@example.org, b@example.org" and sent["tls"] and sent["login"] == "u"


def test_landing_refuses_without_the_token(tmp_path, monkeypatch):
    monkeypatch.delenv("PARABUDDHI_TOKEN", raising=False)
    res = tmp_path / "r.json"
    res.write_text(json.dumps({"changed": [{"id": "x", "kind": "feed", "probe": {}}]}))
    assert land_raw.main(["--pb", str(tmp_path), "--result", str(res)]) == 2


def test_landing_with_nothing_changed_succeeds(tmp_path):
    res = tmp_path / "r.json"
    res.write_text(json.dumps({"changed": []}))
    assert land_raw.main(["--pb", str(tmp_path), "--result", str(res)]) == 0


def test_dump_archives_and_prunes(tmp_path):
    pb = tmp_path / "pb"
    pb.mkdir()
    os.system("git -C %s init -q" % pb)
    f = tmp_path / "x.json"
    f.write_text("{}")
    # no remote: the push fails, but the archive and its LATEST.json must exist and be pruned to --keep
    rc = dump_to_parabuddhi.main(["--pb", str(pb), "--id", "w", "--path", str(f), "--keep", "1"])
    assert rc == 2
    out = pb / "source/_raw/w"
    assert (out / "LATEST.json").exists() and len(list(out.glob("*.tar.gz"))) == 1


def _mini(tmp_path):
    pb, sb = tmp_path / "pb", tmp_path / "sb"
    m = pb / "provenance/source/setutila.in/darshana/vedanta/dvaita/SetuTila/sec/g1/data.json"
    m.mkdir(parents=True)
    (m / "map.jsonl").write_text("\n".join(json.dumps({"origin": {"cls": "Sarvamula", "chunk": "c1", "origin_reference": "r", "url": "u"}}) for _ in range(3)) + "\n")
    m2 = pb / "provenance/source/setutila.in/darshana/vedanta/dvaita/SetuTila/sec/g2/data.json"
    m2.mkdir(parents=True)
    (m2 / "map.jsonl").write_text(json.dumps({"origin": {"cls": "Tika", "chunk": "c2"}}) + "\n")
    (sb / "data/Tattvavada/SarvaMula/sec/g1").mkdir(parents=True)
    (sb / "data/Tattvavada/SarvaMula/sec/g1/data.json").write_text("{}")
    return pb, sb


def test_destinations_are_mapped_by_unique_suffix_and_unresolved_are_listed(tmp_path):
    pb, sb = _mini(tmp_path)
    assert build_destinations.main(["--pb", str(pb), "--sb", str(sb), "--write"]) == 0
    reg = json.loads((pb / "import_config/destinations.registry.json").read_text())
    secs = {s["staged_path"].split("/")[-1]: s for s in reg["sources"]["setutila.in"]["sections"]}
    assert secs["g1"]["destination"] == "Tattvavada/SarvaMula/sec/g1" and secs["g1"]["status"] == "mapped"
    assert secs["g2"]["destination"] is None and secs["g2"]["status"] == "unresolved"
    assert reg["sources"]["setutila.in"]["label_map"]["Sarvamula"] == {"g1": 3}


def test_hand_edits_survive_a_rebuild(tmp_path):
    pb, sb = _mini(tmp_path)
    build_destinations.main(["--pb", str(pb), "--sb", str(sb), "--write"])
    p = pb / "import_config/destinations.registry.json"
    reg = json.loads(p.read_text())
    for s in reg["sources"]["setutila.in"]["sections"]:
        if s["status"] == "unresolved":
            s["decision"], s["note"] = "not_used", "left out on purpose"
    p.write_text(json.dumps(reg))
    assert build_destinations.main(["--pb", str(pb), "--sb", str(sb), "--write", "--check"]) == 0
    reg = json.loads(p.read_text())
    assert any(s.get("note") == "left out on purpose" for s in reg["sources"]["setutila.in"]["sections"])


def test_branch_cleanup_plan_is_coherent():
    plan = json.loads((REPO / "config/cleanup/branch-plan.json").read_text(encoding="utf-8"))["groups"]
    seen = {}
    for g, names in plan.items():
        for n in names:
            assert n not in seen, "%s is in both %s and %s" % (n, seen[n], g)
            seen[n] = g
    assert "main" in plan["keep"]
    assert not any(n.startswith("ocr-staging/") for n in plan["keep"])
    # nothing deleted that a workflow still writes
    for n in ("search-dist", "nightly/library-sync"):
        assert n in plan["keep"]
