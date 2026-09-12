#!/usr/bin/env python3
"""Build the self-contained Gemini *phone* pack: one folder of paste-ready prompt files + a README, zipped.

    python3 tools/gemini_phone_pack.py [--out /path/gemini_phone_pack.zip] [--chandas-batch 25] [--verse-batch 20]

Each prompt file is complete on its own (rules + data + the exact reply shape), sized for pasting into the Gemini
Android app; nothing refers to GitHub. Every reply carries a `pack` tag so the answer can be routed back to
tools/chandas/apply_gemini_chandas.py (Chandas) or tools/saroddhara/apply_chat_answers.py (Sāroddhāra).
Covers: Chandas Part A (example verses for every vṛtta without one), Part B (table corrections), Part C (verdicts on
every unresolved verse), Part D (missing metres); Sāroddhāra critical items and word-diff batches."""
import argparse, io, json, sys, zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "chandas"))
from build_gemini_task import load, vrutta_rows, unresolved  # noqa: E402
VI = ROOT / "dge/data/ocr_staging/bhagavata_saroddhara/verify_input"

RULES = """SCAN NOTATION: L = laghu, G = guru, one letter per akṣara, one string per pāda. Guru = long vowel, or a vowel
followed by anusvāra / visarga / candrabindu / jihvāmūlīya / upadhmānīya, or followed by a conjunct; the last akṣara of
a pāda is anceps. Gaṇa letters: य=LGG म=GGG त=GGL र=GLG ज=LGL भ=GLL न=LLL स=LLG ल=L ग=G.
Devanagari only. Split verses into pādas with a newline (four pādas). No dandas, verse numbers or speaker lines.
Cite sources as 'work chapter.verse' (Sumadhva Vijaya 7.10, Bhāgavata 4.9.6, Kumārasambhava 1.1, Vṛttaratnākara 3.30).
Answer null rather than invent anything — every example is re-scanned by a machine before it is used."""

REPLY = "REPLY WITH JSON ONLY — no prose, no code fences. Start your reply with {{ and end with }}. Shape:\n"


def chandas_header(part, pack, task):
    return (f"You are helping a Sanskrit digital library finish its classical-metre (vṛtta) identifier. This message is\n"
            f"self-contained. Task tag: {pack}.\n\n{RULES}\n\nTASK: {task}\n\n")


def part_a(rows, have, per):
    need = [r for r in rows if r["id"] not in have]
    files = []
    for i in range(0, len(need), per):
        chunk = need[i:i + per]; k = i // per + 1; pack = f"CH-A-{k:02d}"
        body = chandas_header("A", pack,
            "For EACH vṛtta below give ONE genuine verse (four pādas) actually composed in that metre, with its source. "
            "A lakṣaṇa verse from Vṛttaratnākara / Chandomañjarī / Śrutabodha written in the metre it defines is fine "
            "(kind = 'lakshana_verse'). Prefer Mādhva works, then Bhāgavata, Kālidāsa, Bhartṛhari, Māgha, Bhāravi. "
            "Scan your own example; if the scan does not match the pattern given, or you know no real verse, put null.")
        body += "VṚTTAS (id | type | gaṇa | L/G pattern per pāda | akṣaras | yati):\n"
        for r in chunk:
            pat = r["padas"][0] if r["type"] == "sama" else " / ".join(r["padas"])
            ak = r["aksharas"][0] if r["type"] == "sama" else "/".join(map(str, r["aksharas"]))
            yati = ",".join(map(str, r["yati"])) if r["type"] == "sama" and r["yati"] else "-"
            body += f"- {r['id']} | {r['type']} | {r['gana']} | {pat} | {ak} | yati {yati}\n"
        body += ("\n" + REPLY + '{"schema": "dge_chandas_gemini_v1", "part": "A", "pack": "' + pack + '", "items": [\n'
                 '  {"vrutta": "<id exactly as above>", "example": {"text": "pāda1\\npāda2\\npāda3\\npāda4", "source": "work chapter.verse", '
                 '"kind": "verse" | "lakshana_verse", "scan": ["L/G pāda1", "…", "…", "…"]} | null, "confidence": 0.0-1.0}\n]}\n'
                 f"Include one object for every one of the {len(chunk)} vṛttas listed.")
        files.append((f"chandas/A_examples_{k:02d}_of_{-(-len(need) // per):02d}.txt", body))
    return files


