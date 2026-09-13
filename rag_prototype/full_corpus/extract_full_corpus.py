"""
Full-corpus representation extraction for DGE RAG -- generalizes the
validated pilot approach (extract_pilot.py) from a 4-grantha sample to the
REAL, ENTIRE dge/data tree (~1,285 granthas, ~580K+ mula units).

Read-only against dge/data. Writes only to this scratch directory.
No licensing gate applied (per explicit instruction, 10 Sep 2026) --
DGE_COPYRIGHT_GATED_COMMENTARY_KEYS content (Mahabharata Kannada +
Tatparya Nirnaya) IS included this run.

For each grantha's data.json, handles both real shapes seen in this
corpus:
  - legacy: {metadata, shlokas: {id: {sa, commentaries: {key: text}}}}
  - schema-driven: {schema, items: [{id, text|sanskrit_text|sa, ...}]}
      -- including the itihasa_purana_text per-canto nested-shlokas[]
      shape (Raghuvamsha-style), which is expanded to real per-verse
      chunks here (finer-grained than production's own lexical indexer,
      which treats one such canto as a single unit -- see conversation
      note on that discovery).

Representation types emitted (matches the pilot's validated vocabulary):
  mula_sa            -- the primary verse/item text (Devanagari or
                         Devanagari-block-aligned script, kept as-is)
  commentary_sa__X    -- legacy-shape named Sanskrit commentary
  translation_en_human / translation_en_ai -- legacy-shape English layers
  meaning_kn          -- Kannada prose meaning alongside a Kannada-script
                         mula (itihasa_purana_text shape seen in
                         Mahabharata Kannada)

Output: JSONL (one representation per line) rather than one giant JSON
array, so this can be written incrementally/resumed and never requires
holding the whole thing in memory to append.

Usage: python3 extract_full_corpus.py
"""
import json, os, re, sys, time
from pathlib import Path

REPO = Path("/home/user/bhumandala")
DGE_DATA = REPO / "dge" / "data"
HERE = Path(__file__).parent
OUT_PATH = HERE / "representations_full.jsonl"
PROGRESS_PATH = HERE / "extract_progress.json"

sys.path.insert(0, str(REPO / "dge"))
from build_search_index import has_devanagari, fold_indic_to_devanagari, clean_devanagari as _prod_clean

_HTML_TAG = re.compile(r"<[^>]+>")


def clean(s):
    return _HTML_TAG.sub(" ", s or "").strip()


MAX_CHUNK_CHARS = 2000

# Sentence-ish boundary for Sanskrit/Kannada/English prose alike: danda,
# double-danda, or a Latin sentence-ending punctuation followed by space.
_SENTENCE_BREAK = re.compile(r"(?<=[।॥.!?])\s+")


