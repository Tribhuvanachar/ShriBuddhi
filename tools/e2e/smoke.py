#!/usr/bin/env python3
"""smoke.py -- walk the site as a reader and report what breaks.

Not a unit test and not a replacement for one. It opens each page the way a
visitor would, waits for it to settle, and reports three things per page:

  * did it stay where it was sent, or bounce somewhere else
  * did it render anything a reader would call content
  * what did it fail to load, and what did the console complain about

Console noise is filtered to what a reader could notice. Fonts, analytics
and CDN assets blocked by this sandbox's proxy are not the site's fault and
would drown the signal.

    python3 tools/e2e/smoke.py --base http://127.0.0.1:8912
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from playwright.sync_api import sync_playwright

VANDANA = """
try {
  sessionStorage.setItem('dge_vandana_passed','1');
  var d=new Date(), m=d.getMonth()+1, day=d.getDate();
  localStorage.setItem('dge_vandana_day', d.getFullYear()+'-'+(m<10?'0':'')+m+'-'+(day<10?'0':'')+day);
} catch(e){}
"""

# Third-party hosts this sandbox blocks. Their failures say nothing about
# whether the site works.
EXTERNAL = re.compile(r"fonts\.(googleapis|gstatic)\.com|gstatic\.com|googletagmanager|"
                      r"google-analytics|cdnjs\.cloudflare\.com|jsdelivr\.net|firebasejs|"
                      r"firebaseio|googleapis\.com/identitytoolkit")

PAGES = [
    ("/", "landing"),
    ("/index.html", "landing (explicit)"),
    ("/render.html?path=Tattvavada/Itara/DasaSahitya/harikathamrutasara", "reader: HKS"),
    ("/render.html?path=Tattvavada/Itara/Kavya/raghavendra_vijaya/sarga_1", "reader: RV sarga 1"),
    ("/kosha2.html", "kosha"),
    ("/vyakarana/dhatu.html", "dhatupatha"),
    ("/vyakarana/ashtadhyayi.html", "ashtadhyayi"),
    ("/dasa-sahitya/index.html", "dasa sahitya"),
    ("/guru-parampara/index.html", "guru parampara"),
    ("/kavya/index.html", "kavya"),
    ("/tirtha/index.html", "tirtha"),
    ("/dvaita-grantha-anukramani/index.html", "anukramani"),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--base", default="http://127.0.0.1:8912")
    ap.add_argument("--shots", default="")
    ap.add_argument("--wait", type=int, default=7000)
    args = ap.parse_args(argv)

    bad = 0
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = br.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_init_script(VANDANA)

        print("%-30s %-8s %-7s %s" % ("page", "text", "own4xx", "notes"))
        print("-" * 96)
        for path, label in PAGES:
            p = ctx.new_page()
            own4xx, console = [], []
            p.on("response", lambda r: own4xx.append("%d %s" % (r.status, r.url.split("/")[-1][:34]))
                 if r.status >= 400 and not EXTERNAL.search(r.url) else None)
            p.on("console", lambda m: console.append(m.text[:80])
                 if m.type == "error" and not EXTERNAL.search(m.text) else None)
            try:
                p.goto(args.base + path, wait_until="load", timeout=45000)
            except Exception as e:
                print("%-30s %-8s %-7s NAVIGATION FAILED: %s" % (label, "-", "-", str(e)[:40]))
                bad += 1
                p.close()
                continue
            p.wait_for_timeout(args.wait)
            text = p.evaluate("document.body.innerText").strip()
            moved = "" if path.split("?")[0] in p.url or path == "/" else "-> " + p.url.split("/")[-1][:24]
            broken = ("could not load" in text.lower() or "not found" in text.lower()
                      or "error code" in text.lower())
            ok = len(text) > 120 and not broken
            note = []
            if moved:
                note.append(moved)
            if broken:
                note.append("PAGE REPORTS AN ERROR")
            if own4xx:
                note.append("|".join(sorted(set(own4xx))[:2]))
            if console:
                note.append("console: " + console[0][:40])
            print("%-30s %-8s %-7d %s" % (label, "%d ch" % len(text), len(set(own4xx)),
                                          "  ".join(note)[:52]))
            if not ok:
                bad += 1
            if args.shots:
                p.screenshot(path="%s/smoke-%s.png" % (args.shots,
                                                       re.sub(r"[^a-z0-9]+", "-", label.lower())))
            p.close()
        br.close()

    print("\n%d of %d page(s) did not render as a reader would expect" % (bad, len(PAGES)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