def part_b(rows):
    pack = "CH-B-01"
    body = chandas_header("B", pack,
        "Check this metre table against Vṛttaratnākara (Kedārabhaṭṭa), Chandomañjarī, Śrutabodha and Piṅgala with commentary. "
        "Report ONLY real disagreements: wrong L/G pattern, wrong akṣara count, wrong or missing yati, wrong/missing name, "
        "two names that are one metre, one name covering two. Specific questions: "
        "(1) the 14 indravajrā/upendravajrā upajāti names — our order is prastāra order (first pāda changes fastest, I before U): "
        "UIII कीर्ति, IUII वाणी, UUII माला, IIUI शाला, UIUI हंसी, IUUI जाया, UUUI माया, IIIU बाला, UIIU आर्द्रा, IUIU भद्रा, UUIU प्रेमा, "
        "IIUU रामा, UIUU ऋद्धि, IUUU बुद्धि; confirm each from the Vṛttaratnākara commentary, especially ऋद्धि and whether जाया/माया "
        "are the right way round. (2) Correct yati for ऋषभगजविलसित and मणिमाला (our yati numbers do not add up to the pāda length). "
        "(3) Any sama vṛtta whose L/G string you know to be wrong.")
    body += "TABLE (id | other names | type | gaṇa | L/G | akṣaras | yati):\n"
    for r in rows:
        pat = r["padas"][0] if r["type"] == "sama" else " / ".join(r["padas"])
        ak = r["aksharas"][0] if r["type"] == "sama" else "/".join(map(str, r["aksharas"]))
        yati = ",".join(map(str, r["yati"])) if r["type"] == "sama" and r["yati"] else "-"
        alt = ", ".join(r["names"][1:]) or "-"
        body += f"- {r['id']} | {alt} | {r['type']} | {r['gana']} | {pat} | {ak} | {yati}\n"
    body += ("\n" + REPLY + '{"schema": "dge_chandas_gemini_v1", "part": "B", "pack": "' + pack + '", "items": [\n'
             '  {"vrutta": "<id>", "field": "lakshana" | "yati" | "name" | "akshara_sankhya" | "merge" | "split", "current": "<what the table says>", '
             '"proposed": "<correct value>", "authority": "text chapter.verse", "note": "", "confidence": 0.0-1.0}\n]}\n'
             "If the table is right on a point you checked, do not list it. An empty items list is a valid answer.")
    return [("chandas/B_table_corrections.txt", body)]


def part_c(unres, per):
    files = []
    for i in range(0, len(unres), per):
        chunk = unres[i:i + per]; k = i // per + 1; pack = f"CH-C-{k:02d}"
        body = chandas_header("C", pack,
            "Each verse below comes from our corpus (Bhagavad Gītā, Sumadhva Vijaya, Rāghavendra Vijaya, Tīrthaprabandha, Dvādaśa Stotra, "
            "Viṣṇu Sahasranāma…) and our engine could not name its metre. 'scan' is OUR L/G scan (pādas separated by |) and may be wrong "
            "because the text is wrong. For each verse decide: verdict 'metre' (metrically fine; give chandas, and scan if ours is wrong), "
            "'text_defect' (typo / missing or extra akṣara / wrong line split; give the full corrected verse in four pādas and the chandas), "
            "'matra' (āryā-family mātrā metre; give name and mātrās per pāda), 'prose' (colophon, gadya, mantra), or 'unsure'.")
        body += "VERSES:\n"
        for u in chunk:
            body += f"- id {u['id']} ({u['work']})\n  text: {u['text'].replace(chr(10), ' / ')}\n  scan: {u['scan']}  syllables {u['syllables']}\n"
        body += ("\n" + REPLY + '{"schema": "dge_chandas_gemini_v1", "part": "C", "pack": "' + pack + '", "items": [\n'
                 '  {"id": "<id>", "verdict": "metre" | "text_defect" | "matra" | "prose" | "unsure", "chandas": "<Devanagari name or null>", '
                 '"corrected_text": "<full verse, pādas separated by \\n, or null>", "scan": ["…"] | null, "note": "<one line>", "confidence": 0.0-1.0}\n]}\n'
                 f"One object for each of the {len(chunk)} ids.")
        files.append((f"chandas/C_unresolved_{k:02d}_of_{-(-len(unres) // per):02d}.txt", body))
    return files


