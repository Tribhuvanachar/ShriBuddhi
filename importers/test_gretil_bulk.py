#!/usr/bin/env python3
"""Offline tests for the registry-driven GRETIL importer.

Every fixture below is transcribed from a real GRETIL file (the exact lines the
2026-08-17 recon read off the archive), not invented. That matters: the whole
point of this importer is that thirteen marker grammars differ in ways a
synthetic fixture would smooth over.

indic-transliteration is stubbed — it is present on the Actions runner via
importers/requirements.txt, absent in the Cowork sandbox.

Run:  python importers/test_gretil_bulk.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common                                  # noqa: E402
common.iast_to_dev = lambda s: "«" + s         # stub before gretil_bulk imports it
import gretil_bulk as G                        # noqa: E402
G.iast_to_dev = common.iast_to_dev

HEAD = """Some Purana
Based on the edition Bombay: Venkatesvara Steam Press 1910
Input by members of the SANSKNET-project
THIS GRETIL TEXT FILE IS FOR REFERENCE PURPOSES ONLY!

TEXT

"""

FIXTURES = {
    # // ViP_1,1.2 //  — book,chapter.verse in slashes
    "slash_book_chapter_verse": HEAD + """
oṃ namo vāsudevāya // ViP_1,1.0 //
maitreya uvāca / parāśaraṃ munivaraṃ // ViP_1,1.1 //
kathaṃ jagad idaṃ brahman // ViP_1,1.2 //
tato 'bravīt sa bhagavān // ViP_2,1.1 //
""",
    # BrP_1.1a — pāda-level, marker at line end, no slashes
    "bare_suffix": HEAD + """
nārāyaṇaṃ namaskṛtya BrP_1.1a
naraṃ caiva narottamam BrP_1.1b
devīṃ sarasvatīṃ vyāsaṃ BrP_1.1c
tato jayam udīrayet BrP_1.1d
munayaḥ śaunakādyāś ca BrP_1.3
""",
    # /AP_1.001ab/ — half-verse, zero-padded, single slashes, plus apparatus
    "agni_halfverse": HEAD + """
% chapter {1}
:ś śriyaṃ(1) sarasvatīṃ gaurīṃ gaṇeśaṃ skandam īśvaram /AP_1.001ab/
brahmāṇaṃ vahnim indrādīn vāsudevaṃ namāmyaham /AP_1.002cd/
""",
    # RKV_1.1 // — marker at LINE START
    "line_start": HEAD + """
RKV_1.1 // oṃ namaḥ śivāya
RKV_1.2 // sūta uvāca
""",
    # AsvSS_1.1/1:  — prefix, dots for word boundaries, trailing ritual tag
    "colon_prefix_sutra": HEAD + """
AsvSS_1.1/1: atha.etasya.samāmnāyasya.vitāne.yoga.āpattim.vakṣyāmaḥ./ (darśa: hotṛ)
AsvSS_1.1/2: agny.ādheya.prabhṛtīny.āha.vaitānikāni./ (darśa: hotṛ)
AsvSS_1.2/1: idhmam.apareṇa.apraṇīte./ (darśa: hotṛ)
""",
    # (kauśs_1,1.1) — parenthesised prefix
    "paren_prefix": HEAD + """
(kauśs_1,1.1) atha vidhiṃ vakṣyāmi
(kauśs_1,1.2) sa punar āmnāyapratyayaḥ
""",
    # <1.1.1> — angle prefix; <...> also wraps inline AV quotations
    "angle_prefix": HEAD + """
<1.1.1> atha vitānasya | brahmā karmāṇi brahmavedavid dakṣiṇato vidhivad upaviśati ||
<1.1.2> homān ādiṣṭān anumantrayate ||
""",
    # // mangs_1,1.1 // — marker trails the sūtra
    "suffix_double_slash": HEAD + """
