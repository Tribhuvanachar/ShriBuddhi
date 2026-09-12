"""Section 12 evidence — compare Vāgdhenu's two metre tables (src/tts_meter.py METERS and
src/chandas_labeler.py SIGNATURES) against the DGE Chandas database. Writes chandas_comparison.json;
chandas_comparison.md quotes it. Run with VAGDHENU=/path/to/clone (default: scratchpad clone)."""
import ast, json, os, re, sys
from pathlib import Path
from .common import DS, DGE, write_json, read_json, log, now_ist

VAG = Path(os.environ.get("VAGDHENU", "/tmp/claude-0/-home-user-bhumandala/e8a5c83c-760f-5d7b-9fbc-3df8440bd264/scratchpad/vagdhenu"))
IAST2DEV = {"indravajra": "इन्द्रवज्रा", "upendravajra": "उपेन्द्रवज्रा", "upajati": "उपजाति", "vamshastha": "वंशस्थ", "indravamsha": "इन्द्रवंशा", "vasantatilaka": "वसन्ततिलका",
            "malini": "मालिनी", "shikharini": "शिखरिणी", "mandakranta": "मन्दाक्रान्ता", "harini": "हरिणी", "prithvi": "पृथ्वी", "shardulavikridita": "शार्दूलविक्रीडित", "sragdhara": "स्रग्धरा",
            "indravajrā(11)": "इन्द्रवज्रा", "upendravajrā(11)": "उपेन्द्रवज्रा", "vaṃśastha(12)": "वंशस्थ", "vasantatilakā(14)": "वसन्ततिलका", "mālinī(15)": "मालिनी", "mandākrāntā(17)": "मन्दाक्रान्ता",
            "śikhariṇī(17)": "शिखरिणी", "pṛthvī(17)": "पृथ्वी", "śārdūlavikrīḍita(19)": "शार्दूलविक्रीडित", "sragdharā(21)": "स्रग्धरा",
            "anuṣṭubh": "अनुष्टुप्", "pramāṇikā": "प्रमाणिका", "rathoddhatā": "रथोद्धता", "śālinī": "शालिनी", "indravaṃśā": "इन्द्रवंशा", "drutavilambita": "द्रुतविलम्बित", "bhujaṅgaprayāta": "भुजङ्गप्रयात", "vasantatilakā": "वसन्ततिलका", "upajāti": "उपजाति", "indravajrā": "इन्द्रवज्रा", "upendravajrā": "उपेन्द्रवज्रा", "vaṃśastha": "वंशस्थ", "mālinī": "मालिनी", "śārdūlavikrīḍita": "शार्दूलविक्रीडित", "sragdharā": "स्रग्धरा"}


def dge_db():
    db = read_json(DGE / "data/vedanga/chandas/data.json")
    idx = {}
    for v in db["sama_vrutta"]:
        lg = "".join("G" if c == "ग" else "L" for c in v["lakshana"])
        for n in v["vrutta_names"]:
            idx[re.sub("म्$", "", n)] = (lg, v)
    return idx, db


def run():
    if not VAG.exists():
        log("Vāgdhenu clone not found; skipping comparison"); return None
    src = (VAG / "src/tts_meter.py").read_text(encoding="utf-8")
    meters = ast.literal_eval(re.search(r"METERS = (\[.*?\n\])", src, re.S).group(1))
    lab = (VAG / "src/chandas_labeler.py").read_text(encoding="utf-8")
    sigs = ast.literal_eval(re.search(r"SIGNATURES = (\{.*?\n\})", lab, re.S).group(1))
    yati = ast.literal_eval(re.search(r"YATI = (\{.*?\n\})", lab, re.S).group(1))
    bank = read_json(VAG / "src/reference_bank/bank.json")
    idx, db = dge_db()
    rows = []
    for name, plen, pats in meters:
        dn = IAST2DEV.get(name); d = idx.get(dn) if dn else None
        for p in pats:
            ok = d and (p[:-1] == d[0][:-1])
            rows.append({"source": "tts_meter.METERS", "vagdhenu_name": name, "vagdhenu_pattern": p, "dge_name": dn, "dge_pattern": d[0] if d else None, "agrees": bool(ok), "dge_yati": d[1].get("yati") if d else None})
    for p, name in sigs.items():
        dn = IAST2DEV.get(name); d = idx.get(dn) if dn else None
        rows.append({"source": "chandas_labeler.SIGNATURES", "vagdhenu_name": name, "vagdhenu_pattern": p, "dge_name": dn, "dge_pattern": d[0] if d else None, "agrees": bool(d and p[:-1] == d[0][:-1]), "dge_yati": d[1].get("yati") if d else None,
                     "vagdhenu_yati": yati.get(name)})
    # internal disagreement between the two Vāgdhenu tables
    internal = []
    m1 = {IAST2DEV.get(n): set(p) for n, _, p in meters}
    for p, name in sigs.items():
        dn = IAST2DEV.get(name)
        if dn in m1 and p not in m1[dn]:
            internal.append({"metre": dn, "tts_meter": sorted(m1[dn]), "chandas_labeler": p})
    bank_metres = [k for k in bank if k != "_doc"]
    bank_in_dge = {k: (IAST2DEV.get(k) in idx) or IAST2DEV.get(k) == "अनुष्टुप्" or IAST2DEV.get(k) == "उपजाति" for k in bank_metres}
    out = {"generated_at": now_ist(), "dge_sama_vrutta": len(db["sama_vrutta"]), "dge_total_vrutta": len(db["sama_vrutta"]) + len(db["ardhasama_vrutta"]) + len(db["vishama_vrutta"]) + len(db["upajati_vrutta"]),
           "vagdhenu_tts_meter_entries": len(meters), "vagdhenu_labeler_signatures": len(sigs), "vagdhenu_bank_metres": bank_metres, "bank_metre_in_dge_db": bank_in_dge,
           "pattern_checks": rows, "vagdhenu_internal_disagreements": internal,
           "disagreements_with_dge": [r for r in rows if not r["agrees"]]}
    write_json(DS / "chandas_comparison.json", out)
    log(f"compare: {len(rows)} pattern checks, {len(out['disagreements_with_dge'])} disagree with DGE, {len(internal)} internal Vāgdhenu disagreements")
    for r in out["disagreements_with_dge"]: log("   ", r["source"], r["vagdhenu_name"], r["vagdhenu_pattern"], "vs DGE", r["dge_pattern"])
    return out


if __name__ == "__main__":
    run()
