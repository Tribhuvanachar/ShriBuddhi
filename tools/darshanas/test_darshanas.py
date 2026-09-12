#!/usr/bin/env python3
"""Offline tests for the Darśana scaffolder and the GRETIL śāstra parser.

No network. indic-transliteration is stubbed because the Cowork sandbox cannot
install it — it IS present on the Actions runner via importers/requirements.txt,
so this exercises the parser logic rather than the transliteration itself.

Run:  python tools/darshanas/test_darshanas.py
"""

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "importers"))

import scaffold_darshanas as S  # noqa: E402


def check(name, condition, detail=""):
    mark = "ok  " if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"   {detail}" if detail and not condition else ""))
    return bool(condition)


GRETIL_FIXTURE = """GRETIL header line
Input by Members of the Sansknet Project
Description: Nyayasutra with Vatsyayana Bhasya
Date of this version: 2010-05-04

TEXT

1.1
athato brahmajijnasa iti ^^ pramanaprameya\\samsaya __________ prayojana //
1.2
duhkhajanmapravrttidosamithyajnananam uttarottarapaye apavargah //
2.1
tatra pramanani pratyaksanumanopamanasabdah //
"""


def test_scaffold(failures):
    print("A. scaffolder")
    tmp = tempfile.mkdtemp(prefix="dscaf_")
    try:
        for name in ("taxonomy.json", "library.json"):
            src = os.path.join(REPO, "dge", "data", name)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(tmp, name))

        config = json.load(open(os.path.join(HERE, "darshana_works.json"), encoding="utf-8"))
        scaffolder = S.Scaffolder(config, tmp).run()
        scaffolder.write_indexes()
        scaffolder.sync_catalog()

        failures += not check("leaves emitted", len(scaffolder.leaves) > 100, len(scaffolder.leaves))
        failures += not check("no unresolved commentary edges",
                              not scaffolder.dangling,
                              [e["from"] for e in scaffolder.dangling][:3])
        failures += not check("every leaf has a verification status",
                              all(l.get("verification") for l in scaffolder.leaves))

        # The modelling decision: vādas are topic x layer, never topic x author.
        vada = "darshana/nyaya/navya_nyaya/tattvacintamani/anumana_khanda/vadas/panchalakshani"
        vada_leaves = [l for l in scaffolder.leaves if l["path"].startswith(vada + "/")]
        failures += not check("Pañcalakṣaṇī has one folder per LAYER",
                              sorted(l["layer_slug"] for l in vada_leaves) ==
                              ["didhiti", "gadadhari", "jagadishi", "mula"],
                              sorted(l["layer_slug"] for l in vada_leaves))
        failures += not check("…and is a section_of, not a work",
                              any(e["type"] == "section_of" and e["from"] == vada
                                  for e in scaffolder.edges))

        # Layer depths must survive: Bhāskarodaya is a 3rd-order gloss.
        bhask = next(l for l in scaffolder.leaves if l["layer_slug"] == "tika_bhaskarodaya")
        failures += not check("Bhāskarodaya recorded at layer 3", bhask["layer_depth"] == 3,
                              bhask["layer_depth"])
        failures += not check("…and points at Nīlakaṇṭhī, not the mūla",
                              bhask["comments_on"] == "tarkasangraha/tika_nilakanthi",
                              bhask["comments_on"])

        # The two Kiraṇāvalīs must not collapse into one.
        kiranavali = [l for l in scaffolder.leaves if l["layer_slug"] == "tika_kiranavali"]
        failures += not check("two distinct Kiraṇāvalī entries", len(kiranavali) == 2,
                              [l["path"] for l in kiranavali])
        failures += not check("…under different works",
                              len({l["work"] for l in kiranavali}) == 2)

        # Ṛjuvimalā is Śālikanātha's, not Prabhākara's.
        rijuvimala = next(l for l in scaffolder.leaves if l["layer_slug"] == "tika_rijuvimala")
        failures += not check("Ṛjuvimalā attributed to Śālikanātha",
                              rijuvimala["author"] == "shalikanatha", rijuvimala["author"])

        # Vyutpattivāda / Śaktivāda are standalone works, not vādas.
        standalone = {l["work"] for l in scaffolder.leaves if l["work"] in ("vyutpattivada", "shaktivada")}
        failures += not check("Vyutpattivāda and Śaktivāda are their own works",
                              standalone == {"vyutpattivada", "shaktivada"}, standalone)
        failures += not check("Bādhānta filed as a work, not a Tattvacintāmaṇi vāda",
                              any(l["work"] == "badhanta" for l in scaffolder.leaves))

        # Stubs must be well formed and never clobber real data.
        stub = json.load(open(os.path.join(
            tmp, "darshana/nyaya/prakarana/tarkasangraha/tika_dipika/data.json"), encoding="utf-8"))
        failures += not check("stub shape", sorted(stub) == ["default_author", "items", "schema"])
        failures += not check("stub carries Devanagari author",
                              stub["default_author"] == "अन्नम्भट्टः", stub["default_author"])

        target = os.path.join(tmp, "darshana/nyaya/prakarana/tarkasangraha/mula/data.json")
        json.dump({"schema": "grantha_mula_text", "default_author": "x",
                   "items": [{"id": "a", "sanskrit_text": "क"}]},
                  open(target, "w", encoding="utf-8"), ensure_ascii=False)
        again = S.Scaffolder(config, tmp).run()
        again.sync_catalog()
        after = json.load(open(target, encoding="utf-8"))
        failures += not check("re-run never clobbers populated data",
                              len(after["items"]) == 1, after)
        failures += not check("…and flips populated to true in library.json",
                              next(e["populated"] for e in
                                   json.load(open(os.path.join(tmp, "library.json"), encoding="utf-8"))["granthas"]
                                   if e["path"].endswith("tarkasangraha/mula/data.json")) is True)

        taxonomy = json.load(open(os.path.join(tmp, "taxonomy.json"), encoding="utf-8"))
        # Named after the real top level, which this fixture copies. They were
        # "vyakarana" and "sarvamoola_grantha" until the taxonomy restructure
        # moved them under vedanga/ and darshana/vedanta/dvaita/ — the point of
        # the check is that sync_catalog adds without removing, so it has to
        # name sections that actually exist.
        failures += not check("existing taxonomy sections untouched",
                              {"vedas", "vedanga", "itihasa"} <= set(taxonomy))
        failures += not check("darshana added to taxonomy", "darshana" in taxonomy)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return failures


