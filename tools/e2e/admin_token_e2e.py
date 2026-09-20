"""admin_token_e2e.py -- the two things only a token holder may do.

Two capabilities, two modes each:

  1. a copyright-gated commentary (the Kannada Mahabharata, 18 works and
     84,138 units) is hidden from a reader and shown to a super admin
  2. an opaque id resolves to a real path -- refused for a reader, and on
     the PUBLISHED site done through the GitHub API with the admin's token

ABOUT THE TOKEN. No real GitHub credential is used and none is needed. The
point of the exercise is whether the browser sends the token through the
real code path, so api.github.com is intercepted by a stub that behaves the
way GitHub does: 401 without an Authorization header, and the raw file with
one. That is a stronger test than a live call would be, because it ASSERTS
the header was sent rather than inferring it from a 200. A live call would
also prove only that somebody's token works today.

    python3 tools/e2e/admin_token_e2e.py

Expects the staged public site on :8911 and the private checkout on :8912 --
see tools/e2e/README.md.
"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

PUB = "http://127.0.0.1:8911"
PRIV = "http://127.0.0.1:8912"
SHOTS = os.environ.get("DGE_E2E_SHOTS", "/tmp/dge-e2e-shots")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GATED_WORK = "itihasa/mahabharata_kannada/mausala_parva"
GATED_TEXT = "ಜನಮೇಜಯ ಹೇ ಭಗವನ್"
OPAQUE_ID = None                      # filled from the id map below
FAKE_TOKEN = "github_pat_TESTONLY_not_a_real_credential"

VANDANA = """
try {
  sessionStorage.setItem('dge_vandana_passed','1');
  var d=new Date(), m=d.getMonth()+1, day=d.getDate();
  localStorage.setItem('dge_vandana_day', d.getFullYear()+'-'+(m<10?'0':'')+m+'-'+(day<10?'0':'')+day);
  localStorage.setItem('search_index_base_override','/search_index');
} catch(e){}
window.DGE_SEARCH_INDEX = '/search_index';
"""
AS_ADMIN = """
try {
  localStorage.setItem('brahmabuddhi_pat', %s);
  localStorage.setItem('is_superadmin','true');
  localStorage.setItem('acharyaAuthorized','true');
} catch(e){}
""" % json.dumps(FAKE_TOKEN)

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("  PASS  " if ok else "  FAIL  ") + name + ((" -- " + detail) if detail else ""))


def hide_overlays(page):
    page.evaluate("""() => {
        Array.from(document.querySelectorAll('body *')).forEach(e => {
            const cs = getComputedStyle(e);
            if (cs.position !== 'fixed') return;
            const r = e.getBoundingClientRect();
            if (r.width > 180 && r.height > 120) e.style.display = 'none';
        });
    }""")


def main():
    global OPAQUE_ID
    ids = json.load(open(os.path.join(REPO, "admin", "config", "opaque_ids.json"),
                         encoding="utf-8"))
    # An id whose work is actually in the staged fixture, so the resolve has
    # something real on the other end.
    for oid, path in ids["by_id"].items():
        if "jayanti_nirnaya" in path:
            OPAQUE_ID = "id:" + oid
            break
    if not OPAQUE_ID:
        print("no id for the fixture work; run tools/e2e/make_fixture.py first")
        return 2

    map_raw = json.dumps(ids, ensure_ascii=False)
    seen_auth = {"with": 0, "without": 0}

    def github_stub(route, request):
        """Behaves like api.github.com for the one call the site makes."""
        auth = request.headers.get("authorization", "")
        if not auth.startswith("token "):
            seen_auth["without"] += 1
            return route.fulfill(status=401, content_type="application/json",
                                 body='{"message":"Requires authentication"}')
        seen_auth["with"] += 1
        if "opaque_ids.json" in request.url:
            return route.fulfill(status=200, content_type="application/json", body=map_raw)
        return route.fulfill(status=404, content_type="application/json",
                             body='{"message":"Not Found"}')

    os.makedirs(SHOTS, exist_ok=True)
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            args=["--no-sandbox", "--disable-dev-shm-usage"])

        # ---- 1. the gated commentary, both modes, on the PUBLISHED site ----
        for label, extra, shot in (("reader", "", "6-reader-no-gated-commentary.png"),
                                   ("admin", AS_ADMIN, "7-admin-sees-gated-commentary.png")):
            ctx = br.new_context(viewport={"width": 1280, "height": 950})
            ctx.add_init_script(VANDANA + extra)
            p = ctx.new_page()
            p.goto(PUB + "/render.html?path=" + GATED_WORK, wait_until="load")
            # Wait on a real signal, not a stopwatch. The reader paints the
            # verses first and builds the commentary bar after, so a fixed
            # sleep made the admin case fail intermittently by querying the
            # bar before it existed -- which reads exactly like the gate
            # being shut, and is the opposite of what was happening.
            try:
                p.wait_for_selector(".dge-cbar-pill" if extra else "body", timeout=20000)
            except Exception:
                pass
            p.wait_for_timeout(2500)
            pills = p.evaluate(
                "Array.from(document.querySelectorAll('.dge-cbar-pill')).map(e=>e.textContent.trim())")
            kannada_pill = [x for x in pills if re.search("kannada", x, re.I)]
            if kannada_pill:
                p.evaluate("""() => { const b = Array.from(document.querySelectorAll('.dge-cbar-pill'))
                    .find(e => /kannada/i.test(e.textContent||'')); if (b) b.click(); }""")
                p.wait_for_timeout(3500)
            body = p.evaluate("document.body.innerText")
            if label == "reader":
                check("a reader is offered no gated commentary", not kannada_pill, str(pills))
                check("a reader never receives the gated text", GATED_TEXT not in body)
            else:
                check("an admin is offered the gated commentary", bool(kannada_pill),
                      kannada_pill[0] if kannada_pill else "")
                check("the offer says it is admin only",
                      bool(kannada_pill) and "admin only" in kannada_pill[0].lower())
                check("an admin reads the gated text", GATED_TEXT in body)
            hide_overlays(p)
            p.wait_for_timeout(600)
            p.screenshot(path=os.path.join(SHOTS, shot))
            ctx.close()

        # ---- 2. resolving an id on the PUBLISHED site, through the API -----
        ctx = br.new_context(viewport={"width": 1280, "height": 950})
        ctx.add_init_script(VANDANA)
        ctx.route("https://api.github.com/**", github_stub)
        p = ctx.new_page()
        p.goto(PUB + "/vyakarana/dhatu.html", wait_until="load")
        p.wait_for_timeout(3000)
        r = p.evaluate("""async (id) => {
            try { return {ok: true, v: await window.dgeOpaqueResolve(id)}; }
            catch (e) { return {ok: false, v: e.message}; }
        }""", OPAQUE_ID)
        check("without a token, the published site cannot resolve an id",
              r["ok"] is False, r["v"])
        ctx.close()

        ctx = br.new_context(viewport={"width": 1280, "height": 950})
        ctx.add_init_script(VANDANA + AS_ADMIN)
        ctx.route("https://api.github.com/**", github_stub)
        p = ctx.new_page()
        p.goto(PUB + "/vyakarana/dhatu.html", wait_until="load")
        p.wait_for_timeout(3000)
        r = p.evaluate("""async (id) => {
            try { return {ok: true, path: await window.dgeOpaqueResolve(id),
                          url: await window.dgeOpaqueReaderUrl(id)}; }
            catch (e) { return {ok: false, path: e.message}; }
        }""", OPAQUE_ID)
        check("with a token, the published site resolves the id through the API",
              r["ok"] and "jayanti_nirnaya" in r.get("path", ""), r.get("path"))
        check("the browser actually sent an Authorization header",
              seen_auth["with"] > 0,
              "authorized calls=%d, unauthorized=%d" % (seen_auth["with"], seen_auth["without"]))
        if r["ok"]:
            p.screenshot(path=os.path.join(SHOTS, "8-public-site-token-resolve.png"))
        ctx.close()
        br.close()

    print()
    bad = [x for x in results if not x[1]]
    print("%d checks, %d passed, %d failed" % (len(results), len(results) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
