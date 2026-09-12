"""Stage 4 — canonical text index from DGE (DGE is the authoritative text source; no second text DB).

Collects every verse/unit of the works that the known recordings could belong to, plus every stotra in the
library, into kamadhenu_dataset/text_index.json with: work, section, chapter, verse_id, clean Devanagari,
SLP1, phonetic keys (same folds as the site search index), and the audio URL DGE's own player would use."""
import glob, json, re, sys, unicodedata
from pathlib import Path
from .common import ROOT, DGE, DS, write_json, read_json, log, now_ist, rel

sys.path.insert(0, str(DGE))
from search_toolkit_pkg.translit import to_slp1            # noqa: E402
from search_toolkit_pkg.normalize import phonetic_key, coarse_key  # noqa: E402
from build_search_index import fold_indic_to_devanagari  # noqa: E402  (Kannada/Telugu/Malayalam → Devanagari code-point fold)

_HTML = re.compile(r"<[^>]+>")
_ZW = re.compile("[​‌‍﻿]")
_VEDIC = re.compile("[॒॑᳐-᳿꣠-ꣿ]")
_VERSE_NO = re.compile(r"[।॥|]+\s*[0-9०-९]+(?:\.[0-9०-९]+)*\s*[।॥|]*\s*$")
_DANDA = re.compile(r"[।॥|]+")

# Works to index: (work id, glob of data.json files, loader kind, human label)
WORKS = [
    ("bhagavad_gita", "data/itihasa/bhagavad_gita/adhyaya_*/data.json", "gita", "Bhagavad Gītā"),
    ("sumadhva_vijaya", "data/DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_*/data.json", "legacy", "Sumadhva Vijaya"),
    ("raghavendra_vijaya", "data/DvaitaVedanta/Itara/Kavya/raghavendra_vijaya/sarga_*/data.json", "legacy", "Rāghavendra Vijaya"),
    ("tirtha_prabandha", "data/DvaitaVedanta/Itara/Kavya/tirtha_prabandha/*_prabandha/data.json", "items", "Tīrtha Prabandha"),
    ("PrahladaKrutaNarasimha", "data/DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha/data.json", "legacy", "Prahlāda-kṛta Narasiṃha Stotra"),
    ("nakha_stuti", "data/darshana/vedanta/dvaita/Anandamakaranda/achara_and_ancillary_granthas/nakha_stuti/mula/data.json", "items", "Nakha Stuti"),
    ("kanduka_stuti", "data/darshana/vedanta/dvaita/Anandamakaranda/achara_and_ancillary_granthas/kanduka_stuti/mula/data.json", "items", "Kanduka Stuti"),
    ("dvadasha_stotra", "data/darshana/vedanta/dvaita/Anandamakaranda/dvadasha_stotra/mula/data.json", "items", "Dvādaśa Stotra"),
    ("vishnu_sahasranama", "data/darshana/vedanta/dvaita/Anandamakaranda/stotra/vishnu_sahasranama/mula/data.json", "items", "Viṣṇu Sahasranāma Stotra"),
    ("bhagavata_saroddhara", "data/bhagavata_saroddhara/mula/data.json", "items", "Bhāgavata Sāroddhāra (Viṣṇutīrtha)"),
    ("bhagavata_7", "data/purana/maha_purana/bhagavata_purana_madhva/skandha_07/data.json", "gita", "Bhāgavata Purāṇa (Madhva) skandha 7"),   # 7.9.8–50 = Prahlāda-stuti recordings
    ("mahabharata_tatparya_nirnaya", "data/darshana/vedanta/dvaita/Anandamakaranda/*/mahabharata_tatparya_nirnaya/mula/data.json", "items", "Mahābhārata Tātparya Nirṇaya"),
    ("stotra_misc", "data/stotra/*/data.json", "auto", "Stotra (misc)"),
    ("vedavyasa_gadya", "data/darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/vedavyasa_gadya/mula/data.json", "items", "Vedavyāsa Gadyam (Yādavārya, prose)"),   # one item per epithet; recorded as one 9.7-min file
    ("harikathamrutasara", "data/DvaitaVedanta/Itara/DasaSahitya/dasakuta/jagannathadasa/harikathamrutasara/data.json", "hks", "Harikathāmṛtasāra (Jagannātha Dāsa, Kannada)"),   # hks.<sandhi>.<n>.aac recordings
]


