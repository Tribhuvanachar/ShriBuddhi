#!/usr/bin/env python3
"""Import Śrī Viṣṇu Sahasranāma Stotram (Mahābhārata, Anuśāsana Parva 149) from sanskritdocuments.org
into the SarvaMūla library as a mūla grantha:

    dge/data/darshana/vedanta/dvaita/Anandamakaranda/stotra/vishnu_sahasranama/mula/data.json

Usage:  python3 tools/vishnu_sahasranama/build_vsn.py [--html cached.html]
Fetches https://sanskritdocuments.org/doc_vishhnu/vsahasranew.html (or reads --html), splits the text into
its traditional sections, one item per śloka (prose nyāsa/saṅkalpa blocks as their own items), keeps the
edition's parenthesised variant readings in `variants`, and registers the grantha in library.json /
taxonomy.json (idempotent — safe to re-run)."""
import html, json, os, re, subprocess, sys, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = "https://sanskritdocuments.org/doc_vishhnu/vsahasranew.html"
OUT_DIR = ROOT / "dge/data/darshana/vedanta/dvaita/Anandamakaranda/stotra/vishnu_sahasranama"
DEV = {ord(c): str(i) for i, c in enumerate("०१२३४५६७८९")}

SECTIONS = [  # (start-line predicate, section id, Devanagari heading, item prefix)
    ("purva_pithika", "पूर्वपीठिका", "PP"),
    ("purva_nyasa", "पूर्वन्यासः", "PN"),
    ("sankalpa", "सङ्कल्पः", "SK"),
    ("dhyanam", "ध्यानम्", "DH"),
    ("stotram", "स्तोत्रम्", "ST"),
    ("phalashruti", "उत्तरन्यासः, फलश्रुतिः", "PH"),
    ("uttara_pithika", "उत्तरपीठिका", "UP"),
]


def fetch(cache):
    if cache and Path(cache).exists():
        return Path(cache).read_text(encoding="utf-8", errors="ignore")
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "60", URL], capture_output=True, text=True, errors="ignore")
    if r.returncode or "सहस्रनाम" not in r.stdout:
        sys.exit("fetch failed: " + r.stderr[-300:])
    return r.stdout


def lines_of(page):
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    txt = html.unescape(re.sub(r"<[^>]+>", "\n", body))
    out = [re.sub(r"[ \t]+", " ", l).strip() for l in txt.split("\n")]
    return [l for l in out if l and re.search(r"[ऀ-ॿ]", l)]


def split_variants(line):
    """'... ॥ ५४॥ विनियोज्यः' / '(विरामो विरतो)' → (clean line, [variants])."""
    vars_ = []
    def grab(m):
        vars_.append(m.group(1).strip()); return ""
    line = re.sub(r"\(([^()]*)\)", grab, line)
    # trailing bare variant after the verse number, e.g. '॥ ५४॥ विनियोज्यः'
    m = re.search(r"(॥\s*[०-९]+\s*॥)\s+(\S.*)$", line)
    if m:
        vars_.append(m.group(2).strip()); line = line[: m.end(1)]
    return re.sub(r"\s+", " ", line).strip(), vars_


def verse_no(line):
    m = re.search(r"॥\s*([०-९]+)\s*॥\s*$", line)
    return int(m.group(1).translate(DEV)) if m else None


