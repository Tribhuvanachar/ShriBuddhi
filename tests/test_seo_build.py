"""tools/seo: the URL grammar is collision-free over the public catalogue, labels resolve, a subset builds pages
that pass the validator's per-page checks, and every generated page carries the essentials."""
import json, re, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/seo"))
import taxonomy as T  # noqa: E402

# The SEO build reads the reader app's own hand-written index.html files — to
# know which public URLs are already taken, and to place the catalogue beside
# them. Those pages used to live only in the public repository, so these two
# tests skipped themselves here and the note left behind said: "the day
# tools/seo moves, or is given a site root to point at, they are the tests that
# say whether it still works."
#
# 17 Sep 2026, that day. The site shell came into this repository, the skip
# lifted, and the first thing the test did on waking was fail — it had a
# canonical URL under tribhuvanachar.github.io/bhumandala frozen into it, two
# repository names and one host out of date. Which is the argument for leaving
# a skipped test in place rather than deleting it.
#
# The expectation is no longer written down twice. It is read from the same
# seo.json the builder reads, so the next move of origin or prefix cannot leave
# this file behind.
SEO = json.load(open(ROOT / "admin/config/seo.json", encoding="utf-8"))
ORIGIN = SEO["siteOrigin"].rstrip("/") + SEO.get("sitePrefix", "")

# (Note the only other index.html here is tools/audio_admin/templates/index.html,
# a Flask template that reserved_urls() already mistakes for a reserved public
# URL — worth excluding there.)
NEEDS_SITE_TREE = not (ROOT / "index.html").exists()
needs_site = pytest.mark.skipif(
    NEEDS_SITE_TREE,
    reason="needs the reader app's index.html tree")


def test_public_urls_unique_and_shaped():
    lib = json.load(open(ROOT / "data/library.json", encoding="utf-8"))["granthas"]
    slugs = T.public_slugs(lib)
    assert len(slugs) > 500
    t = T.Taxonomy(slugs)                      # raises on a collision
    for s in slugs:
        u = t.url(s)
        assert re.match(r"^/[a-z0-9\-/]+/$", u), u
        assert "_" not in u and "mula" not in u.split("/")[-2:]
    assert t.url("vedas/rigveda/shakala_shakha/samhita/mandala_01") == "/veda/rigveda/samhita/mandala-1/"
    # 14 Sep 2026: the shelf renamed DvaitaVedanta -> Tattvavada and its public
    # URL root moved with it. Safe only because seo.json still has
    # canonicalLive: false -- no canonical URL was ever published under
    # /dvaitavedanta/ for a search engine to have indexed. Once that flips, a
    # rename here needs redirects, not an edited expectation.
    assert t.url("Tattvavada/Itara/Kavya/raghavendra_vijaya/sarga_1") == "/tattvavada/kavya/raghavendra-vijaya/sarga-1/"
    assert t.url("itihasa/mahabharata/adi_parva/mula") == "/itihasa/mahabharata/adi-parva/"
    for s in slugs:                            # nothing from the licensed corpora leaks into the public tree
        assert not s.startswith("darshana/vedanta/dvaita/DvaitaVedantaIn") and not s.startswith("darshana/vedanta/advaita")


def test_labels_and_transliteration():
    assert T.label_sa("rigveda") == "ऋग्वेदः" and T.label_en("rigveda") == "ṛgvedaḥ"
    assert T.label_sa("mandala_01").startswith("मण्डलम्") and T.label_en("sarga_3").endswith(" 3")
    assert T.slugify_segment("mandala_01") == "mandala-1" and T.slugify_segment("PrahladaKrutaNarasimha") == "prahladakrutanarasimha"


@needs_site
def test_subset_build_and_validate(tmp_path):
    out = tmp_path / "site"
    subprocess.run([sys.executable, str(ROOT / "tools/seo/build_seo_site.py"), "--out", str(out), "--only", "Tattvavada/Itara/Kavya/raghavendra_vijaya", "--quiet"], check=True, capture_output=True)
    page = out / "tattvavada/kavya/raghavendra-vijaya/sarga-1/index.html"
    html = page.read_text(encoding="utf-8")
    canonical = '<link rel="canonical" href="%s/tattvavada/kavya/raghavendra-vijaya/sarga-1/">' % ORIGIN
    assert '<html lang="sa">' in html and canonical in html, canonical
    assert "<h1>" in html and 'class="sa" lang="sa"' in html and 'lang="sa-Latn"' in html and "BreadcrumbList" in html
    assert re.search(r"<title>Sarga 1 — [^<]*Rāghavendra[^<]*</title>", html, re.I) or "sargaḥ 1" in html.lower()
    reader = 'href="%srender.html?path=Tattvavada/Itara/Kavya/raghavendra_vijaya/sarga_1' % (SEO.get("sitePrefix", "") + "/")
    assert reader in html, reader                                                                       # link into the reader
    assert "?rgv1" in html                                                                              # the short address
    assert (out / "sitemap.xml").exists() and (out / "robots.txt").read_text().count("Sitemap:") == 1
    # The validator's PER-PAGE checks pass on the subset; its site-wide ones cannot,
    # because a subset is not a site. Broken links, sitemap membership, orphans and
    # "no page" were already discounted for that reason. "catalogue root /texts/ was
    # not generated" belongs in the same list and was missing only because this test
    # spent its life skipped and never met a real report: --only builds one work, and
    # the catalogue root indexes all of them.
    rep = json.loads(subprocess.run([sys.executable, str(ROOT / "tools/seo/validate_seo.py"), "--site", str(out), "--report", str(tmp_path / "r.json")],
                                    capture_output=True, text=True).stdout.split("\n")[0] and (tmp_path / "r.json").read_text())
    assert rep["duplicateTitles"] == 0
    assert not [b for b in rep["blocking"] if "broken link" not in b and "missing from the sitemap" not in b and "orphan" not in b and "no page" not in b
                   and "catalogue root" not in b], rep["blocking"][:5]


@needs_site
def test_generated_index_never_lands_on_an_app_page(tmp_path):
    """The reader owns / and /kavya/ (its own index.html files); generated category indexes move aside."""
    import sys, json
    sys.path.insert(0, str(ROOT / "tools" / "seo"))
    import taxonomy as T
    lib = json.load(open(ROOT / "data/library.json", encoding="utf-8"))
    lib = lib["granthas"] if isinstance(lib, dict) and "granthas" in lib else lib
    t = T.Taxonomy(T.public_slugs(lib))
    assert "/" in t.reserved and "/kavya/" in t.reserved
    assert t.catalogue == "/texts/"
    assert t.prefix_url("kavya_alankara") == "/kavya/texts/"
    assert t.url("Tattvavada/Itara/Kavya/raghavendra_vijaya/sarga_1") == "/tattvavada/kavya/raghavendra-vijaya/sarga-1/"
    assert not (set(t._urls.values()) & t.reserved)
