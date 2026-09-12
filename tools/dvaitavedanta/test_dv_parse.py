#!/usr/bin/env python3
"""Fixture tests for dv_parse.

The Cowork sandbox has no network egress to dvaitavedanta.in, so these fixtures
reproduce the two markup shapes the parser must survive:
  A. anchored  — commentary layers carry id="article<N>"  (primary path)
  B. plain     — layers are just headings + prose         (fallback path)

Run:  python tools/dvaitavedanta/test_dv_parse.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dv_parse as P

SIDEBAR = """
<div class="sidebar-menu">
  <ul>
    <li><a href="/category-details/13528/937/thasha/1-para/managa/garana">मङ्गलाचरणम्</a></li>
    <li><a href="/category-details/13529/937/thasha/1-para/managa/naraya">नारायणम्</a></li>
    <li><a href="/category-details/13533/937/thasha/1-para/lkashh/lkashh">लक्षणम्</a></li>
  </ul>
</div>
"""

BREADCRUMB = """
<ol class="breadcrumb">
  <li><a href="/">Home</a></li>
  <li><a href="/category-details/937/937/thasha">दशप्रकरणानि</a></li>
  <li><a href="/category-details/13524/937/thasha/1-para">1. प्रमाणलक्षणम्</a></li>
  <li class="active">मङ्गलाचरणम्</li>
</ol>
"""

PAGE_ANCHORED = f"""
<html><head><meta name="csrf-token" content="AZrHEzilK85TAa6"></head><body>
<nav class="navbar"><a href="/">Home</a><a href="/about">About</a></nav>
{BREADCRUMB}
<div class="row">
  {SIDEBAR}
  <div class="col-md-9 content">
    <div id="article13528">
      <h4>मूलम्</h4>
      <p>अशेषगुरुमीशेशं नारायणमनामयम् ।<br>
         सम्प्रणम्य प्रवक्ष्यामि प्रमाणानां स्वलक्षणम् ।।</p>
    </div>
    <div id="article13528b">
      <h4>टीका</h4>
      <p>प्रणम्यागण्यकल्याणगुणाब्धिं पुरुषोत्तमम् ।</p>
    </div>
  </div>
</div>
<footer><p>Copyright © 2026 Dvaita Vedanta Studies &amp; Research Foundation.</p></footer>
<script>var x = 1;</script><style>.a{{color:red}}</style>
</body></html>
"""

PAGE_PLAIN = f"""
<html><body>
{BREADCRUMB}
<div class="row">
  {SIDEBAR}
  <div class="col-md-9 article-body">
    <h3>सूत्रभाष्यम्</h3>
    ॐ अथातो ब्रह्मजिज्ञासा ॐ अथशब्दो मङ्गलार्थोऽधिकारानन्तर्यार्थश्च।
    <h3>तत्त्वप्रकाशिका</h3>
    तत्रादिसूत्रस्येदं सङ्गत्यादि। अत्र ब्रह्मजिज्ञासायाः कर्तव्यत्वसमर्थनादस्ति।
  </div>
</div>
</body></html>
"""

PAGE_CONTAINER = f"""
<html><body>
{BREADCRUMB}
<div class="row">{SIDEBAR}<div class="col-md-9"><p>No record found!!</p></div></div>
</body></html>
"""


# Transcribed from probe pages (run 31933375009): pramana_lakshana_13533 for
# the h2.shloka/#dynamicContent frame, katha_lakshana_14031 for the repeated
# h3 passes and the "श्री"-prefixed variant of one heading.
PAGE_REAL = f"""
<html><body>
{BREADCRUMB}
<div class="row">{SIDEBAR}
<div class="col-md-9">
  <div id="article13700" class="lazy-1">
    <h2 class="shloka">लक्ष्यमात्रव्यापको धर्मो लक्षणम्</h2>
    <div id="dynamicContent" class="details">
      <p class="MsoPlainText"><strong><span>लक्षणलक्षणप्रयोजने</span></strong></p>
      <h3><strong><span>प्रमाणलक्षणटीका</span></strong></h3>
      <p class="MsoPlainText"><span>लक्ष्यमात्रव्यापको धर्मो लक्षणम् इति प्रथमः पक्षः ।</span></p>
      <p class="MsoPlainText"><strong><span>श्रीराघवेन्द्रतीर्थयतिकृतः</span></strong></p>
      <h3><strong><span>प्रमाणलक्षणटीकाभावदीपः</span></strong></h3>
      <p class="MsoPlainText"><span>कल्याणगुणपूर्णाय दोषदूराय विष्णवे ।</span></p>
      <h3><strong><span>श्री प्रमाणलक्षणटीका</span></strong></h3>
      <p class="MsoPlainText"><span>अत्र द्वितीयः विचारः प्रस्तूयते ।</span></p>
    </div>
  </div>
