"""tools/seo: the URL grammar is collision-free over the public catalogue, labels resolve, a subset builds pages
that pass the validator's per-page checks, and every generated page carries the essentials."""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/seo"))
import taxonomy as T  # noqa: E402


def test_public_urls_unique_and_shaped():
    lib = json.load(open(ROOT / "dge/data/library.json", encoding="utf-8"))["granthas"]
    slugs = T.public_slugs(lib)
    assert len(slugs) > 500
    t = T.Taxonomy(slugs)                      # raises on a collision
    for s in slugs:
        u = t.url(s)
        assert re.match(r"^/dge/[a-z0-9\-/]+/$", u), u
        assert "_" not in u and "mula" not in u.split("/")[-2:]
    assert t.url("vedas/rigveda/shakala_shakha/samhita/mandala_01") == "/dge/veda/rigveda/samhita/mandala-1/"
    assert t.url("DvaitaVedanta/Itara/Kavya/raghavendra_vijaya/sarga_1") == "/dge/dvaitavedanta/kavya/raghavendra-vijaya/sarga-1/"
    assert t.url("itihasa/mahabharata/adi_parva/mula") == "/dge/itihasa/mahabharata/adi-parva/"
    for s in slugs:                            # nothing from the licensed corpora leaks into the public tree
        assert not s.startswith("darshana/vedanta/dvaita/DvaitaVedantaIn") and not s.startswith("darshana/vedanta/advaita")


def test_labels_and_transliteration():
    assert T.label_sa("rigveda") == "ऋग्वेदः" and T.label_en("rigveda") == "ṛgvedaḥ"
    assert T.label_sa("mandala_01").startswith("मण्डलम्") and T.label_en("sarga_3").endswith(" 3")
    assert T.slugify_segment("mandala_01") == "mandala-1" and T.slugify_segment("PrahladaKrutaNarasimha") == "prahladakrutanarasimha"


def test_subset_build_and_validate(tmp_path):
    out = tmp_path / "site"
    subprocess.run([sys.executable, str(ROOT / "tools/seo/build_seo_site.py"), "--out", str(out), "--only", "DvaitaVedanta/Itara/Kavya/raghavendra_vijaya", "--quiet"], check=True, capture_output=True)
    page = out / "dge/dvaitavedanta/kavya/raghavendra-vijaya/sarga-1/index.html"
    html = page.read_text(encoding="utf-8")
    assert '<html lang="sa">' in html and '<link rel="canonical" href="https://tribhuvanachar.github.io/bhumandala/dge/dvaitavedanta/kavya/raghavendra-vijaya/sarga-1/">' in html
    assert "<h1>" in html and 'class="sa" lang="sa"' in html and 'lang="sa-Latn"' in html and "BreadcrumbList" in html
    assert re.search(r"<title>Sarga 1 — [^<]*Rāghavendra[^<]*</title>", html, re.I) or "sargaḥ 1" in html.lower()
    assert 'href="/bhumandala/dge/index.html?path=DvaitaVedanta/Itara/Kavya/raghavendra_vijaya/sarga_1' in html   # link into the reader
    assert "?rgv1" in html                                                                              # the short address
    assert (out / "sitemap.xml").exists() and (out / "robots.txt").read_text().count("Sitemap:") == 1
    # the validator's per-page checks pass on the subset (site-wide link checks are only meaningful on a full build)
    rep = json.loads(subprocess.run([sys.executable, str(ROOT / "tools/seo/validate_seo.py"), "--site", str(out), "--report", str(tmp_path / "r.json")],
                                    capture_output=True, text=True).stdout.split("\n")[0] and (tmp_path / "r.json").read_text())
    assert rep["duplicateTitles"] == 0
    assert not [b for b in rep["blocking"] if "broken link" not in b and "missing from the sitemap" not in b and "orphan" not in b and "no page" not in b], rep["blocking"][:5]


def test_generated_index_never_lands_on_an_app_page(tmp_path):
    """The reader owns /dge/ and /dge/kavya/ (its own index.html files); generated category indexes move aside."""
    import sys, json
    sys.path.insert(0, str(ROOT / "tools" / "seo"))
    import taxonomy as T
    lib = json.load(open(ROOT / "dge/data/library.json", encoding="utf-8"))
    lib = lib["granthas"] if isinstance(lib, dict) and "granthas" in lib else lib
    t = T.Taxonomy(T.public_slugs(lib))
    assert "/dge/" in t.reserved and "/dge/kavya/" in t.reserved
    assert t.catalogue == "/dge/texts/"
    assert t.prefix_url("kavya_alankara") == "/dge/kavya/texts/"
    assert t.url("DvaitaVedanta/Itara/Kavya/raghavendra_vijaya/sarga_1") == "/dge/dvaitavedanta/kavya/raghavendra-vijaya/sarga-1/"
    assert not (set(t._urls.values()) & t.reserved)
