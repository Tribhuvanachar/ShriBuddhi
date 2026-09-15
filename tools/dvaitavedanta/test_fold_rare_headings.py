"""Offline tests for build_items' rare-heading folding (1 Sep 2026).

The Nyāyasudhā fix: one-off topic/pratika <h3>s (measured max 25 units on
the live corpus) stop minting their own tika_<slug> folders and instead
fold into the record's enclosing layer — or open the mula spine when the
record starts with one. Recurring layer names (the real sub-commentaries,
518+ units each) are untouched, as is every grantha without the config
flag.

Run: python tools/dvaitavedanta/test_fold_rare_headings.py
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_dvaitavedanta import build_items  # noqa: E402

DEFAULTS = {"mula_schema": "grantha_mula_text", "tika_schema": "grantha_tika_text"}
DEVA_PAD = "इति चेन्न तस्य प्रागुक्तत्वात् समन्वयाच्च तत्त्वनिर्णयः भवति खलु"


def _warnings():
    return {"unmapped_layers": Counter(), "low_devanagari": [], "id_collisions": []}


def rec(cid, layers):
    return {
        "url": f"https://dvaitavedanta.in/category-details/{cid}/975/x",
        "content_id": str(cid), "ancestor_id": "975",
        "breadcrumb": ["श्रीमन्न्यायसुधा", "सुधा", "मङ्गलमाचरणम्", f"unit{cid}"],
        "layers": layers, "sidebar": [], "is_container": False,
        "no_record_marker": False,
    }


def layer(title, text, article_id=None, role="tika"):
    return {"title": title, "text": text, "anchor": "", "author": "",
            "article_id": article_id, "role": role}


GRANTHA = {"slug": "nyaya_sudha", "title": "श्रीमन्न्यायसुधा",
           "acharya": "श्रीजयतीर्थः", "fold_rare_headings": 2}

# सुधा recurs (3 records >= threshold 2) — a real layer. The topic headings
# appear once each — folded.
RECORDS = [
    rec(101, [layer("मूलम्", "प्रतीकः प्रथमः " + DEVA_PAD, "101", role="mula"),
              layer("सुधा", "सुधाव्याख्यानं प्रथमम् " + DEVA_PAD, "101"),
              layer("वैशेषिकाधिकरणम्", "अधिकरणविषयः " + DEVA_PAD, "101")]),
    rec(102, [layer("सुधा", "सुधाव्याख्यानं द्वितीयम् " + DEVA_PAD, "102")]),
    # a record OPENING with a rare heading = a सुधा prose section -> mula
    rec(103, [layer("अणुत्वमहत्त्वनिरासः", "प्रकरणपाठः " + DEVA_PAD, "103"),
              layer("सुधा", "सुधाव्याख्यानं तृतीयम् " + DEVA_PAD, "103")]),
]


def test_rare_heading_folds_into_previous_layer():
    out = build_items([json.loads(json.dumps(r)) for r in RECORDS], GRANTHA, {},
                      DEFAULTS, "2026-09-01", _warnings())
    assert "tika_sudha" in out, sorted(out)
    assert not any(k.startswith("tika_v") for k in out), sorted(out)
    sudha_101 = next(i for i in out["tika_sudha"]["items"] if i["id"] == "DV_101")
    assert "वैशेषिकाधिकरणम्" in sudha_101["sanskrit_text"]
    assert "अधिकरणविषयः" in sudha_101["sanskrit_text"]


def test_record_opening_rare_heading_goes_to_mula():
    out = build_items([json.loads(json.dumps(r)) for r in RECORDS], GRANTHA, {},
                      DEFAULTS, "2026-09-01", _warnings())
    mula_ids = [i["id"] for i in out["mula"]["items"]]
    assert "DV_103" in mula_ids, mula_ids
    m103 = next(i for i in out["mula"]["items"] if i["id"] == "DV_103")
    assert m103["sanskrit_text"].startswith("अणुत्वमहत्त्वनिरासः")
    assert out["mula"]["default_author"] == "श्रीजयतीर्थः"


def test_no_flag_no_fold():
    g = {k: v for k, v in GRANTHA.items() if k != "fold_rare_headings"}
    out = build_items([json.loads(json.dumps(r)) for r in RECORDS], g, {},
                      DEFAULTS, "2026-09-01", _warnings())
    assert any(k.startswith("tika_v") for k in out), sorted(out)  # old behavior


def test_attributed_rare_heading_still_gets_folder():
    recs = [rec(201, [layer("सुधा", "सुधापाठः " + DEVA_PAD, "201"),
                      layer("श्रीरघूत्तमतीर्थविरचिता टिप्पणी", "टिप्पणीपाठः " + DEVA_PAD, "201")]),
            rec(202, [layer("सुधा", "सुधापाठः द्वितीयः " + DEVA_PAD, "202")])]
    out = build_items(recs, GRANTHA, {}, DEFAULTS, "2026-09-01", _warnings())
    others = [k for k in out if k not in ("mula", "tika_sudha")]
    assert others, sorted(out)  # the attributed one kept its own folder


def test_flag_survives_select_granthas():
    # The real-run path: select_granthas copies entries through a key
    # whitelist, which silently dropped fold_rare_headings on the first
    # live run (all 745 topic folders came back). Guard the whitelist.
    from import_dvaitavedanta import select_granthas
    cfg = {"site": {"base": "https://dvaitavedanta.in"},
           "sections": [{"slug": "later_acharyas", "title": "उत्तराचार्याः",
                         "granthas": [{"slug": "nyaya_sudha", "title": "श्रीमन्न्यायसुधा",
                                       "seed": "/x", "acharya": "श्रीजयतीर्थः",
                                       "fold_rare_headings": True, "enabled": False}]}]}
    sel = select_granthas(cfg, None, ["nyaya_sudha"])
    assert sel and sel[0]["fold_rare_headings"] is True, sel
    assert sel[0]["acharya"] == "श्रीजयतीर्थः"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all checks passed")