</div></div>
<footer>Copyright 2026</footer>
</body></html>
"""


def check(name, condition, detail=""):
    mark = "ok  " if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"   {detail}" if detail and not condition else ""))
    return bool(condition)


def main():
    failures = 0
    url = "https://dvaitavedanta.in/category-details/13528/937/x"

    print("A. anchored markup (id=article<N>)")
    rec = P.parse_page(PAGE_ANCHORED, url)
    failures += not check("content_id parsed", rec["content_id"] == 13528, rec["content_id"])
    failures += not check("not a container", rec["is_container"] is False)
    failures += not check("two layers", len(rec["layers"]) == 2, rec["layers"])
    failures += not check("layer titles", [l["title"] for l in rec["layers"]] == ["मूलम्", "टीका"],
                          [l["title"] for l in rec["layers"]])
    failures += not check("heading stripped from body",
                          not rec["layers"][0]["text"].startswith("मूलम्"),
                          rec["layers"][0]["text"][:40])
    failures += not check("<br> became newline", "\n" in rec["layers"][0]["text"])
    failures += not check("no CSS/JS bleed",
                          "color:red" not in rec["layers"][0]["text"]
                          and "var x" not in rec["layers"][0]["text"])
    failures += not check("no footer bleed", "Copyright" not in rec["layers"][0]["text"])
    failures += not check("devanagari ratio high",
                          P.devanagari_ratio(rec["layers"][0]["text"]) > 0.9,
                          P.devanagari_ratio(rec["layers"][0]["text"]))
    failures += not check("breadcrumb without Home",
                          rec["breadcrumb"][:2] == ["दशप्रकरणानि", "1. प्रमाणलक्षणम्"],
                          rec["breadcrumb"])
    sidebar_ids = sorted(l["content_id"] for l in rec["sidebar"] if not l["in_breadcrumb"])
    failures += not check("sidebar ids harvested", sidebar_ids == [13528, 13529, 13533], sidebar_ids)
    failures += not check("breadcrumb links flagged",
                          any(l["in_breadcrumb"] for l in rec["sidebar"]))

    print("B. plain markup (heading fallback)")
    rec2 = P.parse_page(PAGE_PLAIN, url)
    failures += not check("two layers", len(rec2["layers"]) == 2, rec2["layers"])
    failures += not check("titles", [l["title"] for l in rec2["layers"]] ==
                          ["सूत्रभाष्यम्", "तत्त्वप्रकाशिका"],
                          [l["title"] for l in rec2["layers"]])
    failures += not check("body captured",
                          "अथातो ब्रह्मजिज्ञासा" in rec2["layers"][0]["text"],
                          rec2["layers"][0]["text"][:60])
    failures += not check("no sidebar bleed", "मङ्गलाचरणम्" not in rec2["layers"][0]["text"])

    print("C. container node")
    rec3 = P.parse_page(PAGE_CONTAINER, url)
    failures += not check("flagged container", rec3["is_container"] is True)
    failures += not check("no_record marker seen", rec3["no_record_marker"] is True)
    failures += not check("still yields sidebar", len(rec3["sidebar"]) >= 3)

    print("D. helpers")
    failures += not check("canonical_url shape",
                          P.canonical_url(13528, 937) ==
                          "https://dvaitavedanta.in/category-details/13528/937/x",
                          P.canonical_url(13528, 937))
    failures += not check("canonical_url without ancestor",
                          P.canonical_url(13528).endswith("/13528/13528/x"))
    failures += not check("parse_content_url", P.parse_content_url(
        "/category-details/13528/937/a/b") == (13528, 937))
    failures += not check("non-content href ignored",
                          P.parse_content_url("/about") is None)
    failures += not check("bare श्री kept — it opens Shrinivasatirtha's name",
                          P.author_name("श्रीनिवासतीर्थ") == "श्रीनिवासतीर्थ",
                          P.author_name("श्रीनिवासतीर्थ"))
    failures += not check("a doubled श्रीश्री collapses to one",
                          P.author_name("श्रीश्रीनिवासतीर्थ") == "श्रीनिवासतीर्थ",
                          P.author_name("श्रीश्रीनिवासतीर्थ"))
    failures += not check("श्रीमज् is honorific and goes",
                          P.author_name("श्रीमज्जयतीर्थभिक्षु") == "जयतीर्थभिक्षु",
                          P.author_name("श्रीमज्जयतीर्थभिक्षु"))
    failures += not check("matching stays honorific-insensitive",
                          P.author_core("श्रीजयतीर्थः") in P.author_core("श्रीमज्जयतीर्थभिक्षु"))
    failures += not check("layer_key squashes stray internal spaces",
                          P.layer_key("अ भिनवचन्द्रिका") == P.layer_key("अभिनवचन्द्रिका"))
    failures += not check("layer_key still strips honorifics",
                          P.layer_key("श्री कथालक्षणटीका") == P.layer_key("कथालक्षणटीका"))
    failures += not check("devanagari_ratio on latin", P.devanagari_ratio("hello world") == 0.0)

    # The shape the site actually serves, transcribed from probe pages saved by
    # run 31933375009. Sections A-D above are synthetic, and the original parser
    # passed all of them while still mis-reading every real page: it emitted one
    # layer per leaf whose "name" was the mula verse.
    print("E. real site shape (#article > h2.shloka + #dynamicContent > h3)")
    rec = P.parse_page(PAGE_REAL, url)
    titles = [l["title"] for l in rec["layers"]]
    failures += not check("mula split from commentaries", titles[:1] == ["मूलम्"], titles)
    failures += not check("mula is the verse, not a commentary",
                          rec["layers"][0]["text"].startswith("लक्ष्यमात्रव्यापको"),
                          rec["layers"][0]["text"][:40])
    failures += not check("verse text is not used as a layer name",
                          not any("लक्ष्यमात्रव्यापको" in t for t in titles), titles)
    failures += not check("h3 headings became the layer names",
                          titles[1:] == ["प्रमाणलक्षणटीका", "प्रमाणलक्षणटीकाभावदीपः"], titles)
    tika = rec["layers"][1]
    failures += not check("repeated passes merged into one layer",
                          "प्रथमः" in tika["text"] and "द्वितीयः" in tika["text"],
                          tika["text"][:60])
    failures += not check("honorific variant merged, not duplicated",
                          len(titles) == len(set(titles)) and len(titles) == 3, titles)
    failures += not check("attribution captured",
                          rec["layers"][2]["author"] == "श्रीराघवेन्द्रतीर्थयतिकृतः",
                          rec["layers"][2]["author"])
    failures += not check("attribution trimmed of restated work title",
                          "भावदीपः" not in rec["layers"][2]["author"],
                          rec["layers"][2]["author"])
    # A tika routinely opens by quoting its verse verbatim; containment-dedupe
    # would otherwise delete the mula of every such leaf.
    failures += not check("mula survives being quoted verbatim by its tika",
                          any(l.get("role") == "mula" for l in rec["layers"]), titles)
    failures += not check("no chrome bleed into layers",
                          all("Copyright" not in l["text"] for l in rec["layers"]))
    failures += not check("layers carry their article's own id",
                          {l.get("article_id") for l in rec["layers"]} == {"13700"},
                          [l.get("article_id") for l in rec["layers"]])

    print()
    print("F. one page, several sutras (multi-article leaf)")
    two = PAGE_REAL.replace(
        "</div></div>\n<footer>",
        """  <div id="article13701" class="lazy-1">
    <h2 class="shloka">अव्याप्तिरतिव्याप्तिरसम्भवश्चेति</h2>
    <div id="dynamicContent" class="details">
      <h3><strong><span>प्रमाणलक्षणटीका</span></strong></h3>
      <p><span>दोषत्रयमिह निरूप्यते इति द्वितीयसूत्रार्थः ।</span></p>
    </div>
  </div>
