#!/usr/bin/env python3
"""
build_batch6_darshana_gaps.py -- 23 Aug, prompted by the project lead
asking to "just check" the classical darshana branches (Nyaya, Vaisheshika,
Sankhya, Yoga, Mimamsa) for anything DCS has that isn't in yet, rather
than assuming batches 2/4 already caught everything.

A full re-scan of the DCS text list for darshana-adjacent names (not just
the ones already touched) found 6 more matches, one of them a real
correction to batch 4's own claim:

- Samkhyakarika's MULA TEXT ITSELF is in DCS after all ("Samkhyakarika",
  1 file) -- batch 4's commit message and dge/PENDING.md both said "the
  Samkhyakarika/Samkhyasutra mula texts are not in DCS at all", checked
  by *listing the mirror directory*, not by grepping the full text-name
  list the way this pass did. That check was real but incomplete: it
  ruled out a directory named exactly "Samkhyakarika" not being found by
  the specific probe used at the time, when in fact it existed all
  along under that very name. Corrected here rather than left standing.
- Samkhyakarikabhashya -- its own DCS name is generic ("commentary on
  Samkhyakarika", chapter line "SKBh zu SamKar"), not attributed to a
  specific author in the corpus metadata. Placed under the existing
  tika_gaudapada stub on the strength of "Samkhyakarikabhashya" being
  the standard scholarly name for Gaudapada's commentary specifically --
  a reasonable but NOT DCS-confirmed attribution, flagged as such in
  dge/PENDING.md rather than asserted as fact.
- Mimamsasutrabhashya -- self-titled, standalone (not "zu" some other
  text), matching the existing empty shabara_bhashya leaf (Sabara's
  bhashya is THE Mimamsasutrabhashya by convention -- high confidence).
- Tattvavaisharadi -- "zu YS, 4, 1.1" (commentary on Yogasutra 4.1),
  matching the existing empty tika_tattva_vaisharadi stub exactly.
- Vaisheshikasutravritti -- "zu VaishSu" -- a vritti on Vaisheshikasutra,
  but the existing taxonomy node under vaisheshika_sutra only had "mula".
  Added a new "vritti" leaf rather than guessing whose vritti it is
  (DCS's own metadata doesn't name an author here either).
- Sarvadarshanasamgraha -- its own chapter names ARE darshana-school
  names ("SDS, Raseshvaradarshana" etc.) -- a doxography surveying every
  school, not one darshana's own text. Doesn't belong nested under any
  single darshana; added as its own leaf directly under "darshana".
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

# New taxonomy.json nodes only -- everything else below fills an
# already-existing empty leaf.
NEW_VAISHESHIKA_VRITTI_KEY = "vritti"
NEW_SARVADARSHANA_NODE = OD([("mula", OD([("_schema", "grantha_mula_text"), ("_default_author", "Madhava Vidyaranya")]))])

ENTRIES = [
    ("Sāṃkhyakārikā", "dge/data/darshana/sankhya/sutra_and_karika/samkhya_karika/mula/data.json", "samkhya_karika_mula", "साङ्ख्यकारिका", None),
    ("Sāṃkhyakārikābhāṣya", "dge/data/darshana/sankhya/sutra_and_karika/samkhya_karika/tika_gaudapada/data.json", "samkhya_karika_gaudapada", "साङ्ख्यकारिका (गौडपादभाष्यम् — DCS-असंपुष्टः कर्तृनिर्देशः)", None),
    ("Mīmāṃsāsūtrabhāṣya", "dge/data/darshana/mimamsa/sutra_and_bhashya/mimamsa_sutra/shabara_bhashya/data.json", "mimamsa_sutra_shabara_bhashya", "मीमांसासूत्रम् (शाबरभाष्यम्)", None),
    ("Tattvavaiśāradī", "dge/data/darshana/yoga/sutra_and_bhashya/yoga_sutra/tika_tattva_vaisharadi/data.json", "yoga_tattva_vaisharadi", "योगसूत्राणि (तत्त्ववैशारदी)", None),
    ("Vaiśeṣikasūtravṛtti", "dge/data/darshana/vaisheshika/sutra_and_bhashya/vaisheshika_sutra/vritti/data.json", "vaisheshika_sutra_vritti", "वैशेषिकसूत्राणि (वृत्तिः — DCS-असंपुष्टः कर्तृनिर्देशः)", "new_top_leaf"),
    ("Sarvadarśanasaṃgraha", "dge/data/darshana/sarvadarshana_sangraha/mula/data.json", "sarvadarshana_sangraha", "सर्वदर्शनसङ्ग्रहः", "new_top_leaf"),
]


def merge_taxonomy():
    path = os.path.join(REPO, "dge/data/taxonomy.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)

    vs_node = d["darshana"]["vaisheshika"]["sutra_and_bhashya"]["vaisheshika_sutra"]
    assert NEW_VAISHESHIKA_VRITTI_KEY not in vs_node
    vs_node[NEW_VAISHESHIKA_VRITTI_KEY] = OD([("_schema", "grantha_tika_text")])

    assert "sarvadarshana_sangraha" not in d["darshana"]
    d["darshana"]["sarvadarshana_sangraha"] = NEW_SARVADARSHANA_NODE

    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("taxonomy.json: added darshana.vaisheshika...vaisheshika_sutra.vritti and darshana.sarvadarshana_sangraha")


def update_library(populated_paths, new_leaf_paths):
    path = os.path.join(REPO, "dge/data/library.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)
    by_path = {g["path"]: g for g in d["granthas"]}
    flipped = 0
    added = 0
    for _, rel_out, _, title, kind in ENTRIES:
        if rel_out in by_path:
            if rel_out in populated_paths and not by_path[rel_out]["populated"]:
                by_path[rel_out]["populated"] = True
                flipped += 1
        else:
            assert kind == "new_top_leaf", f"unexpected new library.json path {rel_out}"
            d["granthas"].append(collections.OrderedDict([
                ("path", rel_out),
                ("populated", rel_out in populated_paths),
                ("title", title),
            ]))
            added += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"library.json: flipped {flipped} existing leaves to populated, added {added} new entries")


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
                "entry (batch 6, darshana gap re-check), for how this was matched "
                "and, for Samkhyakarika, a correction to batch 4's own claim."
            ),
            tag="dcs-import",
        )
        populated_paths.add(rel_out)
        print(f"{dcs_name}: {n} files -> {count} items -> {rel_out}")
    return populated_paths


def main():
    merge_taxonomy()
    populated_paths = run_imports()
    new_leaf_paths = {rel_out for _, rel_out, _, _, kind in ENTRIES if kind == "new_top_leaf"}
    update_library(populated_paths, new_leaf_paths)
    print(f"\n{len(populated_paths)}/{len(ENTRIES)} matched and imported")


if __name__ == "__main__":
    main()
