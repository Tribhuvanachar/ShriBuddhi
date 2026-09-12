"""Section 11 — Sanskrit text-frontend audit: run the SAME tricky inputs through every text path that
exists (DGE search_toolkit to_slp1 + phonetic folds, DGE subanta-steps SLP1 converter, DGE chandas.js
syllabifier, Vāgdhenu prep_text / tts_normalize / tts_g2p / tts_syllabify) and record where Sanskrit
pronunciation information is lost or damaged. Output: frontend_gap_report.json (quoted by the .md)."""
import json, os, re, subprocess, sys, unicodedata
from pathlib import Path
from .common import ROOT, DGE, DS, TOOLS, write_json, log, now_ist

VAG = Path(os.environ.get("VAGDHENU", "/tmp/claude-0/-home-user-bhumandala/e8a5c83c-760f-5d7b-9fbc-3df8440bd264/scratchpad/vagdhenu"))
sys.path.insert(0, str(DGE))
from search_toolkit_pkg.translit import to_slp1 as dge_to_slp1     # noqa
from search_toolkit_pkg.normalize import phonetic_key, coarse_key  # noqa

CASES = [
    ("visarga before k (jihvāmūlīya context)", "दुःखम्", {"jihvamuliya"}),
    ("visarga before p (upadhmānīya context)", "तपःफलम्", {"upadhmaniya"}),
    ("explicit jihvāmūlīya U+1CF5", "दुᳵखम्", {"vedic_ext"}),
    ("explicit upadhmānīya U+1CF6", "अन्तᳶपुरम्", {"vedic_ext"}),
    ("candrabindu", "सँयोगः", {"candrabindu"}),
    ("anusvāra before sibilant", "संसारः", {"anusvara"}),
    ("anusvāra before y", "संयोगः", {"anusvara"}),
    ("anusvāra before stop (homorganic)", "अङ्कः अंकः", {"anusvara"}),
    ("long vocalic ṝ", "पितॄणाम्", {"vocalic"}),
    ("vocalic ḷ", "कॢप्तम्", {"vocalic"}),
    ("avagraha", "सोऽहम्", {"avagraha"}),
    ("ZWJ/ZWNJ inside conjunct", "क्‍ष क्‌ष", {"zw"}),
    ("nukta consonants", "क़ ख़ ग़ ज़ ड़ ढ़ फ़", {"nukta"}),
    ("geminate", "सत्त्वम् उत्पत्तिः", {"geminate"}),
    ("retroflex series", "षट् षष्ठः ढक्का", {"retroflex"}),
    ("aspirate cluster", "कृष्ण ब्रह्मा वृद्धिः", {"aspirate"}),
    ("Kannada script input", "ಧರ್ಮಕ್ಷೇತ್ರೇ ಕುರುಕ್ಷೇತ್ರೇ", {"kannada"}),
    ("daṇḍa and verse number", "किमकुर्वत सञ्जय ॥१.१॥", {"punct"}),
    ("ॐ praṇava", "ॐ नमो नारायणाय", {"om"}),
    ("Vedic svara marks", "अ॒ग्निमी॑ळे पु॒रोहि॑तम्", {"svara"}),
    ("word-final visarga (echo/lengthening)", "रामः", {"visarga_final"}),
    ("visarga sandhi context aḥ+voiced", "रामः गच्छति", {"sandhi"}),
]


def vag_paths():
    try:
        sys.path.insert(0, str(VAG / "src"))
        import prep_text, tts_normalize, tts_g2p, tts_syllabify, tts_weight
        return dict(prep_text=prep_text, tts_normalize=tts_normalize, tts_g2p=tts_g2p, tts_syllabify=tts_syllabify, tts_weight=tts_weight)
    except Exception as e:
        return {"error": str(e)}