</div></div>
<footer>""")
    rec2 = P.parse_page(two, url)
    ids = [l.get("article_id") for l in rec2["layers"]]
    # The page has ONE content id but TWO verses. Keying items on the content
    # id made them collide; the article id keeps them apart.
    failures += not check("both articles parsed", len(rec2["layers"]) == 5, len(rec2["layers"]))
    failures += not check("second article keeps its own id", set(ids) == {"13700", "13701"}, ids)
    failures += not check("mula and its tika share one article id",
                          ids[0] == ids[1] == "13700", ids[:2])

    # Clipboard chrome. A pasted-from-Word selection leaves StartFragment /
    # EndFragment behind, and on this source the comment delimiters are gone,
    # so the bare words sit in the text -- 1,590 of Nyaya Sudha's 9,929
    # entries carried one. On short entries it dragged the Devanagari ratio
    # under the verifier's floor and failed the whole merged tree.
    failures += not check("bare EndFragment stripped",
                          P.clean_text("संज्ञानं भोगः ।\nEndFragment") == "संज्ञानं भोगः ।",
                          P.clean_text("संज्ञानं भोगः ।\nEndFragment"))
    failures += not check("commented form stripped",
                          P.clean_text("<!--StartFragment-->अथ<!--EndFragment-->") == "अथ",
                          P.clean_text("<!--StartFragment-->अथ<!--EndFragment-->"))
    # A word that merely begins with the token is not chrome.
    failures += not check("word boundary respected",
                          P.clean_text("StartFragmentation") == "StartFragmentation",
                          P.clean_text("StartFragmentation"))

    print()
    print("G. structural heading, not a verse (real corpus bug: 22 occurrences,"
          " e.g. Nyaya Sudha's 4x 'प्रथमः पादः', Sumadhva Vijaya's 16 sarga headings)")
    for text in ["प्रथमः पादः", "द्वितीयः पादः", "चतुर्थपादः", "षोडशः सर्गः", "द्वितीयोऽध्यायः"]:
        failures += not check(f"{text!r} recognised as a structural heading",
                              P.is_structural_heading(text))
    for text in ["नारायणं निखिलपूर्णगुणैकदेहं", "गुरुर्गुरूपणां प्रभवः",
                 "अतो नैतादृशं किञ्चित्प्रमाणतममिष्यते", "प्रथमः पादो न वेदितव्यः"]:
        failures += not check(f"{text!r} is real text, not a heading",
                              not P.is_structural_heading(text))

    # The real shape: an h2.shloka that is a bare pada-heading, with genuine
    # h3 commentary right alongside it under the same article id (this is
    # exactly Nyaya Sudha's DV_4841/DV_4845/DV_4853 -- the heading and the
    # commentary on the sutras inside that pada share one article block).
    heading_page = f"""
