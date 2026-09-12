#!/usr/bin/env python3
"""End-to-end test of the importer with zero network.

Primes the on-disk cache with fixture HTML at the exact SHA1-of-URL keys the
Fetcher will look for, then runs main() in --write mode against a temp output
root and asserts the emitted data.json files match DGE conventions.

This also proves the cache is a real resume mechanism: if it works here with no
egress, a re-run on Actions resumes without refetching.

Run:  python tools/dvaitavedanta/test_import_offline.py
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import import_dvaitavedanta as I  # noqa: E402
from test_dv_parse import BREADCRUMB, SIDEBAR  # noqa: E402

BASE = "https://dvaitavedanta.in"


def page(layers_html, breadcrumb=BREADCRUMB):
    return f"""<html><body><nav class="navbar"><a href="/">Home</a></nav>
{breadcrumb}
<div class="row">{SIDEBAR}<div class="col-md-9 content">{layers_html}</div></div>
<footer>Copyright © 2026 Dvaita Vedanta Studies &amp; Research Foundation.</footer>
</body></html>"""


LEAF_A = page("""
  <div id="article13528"><h4>मूलम्</h4>
    <p>अशेषगुरुमीशेशं नारायणमनामयम् ।<br>सम्प्रणम्य प्रवक्ष्यामि प्रमाणानां स्वलक्षणम् ।।</p></div>
  <div id="article13530"><h4>टीका</h4>
    <p>प्रणम्यागण्यकल्याणगुणाब्धिं पुरुषोत्तमम् ।</p></div>
""")

LEAF_B = page("""
  <div id="article13531"><h4>मूलम्</h4><p>प्रमाणं द्विविधं प्रोक्तम् ।</p></div>
  <div id="article13532"><h4>टीका</h4><p>तत्र केवलमनुप्रमाणमिति ।</p></div>
  <div id="article13535"><h4>तत्त्वप्रदीपिका</h4><p>अथ प्रमाणलक्षणमुच्यते ।</p></div>
""")

CONTAINER = page("<p>No record found!!</p>")

# A container whose OWN sidebar exposes a deeper id the seed page never listed.
# This is the real Upanishad/Sutra shape: the grantha's sidebar lists
# adhyaya/adhikarana index nodes, and the text sits one level below them.
DEEP_SIDEBAR = """
<div class="sidebar-menu">
  <ul>
    <li><a href="/category-details/13528/937/thasha/1-para/managa/garana">मङ्गलाचरणम्</a></li>
    <li><a href="/category-details/13777/937/thasha/1-para/deep/deep">गूढार्थः</a></li>
  </ul>
</div>
"""
CONTAINER_WITH_CHILDREN = f"""<html><body><nav class="navbar"><a href="/">Home</a></nav>
{BREADCRUMB}
<div class="row">{DEEP_SIDEBAR}<div class="col-md-9 content"><p>No record found!!</p></div></div>
<footer>Copyright © 2026 Dvaita Vedanta Studies &amp; Research Foundation.</footer>
</body></html>"""

LEAF_DEEP = page("""
  <div id="article13777">
    <h2 class="shloka">गूढार्थबोधिनी मूलपाठः ।</h2>
    <div id="dynamicContent" class="details">
      <h3>प्रमाणलक्षणटीका</h3>
      <p>गूढार्थोऽत्र विवृतो भवति ।</p>
    </div>
  </div>
""")


# The real DOM, twice over: one page, two #article blocks, each a verse plus
# its commentary. This is the shape the probe confirmed on the live site.
MULTI_SUTRA = page("""
  <div id="article13800">
    <h2 class="shloka">प्रथमसूत्रम् इदम् उच्यते ।</h2>
    <div id="dynamicContent" class="details">
      <h3>प्रमाणलक्षणटीका</h3>
      <p>प्रथमसूत्रस्य व्याख्या इयम् ।</p>
    </div>
  </div>
  <div id="article13801">
    <h2 class="shloka">द्वितीयसूत्रम् अपि निरूप्यते ।</h2>
    <div id="dynamicContent" class="details">
      <h3>प्रमाणलक्षणटीका</h3>
      <p>द्वितीयसूत्रस्य व्याख्या इयम् ।</p>
    </div>
  </div>