def clean_deva(t):
    t = unicodedata.normalize("NFC", str(t or ""))
    t = _HTML.sub(" ", t.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n"))
    t = t.replace("ꣳ", "ं")
    t = _VEDIC.sub("", t); t = _ZW.sub("", t)
    t = t.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    t = _VERSE_NO.sub("", t.strip())
    lines = []
    for ln in re.split(r"[\n]+|॥|।", t):
        ln = re.sub(r"[ \t]+", " ", ln).strip(" -–—|/.,;:")
        ln = re.sub(r"^[0-9०-९.]+\s*", "", ln)
        if ln and re.search(r"[ऀ-ॿ]", ln):
            lines.append(ln)
    return lines


def unit_record(work, label, section, chapter, verse_id, raw, uid, path, audio_url=None, extra=None):
    lines = clean_deva(raw)
    text = "\n".join(lines)
    # drop speaker headers like "धृतराष्ट्र उवाच" from the metrical text but keep them in raw
    metrical = []
    for l in lines:
        if re.search(r"(उवाच|नुवाच|ोवाच|ावाच|युवाच)\s*$", l) and len(l.split()) <= 3:
            continue   # speaker headers (श्रीभगवानुवाच, अर्जुन उवाच, सञ्जय उवाच …) are not part of the metre
        if re.fullmatch(r"(ॐ|ओम्|श्री|हरिः ॐ|ॐ तत्सत्|श्रीः)[ ।॥]*", l):
            continue   # praṇava / auspicious marks
        l = re.sub(r"^(?:श्री\s*)?\S{0,14}?(?:उवाच|नुवाच|ोवाच|ावाच|युवाच)(?=\S)", "", l)   # "अर्जुन उवाचएवं…" glued to the verse
        l = re.sub(r"\([^)]*\)", "", l)          # editorial variant readings "(भा)" are not recited
        l = re.sub(r"\s+", " ", l).strip()
        if l:
            metrical.append(l)
    slp = to_slp1(" ".join(metrical), "devanagari") if metrical else ""
    rec = {"id": uid, "work": work, "work_label": label, "section": section, "chapter": chapter, "verse_id": str(verse_id),
           "dge_path": rel(path), "text": text, "metrical_text": "\n".join(metrical),
           "slp1": slp, "phonetic_key": phonetic_key(slp) if slp else "",
           "n_lines": len(metrical), "dge_audio_url": audio_url}
    if extra: rec.update(extra)
    return rec


def load_work(work, pattern, kind, label):
    out = []
    for p in sorted(glob.glob(str(DGE / pattern)), key=lambda s: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)]):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            log(f"  cannot read {p}: {e}"); continue
        section = Path(p).parent.name
        k = kind
        if k == "auto":
            k = "legacy" if isinstance(d, dict) and "shlokas" in d else "items"
            if work == "stotra_misc":
                work_id = Path(p).parent.name
                if work_id == "PrahladaKrutaNarasimha":
                    continue
            else:
                work_id = work
        else:
            work_id = work
        if k == "hks":
            # Kannada ṣaṭpadi verses: items {id: hks-<sandhi>-<n>, sa: Kannada text, sandhi_number, sandhi_title}.
            # The Chandas engine and SLP1 path are Devanagari-only, so the text is folded code-point-wise
            # (same fold as build_search_index.py); the Kannada original is kept as text_kannada.
            for it in d.get("items", []):
                m = re.match(r"hks-(\d+)-(\d+)$", str(it.get("id", "")))
                if not m or not it.get("sa"):
                    continue
                sn, n = int(m.group(1)), int(m.group(2))
                kn = re.sub(r"\s*\|\|\s*|\s*\|\s*", "\n", it["sa"])   # the app text marks pāda breaks with | and || → one pāda per line
                rec = unit_record(work_id, label, f"sandhi_{sn:02d}", sn, n, fold_indic_to_devanagari(kn), f"{work_id}:{it['id']}", p,
                                  extra={"text_kannada": it["sa"], "text_script": "kannada", "language": "kn", "sandhi_title": it.get("sandhi_title", "")})
                out.append(rec)
            continue
        if k == "gita":
            for it in d.get("items", []):
                adh = int(re.sub(r"\D", "", it.get("id", "0")) or 0)
                for sh in it.get("shlokas", []):
                    n = sh.get("number")
                    prefix = "gita" if work == "bhagavad_gita" else work_id
                    out.append(unit_record(work_id, label, f"adhyaya_{adh:02d}", adh, n, sh.get("sanskrit_text", ""), f"{prefix}:{adh}.{n}", p))
        elif k == "legacy":
            m = d.get("metadata", {}); shl = d.get("shlokas", {})
            base, pre, ext, width = m.get("archiveBaseUrl"), m.get("filePrefix", ""), m.get("fileExtension", ".mp3"), m.get("fileNumberWidth")
            chap = int(re.sub(r"\D", "", section) or 0) if re.search(r"\d", section) else section
            keys = sorted(shl.keys(), key=lambda x: int(x) if str(x).isdigit() else 0) if isinstance(shl, dict) else range(1, len(shl) + 1)
            for n in keys:
                sh = shl[n] if isinstance(shl, dict) else shl[n - 1]
                fid = str(n).zfill(width) if width else str(n)
                url = f"{base}{pre}{fid}{ext}" if base else None
                out.append(unit_record(work_id, m.get("title", label) if work == "stotra_misc" else label, section, chap, n, sh.get("sa", "") if isinstance(sh, dict) else sh, f"{work_id}:{section}:{n}", p, url))
        else:
            for it in d.get("items", []):
                tags = it.get("tags") or []
                if any(str(t).lower().startswith("heading") for t in tags):
                    continue
                txt = it.get("sanskrit_text") or it.get("text") or ""
                if not txt or not re.search(r"[ऀ-ॿ]", str(txt)):
                    continue
                mv = re.search(r"_V(\d+)$", str(it.get("id", "")))
                vid = int(mv.group(1)) if mv else ((it.get("source") or {}).get("verse") or it.get("reference") or it.get("id"))
                if it.get("kind") in ("mantra", "colophon", "prose"):
                    continue   # not metrical, not recitation units for the dataset
                sec = it.get("section") or section
                out.append(unit_record(work_id, d.get("title", label) if work == "stotra_misc" else label, sec, sec, vid, txt, f"{work_id}:{it.get('id')}", p,
                                       extra={"reference": it.get("reference", ""), "category": it.get("category", "")}))
    return out


def run():
    units = []
    for work, pat, kind, label in WORKS:
        u = load_work(work, pat, kind, label)
        log(f"  texts: {work:32s} {len(u):5d} units")
        units.extend(u)
    # de-duplicate exact ids
    seen = set(); uniq = []
    for u in units:
        if u["id"] in seen: continue
        seen.add(u["id"]); uniq.append(u)
    by_work = {}
    for u in uniq:
        by_work[u["work"]] = by_work.get(u["work"], 0) + 1
    out = {"_readme": "Canonical DGE text units for audio mapping. text = cleaned Devanagari (HTML/verse numbers/daṇḍas removed); slp1/phonetic_key use the same folds as search_toolkit_pkg so matching agrees with site search. dge_audio_url = the URL the DGE player itself would use for this verse (null when DGE links no audio).",
           "generated_at": now_ist(), "counts": by_work, "units": uniq}
    write_json(DS / "text_index.json", out)
    log(f"texts: {len(uniq)} units across {len(by_work)} works")
    return out


if __name__ == "__main__":
    run()