<html><body>
{BREADCRUMB}
<div class="row">{SIDEBAR}
<div class="col-md-9">
  <div id="article14841" class="lazy-1">
    <h2 class="shloka">प्रथमः पादः</h2>
    <div id="dynamicContent" class="details">
      <h3><strong><span>शास्त्रयोनित्वाधिकरणम्</span></strong></h3>
      <p class="MsoPlainText"><span>शैवाद्यागमसम्प्राप्तदृष्टगेन फलेन तु ।</span></p>
    </div>
  </div>
</div></div>
<footer>Copyright 2026</footer>
</body></html>
"""
    rec_h = P.parse_page(heading_page, url)
    titles_h = [l["title"] for l in rec_h["layers"]]
    failures += not check("the heading itself does not become a mula layer",
                          "मूलम्" not in titles_h, titles_h)
    failures += not check("the real commentary alongside it still comes through",
                          titles_h == ["शास्त्रयोनित्वाधिकरणम्"], titles_h)
    failures += not check("no layer's text is the bare heading",
                          not any(l["text"].strip() == "प्रथमः पादः" for l in rec_h["layers"]),
                          [l["text"][:20] for l in rec_h["layers"]])

    # A heading-only leaf with no commentary at all must drop to nothing,
    # not a lone fake "verse" item -- the case this bug actually produced
    # (a reader card with a reference and nothing to read).
    heading_only_page = f"""
<html><body>
{BREADCRUMB}
<div class="row">{SIDEBAR}
<div class="col-md-9">
  <div id="article14842" class="lazy-1">
    <h2 class="shloka">द्वितीयः सर्गः</h2>
  </div>
