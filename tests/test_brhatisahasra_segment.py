"""The Bṛhatīsahasram segmenter.

बृहतीसहस्रम् with the Tattvasāra of Raghunātha Tīrtha, 568 pages.

Two things this encodes:

  * THE NUMBERING RUNS STRAIGHT THROUGH. The book divides into प्राग्भागः,
    three तृचाशीति sections and उत्तरभागः, and the numbers do NOT restart:
    प्राग्भागः ends at 317, गायत्रतृचाशीतिः runs 318-475, वार्हततृचाशीतिः
    476-722, औष्णिही 723-897, उत्तरभागः 898 on. Read as separate sections
    each looked like a text missing its first few hundred verses.
  * THE APPENDICES ARE FOUND BY A HEADER, not by a mention. The contents page
    names विष्णुसहस्रनाम on p22; cutting there left ten pages of front matter
    and no verses at all.

And the count checks itself: बृहती-सहस्रम् is "a thousand bṛhatīs", and the
work's own numbering reaches exactly 1000.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bs = _load("bs_segment", "tools/brhatisahasra/segment.py")
VC = _load("verse_commentary", "tools/ocr_common/verse_commentary.py")
STAGED = ROOT / "data/ocr_staging/brhatisahasram_tattvasara_raghunatha_tirtha"


def page(*blocks):
    return "".join(f'<p data-layout="{k}">{v}</p>' for k, v in blocks)


def test_the_appendix_boundary_is_a_header_not_a_mention():
    pages = {
        1: page(("paragraph", "विषयानुक्रमणिका — विष्णुसहस्रनामस्तोत्रपाठः ... ५०७"),
                ("paragraph", "श्लोकपाठोऽयमत्र वर्तते सुदीर्घतरः सुन्दरः ॥ १ ॥")),
        2: page(("header", "सुमुक्तामञ्जरी"),
                ("paragraph", "परिशिष्टपाठोऽयमत्र वर्तते दीर्घः ॥ १ ॥")),
    }
    body, first = bs.body_pages(pages)
    assert first == 2, "the contents-page mention cut the body off at page 1"
    assert sorted(body) == [1]


def test_one_continuous_run_across_the_sections():
    pages = {1: page(("header", "प्राग्भागः"),
                     ("paragraph", "श्लोकपाठोऽयमत्र वर्तते सुदीर्घतरः ॥ ३१७ ॥")),
             2: page(("header", "गायत्रतृचाशीतिः"),
                     ("paragraph", "श्लोकपाठोऽन्योऽत्र वर्तते सुदीर्घतरः ॥ ३१८ ॥"))}
    r = bs.segment(pages)
    assert len(r["sections"]) == 1, "the sections were read as separate texts"
    assert sorted(n for _, n in r["units"]) == [317, 318]


# --- the real book ---------------------------------------------------------

def _real():
    if not STAGED.is_dir():
        import pytest
        pytest.skip("Bṛhatīsahasram staging not present")
    import sys
    sys.path.insert(0, str(ROOT / "tools/ocr_common"))
    import staged as S
    return bs.segment(S.load_sarvam(str(STAGED)))


def test_the_count_bears_the_name_out():
    """बृहती-सहस्रम् is a thousand bṛhatīs, and the numbering reaches 1000."""
    r = _real()
    assert r["sections"][0]["highest"] == 1000
    assert r["verses_found"] == 986
    assert r["verses_missing"] == 14
    assert r["appendix_from"] == 494


def test_the_addressed_verses_are_actually_verse_SHAPED():
    r = _real()
    q = VC.quality(r["units"])
    assert q["empty"] == 0 and q["long"] == 0
    assert q["plausible_pct"] == 100
    assert q["duplicate_text"] == 0 and q["duplicate_commentary"] == 0
    assert q["commentary_equals_verse"] == 0
    assert q["len_min"] >= 25