def part_d():
    pack = "CH-D-01"
    body = chandas_header("D", pack,
        "List classical metres used in Mādhva kāvya and stotra literature (Sumadhva Vijaya, Rāghavendra Vijaya, Madhva's Dvādaśa Stotra "
        "and other stotras, Vādirāja, Vyāsatīrtha, Jagannāthadāsa's Sanskrit works) or in the standard prosody manuals that are NOT in the "
        "245-vṛtta table you were shown in task CH-B-01 (if you have not seen it, list the metres you consider most likely to be missing from a "
        "Chandojñānam-derived table: rare sama vṛttas, ardhasama and viṣama metres, and the mātrā metres beyond āryā/gīti/upagīti/vaitālīya). "
        "Each with lakṣaṇa, gaṇa, akṣara count, yati, an authority, and one genuine example verse. Do not list a metre you are unsure exists.")
    body += ("\n" + REPLY + '{"schema": "dge_chandas_gemini_v1", "part": "D", "pack": "' + pack + '", "items": [\n'
             '  {"vrutta": "<Devanagari name>", "type": "sama" | "ardhasama" | "vishama" | "matra", "gana": "…", "padas": ["L/G pāda1", "…"], '
             '"aksharas": [n, n, n, n], "yati": [..], "authority": "text chapter.verse", "example": {"text": "…", "source": "…", "scan": ["…"]}, "confidence": 0.0-1.0}\n]}')
    return [("chandas/D_missing_metres.txt", body)]


def saroddhara_files():
    files = []
    crit = json.load(open(VI / "batch_01_critical.json", encoding="utf-8"))
    head = ("You are helping verify the OCR of a printed Sanskrit book, the Bhāgavata Sāroddhāra (Viṣṇutīrtha's selection of Bhāgavata verses "
            "with his commentary). This message is self-contained. Task tag: {pack}.\n\n"
            "POLICY: the library's Madhva Bhāgavata text ('dge') is the master copy. decision 'dge' = the print shows the same verse, differences "
            "are OCR noise (or a variant you name in the note — it becomes a footnote). decision 'printed' = the print genuinely differs; give the exact "
            "printed text. decision 'vision' = the Vision OCR is right as it stands. 'unsure' = cannot decide. For a missing verse give the full verse "
            "(no number), the Bhāgavata reference as skandha.adhyaya.verse in the book's own numbering, and the PDF page. Devanagari only. "
            "Do not type a verse from memory — copy it from the OCR fields or say which OCR line it is.\n\n")
    slim = lambda it: {k: v for k, v in it.items() if k not in ("current_text", "dge_similarity")}   # noqa: E731
    items = [slim(i) for i in crit["items"]]
    pack = "BS-CRIT-01"
    body = head.format(pack=pack) + "ITEMS:\n" + json.dumps(items, ensure_ascii=False, indent=0)
    body += ("\n\n" + REPLY + '{"pack": "' + pack + '", "items": [ {"id": "BS_V042", "decision": "dge" | "printed" | "vision" | "unsure", '
             '"verified_text": "… or null", "bhagavata_ref": "s.a.v or null", "pdf_page": 128, "note": "one line"} ]}\n'
             f"One object per id ({len(items)} ids). If a neighbouring verse's current_text is really this verse, add an object for that id too.")
    files.append(("saroddhara/CRIT_01_missing_mismatch_near.txt", body))
    for f in sorted(VI.glob("diffs_batch_*.json")):
        d = json.load(open(f, encoding="utf-8")); k = f.stem.split("_")[-1]; pack = f"BS-DIFF-{k}"
        body = head.format(pack=pack) + ("These are single WORD differences between the print (Vision OCR) and the master text, with two words of context "
            "(the differing stretch is inside 【】; null = that side has nothing there). Numbers like '१२४' or '७/१६' in the print are verse numbers "
            "the OCR swept in → 'dge'. A null print word means the OCR dropped that stretch → 'dge'. Only a genuinely different word needs thought: "
            "if the print's reading is a real variant, answer 'dge' and name the reading in the note (it becomes a footnote); answer 'printed' only if "
            "the master is wrong.\n\nITEMS:\n") + json.dumps(d["items"], ensure_ascii=False, indent=0)
        body += ("\n\n" + REPLY + '{"pack": "' + pack + '", "items": [ {"id": "BS_V014", "decision": "dge" | "printed" | "unsure", '
                 '"verified_text": "full verse only when printed, else null", "note": "one line"} ]}\n'
                 f"One object per id ({len({i['id'] for i in d['items']})} distinct ids).")
        files.append((f"saroddhara/DIFF_{k}_word_differences.txt", body))
    return files


