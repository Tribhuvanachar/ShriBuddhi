#!/usr/bin/env python3
"""
triage_reports.py -- sort the night's reader reports into queues and tell the right people.

Readers file reports with "Report a problem" (js/report-issue.js), which stores one Firestore
document per report in `reports/`. This runs nightly (triage-reports.yml), and:

  1. reads reports not yet triaged,
  2. gives each a QUEUE and a PRIORITY by fixed rules (no AI, no external service),
  3. writes `queue`, `priority`, `triaged` back to the report (admin/reports.html shows and filters on them),
  4. sends ONE digest to the reports mailbox, grouped queue -> priority, so a content admin or a
     proofreader opens the email and picks from the top.

RULES (edit here; there is nothing hidden):

  queue      wrong-text -> proofreader          missing-text, wrong-mapping -> content
             wrong-form, not-resolving, wrong-split -> linguistics         anything else -> admin
  priority   P1  the same subject (or the same library path) reported 3+ times, or by an admin/editor
             P2  reported twice, or a precise report (a selected passage, or a subject plus a long message)
             P3  everything else
             P4  too short to act on (under 8 characters of message): kept, listed last, never e-mailed in detail

CONTROLS: the workflow is skipped when the repository variable REPORT_TRIAGE is `off`. The mailbox is
REPORTS_EMAIL (falls back to SUPERADMIN_EMAILS). Nothing here calls an LLM; there is no AI to turn off.

    python3 tools/watch/triage_reports.py --dry-run          # classify and print; change nothing, send nothing
    python3 tools/watch/triage_reports.py --from-json r.json # classify a file of reports (testing)
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

QUEUE_OF = {"wrong-text": "proofreader", "missing-text": "content", "wrong-mapping": "content",
            "wrong-form": "linguistics", "not-resolving": "linguistics", "wrong-split": "linguistics"}
QUEUE_ORDER = ["content", "proofreader", "linguistics", "admin"]
STAFF_ROLES = {"admin", "superadmin", "editor", "special"}


def queue_for(r):
    return QUEUE_OF.get(r.get("category") or "", "admin")


def classify(reports, roles=None):
    """reports: list of dicts with at least id, category, message, subject, path. Returns the same list
    with `queue`, `priority` added. `roles` maps uid -> role."""
    roles = roles or {}
    by_subject = collections.Counter((r.get("subject") or "").strip().lower() for r in reports if (r.get("subject") or "").strip())
    by_path = collections.Counter((r.get("path") or "").strip() for r in reports if (r.get("path") or "").strip())
    out = []
    for r in reports:
        r = dict(r)
        msg = (r.get("message") or "").strip()
        subj = (r.get("subject") or "").strip().lower()
        path = (r.get("path") or "").strip()
        n = max(by_subject.get(subj, 0) if subj else 0, by_path.get(path, 0) if path else 0)
        staff = roles.get(r.get("uid")) in STAFF_ROLES
        if len(msg) < 8:
            pri = "P4"
        elif n >= 3 or staff:
            pri = "P1"
        elif n == 2 or r.get("selected") or (subj and len(msg) >= 60):
            pri = "P2"
        else:
            pri = "P3"
        r["queue"], r["priority"] = queue_for(r), pri
        out.append(r)
    return out


def digest(items, admin_url=""):
    total = len(items)
    if not total:
        return "No new reader reports.", ""
    counts = collections.Counter(i["priority"] for i in items)
    subject = "Reader reports: %d new (P1 %d, P2 %d, P3 %d%s)" % (
        total, counts["P1"], counts["P2"], counts["P3"], (", P4 %d" % counts["P4"]) if counts["P4"] else "")
    lines = [subject, ""]
    by_q = collections.defaultdict(list)
    for i in items:
        by_q[i["queue"]].append(i)
    for q in QUEUE_ORDER:
        if q not in by_q:
            continue
        lines += ["== %s queue (%d) ==" % (q.upper(), len(by_q[q])), ""]
        for i in sorted(by_q[q], key=lambda x: (x["priority"], x.get("id", ""))):
            lines.append("[%s] %s · %s" % (i["priority"], i.get("category", ""), i.get("subject") or i.get("title") or i.get("feature", "")))
            if i["priority"] != "P4":
                lines.append("     %s" % (i.get("message", "").replace("\n", " ")[:240]))
                if i.get("path"):
                    lines.append("     library path: %s" % i["path"])
                if i.get("url"):
                    lines.append("     page: %s" % i["url"])
            lines.append("     report id: %s" % i.get("id", ""))
        lines.append("")
    lines.append("Open the reports page in ShriBuddhi (admin/reports.html%s) for the screenshots; filter by queue and priority." %
                 ((" — " + admin_url) if admin_url else ""))
    return subject, "\n".join(lines)


def _service_account():
    for k in ("SA_JSON_1", "SA_JSON_2", "SA_JSON_3", "SA_JSON_4", "SA_JSON_5"):
        v = os.environ.get(k, "").strip()
        if not v:
            continue
        try:
            d = json.loads(v)
            if d.get("client_email") and d.get("private_key"):
                return d
        except ValueError:
            continue
    return None


def resolved_notice(report):
    """(subject, body) of the thank-you sent to the reader once an admin marks their report resolved."""
    note = (report.get("resolution") or "").strip()
    subject = "Your report on the Sarvamula Digital Library has been dealt with"
    lines = ["Namaste,", "", "Thank you for taking the trouble to tell us. The report you sent about:", "",
             "    %s" % (report.get("subject") or report.get("title") or report.get("feature") or "the library"), "",
             "has been looked at and marked resolved."]
    if note:
        lines += ["", "What was done:", "", "    " + note.replace("\n", "\n    ")]
    lines += ["", "If something is still wrong, please use \"Report a problem\" on that page again.", "",
              "-- Sarvamula Digital Library"]
    return subject, "\n".join(lines)


def notify_resolved(db, dry_run=False):
    """E-mail each reader whose report is resolved and who gave an address, once. Off when
    REPORT_NOTIFY_REPORTERS is 'off'. Returns how many were sent."""
    if os.environ.get("REPORT_NOTIFY_REPORTERS", "on").strip().lower() in ("off", "no", "false", "0"):
        print("reporter notices are off (REPORT_NOTIFY_REPORTERS=off)")
        return 0
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import send_report
    sent = 0
    for d in db.collection("reports").where("status", "==", "resolved").limit(200).stream():
        x = d.to_dict()
        to = (x.get("email") or "").strip()
        if x.get("notified") or "@" not in to:
            continue
        subject, body = resolved_notice(x)
        if dry_run:
            print("would notify %s: %s" % (to, x.get("subject") or d.id))
            continue
        ok, why = send_report.send_mail(subject, body, recipients=[to])
        print("notify %s: %s" % (d.id, why))
        if ok:
            db.collection("reports").document(d.id).update({"notified": True})
            sent += 1
    return sent


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from-json", default="", help="classify reports from a JSON list instead of Firestore")
    ap.add_argument("--out", default="", help="write the digest here (for send_report.py)")
    ap.add_argument("--limit", type=int, default=500)
    a = ap.parse_args(argv)

    db = None
    roles = {}
    if a.from_json:
        reports = json.load(open(a.from_json, encoding="utf-8"))
    else:
        sa = _service_account()
        if not sa:
            print("::error::no Firebase service-account secret is set (the same one deploy-firestore.yml uses)", file=sys.stderr)
            return 2
        from google.cloud import firestore  # pip install google-cloud-firestore
        db = firestore.Client.from_service_account_info(sa)
        reports = []
        for d in db.collection("reports").where("status", "==", "new").limit(a.limit).stream():
            x = d.to_dict()
            if x.get("triaged"):
                continue
            x["id"] = d.id
            x.pop("screenshot", None)               # never carried into the digest
            reports.append(x)
        for r in reports:
            uid = r.get("uid")
            if uid and uid not in roles:
                u = db.collection("users").document(uid).get()
                roles[uid] = (u.to_dict() or {}).get("role", "basic") if u.exists else "basic"
    items = classify(reports, roles)
    subject, body = digest(items, os.environ.get("REPORTS_ADMIN_URL", ""))
    print(subject)
    print(body)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(body or subject)
        open(a.out + ".subject", "w", encoding="utf-8").write(subject)
    if db is not None and not a.dry_run and items:
        for i in items:
            db.collection("reports").document(i["id"]).update(
                {"queue": i["queue"], "priority": i["priority"], "triaged": True,
                 "triagedAt": firestore.SERVER_TIMESTAMP})
        print("triaged %d report(s)" % len(items))
    notified = notify_resolved(db, a.dry_run) if db is not None else 0
    if os.environ.get("GITHUB_OUTPUT"):
        open(os.environ["GITHUB_OUTPUT"], "a").write("count=%d\nnotified=%d\n" % (len(items), notified))
    return 0


if __name__ == "__main__":
    sys.exit(main())
