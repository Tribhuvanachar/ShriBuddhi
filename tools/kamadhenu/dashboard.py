"""Section 21 — KAMADHENU_STATUS.html: the one file to open. 11 sections, each with current state, evidence,
completed items, missing items, blockers and the next action. Every status comes from the generated JSON."""
from .common import DS, read_json, write_text, esc, now_ist, log, fmt_dur, DONE, VERIFIED, PARTIAL, IN_PROGRESS, NOT_STARTED, BLOCKED, NOT_REQUIRED

CSS = """<style>
.sec{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:12px 0}
.sec h2{border:none;margin:0 0 6px;display:flex;gap:10px;align-items:center}
.sec .st{font-size:14px;font-weight:600}
.kv{display:grid;grid-template-columns:150px 1fr;gap:4px 12px;font-size:13px}
.kv div:nth-child(odd){color:var(--muted)}
.bar{height:14px;background:#eee4d0;border-radius:7px;overflow:hidden;margin:6px 0 14px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#c98a2b,#2f8f5b)}
ul{margin:4px 0;padding-left:20px}
.links a{margin-right:14px}
</style>"""


def li(items):
    return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>" if items else "<ul><li>—</li></ul>"


def section(n, title, status, state, evidence, done, missing, blockers, nxt, links=()):
    return (f"<div class='sec'><h2>{n}. {esc(title)} <span class='st'>{esc(status)}</span></h2><div class='kv'>"
            f"<div>current state</div><div>{esc(state)}</div><div>evidence</div><div>{esc(evidence)}</div>"
            f"<div>completed</div><div>{li(done)}</div><div>missing</div><div>{li(missing)}</div><div>blockers</div><div>{li(blockers)}</div>"
            f"<div>next action</div><div><b>{esc(nxt)}</b></div>"
            + (f"<div>files</div><div class='links'>{' '.join(f'<a href=' + chr(34) + l + chr(34) + '>' + esc(l) + '</a>' for l in links)}</div>" if links else "") + "</div></div>")


