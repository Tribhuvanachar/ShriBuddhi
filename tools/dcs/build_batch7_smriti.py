#!/usr/bin/env python3
"""
build_batch7_smriti.py -- 23 Aug, prompted to "get the entire fold" of
the Smriti/Dharmashastra cluster. Checked library.json first (not
assumed): Manusmriti, Naradasmriti, Parasharasmriti, Vishnusmriti and
Yajnavalkyasmriti are ALREADY populated:true with NO "source" field --
i.e. sourced from somewhere other than DCS, before this session existed.
DCS also carries all five of these under slightly different names
(Parasharasmriti's DCS name is "Parasharadharmasamhita") -- re-importing
them from DCS would create a second, conflicting version inside an
already-filled leaf, the same duplicate-content risk the Mahabharata/
Ramayana check caught back in the pilot import. Left untouched.

Three real, safe DCS matches instead:
- Vriddhayamasmriti -> the existing empty yama_smriti leaf (it is
  specifically the "Vriddha" recension; noted in the item's own source
  metadata, not folded into the taxonomy key name).
- Katyayanasmriti -> no existing leaf matched this name; added a new
  one (smriti_dharma.smriti.katyayana_smriti).
- Nibandhasamgraha -- a real near-miss caught by checking its own DCS
  chapter header rather than trusting the name: it looked like it might
  belong to the dharmashastra nibandha cluster (Dayabhaga/Mitakshara/
  Kalpataru/etc are all named "-nibandha"-genre works), but its chapter
  line is "NiSam zu Su, Cik., 27, 2.1" -- a commentary ON Sushrutasamhita,
  not a dharmashastra digest at all. "Nibandhasangraha" is in fact the
  standard name of Dalhana's own commentary on Sushrutasamhita. Added as
  a new tika leaf under the existing sushruta_samhita node instead.

Checked and confirmed absent from DCS (not silently skipped): none of
the 7 dharmashastra-nibandha leaves (Dayabhaga, Mitakshara, Kalpataru,
Nirnayasindhu, Dharmasindhu, Smritichandrika, Chaturvargachintamani) or
Parasharasmritika (Madhava's tika on Parasharadharmasamhita -- DCS has
it, "Parasharasmritika zu ParDhSmriti", but the existing parashara_smriti
leaf is a FLAT single-file leaf with no mula/tika substructure to attach
a commentary to, and restructuring an already-populated, already-live
leaf just to fit one commentary is out of scope here -- flagged in
dge/PENDING.md instead) have a safe match this round.

Also fixes a real site-catalog gap unrelated to DCS: taxonomy.json has
had vasistha_smriti and baudhayana_smriti leaves with no library.json
registration at all (found while auditing this cluster) -- registered
as populated:false stubs. No DCS match found for either name either
(checked: DCS's Vasishthadharmasutra/Baudhayanadharmasutra are already
imported elsewhere, under vedanga/kalpa, and there's no separately-named
"Vasisthasmriti"/"Baudhayanasmriti" text in DCS's list).
"""
import collections
import json
import os
import shutil

from dcs_common import build_generic_import

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DCS_MIRROR = os.environ.get(
    "DCS_MIRROR",
    "/tmp/claude-0/-home-user-bhumandala/e8a5c83c-760f-5d7b-9fbc-3df8440bd264/scratchpad/sanskrit_check/dcs/data/conllu/files",
)
VENDOR_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
SOURCE_NAME = "Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024"
LICENCE = "CC-BY 4.0"
OD = collections.OrderedDict

ENTRIES = [
    ("Vṛddhayamasmṛti", "dge/data/smriti_dharma/smriti/yama_smriti/data.json", "vriddha_yama_smriti", "यमस्मृतिः (वृद्धयमस्मृतिः)", None),
    ("Kātyāyanasmṛti", "dge/data/smriti_dharma/smriti/katyayana_smriti/data.json", "katyayana_smriti", "कात्यायनस्मृतिः", "new_leaf"),
    ("Nibandhasaṃgraha", "dge/data/vedas/upaveda/ayurveda/samhita/sushruta_samhita/tika_nibandhasangraha/data.json", "sushruta_nibandhasangraha", "सुश्रुतसंहिता (निबन्धसङ्ग्रहः — डल्हणः)", "new_leaf"),
]

