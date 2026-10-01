#!/usr/bin/env python3
"""
send_report.py -- the weekly watcher report, by e-mail to the superadmins.

Recipients: the SUPERADMIN_EMAILS environment variable (comma-separated; set it as an Actions
variable or secret). Roles live in Firestore, not in the repository, so the list cannot be read
from here and is not stored here.

Transport: SMTP, from SMTP_HOST / SMTP_PORT (default 587, STARTTLS) / SMTP_USER / SMTP_PASSWORD /
SMTP_FROM. A Gmail account with an app password works (smtp.gmail.com:587).

When mail cannot be sent (no recipients, no SMTP settings, or the server refuses) the report is NOT
lost: it is written to the step summary and, with --issue, opened as (or added to) a GitHub issue
labelled `watch-report`, and this script says plainly that e-mail was not sent. It exits 0 either way
unless --require-email is given.

    python3 tools/watch/send_report.py --subject "Weekly source watch" --body report.md [--issue]
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.request
from email.message import EmailMessage


def send_mail(subject, body, recipients=None):
    """recipients=None -> the superadmins (SUPERADMIN_EMAILS); a list -> exactly those addresses."""
    to = list(recipients) if recipients is not None else \
        [e.strip() for e in os.environ.get("SUPERADMIN_EMAILS", "").replace(";", ",").split(",") if e.strip()]
    host = os.environ.get("SMTP_HOST", "")
    if not to:
        return False, "no recipients (SUPERADMIN_EMAILS is not set)"
    if not host:
        return False, "SMTP_HOST is not set"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "watch@localhost"
    msg["To"] = ", ".join(to)
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=60) as s:
            s.starttls(context=ssl.create_default_context())
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
    except Exception as exc:                                       # noqa: BLE001
        return False, "SMTP failed: %s" % str(exc)[:160]
    return True, "sent to %d recipient(s)" % len(to)


def open_issue(subject, body):
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (repo and tok):
        return "no GitHub context for an issue"
    req = urllib.request.Request(
        "https://api.github.com/repos/%s/issues" % repo,
        data=json.dumps({"title": subject, "body": body[:60000], "labels": ["watch-report"]}).encode(),
        headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "sarvamula-watch"}, method="POST")
    try:
        return "issue %s" % json.load(urllib.request.urlopen(req, timeout=60)).get("html_url", "opened")
    except Exception as exc:                                       # noqa: BLE001
        return "issue failed: %s" % str(exc)[:100]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", required=True, help="markdown/text file")
    ap.add_argument("--issue", action="store_true", help="when e-mail cannot be sent, open an issue instead")
    ap.add_argument("--require-email", action="store_true")
    a = ap.parse_args(argv)
    body = open(a.body, encoding="utf-8").read()
    ok, why = send_mail(a.subject, body)
    print("e-mail:", why)
    line = "E-mail report: %s." % why
    if not ok and a.issue:
        line += " Filed instead as %s." % open_issue(a.subject, body + "\n\n---\n" + line)
        print(line)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        open(summ, "a", encoding="utf-8").write("\n" + line + "\n")
    return 0 if ok or not a.require_email else 1


if __name__ == "__main__":
    sys.exit(main())