</div></div>
<footer>Copyright 2026</footer>
</body></html>
"""
    rec_ho = P.parse_page(heading_only_page, url)
    failures += not check("a heading with no commentary yields no layers at all",
                          rec_ho["layers"] == [], rec_ho["layers"])

    print()
    print("H. the .details preamble (live-confirmed 25 Aug 2026 — full mula verse"
          " and Madhva's bhashya sat before the first <h3> and were dropped)")
    # Shape 1 — kathopanishad_bhashya: h1 उपनिषत् (full mantra), inner-h2
    # भाष्यम् (Madhva), then named h3 tikas. The mantra lines are themselves
    # <h1> and must be content, not layer boundaries.
    preamble_page = f"""
<html><body>
{BREADCRUMB}
<div class="row">{SIDEBAR}
<div class="col-md-9">
  <div id="article15829" class="lazy-1">
    <h2 class="shloka">ओम् । उशन् ह वै वाजश्रवसः सर्ववेदसं ददौ ..</h2>
    <div id="dynamicContent" class="details">
      <p class="MsoNormal"><strong><span>स्वर्गप्राप्त्यर्थं सर्वस्वदानम्</span></strong></p>
      <h1><strong><span>उपनिषत्</span></strong></h1>
      <h1><strong><span>ओम् । उशन् ह वै वाजश्रवसः सर्ववेदसं ददौ ।</span></strong></h1>
      <h1><strong><span>तस्य ह नचिकेता नाम पुत्र आस ।। १.१.१ ॥</span></strong></h1>
      <h2><strong><span>भाष्यम्</span></strong></h2>
      <p class="MsoNormal"><span>अग्ग्रौ विष्णुं सदा ध्यायन् इति ब्रह्मसारे वचनम् ।</span></p>
      <h3><strong><span>श्रीव्यासतीर्थ</span></strong></h3>
      <p class="MsoNormal"><span>न केवलं ब्रह्मविद्या मोक्षैकफला इत्याशयवान् वेदपुरुषः ।</span></p>
    </div>
  </div>
</div></div>
</body></html>
"""
    rec_p = P.parse_page(preamble_page, url)
    by_title = {l["title"]: l for l in rec_p["layers"]}
    failures += not check("mula upgraded from pratika to the full mantra",
                          "तस्य ह नचिकेता" in by_title.get("मूलम्", {}).get("text", ""),
                          by_title.get("मूलम्", {}).get("text", "")[:60])
    failures += not check("topic line before उपनिषत् is not glued onto the mantra",
                          "स्वर्गप्राप्त्यर्थं" not in by_title.get("मूलम्", {}).get("text", ""))
    failures += not check("भाष्यम् became its own layer",
                          "ब्रह्मसारे" in by_title.get("भाष्यम्", {}).get("text", ""),
                          sorted(by_title))
    failures += not check("भाष्यम् heading itself is not in its text",
                          not by_title.get("भाष्यम्", {}).get("text", "").startswith("भाष्यम्"))
    failures += not check("h3 tika unaffected by the preamble pass",
                          "वेदपुरुषः" in by_title.get("श्रीव्यासतीर्थ", {}).get("text", ""),
                          sorted(by_title))
    failures += not check("bhashya sits between mula and the h3 tikas",
                          [l["title"] for l in rec_p["layers"]][:2] == ["मूलम्", "भाष्यम्"],
                          [l["title"] for l in rec_p["layers"]])

    # Shape 2 — brahma_sutra_bhashya: the preamble heading is सूत्रभाष्यम्
    # (a *भाष्यम् form), and the sutra pratika in h2.shloka is already the
    # complete sutra — it must NOT be replaced by the bhashya text even
    # though the bhashya quotes the sutra verbatim.
    bsb_page = preamble_page.replace(
        '<h2 class="shloka">ओम् । उशन् ह वै वाजश्रवसः सर्ववेदसं ददौ ..</h2>',
        '<h2 class="shloka">ॐ अथातो ब्रह्मजिज्ञासा ॐ</h2>').replace(
        '<h1><strong><span>उपनिषत्</span></strong></h1>', '').replace(
        '<h1><strong><span>ओम् । उशन् ह वै वाजश्रवसः सर्ववेदसं ददौ ।</span></strong></h1>', '').replace(
        '<h1><strong><span>तस्य ह नचिकेता नाम पुत्र आस ।। १.१.१ ॥</span></strong></h1>', '').replace(
        '<h2><strong><span>भाष्यम्</span></strong></h2>',
        '<h2><strong><span>सूत्रभाष्यम्</span></strong></h2>').replace(
        '<p class="MsoNormal"><span>अग्ग्रौ विष्णुं सदा ध्यायन् इति ब्रह्मसारे वचनम् ।</span></p>',
        '<p class="MsoNormal"><span>ॐ अथातो ब्रह्मजिज्ञासा ॐ</span></p>'
        '<p class="MsoNormal"><span>अथशब्दो मङ्गलार्थोऽधिकारानन्तर्यार्थश्च। अतःशब्दो हेत्वर्थः।</span></p>')
    rec_b = P.parse_page(bsb_page, url)
    by_title_b = {l["title"]: l for l in rec_b["layers"]}
    failures += not check("sutra pratika kept as mula",
                          by_title_b.get("मूलम्", {}).get("text", "") == "ॐ अथातो ब्रह्मजिज्ञासा ॐ",
                          by_title_b.get("मूलम्", {}).get("text", "")[:40])
    failures += not check("सूत्रभाष्यम् block became the भाष्यम् layer",
                          "मङ्गलार्थ" in by_title_b.get("भाष्यम्", {}).get("text", ""),
                          sorted(by_title_b))

    # Shape 3 — no <h3> at all (rig_bhashya / mahabharata_tatparya_nirnaya):
    # the old fallback captured NOTHING; the whole .details region is the
    # full mula text when it contains the pratika's stem. Structural,
    # grantha-title and leading attribution lines are filtered out.
    noh3_page = f"""