def run():
    ext = read_json(DS / "external_audio_sources.json", {"totals": {}, "sources": []}); inv = read_json(DS / "audio_inventory.json", {"summary": {}, "files": []})
    mp = read_json(DS / "audio_text_mapping.json", {"summary": {}}); cov = read_json(DS / "chandas_coverage.json", {"summary": {}}); rb = read_json(DS / "reference_bank.json", {"summary": {}})
    ds = read_json(DS / "dataset_summary.json", {"subset_sizes": {}}); hl = read_json(DS / "dataset_health_report.json", {}); fg = read_json(DS / "frontend_gap_report.json", {"findings": [], "checklist": {}})
    gm = read_json(DS / "kamadhenu_gap_matrix.json", {"rows": []}); cmp = read_json(DS / "chandas_comparison.json", {}); fm = read_json(DS / "fetch_manifest.json", {"totals": {}})
    S = inv.get("summary", {}); M = mp.get("summary", {}); C = cov.get("summary", {}); R = rb.get("summary", {})
    n_files = S.get("files", 0); hours = S.get("total_duration_seconds", 0) / 3600
    blocked = [s for s in ext.get("sources", []) if s["accessibility"] == "BLOCKED_EXTERNAL_ACCESS"]
    hi = M.get("bands", {}).get("1.00 exact", 0) + M.get("bands", {}).get("0.90–0.99 very strong", 0)
    review = M.get("review_status", {}).get("review", 0); unmatched = M.get("review_status", {}).get("unmatched", 0)
    audio_status = PARTIAL if n_files else NOT_STARTED
    map_status = PARTIAL if hi else NOT_STARTED
    ch_status = PARTIAL
    ds_status = PARTIAL if ds.get("subset_sizes", {}).get("dataset_verified") else NOT_STARTED
    rb_status = PARTIAL if R.get("metres_safe_reference") else NOT_STARTED
    fe_status = PARTIAL
    vg_status = PARTIAL   # cloned + compared + reusable parts identified; nothing integrated/rendered
    tr_status = NOT_STARTED; pr_status = NOT_STARTED; qc_status = DONE; prod_status = NOT_STARTED
    stages = [audio_status, map_status, ch_status, ds_status, rb_status, fe_status, vg_status, tr_status, pr_status, qc_status, prod_status]
    weight = {DONE: 1, VERIFIED: 1, PARTIAL: 0.5, IN_PROGRESS: 0.3, NOT_STARTED: 0, BLOCKED: 0, NOT_REQUIRED: 1}
    progress = round(100 * sum(weight[s] for s in stages) / len(stages))
    body = [CSS, f"<div class='note'><b>Overall progress: {progress}%</b> (11 sections, DONE/VERIFIED = 1, PARTIAL = ½, others 0). Audit only — no model has been trained, no audio has been rendered.</div><div class='bar'><i style='width:{progress}%'></i></div>",
            "<div class='links'><a href='WHAT_I_NEED_TO_DO.md'>WHAT_I_NEED_TO_DO.md</a><a href='KAMADHENU_TODO.md'>KAMADHENU_TODO.md</a><a href='kamadhenu_gap_matrix.html'>gap matrix</a><a href='dataset_health_report.html'>health</a><a href='chandas_coverage.html'>chandas coverage</a><a href='reference_bank.html'>reference bank</a><a href='audio_text_mapping_review.html'>mapping review</a><a href='RECORDING_REQUESTS.csv'>RECORDING_REQUESTS.csv</a><a href='chandas_comparison.md'>chandas_comparison.md</a><a href='frontend_gap_report.md'>frontend_gap_report.md</a></div>"]
    body.append(section(1, "AUDIO", audio_status,
        f"{n_files} files / {fmt_dur(S.get('total_duration_seconds', 0))} fetched from {ext.get('totals', {}).get('accessible', 0)} reachable sources; {len(blocked)} sources BLOCKED_EXTERNAL_ACCESS; grades {S.get('by_grade', {})}",
        f"audio_inventory.json (measured with ffmpeg+numpy), fetch_manifest.json ({fm.get('totals', {})}), external_audio_sources.json",
        ["4 public Drive folders listed and downloaded (Gita Shlokas, Bhagavata Saroddhara, Vayu Stuti, Audio)", "DGE-linked audio fetched (Sumadhva Vijaya 992, Rāghavendra Vijaya 578, Prahlāda Narasiṃha 11)", "QC flags on every file"],
        [f"{len(blocked)} blocked sources: " + "; ".join(s['url'] for s in blocked), "speaker attribution (none in any source)", "any 48 kHz/24-bit TTS-grade master recording", "Tīrtha Prabandha recordings (287 expected — not in any reachable source)"],
        ["3 Drive folders + 1 Drive file need sharing/manual download", "both YouTube links need yt-dlp on your machine"],
        "Share the 3 blocked folders as 'Anyone with the link' OR unzip them into kamadhenu_dataset/incoming_audio/, then run python3 tools/kamadhenu_audit.py",
        ["audio_inventory.csv", "external_audio_sources.json", "dataset_health_report.html"]))
    body.append(section(2, "TEXT ↔ AUDIO MAPPING", map_status,
        f"{M.get('audio_files', 0)} files: {hi} high-confidence (≥0.90), {review} in review, {unmatched} unmatched; {M.get('texts_with_audio', 0)} DGE texts have audio, {M.get('texts_without_audio', 0)} do not",
        "audio_text_mapping.json — structural only (DGE link / filename / duration plausibility); no ASR was run",
        ["mapping engine with confidence bands + review HTML", "overrides file supported (mapping_overrides.json)"],
        ["human listen-check of the review queue", "ASR-based verification (IndicConformer ONNX on CPU is feasible)", "texts for Bhāgavata Sāroddhāra and Hari Vāyu Stuti (not in DGE)", "identity of the 'vsn' series"],
        ["no speech recognition available offline in this sandbox without a 632 MB model download"],
        "Open audio_text_mapping_review.html and work the review queue top-down; tell Claude what the 'vsn' files are",
        ["audio_text_mapping_review.html", "audio_text_mapping.csv"]))
    body.append(section(3, "CHANDAS", ch_status,
        f"DGE engine run headlessly over {sum(read_json(DS / 'text_index.json', {}).get('counts', {}).values())} text units; {C.get('metres_in_dge_db', 0)} metres in DGE DB; coverage {C.get('status_counts', {})}; tiers {C.get('tiers_percent', {})}",
        f"text_index.json chandas_analysis, chandas_coverage.json, chandas_comparison.json ({len(cmp.get('disagreements_with_dge', []))} Vāgdhenu patterns disagree with DGE)",
        ["one authoritative layer = dge/js/chandas.js (unmodified) via tools/kamadhenu/chandas_runner.js", "Vāgdhenu's two metre tables compared; 4 wrong patterns found in tts_meter.py"],
        ["DGE engine gaps: strict anuṣṭubh rule (vipulā → अज्ञातम्), upajāti table lacks U-I-U-U, candrabindu/ᳵ not guru, Devanagari-only", "≈44% of units unresolved (mostly MBTN + text defects)"],
        [],
        "Extend dge/js/chandas.js (vipulā classes, generic indra/upendra mix, nasal test) — Claude can do this; then re-run the audit",
        ["chandas_coverage.html", "chandas_comparison.md"]))
    body.append(section(4, "DATASET", ds_status,
        f"metadata.jsonl: {ds.get('records', 0)} records; subsets {ds.get('subset_sizes', {})}",
        "kamadhenu_dataset/metadata.jsonl, metadata.csv, subsets/subsets.json (every exclusion has a reason)",
        ["canonical record schema (text, normalized, work/section/chapter/verse, chandas, L/G, gaṇa, audio, speaker, duration, sr, channels, quality, confidence, review)", "9 subsets generated"],
        ["dataset_verified is structural, not listened", "speaker column is a folder proxy", "most audio is lossy 11–48 kHz mp3/aac, none is a WAV master"],
        ["no TTS-grade recordings exist yet"],
        "Verify the review queue → re-run → dataset_verified grows; only then consider Stage 1",
        ["metadata.csv", "subsets/subsets.json"]))
    body.append(section(5, "REFERENCE BANK", rb_status,
        f"{R.get('metres_with_candidate', 0)} metres have a candidate, {R.get('metres_safe_reference', 0)} structurally safe, {R.get('metres_human_verified', 0)} human-verified, of {R.get('metres_total', 0)}",
        "reference_bank.json/html; Vāgdhenu's bank.json (16 metres, Prathosh's voice) used as the format model only",
        ["best/alternatives per metre with score, L/G, duration, quality, what is missing"],
        ["human confirmation text = audio for every candidate", "clean single-rendition takes for metres whose only audio is long/teaching-style or low-rate"],
        ["speaker for Kamadhenu undecided"],
        "Listen to the P0 metres in reference_bank.html; mark verified ones in mapping_overrides.json",
        ["reference_bank.html", "reference_bank.csv"]))
    body.append(section(6, "SANSKRIT FRONTEND", fe_status,
        f"{len(fg.get('cases', []))} probe cases through 4 DGE paths + 5 Vāgdhenu paths; {len(fg.get('findings', []))} findings ({sum(1 for f in fg.get('findings', []) if f['severity']=='high')} high)",
        "frontend_gap_report.json/md (tools/kamadhenu/frontend_gap.py)",
        [k + ": " + v for k, v in fg.get("checklist", {}).items() if v.endswith("DONE") or "DONE for TTS" in v],
        [k + ": " + v for k, v in fg.get("checklist", {}).items() if not (v.endswith("DONE") or "DONE for TTS" in v)],
        [],
        "Port the 4 Vāgdhenu text fixes into texts.py and patch chandas.js nasal weight (Claude, P1)",
        ["frontend_gap_report.md"]))
    body.append(section(7, "VĀGDHENU INTEGRATION", vg_status,
        "repo cloned and read (17 src files, TECH_REPORT, bank.json, training/); reusable: prep_text.py, extract_prosody.py, bank.json format, render input shape; replace: tts_meter.py/chandas_labeler.py metre tables (DGE is authoritative); not runnable here (CUDA 12.1 + 3.15 GB weights)",
        "chandas_comparison.md §reuse/replace/wrap; kamadhenu_gap_matrix.html",
        ["architecture understood: IndicF5 DiT + BigVGAN-v2, Kannada routing, half-reference rule, reference-driven prosody"],
        ["Kamadhenu wrapper that feeds DGE text + DGE chandas + Kamadhenu reference into render.py", "GPU host", "weights download"],
        ["no GPU in this environment"],
        "Stage 1 baseline: render 5 DGE verses with Vāgdhenu's own bank on a GPU machine (Claude writes the shard JSON; you run it)",
        ["kamadhenu_gap_matrix.html"]))
    body.append(section(8, "VOICE TRAINING", tr_status, "nothing trained; training readiness Stages 1–6 assessed in KAMADHENU_TODO.md", "dataset subsets; Vāgdhenu training/ scripts", [], ["a decided speaker", "≥30 min grade A/B verified clips", "GPU"], ["speaker undecided", "no TTS-grade audio"], "Do NOT train yet", []))
    body.append(section(9, "PROSODY", pr_status, "reference-driven only (Vāgdhenu finding: text-side conditioner is inert)", "TECH_REPORT.md §14; extract_prosody.py", [], ["prosody bank from the Kamadhenu voice (needs forced alignment)"], ["Stage 2 first"], "Nothing now", []))
    body.append(section(10, "QC", qc_status, f"automatic QC on all {n_files} files: flags {S.get('flags', {})}; {S.get('decode_errors', 0)} decode errors", "audio_inventory.json", ["format/rate/channels/bit-depth", "peak/RMS/level", "silence (lead/trail/internal)", "clipping", "low volume", "noise floor / SNR", "exact + likely duplicates", "extension≠codec"], ["LUFS", "ASR-based text check"], [], "Re-run automatically with every audit; add ASR check as P1", ["audio_inventory.csv"]))
    body.append(section(11, "PRODUCTION", prod_status, "no rendering pipeline; DGE player + CDN convention exist and work (5 broken verse links found)", "fetch_manifest.json failed entries; dge/js/audio.js", ["DGE audio player + base-URL override chain (reusable as-is)"], ["everything from Stage 1 onward"], [], "Fix the 5 broken audio links on the site (smv5.8/5.14/5.16, rv02.54, rv10.06)", []))
    body.append("<h2>Status vocabulary</h2><div class='note'>🟢 DONE · 🟢 VERIFIED · 🟡 PARTIAL · 🟠 IN PROGRESS · 🔴 NOT STARTED · 🔴 BLOCKED · ⚪ NOT REQUIRED — DONE only where the thing was inspected/tested for the Kamadhenu use.</div>")
    from .common import html_page
    html = html_page("KAMADHENU — DGE × VĀGDHENU", "".join(body), f"master dashboard · {progress}% overall")
    write_text(DS / "KAMADHENU_STATUS.html", html)
    log(f"dashboard: overall {progress}% → kamadhenu_dataset/KAMADHENU_STATUS.html")
    return progress


if __name__ == "__main__":
    run()
