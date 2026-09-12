#!/usr/bin/env python3
"""Generate the dge/data/darshana/ tree from tools/darshanas/darshana_works.json.

The tree is a BUILD PRODUCT. Nothing under dge/data/darshana/ is hand-authored:
edit darshana_works.json and re-run this. That is what makes the bibliographic
graph — who commented on whom, at what layer, with what verification status —
the single source of truth rather than something implied by folder names.

What it emits
  dge/data/darshana/_meta.json
  dge/data/darshana/_works_index.json     flat lookup: path -> work/layer metadata
  dge/data/darshana/_graph.json           commentary edges, for the reader UI
  dge/data/darshana/<school>/<subsection>/<work>/_meta.json
  dge/data/darshana/<school>/<subsection>/<work>/<layer>/data.json   (empty stub)
  ...and for Tattvacintāmaṇi, the topic x layer vāda matrix:
  .../tattvacintamani/<khanda>/<layer>/data.json
  .../tattvacintamani/<khanda>/vadas/<vada>/<layer>/data.json

It also updates dge/data/taxonomy.json (adds the darshanas subtree) and
dge/data/library.json (one entry per data.json, with populated and title set
explicitly — register_layers.py writes title:null, and a stale populated:false
makes dge/js/core.js short-circuit to "Not Yet Available" over real data).

Existing data.json files are NEVER overwritten — a stub is written only where
none exists, so re-running after an ingest is safe.

Run:  python tools/darshanas/scaffold_darshanas.py --data dge/data
      python tools/darshanas/scaffold_darshanas.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os

# The taxonomy folder these works live in. Singular, and a sibling of
# vedanta/ under darshana/ — see DGE_Shastra_Taxonomy.md, which lists Nyaya,
# Vaisheshika, Samkhya, Yoga, Mimamsa and Vedanta as the six branches of
# Darshana. This branch was authored before that restructure and used a
# separate top-level "darshanas"; keeping it would have split Darshana in two.
ROOT_KEY = "darshana"
META_DESC = "DGE category structure file to anchor the directory."


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def dump(path, payload, indent):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=indent)
        handle.write("\n")


class Scaffolder:
    def __init__(self, config, data_root, dry_run=False):
        self.config = config
        self.data_root = data_root
        self.dry_run = dry_run
        self.authors = config["authors"]
        self.leaves: list[dict] = []      # one per data.json
        self.nodes: list[dict] = []       # one per _meta.json directory
        self.edges: list[dict] = []       # commentary graph
        self.work_paths: dict[str, str] = {}   # work slug -> rel path, for edge resolution
        self.created = self.skipped = 0

    def resolve(self, ref):
        """'tarkasangraha/tika_dipika' -> full rel path.

        References cross subsection boundaries (Bhāṭṭadīpikā sits under
        mimamsa/prakarana but comments on mimamsa/sutra_and_bhashya/mimamsa_sutra),
        so they resolve against a work-slug index built during the walk rather
        than against the referrer's own directory.
        """
        if not ref:
            return None
        work_slug = ref.split("/", 1)[0]
        base = self.work_paths.get(work_slug)
        if base is None:
            return ref                      # unresolved; surfaced by verify below
        rest = ref.split("/", 1)[1] if "/" in ref else ""
        return f"{base}/{rest}" if rest else base

    # ---------------- filesystem ----------------

    def _abs(self, rel):
        return os.path.join(self.data_root, rel)

    def mkmeta(self, rel, directory, description, schema=None):
        self.nodes.append({"path": rel, "description": description})
        if self.dry_run:
            return
        os.makedirs(self._abs(rel), exist_ok=True)
        target = self._abs(os.path.join(rel, "_meta.json"))
        meta = {"directory": directory, "description": description}
        if schema:
            meta["schema"] = schema
        dump(target, meta, 2)

    def mkleaf(self, rel, schema, default_author, meta):
        """Write an empty data.json stub — never clobber real data."""
        target = self._abs(os.path.join(rel, "data.json"))
        existing = load(target)
        item_count = len(existing.get("items", [])) if isinstance(existing, dict) else 0
        self.leaves.append({**meta, "path": rel, "schema": schema,
                            "default_author": default_author, "items": item_count})
        if existing is not None:
            self.skipped += 1
            return
        self.created += 1
        if self.dry_run:
            return
        os.makedirs(self._abs(rel), exist_ok=True)
        dump(target, {"schema": schema, "default_author": default_author, "items": []}, 1)

    # ---------------- author helper ----------------

    def author_name(self, slug):
        if not slug:
            return ""
        entry = self.authors.get(slug)
        return entry["devanagari"] if entry else slug

    # ---------------- tree walk ----------------

    def run(self):
        self.mkmeta(ROOT_KEY, ROOT_KEY,
                    "Darśana śāstras — Nyāya, Vaiśeṣika, Mīmāṃsā. Generated from "
                    "tools/darshanas/darshana_works.json; do not hand-edit.")
        for school in self.config["sections"]:
            self.walk_school(school)
        self.resolve_edges()
        return self

    def resolve_edges(self):
        """Turn work-relative references into full paths, once every work is known."""
        self.dangling = []
        for edge in self.edges:
            ref = edge.pop("_ref", None)
            edge["to"] = self.resolve(ref)
            if edge["to"] == ref:
                self.dangling.append(edge)
                edge["unresolved"] = True

    def walk_school(self, school):
        rel = f"{ROOT_KEY}/{school['slug']}"
        self.mkmeta(rel, school["slug"],
                    f"{school['title']['devanagari']} ({school['title']['iast']}). {META_DESC}")
        for sub in school["subsections"]:
            subrel = f"{rel}/{sub['slug']}"
            self.mkmeta(subrel, sub["slug"],
                        f"{sub['title']['devanagari']} ({sub['title']['iast']}). {META_DESC}")
            for work in sub["works"]:
                self.walk_work(subrel, work, school, sub)

    def walk_work(self, parent_rel, work, school, sub):
        rel = f"{parent_rel}/{work['slug']}"
        title = work["title"]
        self.mkmeta(rel, work["slug"],
                    f"{title['devanagari']} ({title['iast']}) — {self.author_name(work.get('author'))}. {META_DESC}",
                    schema="grantha_prakarana_text")

        self.work_paths[work["slug"]] = rel
        if work.get("comments_on"):
            self.edges.append({"from": rel, "_ref": work["comments_on"], "type": "comments_on",
                               "layer": work.get("layer"),
                               "verification": work.get("verification", "plausible")})

        khandas = work.get("khandas")
        if khandas:
            self.walk_khanda_work(rel, work, school, sub, khandas)
            return

        for layer in work.get("layers", []):
            self.emit_layer(rel, work, layer, school, sub)

    def walk_khanda_work(self, rel, work, school, sub, khandas):
        """Tattvacintāmaṇi shape: khaṇḍa x layer, plus a vāda topic x layer matrix.

        The vādas are named topical sections of the Anumāna-khaṇḍa that circulate
        as printed extracts across commentary layers — they are NOT independent
        works, so they get one folder per topic with a layer folder inside,
        rather than one folder per (topic, author) pair which would duplicate the
        same section under Jagadīśa and Gadādhara.
        """
        vadas_by_khanda: dict[str, list] = {}
        for vada in work.get("vadas", []):
            vadas_by_khanda.setdefault(vada["khanda"], []).append(vada)

        for khanda in khandas:
            krel = f"{rel}/{khanda['slug']}"
            self.mkmeta(krel, khanda["slug"],
                        f"{khanda['title']['devanagari']} ({khanda['title']['iast']}) — "
                        f"{work['title']['devanagari']}. {META_DESC}")
            for layer in work.get("layers", []):
                self.emit_layer(krel, work, layer, school, sub, khanda=khanda)

            vadas = vadas_by_khanda.get(khanda["slug"], [])
            if not vadas:
                continue
            vrel = f"{krel}/vadas"
            self.mkmeta(vrel, "vadas",
                        "Named topical sections (vāda / prakaraṇa) of this khaṇḍa. Each is one "
                        "topic with a folder per commentary layer — not an independent work.")
            layer_by_slug = {lay["slug"]: lay for lay in work.get("layers", [])}
            for vada in vadas:
                self.emit_vada(vrel, work, vada, layer_by_slug, school, sub, khanda)

    def emit_vada(self, parent_rel, work, vada, layer_by_slug, school, sub, khanda):
        rel = f"{parent_rel}/{vada['slug']}"
        title = vada["title"]
        alt = f" (also {', '.join(vada['alt_titles'])})" if vada.get("alt_titles") else ""
        self.mkmeta(rel, vada["slug"],
                    f"{title['devanagari']} ({title['iast']}){alt} — section of "
                    f"{khanda['title']['devanagari']}, topic: {vada.get('topic', '')}. {META_DESC}")
        self.edges.append({"from": rel, "_ref": f"{work['slug']}/{khanda['slug']}",
                           "type": "section_of", "topic": vada.get("topic"),
                           "verification": vada.get("verification", "plausible")})
        for layer_slug in vada.get("layers", []):
            layer = layer_by_slug.get(layer_slug)
            if layer is None:
                continue
            self.emit_layer(rel, work, layer, school, sub, khanda=khanda, vada=vada)

    def emit_layer(self, parent_rel, work, layer, school, sub, khanda=None, vada=None):
        rel = f"{parent_rel}/{layer['slug']}"
        author = layer.get("author") or work.get("author")
        if layer.get("comments_on"):
            self.edges.append({"from": rel, "_ref": layer["comments_on"],
                               "type": layer.get("relation", "comments_on"),
                               "layer": layer.get("layer"),
                               "verification": layer.get("verification", "plausible")})
        self.mkleaf(rel, layer["schema"], self.author_name(author), {
            "school": school["slug"],
            "subsection": sub["slug"],
            "work": work["slug"],
            "work_title": work["title"],
            "khanda": khanda["slug"] if khanda else None,
            "vada": vada["slug"] if vada else None,
            "vada_title": vada["title"] if vada else None,
            "layer_slug": layer["slug"],
            "layer_title": layer["title"],
            "layer_depth": layer.get("layer"),
            "author": author,
            "author_name": self.author_name(author),
            "comments_on": layer.get("comments_on"),
            "relation": layer.get("relation", "comments_on" if layer.get("comments_on") else "mula"),
            "verification": layer.get("verification", "plausible"),
            "note": layer.get("note"),
        })

    # ---------------- catalog integration ----------------

    def display_title(self, leaf):
        work = leaf["work_title"]["devanagari"]
        layer = leaf["layer_title"]["devanagari"]
        parts = [work]
        if leaf.get("vada_title"):
            parts.append(leaf["vada_title"]["devanagari"])
        if leaf["layer_slug"] != "mula":
            parts.append(layer)
        elif leaf.get("vada_title") or leaf.get("khanda"):
            parts.append(layer)
        return " — ".join(parts)

    def sync_catalog(self):
        taxonomy_path = os.path.join(self.data_root, "taxonomy.json")
        library_path = os.path.join(self.data_root, "library.json")
        taxonomy = load(taxonomy_path, {})
        library = load(library_path, {"granthas": []})

        for leaf in self.leaves:
            node = taxonomy
            for part in leaf["path"].split("/")[:-1]:
                node = node.setdefault(part, {})
            entry = node.setdefault(leaf["path"].split("/")[-1], {})
            entry["_schema"] = leaf["schema"]
            if leaf["default_author"]:
                entry["_default_author"] = leaf["default_author"]

        by_path = {e["path"]: e for e in library.get("granthas", [])}
        added = fixed = 0
        for leaf in self.leaves:
            repo_path = f"dge/data/{leaf['path']}/data.json"
            title = self.display_title(leaf)
            entry = by_path.get(repo_path)
            if entry is None:
                library.setdefault("granthas", []).append(
                    {"path": repo_path, "populated": leaf["items"] > 0, "title": title})
                added += 1
            else:
                if entry.get("populated") != (leaf["items"] > 0):
                    entry["populated"] = leaf["items"] > 0
                    fixed += 1
                if not entry.get("title"):
                    entry["title"] = title
                    fixed += 1

        print(f"taxonomy.json: synced {ROOT_KEY} subtree ({len(self.leaves)} leaves)")
        print(f"library.json:  +{added} new, {fixed} corrected")

        # Re-serialising taxonomy.json reflows lines that were hand-written inline
        # (e.g. '"bala_kanda": { "mula": {}, "saartha": {} }'), so the diff shows
        # deletions that are pure whitespace. Prove no key or value was actually
        # lost before writing — a silent drop here would orphan real granthas.
        original = load(taxonomy_path, {})
        lost = self._missing_keys(original, taxonomy)
        if lost:
            raise SystemExit("ABORT: taxonomy.json would lose keys: " + ", ".join(lost[:10]))
        if set(original) - set(taxonomy):
            raise SystemExit("ABORT: taxonomy.json would lose top-level sections")

        if self.dry_run:
            return
        dump(taxonomy_path, taxonomy, 1)
        dump(library_path, library, 2)      # indent=2 by convention; 1 floods the diff

    @staticmethod
    def _missing_keys(old, new, prefix=""):
        missing = []
        for key, value in old.items():
            if key not in new:
                missing.append(f"{prefix}/{key}")
                continue
            if isinstance(value, dict) and isinstance(new[key], dict):
                missing += Scaffolder._missing_keys(value, new[key], f"{prefix}/{key}")
            elif value != new[key]:
                missing.append(f"{prefix}/{key} (value changed)")
        return missing

    def write_indexes(self):
        index = {
            "generated_note": "Generated by tools/darshanas/scaffold_darshanas.py from "
                              "tools/darshanas/darshana_works.json. Do not hand-edit.",
            "authors": self.authors,
            "corrections": self.config.get("corrections", []),
            "unverified_do_not_encode": self.config.get("unverified_do_not_encode", []),
            "leaves": self.leaves,
        }
        graph = {
            "generated_note": "Commentary graph for the darśana tree. 'layer' is depth from the "
                              "mūla: 0 mūla, 1 commentary, 2 sub-commentary, 3 gloss. The folder "
                              "tree is flat; this file carries the real genealogy.",
            "edges": self.edges,
        }
        counts = {}
        for leaf in self.leaves:
            counts[leaf["verification"]] = counts.get(leaf["verification"], 0) + 1
        index["verification_counts"] = counts
        print(f"leaves: {len(self.leaves)}  ({', '.join(f'{k}={v}' for k, v in sorted(counts.items()))})")
        print(f"edges:  {len(self.edges)}"
              + (f"  ({len(self.dangling)} UNRESOLVED)" if self.dangling else ""))
        for edge in self.dangling:
            print(f"  ! unresolved reference: {edge['from']} -> {edge['to']}")
        if self.dry_run:
            return
        dump(os.path.join(self.data_root, ROOT_KEY, "_works_index.json"), index, 1)
        dump(os.path.join(self.data_root, ROOT_KEY, "_graph.json"), graph, 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="tools/darshanas/darshana_works.json")
    parser.add_argument("--data", default="dge/data")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-catalog", action="store_true",
                        help="skip taxonomy.json / library.json updates")
    args = parser.parse_args(argv)

    with open(args.config, encoding="utf-8") as handle:
        config = json.load(handle)

    mode = "DRY RUN" if args.dry_run else "WRITE"
    print(f"scaffolding {ROOT_KEY} → {args.data}  [{mode}]\n")

    scaffolder = Scaffolder(config, args.data, args.dry_run).run()
    print(f"directories: {len(scaffolder.nodes)}")
    print(f"data.json:   {scaffolder.created} created, {scaffolder.skipped} left alone (already populated)")
    scaffolder.write_indexes()
    if not args.no_catalog:
        scaffolder.sync_catalog()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