def build(lines):
    # locate section starts by the edition's own headings
    idx = {}
    for i, l in enumerate(lines):
        if l == "पूर्वन्यासः": idx["purva_nyasa"] = i
        elif l.startswith("श्रीकृष्णप्रीत्यर्थे"): idx["sankalpa"] = i
        elif l.startswith("क्षीरोदन्वत्प्रदेशे"): idx["dhyanam"] = i
        elif l == "स्तोत्रम्": idx["stotram"] = i
        elif l.startswith("उत्तरन्यासः"): idx["phalashruti"] = i
        elif l.startswith("महाभारते अनुशासनपर्वणि"): idx["uttara_pithika"] = i
    # drop the two title lines + lone ॐ at top
    start = next(i for i, l in enumerate(lines) if l.startswith("श्रीपरमात्मने"))
    idx["purva_pithika"] = start
    order = sorted(idx.items(), key=lambda kv: kv[1])
    items = []
    for n, (sec, s) in enumerate(order):
        e = order[n + 1][1] if n + 1 < len(order) else len(lines)
        seg = lines[s:e]
        heading = {sid: h for sid, h, _ in SECTIONS}[sec]; prefix = {sid: p for sid, _, p in SECTIONS}[sec]
        if seg and (seg[0] == heading or seg[0].startswith("उत्तरन्यासः") or seg[0].startswith("महाभारते अनुशासन")):
            note_line = seg[0] if seg[0].startswith("महाभारते") else ""
            seg = seg[1:]
        else:
            note_line = ""
        speaker = ""; speaker_pending = False; buf = []; vars_ = []; k = 0; paren = False; kc = {"verse": 0, "prose": 0, "mantra": 0, "colophon": 0}
        def flush(kind="verse", num=None, with_speaker=True):
            nonlocal buf, vars_, k, speaker, paren, speaker_pending
            if not buf: return
            k += 1; kc[kind] += 1
            text = "\n".join(buf)
            if speaker and with_speaker and speaker_pending:
                text = speaker + "\n" + text; speaker_pending = False   # speaker line printed once, on the first item it governs (as in the Gītā data)
            tags = {"verse": ["verse", "stotra"], "prose": ["prose", "stotra"], "mantra": ["mantra"], "colophon": ["colophon"]}[kind]
            if sec == "stotram" and kind == "verse": tags.append("mantra")
            note = "edition prints this in parentheses (optional / variant verse)" if paren else ""
            tag = ("V" if num is not None else "X") if kind == "verse" else kind[0].upper()   # V = numbered verse, X = unnumbered verse, M/P/C = mantra/prose/colophon
            items.append({"id": f"VSN_{prefix}_{tag}{(num if tag == 'V' else kc[kind]):03d}", "reference": f"{heading} · {num if num is not None else k}",
                          "sanskrit_text": text, "tags": tags, "notes": note, "references": [], "audio": [], "variants": vars_, "category": heading, "section": sec,
                          "kind": kind, "verse_no": num, "speaker": (speaker.strip() or None) if with_speaker else None, "parenthesised": paren,
                          "breadcrumb": ["श्रीविष्णुसहस्रनामस्तोत्रम्", heading, str(num if num is not None else k)],
                          "source": {"site": "sanskritdocuments.org", "url": URL, "section": sec, "verse": num}})
            buf = []; vars_ = []; paren = False
        colo = []
        for l in seg:
            if colo:                                   # continuation of a multi-line colophon
                colo.append(l)
                if re.search(r"[।॥]\s*$", l):
                    buf = [" ".join(colo)]; colo = []; flush("colophon", with_speaker=False)
                continue
            if re.search(r"उवाच\s*-*\s*$", l):
                flush(); speaker = re.sub(r"\s*-+\s*$", "", l); speaker_pending = True; continue
            if l.startswith("ॐ तत्सदिति") or l.startswith("इति श्री") or l.startswith("इति षडङ्ग"):
                flush()
                if re.search(r"[।॥]\s*$", l):
                    buf = [l]; flush("colophon", with_speaker=False)
                else:
                    colo = [l]
                continue
            if re.search(r"ॐ नम इति\s*[।॥]?\s*$", l) or re.fullmatch(r"(हरिः\s*)?ॐ(\s+(नमो|नमः|नम|तत्\s*सत्)[^।॥]{0,40})?\s*[।॥]+", l) or l in ("ॐ", "हरिः ॐ"):
                flush(); buf = [l]; flush("mantra", with_speaker=False); continue
            if l.startswith("(") and l.count("(") > l.count(")"):
                flush(); paren = True; l = l[1:].strip()
            if l.endswith(")") and l.count(")") > l.count("("):
                l = l[:-1].strip()
            clean, v = split_variants(l); vars_ += v
            if not clean:
                continue
            if sec in ("purva_nyasa", "sankalpa"):
                # prose blocks: paragraph = run of lines until a line ending in ॥
                buf.append(clean)
                if clean.endswith("॥"): flush("prose")
                continue
            buf.append(clean)
            num = verse_no(clean)
            if num is not None or (clean.endswith("॥") and sec in ("uttara_pithika", "purva_pithika") and len(buf) >= 2):
                flush("verse", num)
            elif clean.endswith("॥") and len(buf) >= 2 and sec not in ("dhyanam",):
                flush("verse", None)
            elif sec == "dhyanam" and clean.endswith("॥") and len(buf) >= 2:
                flush("verse", None)
        flush()
        if note_line and items:
            items[-1]["notes"] = (items[-1]["notes"] + " " + note_line).strip()
    # de-speaker the same speaker on consecutive items is fine (kept on each item, like the Gītā)
    return items


