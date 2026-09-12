"""Offline tests for the lazy "Load More" harvest fix (1 Sep 2026).

Verified live against category-details/977/975 (maṅgalamācaraṇam of
Nyāyasudhā): the initial HTML carries one #article block (978) while the
right-hand nav lists units 979–986, served only by
GET /load-data?book_id=975&id=<unit>&search= — and exactly those eight were
absent from dge/data. These tests pin the two new helpers on fixtures shaped
like the real responses captured during that verification.

Run: python tools/dvaitavedanta/test_load_more.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dv_parse import extract_lazy_units, parse_load_fragment, parse_page  # noqa: E402

PAGE = """
<html><body>
<input type="hidden" id="category_book_id" value="975">
<input type="hidden" id="first_sutra_id" value="978">
<input type="hidden" id="total_sutra_count" value="9">
<div class="breadcrumb"><a href="/">Home</a> / <a href="/x">श्रीमन्न्यायसुधा</a> /
  <a href="/y">सुधा</a> / <a href="/z">मङ्गलमाचरणम्</a></div>
<div class="lazy-1" data-id="978" id="article978">
  <h2 class="shloka">प्रारम्भपद्यम् प्रथमम् ॥ १ ॥</h2>
  <h3>सुधा</h3><p>प्रथमव्याख्यानम् इति ।</p>
</div>
<p class="explanation-text" data-load="1" id="978"><a>१</a></p>
<p class="explanation-text" data-load="0" id="979"><a>२</a></p>
<p class="explanation-text" data-load="0" id="980"><a>३</a></p>
<a id="load_more_article" onclick="sortDescriptionBottom()">Load More</a>
</body></html>
"""

FRAGMENT = """
<hr>
<div class="lazy-1" data-id="979" id="article979">
  <p class="shloka">सुधा</p>
  <p class="details" id="dynamicContent">
    <h3><span lang="HI">सुधा</span></h3>
    <p><span lang="HI">येन प्रादुरभावि भूमिवलये व्यस्तारि गोसन्ततिः ।। २ ।।</span></p>
    <h3><span lang="HI">परिमळ</span></h3>
    <p><span lang="HI">स्वगुरुं नमति । व्याख्यानान्तरम् इति ।। २ ।।</span></p>
  </p>
</div>
"""


def test_extract_lazy_units():
    book, ids = extract_lazy_units(PAGE)
    assert book == "975", book
    # 978 appears in the list too (data-load=1, already delivered) — the
    # caller's seen_ids set is what filters it; extraction reports all.
    assert ids == ["978", "979", "980"], ids


def test_extract_lazy_units_absent():
    book, ids = extract_lazy_units("<html><body>plain page</body></html>")
    assert book is None and ids == []


def test_parse_load_fragment_inherits_page_context():
    page = parse_page(PAGE, "https://dvaitavedanta.in/category-details/977/975/sharam/sathha/managa")
    rec = parse_load_fragment(FRAGMENT, page, "979", page["url"])
    assert rec["content_id"] == "979"
    assert rec["ancestor_id"] == page["ancestor_id"]
    assert rec["breadcrumb"] == page["breadcrumb"]
    assert not rec["is_container"]
    titles = [l.get("title") for l in rec["layers"]]
    assert any("सुधा" in (t or "") for t in titles), titles
    assert any("परिमळ" in (t or "") for t in titles), titles
    body = "".join(str(l) for l in rec["layers"])
    assert "प्रादुरभावि" in body
    assert rec["url"].endswith("#article979")


def test_source_html_preserved():
    # 1 Sep 2026: records carry a sanitized copy of the site's own markup
    # (class markers, headings, bold) so a renderer can style by them.
    page = parse_page(PAGE, "https://dvaitavedanta.in/category-details/977/975/x")
    h = page["source_html"]
    assert 'class="shloka"' in h and "<h3>" in h, h
    assert "script" not in h and "data-id" not in h and "onclick" not in h
    frag = parse_load_fragment(FRAGMENT, page, "979", page["url"])
    assert 'class="lazy-1"' in frag["source_html"]
    assert "परिमळ" in frag["source_html"]


def test_empty_fragment_is_container():
    page = parse_page(PAGE, "https://dvaitavedanta.in/category-details/977/975/x")
    rec = parse_load_fragment("<div></div>", page, "981", page["url"])
    assert rec["is_container"] and rec["layers"] == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all checks passed")