""")


# dv_parse.py hardcodes the h2.shloka layer's title to the literal "मूलम्"
# regardless of which grantha's page it came from, so this fixture -- for
# karmavijaya, a later_acharyas grantha configured in dv_sources.json with
# its own acharya (Satyatmatirtha, not Madhva) -- exercises the exact real
# bug: without the fix, this "मूलम्" layer resolves against the canonical
# config entry and is misattributed to Madhva.
KARMAVIJAYA_LEAF = page("""
  <div id="article19180">
    <h2 class="shloka">कर्मणो विजयो नाम ग्रन्थ आरभ्यते ।</h2>
    <div id="dynamicContent" class="details">
      <h3>टिप्पणी</h3>
      <p>अत्र कर्मणः स्वरूपं निरूप्यते ।</p>
    </div>
  </div>
""")

# The real anuvyakhyana shape (content_id 14473, confirmed against the live
# site 25 Aug): one pada page's h2.shloka mula, followed by several h3
# ADHIKARANA-NAMED headings with no attribution verb at all -- each one is
# more of Madhva's own Anuvyakhyana verses, grouped by section, not a
# different commentator. A real attributed heading (a genuine quoted
# sub-commentary) is included too, to prove that path still gets its own
# tika folder and isn't swept into mula by the single_work fix.
ANUVYAKHYANA_LEAF = page("""
  <div id="article14473">
    <h2 class="shloka">प्रथमः पादः ।</h2>
    <div id="dynamicContent" class="details">
      <h3>जिज्ञासाधिकरणम्</h3>
      <p>ओतत्ववाची ह्योङ्कारो वक्त्यसौ तद्गुणोतताम् ॥</p>
      <h3>श्रीजयतीर्थविरचिता न्यायसुधा</h3>
      <p>अत्र जिज्ञासाशब्दार्थो विविच्यते ।</p>
    </div>
  </div>
