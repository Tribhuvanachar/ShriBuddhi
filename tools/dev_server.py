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

    def do_GET(self):
        if self.path.startswith(PREFIX):
            return self._proxy("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith(PREFIX):
            return self._proxy("POST")
        self.send_error(405)

    def log_message(self, fmt, *args):
        # The default logs the full path, which for a proxied call would put the
        # upstream URL in the terminal. Keep it to method and status.
        sys.stderr.write("%s %s\n" % (self.command, args[1] if len(args) > 1 else ""))


def main() -> int:
    if os.environ.get(KEY_ENV):
        print(f"{KEY_ENV} found — {PREFIX}… proxies to {UPSTREAM} (Sarvam bills per page)")
    else:
        print(f"{KEY_ENV} not set — pages load, {PREFIX}… returns 503")
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
