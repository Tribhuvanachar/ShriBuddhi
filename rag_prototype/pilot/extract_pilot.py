"""
Read-only extraction of a larger RAG pilot corpus from the REAL DGE data
files. Writes only into the scratch `pilot/` directory:
  - lexical_src/dge/data/... : trimmed-but-real copies of the source
    data.json files (same schema, same real content, just capped item
    counts for large files) used to build a REAL lexical index with the
    unmodified production `dge/build_search_index.py`.
  - representations.jsonl : one row per embeddable "representation" chunk
    (mula / commentary / human translation / AI translation / Kannada
    meaning / OCR-staged text), each carrying a shared `parent_unit_id`
    so retrieval can always be scored against the right source unit.

Never writes to the real repository. Every representation's text is a
verbatim excerpt from the real file it names in `source`.
"""
import json, os, re, shutil
from pathlib import Path

REPO = Path("/home/user/bhumandala")
DGE_DATA = REPO / "dge" / "data"
OUT = Path(__file__).parent
LEXICAL_SRC = OUT / "lexical_src" / "dge" / "data"
LEXICAL_SRC.mkdir(parents=True, exist_ok=True)

shutil.copy(DGE_DATA / "schemas.json", LEXICAL_SRC / "schemas.json")

reps = []
_HTML_TAG = re.compile(r"<[^>]+>")


def clean(s):
    return _HTML_TAG.sub(" ", s or "").strip()


def add_rep(parent, rep_type, lang, script, source, text, ai=False):
    text = clean(text)
    if not text:
        return
    reps.append({
        "chunk_id": f"{parent}::{rep_type}::{len(reps)}",
        "parent_unit_id": parent,
        "rep_type": rep_type,
        "lang": lang,
        "script": script,
        "source": source,
        "ai_generated": ai,
        "text": text,
    })


def write_trimmed(rel, data):
    out_path = LEXICAL_SRC / rel / "data.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load(rel):
    return json.loads((DGE_DATA / rel / "data.json").read_text(encoding="utf-8"))


# --- 1. Prahlada Nrsimha Stotra: legacy shlokas{}, Sanskrit commentary only ---
rel = "stotra/PrahladaKrutaNarasimha"
src = load(rel)
write_trimmed(rel, src)
for sid, sh in src["shlokas"].items():
    parent = f"{rel}::{sid}"
    add_rep(parent, "mula_sa", "sa", "deva", rel, sh.get("sa", ""))
    for ck, ctext in (sh.get("commentaries") or {}).items():
        add_rep(parent, f"commentary_sa__{ck}", "sa", "deva", rel, ctext)

# --- 2. Raghavendra Vijaya sarga_1: legacy shlokas{}, human EN + AI EN summary ---
rel = "kavya_alankara/raghavendra_vijaya/sarga_1"
src = load(rel)
write_trimmed(rel, src)
for sid, sh in src["shlokas"].items():
    parent = f"{rel}::{sid}"
    add_rep(parent, "mula_sa", "sa", "deva", rel, sh.get("sa", ""))
    c = sh.get("commentaries") or {}
    if c.get("pavamanacharya_english"):
        add_rep(parent, "translation_en_human", "en", "latin", rel, c["pavamanacharya_english"])
    if c.get("gemini_summary"):
        add_rep(parent, "translation_en_ai", "en", "latin", rel, c["gemini_summary"], ai=True)

# --- 3. Aitareya Upanishad: items[], plain Sanskrit prose, first 60 ---
rel = "vedas/rigveda/shakala_shakha/upanishads/aitareya_upanishad"
src = load(rel)
items = src["items"][:60]
trimmed = dict(src); trimmed["items"] = items
write_trimmed(rel, trimmed)
for it in items:
    parent = f"{rel}::{it['id']}"
    add_rep(parent, "mula_sa", "sa", "deva", rel, it.get("text", ""))

# NOTE: kavya_alankara/raghuvamsha/mula uses schema "itihasa_purana_text"
# with items[] = one dict PER SARGA (canto), each holding a nested
# shlokas[]:[{number, sanskrit_text}] list -- extract_text() in
# build_search_index.py concatenates the WHOLE sarga into one search unit
# for this shape (confirmed by reading the function: the "shlokas" key is
# a list, so every verse's sanskrit_text is joined into one string keyed
# by the sarga's own "id"). That means lexical search's real granularity
# for this text is per-CANTO, not per-verse -- a genuine, useful finding
# (documented in the report) rather than an extraction bug to route
# around. Left out of the embedding pilot's parent-unit set for a clean
# verse-level comparison; Raghavendra Vijaya's own compound-heavy verses
# (2, 4, ...) cover the sandhi/compound test category instead.

# --- 5. Mahabharata Kannada, Bhishma Parva: items[], Kannada-script sloka + Kannada meaning, first 40 ---
rel = "itihasa/mahabharata_kannada/bhishma_parva"
src = load(rel)
items = src["items"][:40]
trimmed = dict(src); trimmed["items"] = items
write_trimmed(rel, trimmed)
for it in items:
    parent = f"{rel}::{it['id']}"
    add_rep(parent, "mula_sa_knscript", "sa", "kannada", rel, it.get("sa", ""))
    kn = (it.get("commentaries") or {}).get("kannada", "")
    if kn:
        add_rep(parent, "meaning_kn", "kn", "kannada", rel, kn)

# --- 6. Vasu Siddhanta Kaumudi OCR-staged English (embedding-only: NOT a
#     data.json, NOT walked by build_search_index.py, so production lexical
#     search cannot reach this content at all today -- included only in the
#     embedding corpus to test that gap directly). ---
ocr_dir = DGE_DATA / "ocr_staging" / "vasu_siddhanta_kaumudi"
ocr_files = [("vol1_pages9-28.json", None), ("vol1_pages29-158.json", 15),
             ("vol1_pages158-307.json", 15)]
for fn, cap in ocr_files:
    p = ocr_dir / fn
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    entries = d.get("entries", [])
    if cap:
        entries = entries[:cap]
    src_label = f"ocr_staging/vasu_siddhanta_kaumudi/{fn} (Gemini OCR, unreviewed)"
    for e in entries:
        parent = f"ocr_staging/vasu_siddhanta_kaumudi/{fn}::sk{e.get('sk')}"
        if e.get("english"):
            add_rep(parent, "ocr_english", "en", "latin", src_label, e["english"], ai=True)
        if e.get("sutra_ocr") and e["sutra_ocr"].strip():
            add_rep(parent, "ocr_sanskrit_sutra", "sa", "deva", src_label, e["sutra_ocr"], ai=True)

# --- write outputs ---
(OUT / "representations.json").write_text(
    json.dumps(reps, ensure_ascii=False, indent=1), encoding="utf-8"
)

parents = {}
for r in reps:
    parents.setdefault(r["parent_unit_id"], []).append(r["rep_type"])

stats = {
    "total_representations": len(reps),
    "total_parent_units": len(parents),
    "by_rep_type": {},
    "by_lang": {},
    "by_source": {},
}
for r in reps:
    stats["by_rep_type"][r["rep_type"]] = stats["by_rep_type"].get(r["rep_type"], 0) + 1
    stats["by_lang"][r["lang"]] = stats["by_lang"].get(r["lang"], 0) + 1
    stats["by_source"][r["source"]] = stats["by_source"].get(r["source"], 0) + 1

(OUT / "corpus_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
print(json.dumps(stats, ensure_ascii=False, indent=2))