def split_long_text(text, max_chars=MAX_CHUNK_CHARS):
    """Split one field's text into <=max_chars pieces on natural
    boundaries, worst case a hard split. Exists because a small number of
    real DGE commentary/bhashya fields (scraped whole-treatise pages under
    darshana/vedanta/.../tika_*, bhashya) store an ENTIRE work as one
    unsplit string -- up to 1.76M characters observed in this corpus.
    Embedding that as one "chunk" wastes enormous compute on content that
    mostly gets silently truncated by the model's own max sequence length
    anyway, and produces a citation granularity no reader could use.
    Non-overlapping paragraph/sentence-aware windows, same spirit as the
    passage-group chunking already validated in the retrieval experiments."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) <= 1:
        paras = [s for s in _SENTENCE_BREAK.split(text) if s.strip()]

    pieces = []
    buf = ""
    for p in paras:
        if len(p) > max_chars:
            # a single paragraph/sentence itself too long -- hard-wrap it
            if buf:
                pieces.append(buf)
                buf = ""
            for i in range(0, len(p), max_chars):
                pieces.append(p[i:i + max_chars])
            continue
        if buf and len(buf) + 1 + len(p) > max_chars:
            pieces.append(buf)
            buf = p
        else:
            buf = f"{buf} {p}".strip()
    if buf:
        pieces.append(buf)
    return pieces or [text[:max_chars]]


def is_real_sanskrit(text):
    """Same stub/placeholder gate production's own lexical indexer uses
    (has_devanagari + the Kannada/Telugu/Malayalam block-fold check) --
    applied here so this RAG extraction doesn't waste embedding compute
    on template stubs like 'Sanskrit text goes here...' that the
    production index already knows to skip."""
    c = _prod_clean(text)
    if has_devanagari(c):
        return True
    return has_devanagari(_prod_clean(fold_indic_to_devanagari(text)))


def grantha_slug(path):
    return os.path.relpath(os.path.dirname(path), DGE_DATA).replace(os.sep, "/")


def iter_reps_for_grantha(slug, data):
    """Yield representation dicts for one grantha's parsed data.json,
    covering every real shape found in this corpus."""
    n = 0

    if isinstance(data.get("shlokas"), dict):
        # legacy shape: metadata + shlokas{id: {sa, commentaries:{}}}
        for sid, sh in data["shlokas"].items():
            if not isinstance(sh, dict):
                continue
            parent = f"{slug}::{sid}"
            sa = sh.get("sa") or sh.get("sanskrit_text") or sh.get("text") or ""
            if sa.strip():
                yield {"parent_unit_id": parent, "rep_type": "mula_sa", "lang": "sa",
                       "source": slug, "ai_generated": False, "text": sa}
                n += 1
            for ck, ctext in (sh.get("commentaries") or {}).items():
                if not isinstance(ctext, str) or not ctext.strip():
                    continue
                if ck == "pavamanacharya_english" or (ck.startswith("translation") and "en" in ck):
                    rep_type, lang, ai = "translation_en_human", "en", False
                elif ck == "gemini_summary":
                    rep_type, lang, ai = "translation_en_ai", "en", True
                elif ck in ("gemini_padaccheda", "gemini_anvaya"):
                    rep_type, lang, ai = f"ai_structural_sa__{ck}", "sa", True
                elif ck == "kannada":
                    rep_type, lang, ai = "meaning_kn", "kn", False
                else:
                    rep_type, lang, ai = f"commentary_sa__{ck}", "sa", False
                yield {"parent_unit_id": parent, "rep_type": rep_type, "lang": lang,
                       "source": slug, "ai_generated": ai, "text": ctext}
                n += 1

    elif isinstance(data.get("items"), list):
        for it in data["items"]:
            if not isinstance(it, dict):
                continue
            iid = str(it.get("id", ""))

            # itihasa_purana_text per-canto nested shlokas[] (Raghuvamsha
            # shape) -- expand to real per-verse chunks (production's own
            # lexical indexer only sees one merged per-canto unit here;
            # this RAG extraction deliberately keeps it verse-level).
            if isinstance(it.get("shlokas"), list) and it["shlokas"] and isinstance(it["shlokas"][0], dict) \
                    and "sanskrit_text" in it["shlokas"][0]:
                for sh in it["shlokas"]:
                    num = sh.get("number")
                    parent = f"{slug}::{iid}#{num}"
                    txt = sh.get("sanskrit_text") or ""
                    if txt.strip():
                        yield {"parent_unit_id": parent, "rep_type": "mula_sa", "lang": "sa",
                               "source": slug, "ai_generated": False, "text": txt}
                        n += 1
                continue

            parent = f"{slug}::{iid}"
            # Mahabharata-Kannada-style: top-level "sa" (Kannada-script
            # sloka) + commentaries.kannada (meaning) on an items[] shape.
            sa = it.get("sa")
            comm = it.get("commentaries") if isinstance(it.get("commentaries"), dict) else None
            if sa and comm is not None:
                if sa.strip():
                    yield {"parent_unit_id": parent, "rep_type": "mula_sa", "lang": "sa",
                           "source": slug, "ai_generated": False, "text": sa}
                    n += 1
                kn = comm.get("kannada", "")
                if kn.strip():
                    yield {"parent_unit_id": parent, "rep_type": "meaning_kn", "lang": "kn",
                           "source": slug, "ai_generated": False, "text": kn}
                    n += 1
                continue

            # generic items[]-shape: plain text/sanskrit_text field
            txt = it.get("text") or it.get("sanskrit_text") or sa or ""
            if isinstance(txt, str) and txt.strip():
                yield {"parent_unit_id": parent, "rep_type": "mula_sa", "lang": "sa",
                       "source": slug, "ai_generated": False, "text": txt}
                n += 1


def main():
    grantha_paths = []
    for root, _dirs, files in os.walk(DGE_DATA):
        if "data.json" in files:
            grantha_paths.append(os.path.join(root, "data.json"))
    grantha_paths.sort()

    print(f"{len(grantha_paths)} grantha data.json files found.", flush=True)

    t0 = time.time()
    n_reps = 0
    n_granthas_done = 0
    n_skipped = 0
    n_stub_skipped = [0]
    n_split = [0]

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for path in grantha_paths:
            slug = grantha_slug(path)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                n_skipped += 1
                continue
            for rep in iter_reps_for_grantha(slug, data):
                rep["text"] = clean(rep["text"])
                if not rep["text"]:
                    continue
                if rep["rep_type"] == "mula_sa" and not is_real_sanskrit(rep["text"]):
                    n_stub_skipped[0] += 1
                    continue
                pieces = split_long_text(rep["text"])
                if len(pieces) > 1:
                    n_split[0] += 1
                for i, piece in enumerate(pieces):
                    row = dict(rep)
                    row["text"] = piece
                    row["chunk_id"] = (f"{rep['parent_unit_id']}::{rep['rep_type']}"
                                        + (f"#{i}" if len(pieces) > 1 else ""))
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n_reps += 1
            n_granthas_done += 1
            if n_granthas_done % 100 == 0:
                print(f"  {n_granthas_done}/{len(grantha_paths)} granthas, {n_reps} reps so far, "
                      f"{time.time()-t0:.1f}s elapsed", flush=True)

    elapsed = time.time() - t0
    stats = {
        "total_granthas": len(grantha_paths), "granthas_skipped_unreadable": n_skipped,
        "total_representations": n_reps, "mula_stubs_skipped": n_stub_skipped[0],
        "fields_split_into_multiple_chunks": n_split[0],
        "elapsed_seconds": round(elapsed, 1),
    }
    PROGRESS_PATH.write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
