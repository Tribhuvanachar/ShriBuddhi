"""
Build multi-granularity additions on top of the existing 423-chunk
representations.json: (a) small non-overlapping groups of 3 consecutive
verses/items per source, for both Sanskrit mula text and Kannada meaning
text where available, and (b) one combined "commentary block" per Prahlada
shloka concatenating all its existing separate Sanskrit commentary chunks.

Read-only against real DGE content indirectly (it only re-groups text
already extracted into representations.json by extract_pilot.py -- no new
file from the real repo is opened here). Adds a `covers` field to every
row (list of parent_unit_id it speaks for) so retrieval can be scored at
the correct source-unit level even for a multi-verse group.
"""
import json
from pathlib import Path
from collections import OrderedDict

HERE = Path(__file__).parent
reps = json.loads((HERE / "representations.json").read_text())

# uniform `covers` for every existing (verse-level) representation: itself
for r in reps:
    r["covers"] = [r["parent_unit_id"]]
    r["granularity"] = "verse"

GROUP_SIZE = 3
new_rows = []


def add_row(rep_type, lang, script, source, text, covers, granularity, ai=False):
    text = text.strip()
    if not text:
        return
    new_rows.append({
        "chunk_id": f"multigrain::{rep_type}::{len(new_rows)}",
        "parent_unit_id": f"{source}::group::{granularity}::{len(new_rows)}",
        "rep_type": rep_type, "lang": lang, "script": script, "source": source,
        "ai_generated": ai, "text": text, "covers": covers, "granularity": granularity,
    })


def ordered_rows_for(source_prefix, rep_type):
    return [r for r in reps if r["source"].startswith(source_prefix) and r["rep_type"] == rep_type]


# --- (a) small groups of GROUP_SIZE consecutive verses/items ---
GROUP_SOURCES = [
    ("stotra/PrahladaKrutaNarasimha", "mula_sa", "sa", "deva"),
    ("kavya_alankara/raghavendra_vijaya/sarga_1", "mula_sa", "sa", "deva"),
    ("vedas/rigveda/shakala_shakha/upanishads/aitareya_upanishad", "mula_sa", "sa", "deva"),
    ("itihasa/mahabharata_kannada/bhishma_parva", "mula_sa_knscript", "sa", "kannada"),
    ("itihasa/mahabharata_kannada/bhishma_parva", "meaning_kn", "kn", "kannada"),
]
for source_prefix, rep_type, lang, script in GROUP_SOURCES:
    rows = ordered_rows_for(source_prefix, rep_type)
    for i in range(0, len(rows), GROUP_SIZE):
        group = rows[i:i + GROUP_SIZE]
        if not group:
            continue
        text = " ".join(g["text"] for g in group)
        covers = [g["parent_unit_id"] for g in group]
        add_row(f"passage_group_{rep_type}", lang, script, source_prefix, text, covers, "passage_group")

# --- (b) per-shloka combined Sanskrit commentary block (Prahlada only --
#     the one source in this pilot with multiple named Sanskrit commentaries
#     per verse) ---
prahlada_shloka_ids = sorted(
    {r["parent_unit_id"] for r in reps if r["source"] == "stotra/PrahladaKrutaNarasimha" and r["rep_type"] == "mula_sa"},
    key=lambda pid: int(pid.split("::")[1]),
)
for parent in prahlada_shloka_ids:
    comm_rows = [r for r in reps if r["parent_unit_id"] == parent and r["rep_type"].startswith("commentary_sa__")]
    if not comm_rows:
        continue
    block = " ".join(f"[{r['rep_type'].split('__', 1)[1]}] {r['text']}" for r in comm_rows)
    # covers = [parent] -- this block still speaks for exactly ONE verse,
    # just merges its scattered per-commentator chunks into one denser
    # representation (unlike the passage groups above, which span several).
    new_rows.append({
        "chunk_id": f"multigrain::commentary_block_sa::{len(new_rows)}",
        "parent_unit_id": parent,
        "rep_type": "commentary_block_sa", "lang": "sa", "script": "deva",
        "source": "stotra/PrahladaKrutaNarasimha", "ai_generated": False,
        "text": block, "covers": [parent], "granularity": "commentary_block",
    })

all_rows = reps + new_rows
(HERE / "representations_multigrain.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=1))
(HERE / "new_multigrain_rows_only.json").write_text(json.dumps(new_rows, ensure_ascii=False, indent=1))

by_gran = {}
for r in all_rows:
    by_gran[r["granularity"]] = by_gran.get(r["granularity"], 0) + 1

print(json.dumps({
    "total_rows": len(all_rows),
    "base_rows": len(reps),
    "new_rows": len(new_rows),
    "by_granularity": by_gran,
}, indent=2))
