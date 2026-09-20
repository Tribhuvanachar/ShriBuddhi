"""opaque_ids_e2e.py -- drive a real browser over a real staged site.

What this proves, and why none of it could be proved without a browser:

  * a reader finds the TEXT of an id-addressed work in search, and sees its
    title and our shelf -- never the shelf it came from
  * the row does not open, and says why
  * the id-to-path map is not on the public site at all
  * an admin on the private checkout turns the same id back into the real
    path and reads the work

Three real bugs were found by running it, each of which passed every static
check first: the resolver resolved its paths against the PAGE rather than
the site root, so a page in a subfolder 404'd in a way that looked like a
permissions failure; it built `render.html?grantha=`, which the reader
ignores, falling back to a default work and reporting "Data Not Found"; and
`index.html?path=`, which is what global-search.js's own readerBase()
produces, loads the LANDING page at the site root rather than the reader.

    python3 tools/e2e/opaque_ids_e2e.py

Expects a staged public site on :8911 and the private checkout on :8912.
tools/e2e/README.md has the four commands that build them.
"""
import json, re, sys, time
from playwright.sync_api import sync_playwright

PUB = "http://127.0.0.1:8911"
PRIV = "http://127.0.0.1:8912"
SHOTS = "/tmp/claude-0/-home-user/f096de45-3b33-5824-92bd-ebc61fbb8b8b/scratchpad/shots"
PRIVATE_NAMES = ["DvaitaVedantaIn", "Anandamakaranda", "RamanujaMeghamala",
                 "dvaitavedanta.in", "anandamakaranda"]
QUERY = "जयन्ती"
results = []
VANDANA = """
try {
  sessionStorage.setItem('dge_vandana_passed','1');
  var d=new Date(), m=d.getMonth()+1, day=d.getDate();
  localStorage.setItem('dge_vandana_day', d.getFullYear()+'-'+(m<10?'0':'')+m+'-'+(day<10?'0':'')+day);
} catch(e){}
// Read the index we just built, not the 330 MB one on the CDN. The comment
// at the top of global-search.js says exactly this is what the variable is
// for, and the staged copy has to be what is tested -- the CDN index was
// built before the rewrite and still carries real paths.
// Two mechanisms, because the pages differ. Pages that load js/config.js get
// their index base from it, and config.js prefers this localStorage override
// (that is what it is for). Pages that do NOT load config.js -- the vyakarana
// ones -- read window.DGE_SEARCH_INDEX directly. Setting only one leaves half
// the site pointed at the 330 MB CDN index, which was built before the
// rewrite and still carries real paths.
try { localStorage.setItem('search_index_base_override', '/search_index'); } catch (e) {}
window.DGE_SEARCH_INDEX = '/search_index';
"""


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + ((" -- " + detail) if detail else ""))

