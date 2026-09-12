"""dge/js/shortcuts.js: every key's example resolves to a grantha that exists and to a verse that is in its data;
the reverse (make) reproduces the token; the reader's URL forms round-trip."""
import json, subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "dge/js/shortcuts.js"


def node(expr):
    out = subprocess.run(["node", "-e", f"global.window={{}}; require({json.dumps(str(JS))}); const S=window.DGEShortcuts; console.log(JSON.stringify({expr}));"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def load(slug):
    return json.load(open(ROOT / "dge/data" / slug / "data.json", encoding="utf-8"))


def item_ids(doc):
    ids = set()
    for it in doc.get("items") or []:
        ids.add(str(it.get("id")))
    sh = doc.get("shlokas")
    if isinstance(sh, dict):
        ids.update(str(k) for k in sh)
    return ids


@pytest.mark.parametrize("key", [e["key"] for e in node("S.table.map(e=>({key:e.key}))")])
def test_example_resolves_against_real_data(key):
    entry = node(f"S.table.find(e=>e.key==={json.dumps(key)})")
    token = entry["example"].split()[0]
    r = node(f"S.parse({json.dumps(token)})")
    assert r and r["granthaPath"], f"{token} did not parse"
    doc = load(r["granthaPath"])                          # the folder exists and is a grantha
    ids = item_ids(doc)
    if r.get("vedicId") and "#" in r["vedicId"]:
        unit, n = r["vedicId"].split("#")
        it = next(x for x in doc["items"] if str(x["id"]) == unit)
        assert any(str(s.get("number")) == n for s in it.get("shlokas") or []) or int(n) <= len(it.get("shlokas") or []), f"{token}: verse {n} not in {unit}"
    elif r.get("vedicId"):
        assert r["vedicId"] in ids or any(i.startswith(r["vedicId"] + ".") for i in ids), f"{token}: {r['vedicId']} not in data"
    else:
        assert str(r["shlokaNumber"]) in ids, f"{token}: shloka {r['shlokaNumber']} not in data"


def test_prefix_and_bounds():
    assert node("S.parse('rv1.1')")["vedicId"] == "1.1" and node("S.parse('rv1')")["vedicId"] == "1"
    assert node("S.parse('rv11.1')") is None and node("S.parse('mbh19.1')") is None and node("S.parse('rv1.1.1.1')") is None
    assert node("S.parse('xx1')") is None and node("S.parse('rv')") is None and node("S.parse('1.1')") is None
    assert node("S.parse('RV 10.191.4')")["granthaPath"].endswith("mandala_10")


def test_make_reverses_parse():
    assert node("S.make('vedas/rigveda/shakala_shakha/samhita/mandala_01',{vedicId:'1.1.3'},3)") == "rv1.1.3"
    assert node("S.make('DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1',{},5)") == "smv1.5"
    assert node("S.make('itihasa/mahabharata/shanti_parva/mula',{unitId:'adhyaya_003',unitNo:'7'},500)") == "mbh12.3.7"
    assert node("S.make('purana/maha_purana/bhagavata_purana/skandha_10',{unitId:'adhyaya_14',unitNo:'8'},9)") == "bhp10.14.8"
    assert node("S.make('vedas/samaveda/kauthuma_shakha/samhita/uttararchika',{vedicId:'651'},1)") == "sv651"
    assert node("S.make('darshana/x/y',{vedicId:'1.2'},3)") is None


def test_url_forms():
    assert node("S.fromSearch('?rv1.1')")["vedicId"] == "1.1"
    assert node("S.fromSearch('?SMV=1.1')")["shlokaNumber"] == 1          # the legacy ?SMV=1.1 form still works
    assert node("S.fromSearch('?path=x&jumpShloka=1')") is None and node("S.fromSearch('?rv=1.1&x=2')") is None
    assert node("S.canonical('/bhumandala/dge/index.html','darshana/x/y',{},3)") == "/bhumandala/dge/index.html?path=darshana/x/y&jumpShloka=3"
    assert node("S.canonical('/x','vedas/rigveda/shakala_shakha/samhita/mandala_01',{vedicId:'1.1.3'},3)") == "/x?rv1.1.3"