def dge_subanta_slp(texts):
    js = """
const fs=require('fs');global.window=global;global.document={currentScript:{src:'x/js/subanta-steps.js'},readyState:'complete',querySelector:()=>null,createElement:()=>({style:{}}),head:{appendChild(){}}};
global.localStorage={getItem:()=>null};
let src=fs.readFileSync('dge/js/subanta-steps.js','utf8');src=src.replace(/import\\(/g,'(function(){return Promise.reject(new Error("no wasm"))})(');
try{eval(src)}catch(e){}
const S=window.DGESubantaSteps;const inp=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(inp.map(t=>{try{return S.slp(t)}catch(e){return 'ERR '+e}})));
"""
    p = TOOLS / "_subanta_probe.js"; p.write_text(js)
    try:
        r = subprocess.run(["node", str(p)], input=json.dumps(texts, ensure_ascii=False), capture_output=True, text=True, cwd=str(ROOT))
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout else ["ERR " + r.stderr[-200:]] * len(texts)
    finally:
        p.unlink(missing_ok=True)


def dge_chandas_sylls(texts):
    r = subprocess.run(["node", str(TOOLS / "chandas_runner.js")], input=json.dumps(texts, ensure_ascii=False), capture_output=True, text=True, cwd=str(ROOT))
    out = json.loads(r.stdout)
    return [" ".join(s["text"] + ("̲" if s["guru"] else "") for p in x.get("padas", []) for s in p["sylls"]) for x in out]


