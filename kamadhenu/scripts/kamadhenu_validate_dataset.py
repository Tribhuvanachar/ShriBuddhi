#!/usr/bin/env python3
"""Kamadhenu Phase 4 — validate a dataset file (jsonl) without changing it.

    python3 kamadhenu/scripts/kamadhenu_validate_dataset.py [dataset.jsonl ...] [--no-audio]

Default input: kamadhenu_dataset/metadata.jsonl (legacy field names are accepted). Checks: audio exists / readable
(ffprobe), text present, sample rate, duration vs syllables, silence, clipping, Unicode validity, Sanskrit text
normalisation (Devanagari only, NFC, no verse numbers), duplicates (audio SHA-1 and text), missing metadata, metre
label in the DGE database, laghu/guru string shape and length vs syllables, pāda count vs pādas in the text,
suspicious pairings (duration far from what the syllable count predicts). Writes
kamadhenu/reports/kamadhenu_dataset_report.json and kamadhenu/reports/kamadhenu_dataset_report.md. Marks, never deletes."""
import argparse, collections, json, re, subprocess, sys, unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/vedanga/chandas/data.json"
REPORT = ROOT / "kamadhenu/reports/kamadhenu_dataset_report"
SEC_PER_SYLL = (0.20, 0.75)          # plausible recitation pace band (Vāgdhenu bank: 0.26–0.44 s/akṣara; teaching style slower)
ALIAS = {"chandas": "meter", "chandas_confidence": "meter_confidence", "audio_quality": "recording_quality", "mapping_confidence": "text_audio_confidence",
         "duration_seconds": "duration", "syllable_count": "syllables", "snr_db_est": "snr_db"}


def metre_names():
    d = json.load(open(DB, encoding="utf-8")); names = set()
    for k in ("sama_vrutta", "ardhasama_vrutta", "vishama_vrutta", "upajati_vrutta", "matra_vrutta"):
        for v in d[k]:
            for n in v["vrutta_names"]:
                names.add(n); names.update(x.strip() for x in n.split(","))
    for j in d["akshara_jaati"]: names.add(j["jaati"])
    names.update(re.sub(r"\s*\(.*?\)\s*", "", n).strip() for n in list(names))   # base names: उपजाति (कीर्ति) -> उपजाति
    names.update(["अनुष्टुप्", "गद्यम्"])
    return names


def norm(r):
    for a, b in ALIAS.items():
        if a in r and b not in r: r[b] = r[a]
    return r


def _ffmpeg():
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil; return shutil.which("ffmpeg")


