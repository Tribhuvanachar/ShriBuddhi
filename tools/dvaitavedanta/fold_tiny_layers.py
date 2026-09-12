#!/usr/bin/env python3
"""Post-extract repair for auto-slugged heading layers.

The dvaitavedanta.in crawl mints one tika_<slug> folder per unmapped
heading. Real sub-commentaries arrive that way too, but so do two kinds
of noise (run 33543273107 minted 1,255 one-to-three-item folders):

  * numbered chunks of one named commentary — tika_23_kashitimmannacarya,
    tika_ramasubba_141, … — which belong together as a single layer;
  * one-off topic / pratika headings — adhikarana names, quoted lemmas —
    which belong inline in whatever layer the reader was inside at that
    point of the page, exactly where build_items' fold_rare_headings
    would have put them at crawl time.

This tool applies both repairs to an emitted tree, in that order:

  1. MERGE: unattributed layers whose digit-stripped slugs collide (and
     at least one member is numbered) are concatenated, ordered by
     content id, into tika_<stripped-name>.
  2. FOLD: remaining unattributed layers with <= --threshold items are
     folded item-by-item into the kept item with the nearest smaller
     content id across all of the grantha's surviving layers (content
     ids follow document order on the site), or open a new mula item
     when nothing precedes them.

Attributed layers, mula, and any folder name configured in
dv_sources.json (global or per-grantha "layers" maps) are never touched.
Run after merging shards, before registration/manifest steps.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import sys
from pathlib import Path

DEFAULT_THRESHOLD = 3  # fold layers with <= this many items


def load_configured_folders(config_path: Path) -> set[str]:
    folders: set[str] = set()
    if not config_path or not config_path.exists():
        return folders

    def walk(node):
        if isinstance(node, dict):
            layers = node.get("layers")
            if isinstance(layers, dict):
                for spec in layers.values():
                    if isinstance(spec, dict) and spec.get("folder"):
                        folders.add(spec["folder"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(config_path.read_text(encoding="utf-8")))
    return folders


def item_id_key(item: dict) -> int:
    m = re.search(r"(\d+)", str(item.get("id") or ""))
    return int(m.group(1)) if m else -1


_AUTHOR_MARK = re.compile(
    r"कृत|विरचित|रचित|तीर्थ|चार्य|यति|भगवत्|पण्डित|स्वामि|शास्त्रि"
    r"|भट्ट|दास|मुनि|सूरि|पाद")


def reliable_author(value: str) -> bool:
    """The crawl's attribution regex sometimes captures verse or pratika
    fragments ('८.', '१३. प्र', 'तदपि किं प्र'). Only a value with enough
    Devanagari letters AND an authorship marker (कृत/विरचित/तीर्थ/…)
    counts as a real attribution."""
    letters = re.findall(r"[ऀ-ॿ]", value or "")
    letters = [c for c in letters if not ("०" <= c <= "९")]
    return len(letters) >= 6 and bool(_AUTHOR_MARK.search(value or ""))


def strip_digits(slug: str) -> str:
    stripped = re.sub(r"(?<=[_a-z])\d+", "", slug)
    stripped = re.sub(r"_+", "_", stripped).strip("_")
    return stripped


def load_layer(path: Path) -> dict:
    return json.loads((path / "data.json").read_text(encoding="utf-8"))


def save_layer(path: Path, doc: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    # match import_dvaitavedanta.py's emit format exactly (indent=1,
    # no trailing newline) so untouched-vs-touched diffs stay honest
    (path / "data.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def process_grantha(grantha_dir: Path, configured: set[str], threshold: int,
                    report: list[str]) -> tuple[int, int, int]:
    layers: dict[str, dict] = {}
    for child in sorted(grantha_dir.iterdir()):
        if child.is_dir() and (child / "data.json").exists():
            layers[child.name] = load_layer(child)

    if "mula" not in layers:
        return (0, 0, 0)

    def is_candidate(name: str, doc: dict) -> bool:
        if name == "mula" or name in configured:
            return False
        if reliable_author((doc.get("default_author") or "").strip()):
            return False
        return True

    merged_layers = folded_layers = folded_items = 0

    # --- pass 1: merge numbered siblings of one name into one layer ---
    # Attribution does not block a merge here: the crawl attributes
    # chunk 1 of a numbered commentary (or captures a verse fragment as
    # the "author") while chunks 2..N arrive bare, so the folder-name
    # family is the reliable signal. The merged layer keeps the group
    # name and no default_author — author curation is a separate task.
    groups: dict[str, list[str]] = {}
    for name, doc in layers.items():
        if name == "mula" or name in configured:
            continue
        key = strip_digits(name)
        if key in ("", "tika"):
            continue
        groups.setdefault(key, []).append(name)

    for key, members in sorted(groups.items()):
        numbered = [m for m in members if m != key]
        if not numbered or len(members) < 2:
            continue
        target_doc = layers.get(key)
        if target_doc is None:
            template = layers[numbered[0]]
            target_doc = {
                k: v for k, v in template.items() if k != "items"
            }
            target_doc["items"] = []
            # keep an author only when every member agrees on it —
            # chunk-1 "author" captures must not label the whole layer
            member_authors = {
                (layers[m].get("default_author") or "").strip()
                for m in members
            }
            if len(member_authors) != 1:
                target_doc["default_author"] = ""
        pooled = list(target_doc.get("items") or [])
        for member in numbered:
            pooled.extend(layers[member].get("items") or [])

        def chunk_no(it: dict) -> int:
            label = str((it.get("source") or {}).get("layer") or "")
            digits = re.sub(r"\D", "", label.translate(
                str.maketrans("०१२३४५६७८९", "0123456789")))
            return int(digits) if digits else 0

        pooled.sort(key=lambda it: (item_id_key(it), chunk_no(it)))
        # One article can carry several sequential chunks of the same
        # commentary (रामसुब्ब_०१..०८ under one content id). They are
        # parts of one comment on one unit: concatenate them so ids
        # stay unique and the reader's id-based layer stitch holds.
        deduped: list[dict] = []
        for it in pooled:
            if deduped and deduped[-1].get("id") == it.get("id"):
                prev = deduped[-1]
                prev["sanskrit_text"] = (
                    (prev.get("sanskrit_text") or "").rstrip() + "\n"
                    + (it.get("sanskrit_text") or "").strip()).strip()
                if it.get("source_html") and not prev.get("source_html"):
                    prev["source_html"] = it["source_html"]
            else:
                deduped.append(it)
        target_doc["items"] = deduped
        pooled = deduped
        # One clean display title for the whole layer: the manifest's
        # layer_label takes the majority tika_title, which would
        # otherwise be an arbitrary chunk heading like "( १) भावप्रदीपः"
        # or "रामसुब्ब_०१". source.layer keeps each chunk's raw heading.
        titles = collections.Counter()
        for it in pooled:
            raw = (it.get("tika_title") or "").strip()
            clean = re.sub(r"[()\[\]०-९0-9._\-–—]+", " ", raw)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                titles[clean] += 1
        if titles:
            label = titles.most_common(1)[0][0]
            for it in pooled:
                if it.get("tika_title"):
                    it["tika_title"] = label
        save_layer(grantha_dir / key, target_doc)
        layers[key] = target_doc
        for member in numbered:
            shutil.rmtree(grantha_dir / member)
            del layers[member]
            merged_layers += 1
        report.append(
            f"  merge {grantha_dir.name}: {len(numbered)} folders -> "
            f"{key} ({len(pooled)} items)"
        )

    # --- pass 2: fold rare headings into the enclosing layer ---
    tiny = [
        name for name, doc in layers.items()
        if is_candidate(name, doc) and len(doc.get("items") or []) <= threshold
    ]
    if tiny:
        kept_index: list[tuple[int, str, int]] = []  # (id, layer, idx)
        for name, doc in layers.items():
            if name in tiny:
                continue
            for idx, item in enumerate(doc.get("items") or []):
                kept_index.append((item_id_key(item), name, idx))
        kept_index.sort()
        kept_ids = [entry[0] for entry in kept_index]

        import bisect

        pending: list[tuple[int, dict]] = []
        for name in tiny:
            for item in layers[name].get("items") or []:
                pending.append((item_id_key(item), item))
        pending.sort(key=lambda pair: pair[0])

        touched: set[str] = set()
        new_mula_items: list[dict] = []
        for nid, item in pending:
            pos = bisect.bisect_right(kept_ids, nid) - 1
            title = (item.get("tika_title") or item.get("unit_title")
                     or "").strip()
            text = (item.get("sanskrit_text") or "").strip()
            if pos >= 0:
                _, tname, tidx = kept_index[pos]
                target = layers[tname]["items"][tidx]
                addition = text if text.startswith(title) else (
                    f"{title}\n{text}" if title else text)
                target["sanskrit_text"] = (
                    (target.get("sanskrit_text") or "").rstrip()
                    + "\n" + addition).strip()
                if item.get("source_html") and not target.get(
                        "source_html"):
                    target["source_html"] = item["source_html"]
                touched.add(tname)
            else:
                moved = dict(item)
                moved.pop("tika_title", None)
                if title:
                    moved["unit_title"] = title
                new_mula_items.append(moved)
            folded_items += 1
        for name in tiny:
            shutil.rmtree(grantha_dir / name)
            del layers[name]
            folded_layers += 1

        if new_mula_items:
            mula = layers["mula"]
            items = list(mula.get("items") or []) + new_mula_items
            items.sort(key=item_id_key)
            mula["items"] = items
            touched.add("mula")

        for name in touched:
            save_layer(grantha_dir / name, layers[name])
        report.append(
            f"  fold  {grantha_dir.name}: {folded_layers} folders, "
            f"{folded_items} items -> enclosing layers"
        )

    return (merged_layers, folded_layers, folded_items)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True,
                    help="DvaitaVedanta output root (…/DvaitaVedanta)")
    ap.add_argument("--config",
                    default="tools/dvaitavedanta/dv_sources.json",
                    help="dv_sources.json for configured-folder exemptions")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                    help="fold unattributed layers with <= N items "
                         f"(default {DEFAULT_THRESHOLD})")
    args = ap.parse_args()

    root = Path(args.data)
    configured = load_configured_folders(Path(args.config))
    report: list[str] = []
    totals = [0, 0, 0]
    for section in sorted(root.iterdir()):
        if not section.is_dir():
            continue
        for grantha in sorted(section.iterdir()):
            if not grantha.is_dir():
                continue
            got = process_grantha(grantha, configured, args.threshold, report)
            for i, v in enumerate(got):
                totals[i] += v

    for line in report:
        print(line)
    print(f"merged {totals[0]} numbered folders; folded {totals[1]} "
          f"rare-heading folders ({totals[2]} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
