"""Śatapatha Brāhmaṇa (Mādhyandina) from github.com/vishvasa/vedAH_yajuH.

SOURCE: vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH in
github.com/vishvasa/vedah_yajuh — maintained by Vishwas Vasukijah, the same
maintainer whose vishvasa/ramanujiyam this project already imports with his
permission (see importers/ramanuja_mula.py); the same case-by-case
non-commercial permission convention (dge/PROJECT_STATUS.md) applies here,
project-lead directed (1 Sep 2026).

Source layout: Hugo markdown, one file per brāhmaṇa —
    sarva-prastutiH/<kāṇḍa>/<adhyāya>/<brāhmaṇa>.md
(kāṇḍa 14 nests grouping dirs for its Bṛhadāraṇyaka portion, e.g.
01-05_bRhad-AraNyakopaniShat/03-04_muni-kANDaH/<adhyāya>/<brāhmaṇa>.md —
the numeric tail is still adhyāya/brāhmaṇa; the group labels go into the
breadcrumb only). Inside each file, `## <devanagari number>` opens one
kaṇḍikā, and per kaṇḍikā the layers sit in <details> blocks whose
<summary> names them:

    विश्वास-प्रस्तुतिः   the curated accented text  -> mula/
    सायणः                Sāyaṇa's bhāṣya            -> tika_sayana/
    Eggeling             SBE English translation    -> tika_eggeling/
    मूलम् - श्रीधरादि / Weber / विस्वरम्             edition variants — NOT
                         imported (recorded in the meta note); they repeat
                         the mūla text per manuscript tradition and would
                         triple the size for variant-collation value the
                         reader has no surface for yet.

OUTPUT: dge/data/vedas/yajurveda/shukla_yajurveda/
        vajasaneyi_madhyandina_shakha/brahmana/shatapatha_brahmana/
        kanda_NN/{mula,tika_sayana,tika_eggeling}/data.json
DV-style layered folders sharing item ids (kāṇḍa.adhyāya.brāhmaṇa.kaṇḍikā),
so tools/build_layer_manifest.py stitches Sāyaṇa/Eggeling as tabs on the
mūla spine exactly like Nyāyasudhā.

Run:  python3 importers/shatapatha_madhyandina.py [--src PATH] [--out PATH]
"""
import argparse
import json
import os
import re
import sys
from collections import OrderedDict

DEFAULT_SRC = "/home/user/vishvasa/vedah_yajuh/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH"
DEFAULT_OUT = "dge/data/vedas/yajurveda/shukla_yajurveda/vajasaneyi_madhyandina_shakha/brahmana/shatapatha_brahmana"

REPO_NOTE = ("github.com/vishvasa/vedAH_yajuH (vAjasaneyam/mAdhyandinam/"
             "shatapatha-brAhmaNam), maintained by Vishwas Vasukijah; used with his "
             "permission per the vishvasa/ramanujiyam precedent (non-commercial, "
             "educational). Weber/Sridharadi/visvaram edition variants present in "
             "the source are not imported. Eggeling's translation is from the "
             "Sacred Books of the East (1882-1900), public domain.")

DETAILS_RE = re.compile(r"<details[^>]*>\s*<summary>(.*?)</summary>(.*?)</details>", re.S)
UNIT_RE = re.compile(r"^##\s+([०-९0-9]+)\s*$", re.M)
FRONT_RE = re.compile(r"\A\+\+\+.*?\+\+\+\s*", re.S)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
DEVA_DIGITS = "०१२३४५६७८९"


def deva_int(s):
    t = "".join(str(DEVA_DIGITS.index(c)) if c in DEVA_DIGITS else c for c in s.strip())
    try:
        return int(t)
    except ValueError:
        return None