def test_gretil(failures):
    print("B. GRETIL śāstra parser")
    import common
    common.iast_to_dev = lambda s: "«dev»" + s
    import darshana_gretil as D
    D.iast_to_dev = common.iast_to_dev

    spec = D.DARSHANA_GRETIL["nyayasutra_bhashya"]
    items, attribution = D.parse(GRETIL_FIXTURE, spec)

    failures += not check("three sections parsed", len(items) == 3, [i["id"] for i in items])
    failures += not check("ids from section numbers",
                          [i["id"] for i in items] == ["adhyaya_1_1", "adhyaya_1_2", "adhyaya_2_1"],
                          [i["id"] for i in items])
    text = items[0]["iast_text"]
    failures += not check("GRETIL analytic markers stripped",
                          "^" not in text and "\\" not in text and "____" not in text, repr(text))
    failures += not check("header never leaks into the text",
                          "Input by" not in text and "GRETIL header" not in text, repr(text))
    failures += not check("attribution captured for provenance",
                          "Sansknet" in attribution, attribution)
    failures += not check("tika_title set on tika schema",
                          items[0].get("tika_title") == "न्यायभाष्यम्")
    failures += not check("IAST kept alongside the Devanagari",
                          items[0]["sanskrit_text"].startswith("«dev»"))

    plain, _ = D.parse("TEXT\n\nkevalam gadyam with no section markers at all.", spec)
    failures += not check("unsegmented text is kept, not dropped", len(plain) == 1)
    failures += not check("…and tagged for follow-up", plain[0]["tags"] == ["unsegmented"])

    empty, _ = D.parse("TEXT\n\n", spec)
    failures += not check("empty body yields no items", empty == [])

    targets = {s["target"] for s in D.DARSHANA_GRETIL.values()}
    failures += not check("every GRETIL target sits under darshana/",
                          all(t.startswith("darshana/") for t in targets))
    return failures


def main():
    failures = 0
    failures = test_scaffold(failures)
    failures = test_gretil(failures)
    print()
    if failures:
        print(f"{failures} check(s) FAILED")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