# library.json stubs for pre-existing taxonomy.json nodes with no catalog entry
CATALOG_GAP_STUBS = [
    ("dge/data/smriti_dharma/smriti/vasistha_smriti/data.json", "वसिष्ठस्मृतिः"),
    ("dge/data/smriti_dharma/smriti/baudhayana_smriti/data.json", "बौधायनस्मृतिः"),
]


def merge_taxonomy():
    path = os.path.join(REPO, "dge/data/taxonomy.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)

    smriti = d["smriti_dharma"]["smriti"]
    assert "katyayana_smriti" not in smriti
    smriti["katyayana_smriti"] = OD([("_default_author", "Katyayana")])

    sushruta = d["vedas"]["upaveda"]["ayurveda"]["samhita"]["sushruta_samhita"]
    assert "tika_nibandhasangraha" not in sushruta
    sushruta["tika_nibandhasangraha"] = OD([("_schema", "grantha_tika_text"), ("_default_author", "Dalhana")])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("taxonomy.json: added smriti_dharma.smriti.katyayana_smriti and sushruta_samhita.tika_nibandhasangraha")


def update_library(populated_paths):
    path = os.path.join(REPO, "dge/data/library.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)
    by_path = {g["path"]: g for g in d["granthas"]}
    flipped = added = 0

    for _, rel_out, _, title, kind in ENTRIES:
        if rel_out in by_path:
            if rel_out in populated_paths and not by_path[rel_out]["populated"]:
                by_path[rel_out]["populated"] = True
                flipped += 1
        else:
            assert kind == "new_leaf", f"unexpected new library.json path {rel_out}"
            d["granthas"].append(OD([("path", rel_out), ("populated", rel_out in populated_paths), ("title", title)]))
            added += 1

    for rel_out, title in CATALOG_GAP_STUBS:
        assert rel_out not in by_path, rel_out
        d["granthas"].append(OD([("path", rel_out), ("populated", False), ("title", title)]))
        added += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"library.json: flipped {flipped}, added {added} (incl. {len(CATALOG_GAP_STUBS)} catalog-gap stubs)")


def run_imports():
    populated_paths = set()
    for dcs_name, rel_out, slug, _, _ in ENTRIES:
        src_dir = os.path.join(DCS_MIRROR, dcs_name)
        if not os.path.isdir(src_dir):
            print(f"SKIP {dcs_name}: not found in DCS mirror")
            continue
        vendor_dir = os.path.join(VENDOR_ROOT, slug)
        os.makedirs(vendor_dir, exist_ok=True)
        n = 0
        for fname in os.listdir(src_dir):
            if fname.endswith(".conllu"):
                shutil.copy(os.path.join(src_dir, fname), os.path.join(vendor_dir, fname))
                n += 1
        out_path = os.path.join(REPO, rel_out)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        count, chapters = build_generic_import(
            vendor_dir, out_path,
            source_name=SOURCE_NAME,
            source_url=f"https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/conllu/files/{dcs_name}",
            licence=LICENCE,
            note=(
                "{count} units across {chapters} -- see dge/PENDING.md, 23 Aug "
                "entry (batch 7, Smriti/Dharmashastra sweep), for how this was "
                "matched."
            ),
            tag="dcs-import",
        )
        populated_paths.add(rel_out)
        print(f"{dcs_name}: {n} files -> {count} items -> {rel_out}")
    return populated_paths


def main():
    merge_taxonomy()
    populated_paths = run_imports()
    update_library(populated_paths)
    print(f"\n{len(populated_paths)}/{len(ENTRIES)} matched and imported")


if __name__ == "__main__":
    main()