README = """GEMINI PHONE PACK — Sarvamūla Digital Library            built {now}

WHAT THIS IS
  A folder of text files. Each file is ONE complete message for the Gemini app on your phone.
  Nothing else is needed: no links, no GitHub, no other files.

HOW TO USE (repeat per file)
  1. Open a file, select all, copy.
  2. In the Gemini app start a NEW chat, paste, send.
     (If the app lets you attach a file, attaching the .txt works too; then type: "Do the task in the attached file.")
  3. Gemini replies with a block of JSON. Copy the WHOLE reply.
  4. Paste it to Claude Code (this chat) with one line saying which file it answers, e.g.
        answer for chandas/A_examples_03_of_08.txt
     Claude checks every answer against the engine / the master text before anything is stored; nothing Gemini says
     is written into the library unverified. Wrong or invented answers are simply held back.
  5. If Gemini stops early or says it cannot finish, reply "continue from where you stopped, JSON only" in the same chat.

ORDER (do what you have time for; every file stands alone)
  chandas/B_table_corrections.txt        one file   — checks the 245-metre table
  chandas/A_examples_NN_of_MM.txt        {na} files  — one real example verse per metre that has none
  chandas/C_unresolved_NN_of_MM.txt      {nc} files  — verdict on every verse the engine could not name
  chandas/D_missing_metres.txt           one file   — metres we do not have at all
  saroddhara/CRIT_01_missing_mismatch_near.txt   one file — the last missing / mismatched / near-match verses
  saroddhara/DIFF_NN_word_differences.txt        {nd} files — single-word print-vs-master differences

WHAT "CLOSED" MEANS
  Chandas: every one of the 245 metres has a verified example verse in the test suite, the table has no known error,
           and every corpus verse is either named, marked as a text defect with a fix, or marked prose.
  Sāroddhāra: every verse carries exactly the master Bhāgavata text (or a confirmed printed variant recorded on both sides),
           and every word difference has a decision.

TIPS
  • One file per chat. Long files may need the "continue" nudge once.
  • Gemini likes to quote verses from memory. The pack tells it not to; when it does anyway, the check on this side catches it.
  • You can send answers in any order and any time; nothing expires.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path("/tmp") / "gemini_phone_pack.zip"))
    ap.add_argument("--chandas-batch", type=int, default=25)
    ap.add_argument("--verse-batch", type=int, default=20)
    a = ap.parse_args()
    db, idx, fx = load(); rows = vrutta_rows(db); have = {e["vrutta"] for e in fx.get("examples", [])}
    files = part_b(rows) + part_a(rows, have, a.chandas_batch) + part_c(unresolved(idx), a.verse_batch) + part_d() + saroddhara_files()
    na = sum(1 for f, _ in files if "/A_" in f); nc = sum(1 for f, _ in files if "/C_" in f); nd = sum(1 for f, _ in files if "/DIFF_" in f)
    now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")
    files.insert(0, ("README.txt", README.format(now=now, na=na, nc=nc, nd=nd)))
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in files:
            z.writestr("gemini_phone_pack/" + name, body)
    sizes = sorted(((len(b.encode()), n) for n, b in files), reverse=True)
    print(f"{out}: {len(files)} files, largest {sizes[0][0] // 1024} KB ({sizes[0][1]}), total {sum(s for s, _ in sizes) // 1024} KB")


if __name__ == "__main__":
    main()