<html><body>
{BREADCRUMB}
<div class="row">{SIDEBAR}
<div class="col-md-9">
  <div id="article14079" class="lazy-1">
    <h2 class="shloka">नारायणाय परिपूर्णगुणार्णवाय विश्वोदयस्थितिलयोन्नियति प्रदाय</h2>
    <div id="dynamicContent" class="details">
      <p class="MsoNormal"><strong><span>श्रीमदानन्दतीर्थभगवत्पादाचार्यविरचित:</span></strong></p>
      <p class="MsoNormal"><strong><span>1. प्रमाणलक्षणम्</span></strong></p>
      <p class="MsoNormal"><strong><span>अथ प्रथमोऽध्यायः</span></strong></p>
      <h1 class="MsoNormal"><span>नारायणाय परिपूर्णगुणार्णवाय विश्वोदयस्थितिलयोन्नियति प्रदाय।</span></h1>
      <h1 class="MsoNormal"><span>ज्ञानप्रदाय विबुधासुरसौख्यदुःखसत्कारणाय वितताय नमो नमस्ते ।। १।।</span></h1>
      <p class="MsoNormal"><span>आसीदुदारगुणवारिधिरप्रमेयो नारायणः परतमः परमात् स एकः। ।। २।।</span></p>
    </div>
  </div>
</div></div>
</body></html>
"""
    rec_n = P.parse_page(noh3_page, url)
    failures += not check("no-h3 leaf: full verses recovered into mula",
                          len(rec_n["layers"]) == 1 and "नमो नमस्ते" in rec_n["layers"][0]["text"]
                          and "आसीदुदारगुणवारिधि" in rec_n["layers"][0]["text"],
                          [l["text"][:50] for l in rec_n["layers"]])
    mtext = rec_n["layers"][0]["text"]
    failures += not check("leading attribution line filtered", "विरचित" not in mtext, mtext[:60])
    failures += not check("grantha-title restatement filtered", "प्रमाणलक्षणम्" not in mtext)
    failures += not check("'अथ प्रथमोऽध्यायः' structural line filtered", "प्रथमोऽध्यायः" not in mtext)
    failures += not check("परिच्छेद is a structural noun now",
                          P.is_structural_heading("प्रथमः परिच्छेदः"))

    # Shape 4 — a preamble that does NOT contain the pratika's verse
    # (gita_bhashya's invocation-only preambles): mula must keep its
    # already-complete h2 verse, and the stray text must not be glued on.
    unrelated_page = noh3_page.replace(
        '<h1 class="MsoNormal"><span>नारायणाय परिपूर्णगुणार्णवाय विश्वोदयस्थितिलयोन्नियति प्रदाय।</span></h1>', '').replace(
        '<h1 class="MsoNormal"><span>ज्ञानप्रदाय विबुधासुरसौख्यदुःखसत्कारणाय वितताय नमो नमस्ते ।। १।।</span></h1>', '').replace(
        '<p class="MsoNormal"><span>आसीदुदारगुणवारिधिरप्रमेयो नारायणः परतमः परमात् स एकः। ।। २।।</span></p>',
        '<p class="MsoNormal"><span>।। श्रीलक्ष्मीहयग्रीवाय नमः ।। इति मङ्गलम् उच्यते सज्जनैः सर्वदा खलु ।</span></p>')
    rec_u = P.parse_page(unrelated_page, url)
    failures += not check("non-matching preamble never replaces the pratika",
                          rec_u["layers"][0]["text"].startswith("नारायणाय परिपूर्णगुणार्णवाय"),
                          rec_u["layers"][0]["text"][:60])

    print()
    print("I. quoted base text inside an <h3> run (live node 9360: the सुधा run"
          " carries <h2>अनुव्याख्यानम्</h2> + Madhva's verse in strong+em paras)")
    quote_page = f"""
