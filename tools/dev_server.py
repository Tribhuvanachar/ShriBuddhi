#!/usr/bin/env python3
"""Local server for the admin pages, with a Sarvam proxy the browser can call.

WHY A PROXY AND NOT A KEY IN THE PAGE. convert/ pastes a Gemini or Vision key
into localStorage and calls googleapis.com straight from the page, and that
works: Google takes the key in the query string and its CORS preflight
authorises the request. Sarvam cannot be used the same way, and the reason is
one missing response header rather than a policy:

    $ curl -X OPTIONS https://api.sarvam.ai/doc-ai/v1/job \
        -H 'Origin: http://localhost:8777' \
        -H 'Access-Control-Request-Method: POST' \
        -H 'Access-Control-Request-Headers: api-subscription-key'
    access-control-allow-origin: *
    (no access-control-allow-headers, no access-control-allow-methods)

Sarvam authenticates with a CUSTOM header, api-subscription-key. A custom
header makes the request non-simple, so the browser preflights it, and the
preflight must name that header in Access-Control-Allow-Headers or the browser
refuses to send the real request at all. It does not. Google's does.

So the page calls /sarvam/... here instead, and this adds the key on the way
out. The key comes from the environment of the shell you start this in and is
never sent to the browser, never written to disk, and never committed -- which
is better than the convert/ model, not a concession to it.

    export SARVAM_API_KEY=...
    python3 tools/dev_server.py
    # http://localhost:8777/admin/ocr-studio.html

LOCALHOST ONLY, deliberately. It binds 127.0.0.1 and refuses to start
otherwise: anything that reaches it can spend money with your key.
"""
from __future__ import annotations

import http.server
import os
import socketserver
import sys
import urllib.error
import urllib.request

import json
import subprocess
import urllib.parse

# The repository this server serves from -- the formatter endpoint confines
# every path it is handed to inside it.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PORT = int(os.environ.get("DGE_PORT", "8777"))
UPSTREAM = "https://api.sarvam.ai"
PREFIX = "/sarvam/"
KEY_ENV = "SARVAM_API_KEY"


class Handler(http.server.SimpleHTTPRequestHandler):
    def _proxy(self, method: str) -> None:
        key = os.environ.get(KEY_ENV, "")
        if not key:
            self.send_error(503, f"{KEY_ENV} is not set in this server's shell")
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        url = UPSTREAM + "/" + self.path[len(PREFIX):]
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("api-subscription-key", key)
        ct = self.headers.get("Content-Type")
        if ct:
            req.add_header("Content-Type", ct)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                payload, status = r.read(), r.status
                ctype = r.headers.get("Content-Type", "application/octet-stream")
        except urllib.error.HTTPError as e:
            payload, status, ctype = e.read(), e.code, "application/json"
        except OSError as e:
            self.send_error(502, f"upstream unreachable: {e}")
            return
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _scan(self) -> None:
        """Run a real Sarvam scan and stage it, so a page can ask for one.

        The browser cannot do this itself. Sarvam authenticates with a custom
        header and its CORS preflight does not permit one, so a fetch() to
        api.sarvam.ai never leaves the page -- which is why the studio has only
        ever REVIEWED readings and never produced them.

        The work is done by tools/sarvam_docai.py, unchanged: it already
        slices the PDF, runs the job, unpacks one entry per page and writes
        data/ocr_staging/<work>/. Reimplementing any of that in JavaScript
        would mean a second, untested copy of the one path that costs money.
        """
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self.send_error(400, "expected JSON")
            return
        pdf, pages, work = body.get("pdf"), body.get("pages"), body.get("work")
        if not (pdf and pages and work):
            self.send_error(400, "need pdf, pages and work")
            return
        if not os.path.isfile(pdf):
            self.send_error(404, f"no such PDF: {pdf}")
            return
        if not os.environ.get(KEY_ENV) and body.get("real"):
            self.send_error(503, f"{KEY_ENV} is not set in this server's shell")
            return

        cmd = [sys.executable, os.path.join("tools", "sarvam_docai.py"),
               "--pdf", pdf, "--pages", str(pages), "--work", work]
        if not body.get("real"):
            cmd.append("--dry-run")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        out = json.dumps({"ok": r.returncode == 0, "dry_run": not body.get("real"),
                          "stdout": r.stdout[-4000:], "stderr": r.stderr[-2000:]}).encode()
        self.send_response(200 if r.returncode == 0 else 500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        if self.path.startswith(PREFIX):
            return self._proxy("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith(PREFIX):
            return self._proxy("POST")
        if self.path.rstrip("/") == "/scan":
            return self._scan()
        if self.path.rstrip("/") == "/format-commentary":
            return self._format_commentary()
        self.send_error(405)

    def _format_commentary(self):
        """The commentary formatter as a service.

        Takes either pasted text or a corpus path -- a single data.json or a
        whole folder -- so the same stage serves an OCR hand-off, a scholar
        checking one grantha, and a paste from anywhere. Read-only unless
        in_place is asked for explicitly: a first look must never write.
        """
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, TypeError) as e:
            return self._json(400, {"error": f"bad request body: {e}"})

        sys.path.insert(0, os.path.join(REPO, "tools"))
        try:
            import format_commentary as FC
        except ImportError as e:
            return self._json(500, {"error": f"formatter unavailable: {e}"})

        fmt = FC.Formatter()
        text = req.get("text")
        if isinstance(text, str) and text.strip():
            events: list = []
            return self._json(200, {"mode": "text", "output": fmt.format(text, events),
                                    "events": events})

        rel = (req.get("path") or "").strip()
        if not rel:
            return self._json(400, {"error": "give either 'text' or 'path'"})
        # Confined to the repository: a path service that will open anything is
        # a file-read primitive, localhost or not.
        target = os.path.realpath(os.path.join(REPO, rel))
        if not target.startswith(os.path.realpath(REPO) + os.sep):
            return self._json(400, {"error": "path must be inside the repository"})
        if not os.path.exists(target):
            return self._json(404, {"error": f"no such path: {rel}"})

        res = FC.run_corpus(target, fmt, bool(req.get("in_place")))
        summary = [{"file": os.path.relpath(r["file"], REPO),
                    "units": r.get("units", 0), "changed": r.get("changed", 0),
                    "pratikas": sum(u["after"].count("<TP>") for u in r.get("detail", [])),
                    "paragraphs": sum(u["after"].count('<p class="rule">')
                                      for u in r.get("detail", [])),
                    "error": r.get("error")} for r in res]
        sample = []
        for r in res:
            for u in r.get("detail", [])[:3]:
                sample.append({"file": os.path.relpath(r["file"], REPO), "id": u["id"],
                               "before": u["before"], "after": u["after"],
                               "events": u["events"]})
            if len(sample) >= 12:
                break
        return self._json(200, {"mode": "corpus", "written": bool(req.get("in_place")),
                                "files": summary, "sample": sample})

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # The default logs the full path, which for a proxied call would put the
        # upstream URL in the terminal. Keep it to method and status.
        sys.stderr.write("%s %s\n" % (self.command, args[1] if len(args) > 1 else ""))


def main() -> int:
    if os.environ.get(KEY_ENV):
        print(f"{KEY_ENV} found — {PREFIX}… proxies to {UPSTREAM} (Sarvam bills per page)")
    else:
        print(f"{KEY_ENV} not set — pages load, {PREFIX}… returns 503")
    print(f"POST /scan runs tools/sarvam_docai.py (dry by default; real spends)")
    print(f"POST /format-commentary runs the commentary formatter (read-only unless in_place)")
    print(f"http://127.0.0.1:{PORT}/admin/ocr-studio.html")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