def clean_body(text):
    text = COMMENT_RE.sub("", text or "")
    # keep footnote markers/definitions (scholarly apparatus), drop stray
    # markdown emphasis that would render literally in the plain-text reader
    text = text.replace("**", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


LAYER_OF = [
    (lambda s: s.startswith("विश्वास-प्रस्तुतिः"), "mula"),
    (lambda s: s.startswith("सायण"), "tika_sayana"),
    (lambda s: s.startswith("Eggeling") or s.startswith("सिद्धार्थः"), "tika_eggeling"),
]


def route(summary):
    s = summary.strip()
    for test, folder in LAYER_OF:
        if test(s):
            return folder
    return None  # मूलम् variants, विस्तारः, anything unknown -> skipped


def parse_brahmana(path):
    """One brāhmaṇa .md -> [(kandika_number_or_0, {folder: (summary, text)})]."""
    raw = open(path, encoding="utf-8").read()
    body = FRONT_RE.sub("", raw)
    parts = UNIT_RE.split(body)
    # parts = [preamble, num1, chunk1, num2, chunk2, ...]
    units = []
    if parts[0].strip():
        units.append((0, parts[0]))
    for i in range(1, len(parts) - 1, 2):
        num = deva_int(parts[i])
        units.append((num if num is not None else 0, parts[i + 1]))
    out = []
    for num, chunk in units:
        layers = {}
        for m in DETAILS_RE.finditer(chunk):
            folder = route(m.group(1))
            if not folder or folder in layers:
                continue
            text = clean_body(m.group(2))
            if len(text) < 2:
                continue
            layers[folder] = (m.group(1).strip(), text)
        if layers:
            out.append((num, layers))
    return out


def walk(src):
    """Yield (kanda:int, group_labels:[str], adhyaya:int, brahmana:int, path)."""
    for kanda in sorted(os.listdir(src)):
        kdir = os.path.join(src, kanda)
        if not os.path.isdir(kdir) or not kanda.isdigit():
            continue
        for root, _dirs, files in os.walk(kdir):
            for f in sorted(files, key=lambda x: (len(x), x)):
                if not f.endswith(".md") or f in ("_index.md", "file_list.md"):
                    continue
                stem = f[:-3]
                if not stem.isdigit():
                    continue
                rel = os.path.relpath(root, kdir)
                segs = [] if rel == "." else rel.split(os.sep)
                # numeric tail = adhyāya; leading non-plain-numeric segs are
                # group labels (kāṇḍa 14's Bṛhadāraṇyaka nesting)
                adhyaya = None
                labels = []
                for s in segs:
                    if s.isdigit():
                        adhyaya = int(s)
                    else:
                        labels.append(re.sub(r"^[0-9-]+_", "", s).replace("-", " "))
                if adhyaya is None:
                    continue
                yield int(kanda), labels, adhyaya, int(stem), os.path.join(root, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    grantha_title = "शतपथब्राह्मणम् (माध्यन्दिनम्)"
    per_kanda = OrderedDict()  # kanda -> folder -> [items]
    counts = {"files": 0, "units": 0, "dupes": 0}
    seen_ids = {}

    for kanda, labels, adhyaya, brahmana, path in sorted(walk(args.src)):
        counts["files"] += 1
        for num, layers in parse_brahmana(path):
            uid = f"{kanda}.{adhyaya}.{brahmana}.{num}"
            key = (kanda, uid)
            if key in seen_ids:
                counts["dupes"] += 1
                suffix = 2
                while (kanda, f"{uid}-{suffix}") in seen_ids:
                    suffix += 1
                uid = f"{uid}-{suffix}"
            seen_ids[(kanda, uid)] = 1
            crumb = [grantha_title, f"काण्डम् {kanda}"] + labels + \
                    [f"अध्यायः {adhyaya}", f"ब्राह्मणम् {brahmana}", f"कण्डिका {num}"]
            counts["units"] += 1
            for folder, (summary, text) in layers.items():
                item = {
                    "id": uid,
                    "reference": " > ".join(crumb),
                    "section": f"काण्डम् {kanda} > अध्यायः {adhyaya}",
                    "unit_title": f"ब्राह्मणम् {brahmana} · कण्डिका {num}",
                    "sanskrit_text": text,
                    "artha": "", "notes": "", "tags": [], "references": [], "audio": [],
                    "breadcrumb": crumb,
                    "source": {
                        "repo": "github.com/vishvasa/vedAH_yajuH",
                        "path": os.path.relpath(path, args.src),
                        "layer": summary,
                    },
                }
                if folder != "mula":
                    item["tika_title"] = summary
                per_kanda.setdefault(kanda, {}).setdefault(folder, []).append(item)

    metas = {
        "mula": ("grantha_mula_text", "Apaurusheya (Shukla Yajurveda, Vajasaneyi Madhyandina Shakha)"),
        "tika_sayana": ("grantha_tika_text", "सायणाचार्यः"),
        "tika_eggeling": ("grantha_tika_text", "Julius Eggeling (tr., Sacred Books of the East)"),
    }
    for kanda, folders in per_kanda.items():
        for folder, items in folders.items():
            schema, author = metas[folder]
            d = os.path.join(args.out, f"kanda_{kanda:02d}", folder)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "data.json"), "w", encoding="utf-8") as f:
                json.dump({"schema": schema, "default_author": author,
                           "source": REPO_NOTE, "items": items},
                          f, ensure_ascii=False, indent=1)
    print(f"files={counts['files']} kandikas={counts['units']} "
          f"dupes-suffixed={counts['dupes']} kandas={len(per_kanda)}")
    for kanda, folders in per_kanda.items():
        print(f"  kanda_{kanda:02d}: " + " ".join(f"{k}={len(v)}" for k, v in folders.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