<html><body>
{BREADCRUMB}
<div class="row">{SIDEBAR}
<div class="col-md-9">
  <div id="article10243" class="lazy-1">
    <h2 class="shloka">ॐ वृद्धिह्रासभाक्त्वमन्तर्भावादुभयसामञ्जस्यादेवम् ॐ</h2>
    <div id="dynamicContent" class="details">
      <p class="MsoPlainText"><strong><span>।। अथ वृद्धिह्रासाधिकरणम् ।।</span></strong></p>
      <h3><strong><em><span>सुधा</span></em></strong></h3>
      <p class="MsoPlainText"><span>यदर्थं भगवन्महिमाऽत्रोच्यते सा भक्तिः तारतम्येन तिष्ठतीति तत्र आह तद्भक्तीति ।</span></p>
      <h2><strong><span>अनुव्याख्यानम्</span></strong></h2>
      <p class="MsoPlainText"><strong><em><span>तद्भक्तितारतम्येन तारतम्यं विमुक्तिगम् ।</span></em></strong></p>
      <p class="MsoPlainText"><strong><em><span>ब्रह्मादीनां च सर्वेषामानन्दादेर्यथाक्रमम् ।। ३२१२ ।।</span></em></strong></p>
      <p class="MsoPlainText"><span>ब्रह्मादीनां चशब्दादस्मदादीनामित्येवं सर्वेषां यथाक्रमं तारतम्यं भवतीत्यर्थः ।</span></p>
      <h3><strong><em><span>परिमळ</span></em></strong></h3>
      <p class="MsoPlainText"><span>वृद्धिह्रासभाक्त्वमन्तर्भावात् ।। युक्तेरिति । सूत्रोक्तयुक्तेरित्यर्थः ।</span></p>
    </div>
  </div>
</div></div>
</body></html>
"""
    rec_q = P.parse_page(quote_page, url)
    by_q = {l["title"]: l for l in rec_q["layers"]}
    failures += not check("अनुव्याख्यानम् verse extracted as its own layer",
                          "विमुक्तिगम्" in by_q.get("अनुव्याख्यानम्", {}).get("text", ""),
                          sorted(by_q))
    failures += not check("only the strong+em verse paras are in the quote layer",
                          "चशब्दादस्मदादीनाम" not in by_q.get("अनुव्याख्यानम्", {}).get("text", ""))
    sudha_text = by_q.get("सुधा", {}).get("text", "")
    failures += not check("Jayatirtha's prose before AND after the verse stays in सुधा",
                          "तद्भक्तीति" in sudha_text and "चशब्दादस्मदादीनाम" in sudha_text,
                          sudha_text[:80])
    failures += not check("the verse itself is NOT duplicated in सुधा",
                          "विमुक्तिगम्" not in sudha_text, sudha_text[:120])
    failures += not check("the following परिमळ h3 run is untouched",
                          "सूत्रोक्तयुक्तेरित्यर्थः" in by_q.get("परिमळ", {}).get("text", ""),
                          sorted(by_q))
    failures += not check("a run without quote headings takes the unchanged path",
                          by_q.get("परिमळ", {}).get("text", "").startswith("परिमळ")
                          or "परिमळ" in by_q, sorted(by_q))

    print()
    if failures:
        print(f"{failures} check(s) FAILED")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