""")


def prime(cache_dir, url, html):
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.sha1(url.encode("utf-8")).hexdigest() + ".html"
    with open(os.path.join(cache_dir, key), "w", encoding="utf-8") as handle:
        handle.write(html)


def check(name, condition, detail=""):
    mark = "ok  " if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"   {detail}" if detail and not condition else ""))
    return bool(condition)


def main():
    tmp = tempfile.mkdtemp(prefix="dvtest_")
    cache = os.path.join(tmp, "cache")
    out = os.path.join(tmp, "out")
    failures = 0

    try:
        prime(cache, BASE + "/category-details/13528/937/thasha/1-para/managa/garana", LEAF_A)
        prime(cache, BASE + "/category-details/13529/937/thasha/1-para/managa/naraya", LEAF_B)
        prime(cache, BASE + "/category-details/13533/937/thasha/1-para/lkashh/lkashh", CONTAINER)

        rc = I.main([
            "--config", os.path.join(HERE, "dv_sources.json"),
            "--out", out, "--cache", cache,
            "--granthas", "pramana_lakshana",
            "--delay", "0", "--write",
            "--fetch-date", "2026-08-15",
            "--summary-file", "",
        ])
        print()
        failures += not check("exit code 0", rc == 0, rc)

        grantha_dir = os.path.join(out, "dasha_prakarana_granthas", "pramana_lakshana")
        failures += not check("grantha dir created", os.path.isdir(grantha_dir))

        emitted = sorted(os.listdir(grantha_dir)) if os.path.isdir(grantha_dir) else []
        failures += not check("three layer folders + _meta",
                              emitted == ["_meta.json", "mula", "tika_jayatirtha",
                                          "tika_tattvapradipika"], emitted)

        mula_path = os.path.join(grantha_dir, "mula", "data.json")
        with open(mula_path, encoding="utf-8") as handle:
            mula = json.load(handle)
        failures += not check("mula top-level keys",
                              sorted(mula) == ["default_author", "items", "schema",
                                               "source_note", "source_url"], sorted(mula))
        failures += not check("mula schema", mula["schema"] == "grantha_mula_text")
        failures += not check("mula 2 items", len(mula["items"]) == 2, len(mula["items"]))
        failures += not check("licence recorded in source_note",
                              "permission" in mula["source_note"].lower())

        item = mula["items"][0]
        failures += not check("item id shape", item["id"] == "DV_13528", item["id"])
        failures += not check("per-item provenance",
                              item["source"]["url"].startswith(BASE)
                              and item["source"]["site"] == "dvaitavedanta.in"
                              and item["source"]["fetched"] == "2026-08-15")
        failures += not check("breadcrumb kept",
                              item["breadcrumb"][0] == "दशप्रकरणानि", item["breadcrumb"])
        failures += not check("devanagari text",
                              "अशेषगुरुमीशेशं" in item["sanskrit_text"])

        tika_path = os.path.join(grantha_dir, "tika_jayatirtha", "data.json")
        with open(tika_path, encoding="utf-8") as handle:
            tika = json.load(handle)
        failures += not check("tika schema", tika["schema"] == "grantha_tika_text")
        failures += not check("tika default_author",
                              tika["default_author"] == "श्रीजयतीर्थः", tika["default_author"])
        failures += not check("tika_title on items",
                              all(i.get("tika_title") == "टीका" for i in tika["items"]))
        mula_ids = {i["id"] for i in mula["items"]}
        tika_ids = {i["id"] for i in tika["items"]}
        failures += not check("tika ids match mula ids (cross-layer link)",
                              tika_ids == mula_ids, (sorted(tika_ids), sorted(mula_ids)))

        with open(os.path.join(out, "_extract_status.json"), encoding="utf-8") as handle:
            status = json.load(handle)
        entry = status["granthas"]["dasha_prakarana_granthas/pramana_lakshana"]
        failures += not check("status discovered 3", entry["discovered"] == 3, entry["discovered"])
        failures += not check("status with_text 2", entry["with_text"] == 2, entry["with_text"])
        failures += not check("status containers 1", entry["containers"] == 1, entry["containers"])
        failures += not check("status items 5", entry["items"] == 5, entry["items"])
        failures += not check("status complete", entry["status"] == "complete", entry["status"])
        failures += not check("totals rolled up", status["totals"]["items"] == 5,
                              status["totals"])
        failures += not check("mapped layers produce no unmapped warnings",
                              status["unmapped_layers"] == {}, status["unmapped_layers"])

        raw = open(mula_path, encoding="utf-8").read()
        failures += not check("ensure_ascii=False (real Devanagari on disk)",
                              "\\u" not in raw)
        failures += not check("indent=1 like importers/common.py",
                              '\n "schema"' in raw)

        # Idempotence: a second --write run must not change anything.
        before = open(mula_path, encoding="utf-8").read()
        I.main([
            "--config", os.path.join(HERE, "dv_sources.json"),
            "--out", out, "--cache", cache, "--granthas", "pramana_lakshana",
            "--delay", "0", "--write", "--fetch-date", "2026-08-15", "--summary-file", "",
        ])
        failures += not check("re-run is idempotent",
                              open(mula_path, encoding="utf-8").read() == before)

        # Dry run must write nothing.
        out2 = os.path.join(tmp, "out2")
        I.main([
            "--config", os.path.join(HERE, "dv_sources.json"),
            "--out", out2, "--cache", cache, "--granthas", "pramana_lakshana",
            "--delay", "0", "--dry-run", "--summary-file", "",
        ])
        failures += not check("dry run wrote nothing", not os.path.exists(out2))

        # The site names each commentary after its own grantha, so canonical
        # layers have to be matched on suffix. A substring rule would file
        # Keshavacharya's Vivarana under Jayatirtha's tika — two different
        # authors' works silently merged into one folder.
        print("layer name resolution")
        cfg = json.load(open(os.path.join(HERE, "dv_sources.json"),
                             encoding="utf-8"))["layers"]
        resolve = I.resolve_layer_config
        cases = [
            ("प्रमाणलक्षणटीका", "tika_jayatirtha"),
            ("प्रमाणलक्षणटीकाभावदीपः", "tika_bhavadipa"),
            ("श्री कथालक्षणटीकाभावदीपः", "tika_bhavadipa"),
            ("प्रमाणलक्षणटीकाविवरणम्", "tika_vivarana"),
            ("कथालक्षणटीकाविवरणं", "tika_vivarana"),
            ("प्रमाणलक्षणटीकावाक्यार्थकौमुदी", "tika_vakyarthakaumudi"),
            ("मूलम्", "mula"),
            # Author inside the heading. Both of these end in भाष्यटीका, so the
            # suffix rule alone filed Vamana Panditacharya's commentary into
            # Jayatirtha's folder on Shatprashnopanishad — 29 items merged under
            # the wrong author, visible only as duplicate ids.
            ("श्रीमज्जयतीर्थभिक्षुविरचिताषट्प्रश्नभाष्यटीका", "tika_jayatirtha"),
        ]
        for title, expected in cases:
            got = resolve(title, cfg)
            failures += not check(f"{title} -> {expected}",
                                  got is not None and got["folder"] == expected,
                                  got["folder"] if got else None)
        failures += not check("an unknown commentary stays unmapped, not guessed",
                              resolve("कस्यचिदपूर्वव्याख्या", cfg) is None)
        failures += not check(
            "a different author's tika is NOT filed under Jayatirtha",
            resolve("श्रीवामनपण्डिताचार्यविरचिताषट्प्रश्रभाष्यटीका", cfg) is None)
        failures += not check(
            "an unattributed heading still matches on suffix alone",
            (resolve("षट्प्रश्नभाष्यटीका", cfg) or {}).get("folder") == "tika_jayatirtha")

        # Regression: later_acharyas/nyaya_sudha's Parimaḷa sub-commentary
        # split across THREE folders -- "न्यायसुधापरिमलः" (ल), "न्यायसुधापरिम ळ"
        # (ळ + stray space), and bare "परिमळ" (no grantha-name prefix at all)
        # -- because none of these matched a canonical layer_config entry, so
        # each fell into the auto-slug fallback (build_items, not
        # resolve_layer_config) with no merging between them. layer_key's ळ->ल
        # fold plus strip_grantha_prefix's self-reference stripping now make
        # all four converge on one slug.
        print("unmapped-layer key normalisation (nyaya_sudha Parimala sub-commentary)")
        grantha_title = "श्रीमन्न्यायसुधा"
        headings = [
            "न्यायसुधापरिमलः",
            "न्यायसुधापरिम ळ",
            "परिम ळ",
            "परिमळ",
        ]
        # Compared at the SLUG level, not the raw key: slugify_devanagari
        # already drops a trailing visarga ("परिमलः" vs "परिमल"), so that
        # residual difference never reaches an actual folder name -- the
        # real guarantee this fix makes is "same folder", not "byte-
        # identical key", and the test should hold it to that, not more.
        slugs = {I.slugify_devanagari(I.strip_grantha_prefix(I.layer_key(h), grantha_title))
                 for h in headings}
        failures += not check(
            "all four heading variants slug to one folder",
            len(slugs) == 1, slugs)
        failures += not check(
            "the grantha's own title alone is left untouched, not emptied",
            I.strip_grantha_prefix(I.layer_key(grantha_title), grantha_title) == I.layer_key(grantha_title))

        # `enabled: false` keeps a grantha out of a routine sweep; naming it
        # is not a routine sweep. nyaya_sudha needs ~46h of its own, so it must
        # be reachable by name without editing the config each time.
        print("explicit selection overrides enabled: false")
        full = json.load(open(os.path.join(HERE, "dv_sources.json"), encoding="utf-8"))
        swept = {g["slug"] for g in I.select_granthas(full, None, None)}
        failures += not check("scope=all leaves nyaya_sudha out",
                              "nyaya_sudha" not in swept)
        named = [g["slug"] for g in I.select_granthas(full, ["later_acharyas"],
                                                      ["nyaya_sudha"])]
        failures += not check("naming it selects it anyway", named == ["nyaya_sudha"],
                              named)

        # Discovery must descend THROUGH containers. Run 31958553804 shipped
        # upanishad_prasthana as "10/10 complete, 0 errors" while extracting 10
        # items from 730 leaves, because the sidebar listed index nodes and the
        # crawler treated every one as a dead end.
        print("container descent")
        deep_tmp = tempfile.mkdtemp(prefix="dvdeep_")
        try:
            deep_cache = os.path.join(deep_tmp, "cache")
            deep_out = os.path.join(deep_tmp, "out")
            # Seed lists 13529/13533 only. 13777 is reachable ONLY through
            # 13533's own sidebar, so this fails unless containers are opened.
            prime(deep_cache, BASE + "/category-details/13528/937/thasha/1-para/managa/garana",
                  CONTAINER)
            prime(deep_cache, BASE + "/category-details/13529/937/thasha/1-para/managa/naraya", CONTAINER)
            prime(deep_cache, BASE + "/category-details/13533/937/thasha/1-para/lkashh/lkashh", CONTAINER_WITH_CHILDREN)
            prime(deep_cache, BASE + "/category-details/13777/937/thasha/1-para/deep/deep", LEAF_DEEP)
            rc2 = I.main([
                "--config", os.path.join(HERE, "dv_sources.json"),
                "--out", deep_out, "--cache", deep_cache,
                "--granthas", "pramana_lakshana",
                "--delay", "0", "--write", "--fetch-date", "2026-08-15",
                "--summary-file", "",
            ])
            failures += not check("exit code 0", rc2 == 0, rc2)
            deep_dir = os.path.join(deep_out, "dasha_prakarana_granthas",
                                    "pramana_lakshana", "tika_jayatirtha", "data.json")
            found = os.path.exists(deep_dir)
            failures += not check("text one level below a container is reached", found)
            if found:
                with open(deep_dir, encoding="utf-8") as handle:
                    deep = json.load(handle)
                failures += not check("deep leaf emitted its commentary",
                                      len(deep["items"]) == 1
                                      and "गूढार्थ" in deep["items"][0]["sanskrit_text"],
                                      deep["items"][:1])
        finally:
            shutil.rmtree(deep_tmp, ignore_errors=True)

        # One URL, several sutras. An adhikarana covering more than one sutra
        # serves them all from a single page, so keying items on the page's
        # content id gave every verse the same id — 11 duplicate-id errors in
        # run 32036326082, caught only by --strict after the crawl finished.
        print("multi-sutra leaf: ids come from the article, not the page")
        multi_tmp = tempfile.mkdtemp(prefix="dvmulti_")
        try:
            multi_cache = os.path.join(multi_tmp, "cache")
            multi_out = os.path.join(multi_tmp, "out")
            prime(multi_cache, BASE + "/category-details/13528/937/thasha/1-para/managa/garana",
                  MULTI_SUTRA)
            for url in ("/category-details/13529/937/thasha/1-para/managa/naraya",
                        "/category-details/13533/937/thasha/1-para/lkashh/lkashh"):
                prime(multi_cache, BASE + url, CONTAINER)
            rc3 = I.main([
                "--config", os.path.join(HERE, "dv_sources.json"),
                "--out", multi_out, "--cache", multi_cache,
                "--granthas", "pramana_lakshana",
                "--delay", "0", "--write", "--fetch-date", "2026-08-15",
                "--summary-file", "",
            ])
            failures += not check("exit code 0", rc3 == 0, rc3)
            base = os.path.join(multi_out, "dasha_prakarana_granthas", "pramana_lakshana")
            with open(os.path.join(base, "mula", "data.json"), encoding="utf-8") as handle:
                m = json.load(handle)
            with open(os.path.join(base, "tika_jayatirtha", "data.json"), encoding="utf-8") as handle:
                t = json.load(handle)
            m_ids = [i["id"] for i in m["items"]]
            t_ids = [i["id"] for i in t["items"]]
            failures += not check("both sutras emitted", len(m_ids) == 2, m_ids)
            failures += not check("ids are unique inside the layer",
                                  len(m_ids) == len(set(m_ids)), m_ids)
            failures += not check("ids follow the article, not the page",
                                  set(m_ids) == {"DV_13800", "DV_13801"}, m_ids)
            failures += not check("cross-layer link survives", set(t_ids) == set(m_ids),
                                  (t_ids, m_ids))
        finally:
            shutil.rmtree(multi_tmp, ignore_errors=True)

        print()
        print("later_acharyas mula is attributed to its own configured acharya, not Madhva")
        ka_tmp = tempfile.mkdtemp(prefix="dvkarma_")
        try:
            ka_cache = os.path.join(ka_tmp, "cache")
            ka_out = os.path.join(ka_tmp, "out")
            prime(ka_cache, BASE + "/category-details/19180/19173/sharas/karama/managa",
                  KARMAVIJAYA_LEAF)
            rc4 = I.main([
                "--config", os.path.join(HERE, "dv_sources.json"),
                "--out", ka_out, "--cache", ka_cache,
                "--granthas", "karmavijaya",
                "--delay", "0", "--write",
                "--fetch-date", "2026-08-15",
                "--summary-file", "",
            ])
            failures += not check("exit code 0", rc4 == 0, rc4)
            ka_mula = os.path.join(ka_out, "later_acharyas", "karmavijaya", "mula", "data.json")
            with open(ka_mula, encoding="utf-8") as handle:
                km = json.load(handle)
            failures += not check(
                "mula attributed to karmavijaya's own acharya (Satyatmatirtha)",
                km.get("default_author") == "श्रीसत्यात्मतीर्थः", km.get("default_author"))
            failures += not check(
                "NOT the canonical Madhva default the raw heading match would give",
                km.get("default_author") != "श्रीमदानन्दतीर्थभगवत्पादाचार्यः", km.get("default_author"))
        finally:
            shutil.rmtree(ka_tmp, ignore_errors=True)

        print()
        print("single_work: true folds unattributed adhikarana headings into mula, "
              "not a fake tika folder per heading")
        av_tmp = tempfile.mkdtemp(prefix="dvanuvy_")
        try:
            av_cache = os.path.join(av_tmp, "cache")
            av_out = os.path.join(av_tmp, "out")
            prime(av_cache, BASE + "/category-details/14473/563/satara/2-anav/parath/parath",
                  ANUVYAKHYANA_LEAF)
            rc5 = I.main([
                "--config", os.path.join(HERE, "dv_sources.json"),
                "--out", av_out, "--cache", av_cache,
                "--granthas", "anuvyakhyana",
                "--delay", "0", "--write",
                "--fetch-date", "2026-08-15",
                "--summary-file", "",
            ])
            failures += not check("exit code 0", rc5 == 0, rc5)
            av_grantha = os.path.join(av_out, "sutra_prasthana", "anuvyakhyana")
            emitted_av = sorted(os.listdir(av_grantha)) if os.path.isdir(av_grantha) else []
            failures += not check(
                "no tika_jijnasadhikaranam folder minted for the unattributed heading",
                "tika_jijnasadhikaranam" not in emitted_av, emitted_av)
            failures += not check(
                "the real attributed sub-commentary still gets its own tika folder",
                any(e.startswith("tika_") for e in emitted_av), emitted_av)
            av_mula_path = os.path.join(av_grantha, "mula", "data.json")
            with open(av_mula_path, encoding="utf-8") as handle:
                av_mula = json.load(handle)
            av_texts = "\n".join(i["sanskrit_text"] for i in av_mula["items"])
            failures += not check(
                "the adhikarana's own verse text landed inside mula",
                "ओतत्ववाची" in av_texts, av_texts[:200])
            failures += not check(
                "mula still has more than one item (shloka + folded adhikarana, "
                "disambiguated ids, not silently overwritten)",
                len(av_mula["items"]) >= 2, len(av_mula["items"]))
        finally:
            shutil.rmtree(av_tmp, ignore_errors=True)

        print()
        if failures:
            print(f"{failures} check(s) FAILED")
            return 1
        print("all checks passed")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