def run():
    vag = vag_paths()
    texts = [c[1] for c in CASES]
    sub = dge_subanta_slp(texts); ch = dge_chandas_sylls(texts)
    rows = []
    for (label, t, tags), s_slp, s_ch in zip(CASES, sub, ch):
        row = {"case": label, "input": t, "dge_search_slp1": dge_to_slp1(t, "devanagari"), "dge_phonetic_key": phonetic_key(dge_to_slp1(t, "devanagari")), "dge_subanta_slp1": s_slp, "dge_chandas_syllables": s_ch}
        if "error" not in vag:
            try:
                row["vag_model_text_kannada"] = vag["prep_text"].model_text(t)
                row["vag_model_text_sandhi"] = vag["prep_text"].model_text_sandhi(t)
                row["vag_mfa_text"] = vag["prep_text"].mfa_text(t)
                row["vag_align_slp1"] = vag["prep_text"].align_slp1(t)
                n = vag["tts_normalize"].normalize(t); g = vag["tts_g2p"].to_slp1(n)
                syl = vag["tts_syllabify"].syllabify(g); vag["tts_weight"].tag_weights(syl)
                row["vag_normalize_g2p"] = g; row["vag_syllables_lg"] = " ".join(f"{x['text']}{x['weight']}" for x in syl)
            except Exception as e:
                row["vag_error"] = str(e)
        else:
            row["vag_error"] = vag["error"]
        rows.append(row)
    # findings derived mechanically from the rows
    findings = []
    def f(sev, comp, case, what, evidence, fix):
        findings.append({"severity": sev, "component": comp, "case": case, "problem": what, "evidence": evidence, "fix": fix})
    for r in rows:
        t = r["input"]
        if "ᳵ" in t or "ᳶ" in t:
            if "ᳵ" not in r["dge_search_slp1"] and "Z" not in r["dge_search_slp1"] and "H" not in r["dge_search_slp1"]:
                f("high", "DGE search_toolkit.to_slp1", r["case"], "explicit jihvāmūlīya/upadhmānīya is dropped (not mapped to H/Z/V)", r["dge_search_slp1"], "map U+1CF5→'Z', U+1CF6→'V' (Vāgdhenu tts_g2p convention) or at least to 'H'")
            if "ᳵ" in r.get("vag_model_text_kannada", "") or "ᳶ" in r.get("vag_model_text_kannada", ""):
                f("medium", "Vāgdhenu prep_text.model_text", r["case"], "explicit jihvāmūlīya/upadhmānīya passes through to the Kannada model text where it is out-of-vocabulary", r["vag_model_text_kannada"], "fold to plain visarga before Kannada routing (Vāgdhenu does this only in the phonetic_mfa kannada_safe arm)")
        if "ँ" in t:
            if "~" not in r["dge_search_slp1"]:
                f("medium", "DGE search_toolkit.to_slp1", r["case"], "candrabindu lost", r["dge_search_slp1"], "map U+0901 → '~'")
            if "̲" not in (r["dge_chandas_syllables"].split(" ")[0]):
                f("medium", "DGE chandas.js", r["case"], "candrabindu does not make the syllable guru (only ं/ः are tested)", r["dge_chandas_syllables"], "extend the nasal test at chandas.js:58 to /[ँंः]/")
        if "ॄ" in t and "F" not in r["dge_search_slp1"]:
            f("medium", "DGE search_toolkit.to_slp1", r["case"], "long vocalic ṝ not represented", r["dge_search_slp1"], "map ॄ/ॠ → 'F'")
        if "ॢ" in t and "x" not in r["dge_search_slp1"]:
            f("low", "DGE search_toolkit.to_slp1", r["case"], "vocalic ḷ not represented", r["dge_search_slp1"], "map ॢ/ऌ → 'x'")
        if r["case"].startswith("Kannada") and not re.search(r"[a-zA-Z]", r["dge_search_slp1"]):
            f("high", "DGE search_toolkit.to_slp1 (as used by texts.py)", r["case"], "Kannada input is not transliterated by the Devanagari path; build_search_index folds Kannada→Devanagari by code-point shift first, texts.py must do the same before Chandas", r["dge_search_slp1"], "always run fold_indic_to_devanagari() before to_slp1/Chandas")
        if r["case"].startswith("Kannada") and r["dge_chandas_syllables"].strip() == "":
            f("high", "DGE chandas.js", r["case"], "Kannada-script verse yields zero syllables (engine is Devanagari-only, silent)", "padas: []", "transliterate to Devanagari upstream (kamadhenu texts.py does; the site page does not)")
        if r["case"].startswith("Vedic svara"):
            if "॒" in r["dge_search_slp1"] or "॑" in r["dge_search_slp1"]:
                f("low", "DGE search_toolkit.to_slp1", r["case"], "svara marks leak into SLP1", r["dge_search_slp1"], "strip U+0951/U+0952 (build_search_index.clean_devanagari already does)")
            f("info", "all", r["case"], "no path preserves udātta/anudātta/svarita — Vedic accent is out of scope for every existing frontend", "", "separate Vedic annotation track (dge/tts/ARCHITECTURE.md §Vedic) — Stage 6 only")
        if r["case"] == "nukta consonants" and ("ERR" in str(r["dge_subanta_slp1"]) or len(re.sub(r"[^a-zA-Z]", "", str(r["dge_subanta_slp1"]))) < 7):
            f("low", "DGE subanta-steps.slp", r["case"], "nukta letters are not all converted", str(r["dge_subanta_slp1"]), "NFD-decompose nukta or add explicit mappings; Sanskrit rarely needs them")
        if r["case"] == "ZWJ/ZWNJ inside conjunct" and ("‍" in r["dge_search_slp1"] or "‌" in r["dge_search_slp1"]):
            f("medium", "DGE search_toolkit.to_slp1", r["case"], "zero-width joiners survive into SLP1", repr(r["dge_search_slp1"]), "strip U+200C/U+200D before transliteration (texts.py does)")
        if r["case"].startswith("visarga sandhi") and r.get("vag_model_text_sandhi"):
            f("info", "Vāgdhenu prep_text.model_text_sandhi", r["case"], "applies utva/rutva/lopa visarga sandhi at word boundaries — changes the text that will be spoken; DGE has no equivalent, and this must NOT be applied when the recording already has plain visarga", r["vag_model_text_sandhi"], "keep as an explicit, logged pronunciation transform; never rewrite DGE canonical text")
        if r["case"].startswith("word-final visarga") and r.get("vag_model_text_sandhi"):
            f("info", "Vāgdhenu prep_text.visarga_echo_final", r["case"], "chant echo-vowel (rāmaḥ→rāmaha) is applied to the last word — a tradition-specific pronunciation choice, must be a per-project switch", r["vag_model_text_sandhi"], "expose as a parameter in the Kamadhenu frontend; default follows the lead's recitation style")
        if r["case"].startswith("anusvāra before y") and r.get("vag_mfa_text") and "ँ" not in r["vag_mfa_text"] and "ञ्" not in r["vag_mfa_text"]:
            f("low", "Vāgdhenu prep_text.phonetic_mfa", r["case"], "anusvāra before y kept as ं (tts_normalize.py turns it into candrabindu) — the two Vāgdhenu normalisers disagree", r["vag_mfa_text"], "pick one rule for Kamadhenu and document it")
    f("high", "DGE (everywhere)", "akṣara segmentation", "DGE has no reusable Sanskrit syllabifier outside chandas.js (browser JS, Devanagari-only, ल/ग alphabet); Vāgdhenu has two (tts_syllabify.py maximize-onset, chandas_labeler.py orthographic) that count the same but split codas differently", "see rows", "Kamadhenu wraps chandas.js headlessly (done: tools/kamadhenu/chandas_runner.js); a Python port is NOT needed for the dataset stage")
    f("high", "both", "G2P", "neither project has a phonemic G2P beyond SLP1 = one char per phone; Vāgdhenu deliberately feeds Kannada script to IndicF5 and lets the model learn pronunciation acoustically", "prep_text.model_text", "for Kamadhenu keep SLP1 as the internal representation; script routing (Devanagari vs Kannada) is a model-side choice to re-test on the lead's voice")
    f("medium", "both", "pāda boundaries", "pāda boundaries come only from line breaks / daṇḍas in the source text; where a verse is stored as two hemistich lines the engine splits at the syllable midpoint, which is wrong for uneven ardhasama/viṣama metres", "chandas.js toPadas()", "store pāda-split text in DGE for reference-bank verses (human-checked), or derive from the metre's per-pāda syllable count")
    f("medium", "DGE data", "text defects surface as metre failures", "unequal pāda counts / typos in the corpus (e.g. सिधुः for सिन्धुः in Tīrthaprabandha TP_DAK_003; 23/22-syllable halves in Sumadhva Vijaya 1.17) make the engine return अज्ञातम्", "text_index.json chandas_analysis.inferred_reason", "route these to the DGE correction workflow; they are corpus bugs, not engine bugs")
    out = {"generated_at": now_ist(), "vagdhenu_available": "error" not in vag, "cases": rows, "findings": findings,
           "checklist": {k: v for k, v in {
               "Unicode normalization": "DGE: NFC in clean_devanagari + subanta slp; Vāgdhenu: none explicit (sanscript tolerates NFC) — PARTIAL",
               "Devanagari": "both — DONE", "Kannada": "DGE search folds by code-point shift; Vāgdhenu detect_script→sanscript; chandas.js NO — PARTIAL",
               "SLP1/internal": "both use SLP1 (DGE search_toolkit; Vāgdhenu sanscript) — DONE", "akṣara segmentation": "chandas.js (JS only) / Vāgdhenu ×2 — PARTIAL",
               "vowels & length": "preserved in SLP1 by both; DGE phonetic_key deliberately folds length (search only, never for TTS) — DONE for TTS path",
               "anusvāra": "kept as M by both; homorganic-nasal rewrite only in Vāgdhenu — PARTIAL", "visarga": "kept as H; Vāgdhenu sandhi/echo transforms optional — PARTIAL",
               "jihvāmūlīya/upadhmānīya": "Vāgdhenu tts_normalize emits them; DGE drops them — NOT STARTED in DGE", "retroflex": "preserved by both — DONE", "aspirates": "preserved — DONE",
               "geminates": "preserved in SLP1; DGE phonetic_key collapses them (search only) — DONE for TTS path", "conjuncts": "preserved; chandas.js counts cluster weight — DONE",
               "word boundaries": "spaces preserved; hyphenated compounds in Sumadhva Vijaya source need joining — PARTIAL", "pāda boundaries": "line/daṇḍa based only — PARTIAL",
               "daṇḍa": "stripped by both (kept as pause token only in Vāgdhenu tts_g2p) — DONE", "sandhi": "Vāgdhenu word-boundary visarga sandhi only; no general sandhi engine anywhere — PARTIAL",
               "pronunciation transformations": "Vāgdhenu: ṝ→rū, hna metathesis, echo visarga, vocalic ḷ; DGE: none — PARTIAL", "Vedic svara": "nowhere — NOT STARTED"}.items()}}
    write_json(DS / "frontend_gap_report.json", out)
    log(f"frontend gap: {len(rows)} cases, {len(findings)} findings (vāgdhenu {'available' if out['vagdhenu_available'] else 'MISSING'})")
    return out


if __name__ == "__main__":
    run()