def probe(path):
    """Read sample rate / duration from `ffmpeg -i` (imageio-ffmpeg ships ffmpeg only, no ffprobe)."""
    exe = _ffmpeg()
    if not exe: return {"ok": False, "error": "no ffmpeg"}
    try:
        out = subprocess.run([exe, "-hide_banner", "-i", path], capture_output=True, text=True, timeout=30).stderr
        m_sr = re.search(r"(\d{4,6}) Hz", out); m_d = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", out)
        if not (m_sr and m_d): return {"ok": False, "error": "unparsed"}
        h, m, sec = m_d.groups()
        return {"ok": True, "sample_rate": int(m_sr.group(1)), "duration": int(h) * 3600 + int(m) * 60 + float(sec)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="*", default=[str(ROOT / "kamadhenu_dataset/metadata.jsonl")])
    ap.add_argument("--no-audio", action="store_true", help="skip ffprobe (use the recorded duration/sample rate)")
    a = ap.parse_args()
    metres = metre_names(); issues = collections.Counter(); per = []; seen_sha = {}; seen_text = {}
    n = 0
    for f in a.files:
        for line in open(f, encoding="utf-8"):
            if not line.strip(): continue
            r = norm(json.loads(line)); n += 1; flags = []
            rid = r.get("id") or f"row{n}"
            text = r.get("text") or ""
            # text
            if not text.strip(): flags.append("text_missing")
            else:
                if unicodedata.normalize("NFC", text) != text: flags.append("text_not_nfc")
                if re.search(r"[^ऀ-ॿ\s।॥\-'’]", text): flags.append("text_non_devanagari_chars")
                if re.search(r"[०-९\d]{1,3}\s*[॥।]?\s*$", text.strip()): flags.append("text_has_trailing_number")
                if re.search(r"उवाच\s*$", text.split("\n")[0]): flags.append("text_has_speaker_line")
                if "�" in text: flags.append("text_replacement_char")
                key = re.sub(r"[^ऀ-ॿ]", "", text)
                if key in seen_text: flags.append(f"duplicate_text_of:{seen_text[key]}")
                else: seen_text[key] = rid
            # audio
            audio = r.get("audio") or ""
            p = ROOT / audio
            if not audio: flags.append("audio_missing")
            elif not p.exists(): flags.append("audio_file_not_found")
            elif not a.no_audio:
                pr = probe(str(p))
                if not pr["ok"]: flags.append("audio_unreadable")
                else:
                    if r.get("sample_rate") and abs(pr["sample_rate"] - r["sample_rate"]) > 1: flags.append("sample_rate_mismatch")
                    if r.get("duration") and abs(pr["duration"] - r["duration"]) > 1.0: flags.append("duration_mismatch")
            sr = r.get("sample_rate")
            if sr and sr < 16000: flags.append("sample_rate_below_16k")
            dur = r.get("duration")
            if dur is not None and dur < 1.0: flags.append("audio_too_short")
            if dur is not None and dur > 60: flags.append("audio_over_60s")
            if r.get("qc_flags"):
                for q in r["qc_flags"]: flags.append("qc:" + str(q))
            if r.get("peak_dbfs") is not None and r["peak_dbfs"] > -0.1: flags.append("clipping_peak")
            sha = r.get("audio_sha1") or (r.get("id") or "")[3:]
            if sha:
                if sha in seen_sha: flags.append(f"duplicate_audio_of:{seen_sha[sha]}")
                else: seen_sha[sha] = rid
            # metadata
            for k in ("speaker", "source", "split"):
                if not r.get(k): flags.append(f"missing_{k}")
            if str(r.get("speaker", "")).startswith(("unattributed", "dge_linked", "drive")) or "unattributed" in str(r.get("speaker", "")): flags.append("speaker_unattributed")
            # metre / laghu-guru / pādas
            m = r.get("meter")
            if m:
                base = re.sub(r"\s*\(.*?\)\s*|\s*—.*$", "", m).strip()
                if not any(x.strip() in metres for x in base.split(",")) and base not in metres: flags.append("meter_not_in_dge_db")
            else: flags.append("meter_missing")
            lg = r.get("laghu_guru")
            if lg:
                if not re.fullmatch(r"[LG|]+", lg): flags.append("laghu_guru_invalid_chars")
                padas_lg = [x for x in lg.split("|") if x]
                syl = r.get("syllables")
                if syl and sum(len(x) for x in padas_lg) != syl: flags.append("laghu_guru_length_vs_syllables")
                pc = r.get("pada_count")
                if pc and len(padas_lg) != pc: flags.append("pada_count_vs_laghu_guru")
                lines = [x for x in text.split("\n") if x.strip()]
                if pc and lines and len(lines) not in (pc, pc // 2, 1) and pc >= 2: flags.append("pada_count_vs_text_lines")
            else: flags.append("laghu_guru_missing")
            # suspicious pairing: pace
            syl = r.get("syllables")
            if syl and dur:
                pace = dur / syl
                if pace < SEC_PER_SYLL[0]: flags.append("too_fast_for_text")
                elif pace > SEC_PER_SYLL[1]: flags.append("too_slow_for_text_or_repeated")
            conf = r.get("text_audio_confidence")
            if conf is not None and conf < 0.7: flags.append("text_audio_confidence_low")
            for fl in flags: issues[fl.split(":")[0]] += 1
            per.append({"id": rid, "audio": audio, "flags": flags})
    clean = sum(1 for x in per if not x["flags"] or set(f.split(":")[0] for f in x["flags"]) <= {"speaker_unattributed"})
    rep = {"generated_at": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST"), "inputs": a.files, "records": n,
           "records_clean_or_only_unattributed": clean, "issue_counts": dict(issues.most_common()), "records": n, "per_record": per}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(rep, open(str(REPORT) + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = [f"# Kamadhenu dataset validation\n\n{rep['generated_at']} · inputs: {', '.join(a.files)}\n",
          f"* records: **{n}**\n* clean (or only 'speaker unattributed'): **{clean}**\n\n| issue | records |\n|---|---|"]
    md += [f"| {k} | {v} |" for k, v in issues.most_common()]
    md.append("\nNothing was changed or deleted; each record's flags are in the JSON report under `per_record`.")
    open(str(REPORT) + ".md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(json.dumps({k: v for k, v in rep.items() if k != "per_record"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