with sync_playwright() as pw:
    br = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox","--disable-dev-shm-usage"])

    # ---------- 1. reader on the published site ----------
    ctx = br.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_init_script(VANDANA)
    page = ctx.new_page()
    seen_urls = []
    page.on("request", lambda r: seen_urls.append(r.url))
    toasts = []
    page.on("console", lambda m: None)
    page.goto(PUB + "/vyakarana/dhatu.html", wait_until="load")
    page.wait_for_timeout(2500)

    check("opaque-resolve.js loaded on the public site",
          page.evaluate("typeof window.dgeIsOpaqueId === 'function'"))
    check("private-names.js is NOT served publicly",
          page.evaluate("typeof window.DGE_PRIVATE_PASCAL_CASE === 'undefined'"))
    check("reader is not treated as admin",
          page.evaluate("window.dgeOpaqueIsAdmin() === false"))

    # display.json resolves an id to a title with no path
    disp = page.evaluate("""async () => {
        const r = await fetch('../data/display.json'); const d = await r.json();
        const k = Object.keys(d.works)[0];
        return {key: k, val: d.works[k], n: Object.keys(d.works).length};
    }""")
    check("display.json gives a title and a shelf, never a path",
          disp["val"].get("public_path") is None and bool(disp["val"].get("title")),
          "%d works, e.g. %s -> %s / %s" % (disp["n"], disp["key"],
                                            disp["val"]["title"], disp["val"]["shelf"]))

    # the id map must be unreachable
    mapstat = page.evaluate("""async () => {
        try { const r = await fetch('../admin/config/opaque_ids.json'); return r.status; }
        catch (e) { return 'blocked'; }
    }""")
    check("the id-to-path map is not on the public site", mapstat == 404, "HTTP %s" % mapstat)

    resolved = page.evaluate("""async () => {
        try { return {ok: true, v: await window.dgeOpaqueResolve('id:r3vpjcdt')}; }
        catch (e) { return {ok: false, v: e.message}; }
    }""")
    check("a reader cannot resolve an id to a path",
          resolved["ok"] is False, resolved["v"])

    # run the real search
    page.evaluate("window.DGEGlobalSearch.open(%s)" % json.dumps(QUERY))
    page.wait_for_timeout(6000)
    try:
        page.wait_for_selector(".dge-gs-row", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(2000)
    rows = page.query_selector_all(".dge-gs-row")
    check("the search returns hits from an id-addressed work", len(rows) > 0,
          "%d row(s)" % len(rows))
    page.wait_for_timeout(1500)
    crumb = page.evaluate("""() => {
        const el = document.querySelector('.dge-gs-crumbs-opaque');
        return el ? {text: el.innerText.replace(/\\s+/g,' ').trim(),
                     shelf: !!el.querySelector('.dge-gs-crumb-shelf')} : null;
    }""")
    check("an id-addressed hit shows its real title and our shelf, not 'mula'",
          bool(crumb) and crumb["shelf"] and "mula" != crumb["text"],
          (crumb or {}).get("text"))
    page.screenshot(path=SHOTS + "/1-reader-search-results.png", full_page=False)

    html = page.content()
    leaked = [n for n in PRIVATE_NAMES if n.lower() in html.lower()]
    check("no private shelf name anywhere in the reader's DOM", not leaked, str(leaked))

    opaque_rows = page.evaluate(
        "Array.from(document.querySelectorAll('.dge-gs-row'))"
        ".filter(r => (r.getAttribute('data-slug')||'').indexOf('id:')===0).length")
    check("id-addressed hits are present and addressed by id", opaque_rows > 0,
          "%d of %d" % (opaque_rows, len(rows)))
    check("an id-addressed row renders no clickable breadcrumb path",
          page.evaluate("document.querySelectorAll('.dge-gs-crumbs-opaque .dge-gs-crumb-seg').length") == 0)

    # click an id row -- must refuse, not navigate
    before = page.url
    page.evaluate("""() => {
        window.__toast = null;
        window.showToast = (m) => { window.__toast = m; };
        const r = Array.from(document.querySelectorAll('.dge-gs-row'))
          .find(r => (r.getAttribute('data-slug')||'').indexOf('id:')===0);
        if (r) r.click(); else window.__toast = null;
    }""")
    page.wait_for_timeout(1500)
    toast = page.evaluate("window.__toast")
    check("clicking an id-addressed hit refuses instead of navigating",
          page.url == before and bool(toast), str(toast))
    page.screenshot(path=SHOTS + "/2-reader-click-refused.png")

    # --- a PUBLIC hit must open the work, from any depth of page ----------
    #
    # Regression guard. readerBase() used to rewrite the CURRENT page's last
    # segment to index.html, which was wrong twice over: from
    # /vyakarana/dhatu.html it produced /vyakarana/index.html, which does not
    # exist -- a flat 404 on every search result -- and from the root it
    # produced the LANDING page, which forwards only short-form URLs and so
    # never opened the work either.
    PUBLIC_WORD = "विजयते"
    PUBLIC_MARK = "विजयते"
    for start in ("/vyakarana/dhatu.html",
                  "/render.html?path=Tattvavada/Itara/Bhagavata_Saroddhara/mula"):
        pg = ctx.new_page()
        pg.goto(PUB + start, wait_until="load")
        pg.wait_for_timeout(4000)
        pg.evaluate("window.DGEGlobalSearch.open(%s)" % json.dumps(PUBLIC_WORD))
        pg.wait_for_timeout(9000)
        slug = pg.evaluate("""() => { const r = Array.from(document.querySelectorAll('.dge-gs-row'))
            .find(r => (r.getAttribute('data-slug')||'').indexOf('id:') !== 0);
            return r ? r.getAttribute('data-slug') : null; }""")
        if not slug:
            check("a public hit opens its work from %s" % start.split("?")[0], False,
                  "no public rows to click")
            pg.close()
            continue
        pg.evaluate("""() => { const r = Array.from(document.querySelectorAll('.dge-gs-row'))
            .find(r => (r.getAttribute('data-slug')||'').indexOf('id:') !== 0); r.click(); }""")
        pg.wait_for_timeout(7000)
        body = pg.evaluate("document.body.innerText")
        check("a public hit opens its work from %s" % start.split("?")[0],
              "render.html" in pg.url and PUBLIC_MARK in body,
              pg.url.split("8911")[-1][:60])
        if start.startswith("/vyakarana"):
            pg.screenshot(path=SHOTS + "/5-public-hit-opens.png")
        pg.close()

    net_leak = [u for u in seen_urls if any(n.lower() in u.lower() for n in PRIVATE_NAMES)]
    check("no request URL contains a private shelf name", not net_leak, str(net_leak[:3]))
    ctx.close()

    # ---------- 2. admin on the private checkout ----------
    ctx2 = br.new_context(viewport={"width": 1280, "height": 900})
    ctx2.add_init_script(VANDANA)
    p2 = ctx2.new_page()
    p2.goto(PRIV + "/vyakarana/dhatu.html", wait_until="load")
    p2.evaluate("localStorage.setItem('acharyaAuthorized','true')")
    p2.reload(wait_until="domcontentloaded")
    p2.wait_for_timeout(2500)
    check("admin is recognised on the private checkout",
          p2.evaluate("window.dgeOpaqueIsAdmin() === true"))
    check("private-names.js IS served on the private checkout",
          p2.evaluate("Array.isArray(window.DGE_PRIVATE_PASCAL_CASE)"))

    got = p2.evaluate("""async () => {
        try { return {ok:true, path: await window.dgeOpaqueResolve('id:r3vpjcdt'),
                      url: await window.dgeOpaqueReaderUrl('id:r3vpjcdt')}; }
        catch (e) { return {ok:false, path:e.message}; }
    }""")
    check("an admin resolves the id back to the real path",
          got["ok"] and "Anandamakaranda" in got.get("path", ""), got.get("path"))
    p2.screenshot(path=SHOTS + "/3-admin-resolves-id.png")

    if got["ok"]:
        p2.goto(got["url"], wait_until="domcontentloaded")
        p2.wait_for_timeout(4000)
        body = p2.evaluate("document.body.innerText")
        # Assert the WORK is on screen, not merely that the page has text.
        # A length check passed here while the page actually read "Data Not
        # Found" -- the resolver was building a URL the reader ignores.
        wanted = "रोहिण्यामर्धरात्रे"
        check("the resolved URL opens the real work for an admin",
              wanted in body and "Data Not Found" not in body,
              ("found the opening verse" if wanted in body
               else body.replace("\n", " ").strip()[:100]))
        # A first-visit "About This Project" panel sits over the reader.
        # Dismiss it so the screenshot shows the work rather than the panel.
        # Cosmetic only, and only for the screenshot: a first-visit "About
        # This Project" panel and a Quick Actions tray float over the reader.
        # Hiding fixed overlays shows the WORK, which is what this image is
        # evidence of. Nothing about the assertion above depends on it -- the
        # verse was found in document.body before any of this ran.
        p2.evaluate("""() => {
            Array.from(document.querySelectorAll('body *')).forEach(e => {
                const cs = getComputedStyle(e);
                if (cs.position !== 'fixed') return;
                const r = e.getBoundingClientRect();
                if (r.width > 180 && r.height > 120) e.style.display = 'none';
            });
        }""")
        p2.wait_for_timeout(600)
        p2.screenshot(path=SHOTS + "/4-admin-reads-the-work.png", full_page=False)
    ctx2.close()
    br.close()

print()
bad = [r for r in results if not r[1]]
print("%d checks, %d passed, %d failed" % (len(results), len(results)-len(bad), len(bad)))
sys.exit(1 if bad else 0)