oṃ upanayanaprabhṛti vratacāri syāt // mangs_1,1.1 //
muñjāṃ mekhalāṃ dhārayed ācāryasyāpratikūlaḥ // mangs_1,1.2 //
""",
    # || āpśus_1.1 || — mūla interleaved with unmarked commentary
    "shulba_suffix": HEAD + """
uktā yajñāḥ / teṣāṃ agnyāyatanāni niyatapramāṇāni /
vihārayogān vyākhyāsyāmaḥ || āpśus_1.1 ||
vihiyante 'sminn agnaya iti vihārāḥ /
caturasraṃ karoti || āpśus_1.2 ||
""",
    # 1,1: — no siglum, and the SAME ref repeats across consecutive lines
    "nirukta_prefix": HEAD + """
1,1: samāmnāyaḥ.samāmnātaḥ.sa.vyākhyātavyaḥ
1,1: tam.imam.samāmnāyam.nighaṇṭava.ity.ācakṣate
1,1: nighaṇṭavaḥ.kasmāt
1,2: bhāva.pradhānam.ākhyātam
""",
    # // 1 — bare verse number, no siglum at all
    "bare_verse_number": HEAD + """
pañcasaṃvatsaramayaṃ yugādhyakṣaṃ prajāpatim /
dinartvayanam āsāṅgaṃ praṇamya śirasā śuciḥ // 1
praṇamya śirasā kālam abhivādya sarasvatīm /
kālajñānaṃ pravakṣyāmi lagadhasya mahātmanaḥ // 2
""",
}


def check(name, condition, detail=""):
    mark = "ok  " if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"   {detail}" if detail and not condition else ""))
    return bool(condition)


def main():
    failures = 0
    registry = G.load_registry()
    patterns = registry["marker_patterns"]
    specs = {t["id"]: t for t in registry["texts"]}

    print("A. registry integrity")
    failures += not check("every text names a defined marker",
                          not ({t["marker"] for t in registry["texts"]} - set(patterns)))
    failures += not check("no unused marker patterns",
                          not (set(patterns) - {t["marker"] for t in registry["texts"]}))
    failures += not check("every text has target/schema/licence",
                          all(t.get("target") and t.get("schema") and t.get("licence")
                              for t in registry["texts"]))
    failures += not check("partial texts declare their scope",
                          all(t.get("scope") for t in registry["texts"]
                              if not t.get("complete")))
    failures += not check("reference-only texts excluded from --all",
                          all(t.get("licence") == "cc-by-nc-sa-4.0"
                              for t in registry["texts"]
                              if t.get("licence") != "reference-only"))

    print("\nB. every marker grammar parses its real-world fixture")
    for marker, raw in FIXTURES.items():
        spec = next(t for t in registry["texts"] if t["marker"] == marker)
        units, attribution, matched = G.parse(raw, dict(spec, _ext="txt"), patterns)
        failures += not check(f"{marker}: matched markers", matched > 0, matched)
        failures += not check(f"{marker}: produced units", len(units) > 0, units)
        if units:
            joined = " ".join(u[2] for u in units)
            failures += not check(f"{marker}: header never leaks",
                                  "SANSKNET" not in joined and "REFERENCE PURPOSES" not in joined,
                                  joined[:60])
            failures += not check(f"{marker}: apparatus stripped",
                                  "% chapter" not in joined and "(darśa" not in joined,
                                  joined[:80])

    print("\nC. per-grammar specifics")
    units, _, _ = G.parse(FIXTURES["slash_book_chapter_verse"],
                          dict(specs["vishnu_purana"], _ext="txt"), patterns)
    failures += not check("ViP: book captured as first ref",
                          [u[0][0] for u in units] == ["1", "1", "1", "2"],
                          [u[0] for u in units])
    failures += not check("ViP: maṅgala verse 0 kept", units[0][0][-1] == "0", units[0][0])

    units, _, _ = G.parse(FIXTURES["bare_suffix"],
                          dict(specs["brahma_purana"], _ext="txt"), patterns)
    failures += not check("BrP: pāda letter captured",
                          [u[1] for u in units[:4]] == ["a", "b", "c", "d"],
                          [u[1] for u in units[:4]])

    units, _, _ = G.parse(FIXTURES["nirukta_prefix"],
                          dict(specs["nirukta"], _ext="txt"), patterns)
    items = G.group_items(units, specs["nirukta"])
    # The fixture is adhyāya 1, sections 1 and 2, with "1,1:" repeated on three
    # consecutive lines. One adhyāya item is correct; four units inside it is
    # the thing that must not collapse.
    failures += not check("Nirukta: one adhyāya item, not one per line",
                          len(items) == 1, [i["id"] for i in items])
    failures += not check("Nirukta: all four lines survive grouping",
                          len(units) == 4, [u[0] for u in units])
    failures += not check("Nirukta: repeated ref does not duplicate the item",
                          len({i["id"] for i in items}) == len(items))

    units, _, _ = G.parse(FIXTURES["colon_prefix_sutra"],
                          dict(specs["ashvalayana_shrautasutra"], _ext="txt"), patterns)
    failures += not check("AsvSS: ritual tag removed",
                          all("hotṛ" not in u[2] for u in units),
                          [u[2][-25:] for u in units])
    failures += not check("AsvSS: dot word-boundaries preserved",
                          any("." in u[2] for u in units))

    units, _, _ = G.parse(FIXTURES["agni_halfverse"],
                          dict(specs["agni_purana"], _ext="txt"), patterns)
    failures += not check("AP: half-verse pāda captured",
                          [u[1] for u in units] == ["ab", "cd"], [u[1] for u in units])
    failures += not check("AP: ':ś' line prefix stripped",
                          all(":ś" not in u[2] for u in units), [u[2][:20] for u in units])

    print("\nD. item shaping")
    units, _, _ = G.parse(FIXTURES["slash_book_chapter_verse"],
                          dict(specs["vishnu_purana"], _ext="txt"), patterns)
    items = G.group_items(units, specs["vishnu_purana"])
    failures += not check("purana schema nests shlokas",
                          all("shlokas" in i for i in items), items[0].keys())
    failures += not check("two aṃśas produced", len(items) == 2, [i["id"] for i in items])
    failures += not check("ids zero-padded", items[0]["id"] == "amsha_01", items[0]["id"])

    units, _, _ = G.parse(FIXTURES["bare_verse_number"],
                          dict(specs["vedanga_jyotisha_arca"], _ext="txt"), patterns)
    items = G.group_items(units, specs["vedanga_jyotisha_arca"])
    failures += not check("generic schema uses flat sanskrit_text",
                          "sanskrit_text" in items[0] and "shlokas" not in items[0],
                          list(items[0]))
    failures += not check("IAST retained alongside Devanagari",
                          items[0]["iast_text"] and items[0]["sanskrit_text"].startswith("«"))

    print("\nE. provenance and licence")
    note = G.build_note(specs["agni_purana"], "Data entry: Jun Takashima")
    failures += not check("CC licence recorded", "CC BY-NC-SA 4.0" in note, note[:70])
    failures += not check("third-party copyright carried",
                          "Takashima" in note, note[:200])
    note = G.build_note(specs["skanda_purana_ce"], "")
    failures += not check("reference-only licence recorded",
                          "REFERENCE PURPOSES ONLY" in note, note[:70])
    failures += not check("partial scope recorded in the note",
                          "1-31.14" in note, note[:200])

    print("\nF. failure modes")
    empty, _, matched = G.parse(HEAD, dict(specs["vishnu_purana"], _ext="txt"), patterns)
    failures += not check("no markers -> no units (caller raises)",
                          empty == [] and matched == 0)

    print()
    if failures:
        print(f"{failures} check(s) FAILED")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