def register(item_count):
    lib_p = ROOT / "dge/data/library.json"; tax_p = ROOT / "dge/data/taxonomy.json"
    lib = json.loads(lib_p.read_text(encoding="utf-8")); tax = json.loads(tax_p.read_text(encoding="utf-8"))
    path = "dge/data/darshana/vedanta/dvaita/Anandamakaranda/stotra/vishnu_sahasranama/mula/data.json"
    entry = {"path": path, "populated": True, "title": "श्रीविष्णुसहस्रनामस्तोत्रम् (Viṣṇu Sahasranāma Stotra) — मूलम्",
             "addedAt": datetime.date.today().isoformat(),
             "source": {"source": "Sanskrit Documents (sanskritdocuments.org), Devanāgarī edition 'vsahasranew' with pūrva/uttara-pīṭhikā, nyāsa, dhyāna and phalaśruti",
                        "source_url": URL, "licence": "sanskritdocuments.org standard usage terms (free non-commercial use, source credited); the text itself is Mahābhārata, public domain"},
             "facets": {"default_author": "Maharshi Veda Vyasa (Mahābhārata, Anuśāsana Parva 149)", "deity": "Viṣṇu", "genre": "stotra"}}
    gs = lib["granthas"]
    for i, g in enumerate(gs):
        if g["path"] == path:
            gs[i] = entry; break
    else:
        # insert right after the last SarvaMula kavya entry so it sits with its neighbours
        pos = max((i for i, g in enumerate(gs) if "/SarvaMula/kavya/" in g["path"]), default=len(gs) - 1) + 1
        gs.insert(pos, entry)
    lib_p.write_text(json.dumps(lib, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sm = tax["darshana"]["vedanta"]["dvaita"]["SarvaMula"]
    sm.setdefault("stotra", {"_schema": "grantha_mula_text", "_readme": "Stotras kept under SarvaMūla for the Mādhva pārāyaṇa corpus (alongside dvadasha_stotra); the flat top-level 'stotra' node stays the home for other stotras."})
    sm["stotra"].setdefault("vishnu_sahasranama", {})["mula"] = {"_schema": "grantha_mula_text", "_default_author": "Maharshi Veda Vyasa (Mahābhārata, Anuśāsana Parva 149)"}
    tax_p.write_text(json.dumps(tax, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for d, desc in ((OUT_DIR.parent, "SarvaMūla stotra granthas (Viṣṇu Sahasranāma etc.) — pārāyaṇa texts kept with the Mādhva corpus"),
                    (OUT_DIR, "श्रीविष्णुसहस्रनामस्तोत्रम् — Viṣṇu Sahasranāma Stotra (Mahābhārata, Anuśāsana Parva 149)")):
        mp = d / "_meta.json"
        if not mp.exists():
            mp.write_text(json.dumps({"directory": d.name, "description": desc, "schema": "grantha_mula_text"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    cache = sys.argv[sys.argv.index("--html") + 1] if "--html" in sys.argv else None
    lines = lines_of(fetch(cache))
    items = build(lines)
    from collections import Counter
    c = Counter(i["section"] for i in items)
    data = {"schema": "grantha_mula_text", "default_author": "Maharshi Veda Vyasa (Mahābhārata, Anuśāsana Parva 149)",
            "title": "श्रीविष्णुसहस्रनामस्तोत्रम्", "source": "Sanskrit Documents (sanskritdocuments.org)", "source_url": URL,
            "licence": "sanskritdocuments.org standard usage terms (free non-commercial use, source credited); text is public domain (Mahābhārata)",
            "source_note": "Edition 'vsahasranew' (Devanāgarī). Sections follow the edition: pūrva-pīṭhikā (22), pūrva-nyāsa, saṅkalpa, dhyānam (7), stotram (108), uttara-nyāsa/phalaśruti (33), uttara-pīṭhikā. Parenthesised alternative readings of the edition are kept per item in `variants`. Speaker lines (… उवाच) are kept as the first line of the item, as in the Gītā data.",
            "availableCommentaries": {}, "sections": [{"id": s, "title": h, "items": c.get(s, 0)} for s, h, _ in SECTIONS], "items": items}
    OUT_DIR.joinpath("mula").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "mula/data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    register(len(items))
    print(f"wrote {len(items)} items: {dict(c)} → {OUT_DIR.relative_to(ROOT)}/mula/data.json")


if __name__ == "__main__":
    main()
