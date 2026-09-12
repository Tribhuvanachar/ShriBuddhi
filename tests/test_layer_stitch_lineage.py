"""js/layer-stitch.js: the lineage strip renders for EVERY library path,
not only the handful with a hand-written DGE_GRANTHA_LINEAGE entry.

The project lead, 9 Sep 2026: "every item rendered from library should have
breadcrumb without miss." Before the fallback branch, only five granthas had
one; jayanti_nirnaya -- reached from a Kannada search hit -- rendered nothing.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "js/layer-stitch.js"

# A DOM small enough to stand up in node, big enough for dgeRenderStitchChrome:
# it reads #lineageStrip, writes innerHTML and flips display.
HARNESS = """
global.window = global.window || {};
global.fetch = () => Promise.resolve({ ok: false, json: () => ({}) });
const strip = { id: 'lineageStrip', innerHTML: '', style: { display: 'none' } };
global.document = {
  getElementById: (id) => (id === 'lineageStrip' ? strip : null),
  addEventListener: () => {},
  querySelector: () => null,
  querySelectorAll: () => [],
  createElement: () => ({ style: {}, classList: { add(){}, remove(){} }, appendChild(){} }),
};
global.window.document = global.document;
global.window.addEventListener = () => {};
// The per-segment label table library.js owns; only the two entries the
// assertions need, so the test does not depend on the whole file loading.
global.window.dgeSegLabel = (seg) => ({
  darshana: 'दर्शनानि', vedanta: 'वेदान्तः', dvaita: 'द्वैतम्',
  Anandamakaranda: 'सर्वमूलग्रन्थाः', achara_and_ancillary_granthas: 'आचारादिग्रन्थाः',
  jayanti_nirnaya: 'जयन्तीनिर्णयः',
}[seg] || seg);
require(%s);
"""


def render(slug, metadata_title=None):
    """Run dgeRenderStitchChrome for a grantha opened straight from the
    library (no stitch manifest) and report what the strip ended up with."""
    script = HARNESS % json.dumps(str(JS)) + f"""
global.window.currentGranthaSlug = {json.dumps(slug)};
global.window.stotraData = {{ metadata: {{ title: {json.dumps(metadata_title)} }} }};
global.window.dgeRenderStitchChrome();
console.log(JSON.stringify({{ html: strip.innerHTML, display: strip.style.display }}));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def nodes(html):
    import re
    return re.findall(r"<(?:a|span) class=\"lineage-(?:link|node)[^\"]*\"[^>]*>([^<]*)<", html)


def test_a_grantha_with_no_curated_lineage_still_gets_a_strip():
    r = render("darshana/vedanta/dvaita/Anandamakaranda/achara_and_ancillary_granthas/jayanti_nirnaya/mula")
    assert r["display"] == "flex"
    assert nodes(r["html"]) == ["दर्शनानि", "वेदान्तः", "द्वैतम्", "सर्वमूलग्रन्थाः",
                                "आचारादिग्रन्थाः", "जयन्तीनिर्णयः"]


def test_every_ancestor_links_into_the_library_at_its_own_depth():
    r = render("darshana/vedanta/dvaita/Anandamakaranda/achara_and_ancillary_granthas/jayanti_nirnaya/mula")
    import re
    hrefs = re.findall(r'href="index\.html\?libraryPath=([^"]+)"', r["html"])
    from urllib.parse import unquote
    assert [unquote(h) for h in hrefs] == [
        "darshana", "darshana/vedanta", "darshana/vedanta/dvaita",
        "darshana/vedanta/dvaita/Anandamakaranda",
        "darshana/vedanta/dvaita/Anandamakaranda/achara_and_ancillary_granthas",
    ]


def test_the_label_table_wins_over_a_synthesised_metadata_title():
    # core.js fills metadata.title from the folder when data.json has none, so
    # karma_nirnaya's reads "Mula" -- worse than useless as the current node.
    r = render("darshana/vedanta/dvaita/Anandamakaranda/achara_and_ancillary_granthas/jayanti_nirnaya/mula",
               metadata_title="Mula")
    assert nodes(r["html"])[-1] == "जयन्तीनिर्णयः"


def test_the_grantha_itself_is_the_current_node_not_a_link():
    r = render("darshana/vedanta/dvaita/Anandamakaranda/achara_and_ancillary_granthas/jayanti_nirnaya/mula")
    assert 'lineage-current">जयन्तीनिर्णयः<' in r["html"]
    assert "jayanti_nirnaya</a>" not in r["html"]


def test_no_slug_means_no_strip_rather_than_an_empty_one():
    r = render("")
    assert r["display"] == "none"
