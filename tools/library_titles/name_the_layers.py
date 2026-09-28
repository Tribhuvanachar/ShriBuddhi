#!/usr/bin/env python3
"""Give every mula and tika a name that says what it is a mula or tika OF.

THE PROBLEM, in the lead's words: "it cannot be a standalone mula, it will be
mula of some text; it cannot be a standalone tika, it should be tika of some
mula". The catalogue had 127 entries titled exactly "Mula" and 38 titled "Tika
Jayatirtha" -- names that identify a FILE, not a work. In a library drawer or a
search result those are indistinguishable from each other, and a reader who
lands on one has no way to tell which grantha they are reading.

WHAT THIS WRITES, per layer entry:

  title   "<work> — <layer>", e.g. युक्तिमल्लिका — सत्यप्रमोदटीका
  partOf  the parent work's slug, so the hierarchy is in the DATA and not only
          inferable from the path
  role    mula | sutra | samhita | tika | tippani

WHERE THE NAMES COME FROM, in order, and never invented:
  * the curator's own label for that path (library-overrides.json)
  * the layer manifest's work title, and its per-layer label -- which is the
    majority `tika_title` carried by the layer's own items, i.e. the edition's
    own name for itself
  * js/path-labels.js, the same table the reader's drawer uses

WHERE A NAME IS NOT AVAILABLE the existing title is kept as the layer half, so
`tika_keith` under a Taittiriya kanda becomes "... — Tika Keith" rather than
being forced into Devanagari it never had: Keith is an English translator and
writing his name in Devanagari would be a fiction. 578 of 851 layers can be
named in Devanagari on both halves today; the rest read honestly and improve
as labels are added, because this is derived and re-runnable.

Deliberately does NOT touch a non-layer entry: a grantha that is its own whole
text already has a real name.

Usage: python3 tools/library_titles/name_the_layers.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "data/library.json"
MANIFEST = ROOT / "data/layer_manifest.json"
LABELS_JS = ROOT / "js/path-labels.js"
OVERRIDES = ROOT / "admin/config/library-overrides.json"

# A path's last segment when the entry is a LAYER of the work above it.
# Folder names alone cannot decide this: `didhiti`, `gadadhari`, `jagadishi`
# and `mathuri` are commentaries named after their authors and look nothing
# like a layer, while `gita` or `isha` beside a mula are sub-WORKS and not
# layers at all. So this pattern is only the fallback; the layer manifest,
# which is built from the data, is asked first (see is_layer below).
LAYER = re.compile(r"^(mula(_.+)?|sutra|samhita|tika|tika_.+|tippani|tippani_.+)$")
ROLE_STEMS = ("mula", "sutra", "samhita", "tippani")


def role_of(folder: str) -> str:
    """Match on the STEM: an edition suffix ("mula_dcs") does not stop a mula
    being a mula, and filing one as a tika would say the text comments on
    itself. Anything else is a tika, which is what the rest of them are."""
    for stem in ROLE_STEMS:
        if folder == stem or folder.startswith(stem + "_"):
            return stem
    return "tika"
INDIC = re.compile(r"[ऀ-ॿಀ-೿]")
# The separator. An em dash with spaces, matching what the manifest already
# uses for the same idea ("गीताभाष्यम् — tika_bhashya").
SEP = " — "


def load_labels() -> dict[str, str]:
    text = LABELS_JS.read_text(encoding="utf-8")
    return dict(re.findall(r"([A-Za-z0-9_]+):\s*'([^']*)'", text))


def auto_label(seg: str) -> str:
    return re.sub(r"[_-]+", " ", seg).title()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    raw = LIBRARY.read_text(encoding="utf-8")
    lib = json.loads(raw)
    man = json.loads(MANIFEST.read_text(encoding="utf-8")).get("granthas") or {}
    labels = load_labels()
    custom = (json.loads(OVERRIDES.read_text(encoding="utf-8")) or {}).get("labels") or {}

    work_title, layer_label = {}, {}
    for fam, entry in man.items():
        if entry.get("title") and entry["title"] != "Mula":
            work_title[fam] = entry["title"]
        for layer in entry.get("layers") or []:
            layer_label[(fam, layer["folder"])] = layer.get("label") or ""

    changed, both_indic = 0, 0
    updates: dict[str, dict] = {}
    for g in lib["granthas"]:
        slug = g["path"][5:-10]
        parts = slug.split("/")
        if len(parts) < 2:
            continue
        family, folder = "/".join(parts[:-1]), parts[-1]
        # The manifest lists a family's real layers, worked out from the ids
        # the files actually share, so it settles cases no folder name can.
        if (family, folder) not in layer_label and not LAYER.match(folder):
            continue
        # Last resort is the parent FOLDER humanised, never nothing: a layer
        # with no work name in front of it is the standalone "Mula" this tool
        # exists to abolish, and it is no better for being in Devanagari.
        work = (custom.get(family) or work_title.get(family)
                or labels.get(parts[-2]) or auto_label(parts[-2]))
        layer = (layer_label.get((family, folder)) or labels.get(folder)
                 or (g.get("title") if g.get("title") != "Mula" else "")
                 or auto_label(folder))
        role = role_of(folder)
        title = f"{work}{SEP}{layer}"
        if work and INDIC.search(work) and INDIC.search(layer):
            both_indic += 1
        if g.get("title") != title or g.get("partOf") != family or g.get("role") != role:
            changed += 1
        updates[g["path"]] = {"title": title, "partOf": family, "role": role}

    print(f"{len(updates)} layer entries, {changed} would change, "
          f"{both_indic} named in Indic script on both halves")
    for path in list(updates)[:6]:
        print(f"   {updates[path]['title'][:58]:<58} {updates[path]['role']}")

    if args.check:
        return 0

    # Textual, one entry at a time. library.json is 17k lines and must not be
    # reserialised (CLAUDE.md): a reformat buries the real change and has twice
    # produced diffs in the millions of lines here.
    lines = raw.split("\n")
    out, i, applied = [], 0, 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(\s*)"path": "([^"]+)",$', line)
        if not m or m.group(2) not in updates:
            out.append(line)
            i += 1
            continue
        indent, path = m.group(1), m.group(2)
        upd = updates[path]
        out.append(line)
        i += 1
        # Rewrite this entry's title in place; drop any stale partOf/role, then
        # add ours straight after the title so the fields read together.
        while i < len(lines) and not re.match(r'^\s*\},?$', lines[i]):
            if re.match(r'^\s*"(partOf|role)":', lines[i]):
                i += 1
                continue
            if re.match(r'^\s*"title":', lines[i]):
                out.append(f'{indent}"title": {json.dumps(upd["title"], ensure_ascii=False)},')
                out.append(f'{indent}"partOf": {json.dumps(upd["partOf"], ensure_ascii=False)},')
                out.append(f'{indent}"role": "{upd["role"]}",')
                applied += 1
                i += 1
                continue
            out.append(lines[i])
            i += 1
    text = "\n".join(out)
    json.loads(text)  # refuse to write anything that is not valid JSON
    LIBRARY.write_text(text, encoding="utf-8")
    print(f"rewrote {applied} entries in {LIBRARY.relative_to(ROOT)}")
    if applied != len(updates):
        print(f"  NOTE: {len(updates) - applied} had no title line to replace",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
