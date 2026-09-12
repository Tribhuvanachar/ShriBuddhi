"""
DGE — Import Taittiriya Samhita, Brahmana and Aranyaka (Krishna Yajurveda)
===========================================================================
Source: sanskritdocuments.org, transliterated by Muralidhara B A,
acknowledged permission from Professor Anathakrishna. Used with the site
operators' permission.

Conversion approach VERIFIED by prototype before writing this:
  - ITRANS Vedic accent markers (\\` anudatta, \\' svarita, \\" dirgha
    svarita, {\\m+} nasal) are swapped for Private Use Area placeholders,
    transliterated, then replaced with standard core-block Devanagari
    marks (U+0952, U+0951, U+A8F3). Confirmed the placeholders survive
    transliteration intact.
  - Each source file contains the ENTIRE text twice — accented, then
    again unaccented after a "(niHsvaraH)" chapter marker. Only the first
    half is used. Confirmed: exactly 50% of lines kept.
  - TS 1.1.1 verified to render as "इ॒षे त्वो॒र्जे त्वा॑ वा॒यवः॑ स्थ..."

KNOWN LIMITATION, flagged not hidden: dirgha svarita (~4k occurrences in
TS) is mapped to plain svarita. Its dedicated codepoint lives in the
Vedic Extensions block, which is the poorly-supported range that caused
the earlier Rigveda rendering failure. Revisit if a well-supported
representation is agreed.

Usage (Colab):
    !pip install requests indic_transliteration
"""

import json
import re
import shutil
import zipfile
from pathlib import Path

import requests
from indic_transliteration import sanscript

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DGE-importer/1.0)", "Accept": "*/*"}
OUT_DIR = Path("./dge_taittiriya_output")
OUT_ZIP = Path("./dge_taittiriya.zip")
SITE = "https://tribhuvanachar.github.io/bhumandala/dge"

SOURCES = {
    "samhita": "https://sanskritdocuments.org/doc_veda/taittirIyasamhitA.itx",
    "brahmana": "https://sanskritdocuments.org/doc_veda/taittirIyabrAhmaNam.itx",
    "aranyaka": "https://sanskritdocuments.org/doc_veda/taittirIyaAraNyaka.itx",
}

SOURCE_NOTE = ("Taittiriya (Krishna Yajurveda), transliterated by Muralidhara B A, "
               "permission acknowledged to Professor Anathakrishna; via "
               "sanskritdocuments.org, used with permission.")

PUA = {"anudatta": "\ue000", "svarita": "\ue001",
       "dirgha_svarita": "\ue002", "nasal_m": "\ue003"}
FINAL = {PUA["anudatta"]: "\u0952", PUA["svarita"]: "\u0951",
         PUA["dirgha_svarita"]: "\u0951", PUA["nasal_m"]: "\ua8f3"}

DEVA_DIGITS = {'0': '०', '1': '१', '2': '२', '3': '३', '4': '४',
               '5': '५', '6': '६', '7': '७', '8': '८', '9': '९'}


def deva(n):
    return ''.join(DEVA_DIGITS[c] for c in str(n))


def convert(itrans):
    t = itrans
    t = t.replace("{\\m+}", PUA["nasal_m"])
    t = t.replace('\\"', PUA["dirgha_svarita"])
    t = t.replace("\\`", PUA["anudatta"])
    t = t.replace("\\'", PUA["svarita"])
    t = t.replace("\\-", "")
    t = re.sub(r"o\((\d)\)m", r"ओ\1म्", t)
    out = sanscript.transliterate(t, sanscript.ITRANS, sanscript.DEVANAGARI)
    for ph, real in FINAL.items():
        out = out.replace(ph, real)
    return re.sub(r"[ \t]+", " ", out).strip()


def strip_nihsvara(text):
    m = re.search(r"\\chapter\{[^}]*niHsvaraH", text)
    return text[:m.start()] if m else text


def parse(text):
    """
    Returns [(kanda_index, kanda_label, prashna_label, ref, itrans_body)].

    Invocation lines ("|| shrI gurubhyo namaH ||") appear before the first
    numbered anuvaka of each chapter. The prototype merged them into that
    anuvaka; here the buffer is reset whenever a new numbered unit starts,
    so invocations are dropped rather than silently prefixed to real text.
    """
    text = strip_nihsvara(text)
    kanda_i, kanda, prashna = 0, None, None
    buf, results = [], []

    for line in text.splitlines():
        s = line.strip()
        ch = re.match(r"\\chapter\{(.*)\}", s)
        if ch:
            kanda_i += 1
            kanda = ch.group(1).strip().strip("|").strip()
            prashna, buf = None, []
            continue
        sec = re.match(r"\\section\{(.*)\}", s)
        if sec:
            prashna = sec.group(1).strip()
            buf = []
            continue
        if s.startswith("\\") or s.startswith("%") or s.startswith("#") or not s:
            continue
        # A new numbered unit begins: anything buffered before it that never
        # closed with a reference was an invocation/heading, not content.
        if re.match(r"^\d+\s", s) and not buf:
            buf = [s]
        elif re.match(r"^\d+\s", s) and buf:
            buf = [s]
        else:
            buf.append(s)
        end = re.search(r"\|\|\s*([\d\|\s]+?)\s*\|\|\s*$", s)
        if end and buf:
            ref = re.sub(r"\s+", "", end.group(1)).strip("|").replace("|", ".")
            body = " ".join(buf)
            body = re.sub(r"\|\|\s*[\d\|\s]+\s*\|\|\s*$", "", body).strip()
            body = re.sub(r"^\d+\s+", "", body)
            if body:
                results.append((kanda_i, kanda, prashna, ref, body))
            buf = []
    return results


def write_grantha(rel_path, title, items):
    d = OUT_DIR / "data" / rel_path
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "vedic_text",
        "default_author": "Apaurusheya (Krishna Yajurveda, Taittiriya Shakha)",
        "source": SOURCE_NOTE,
        "items": items,
    }
    with open(d / "data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  wrote {rel_path}/data.json ({len(items):,} items)")
    return "data/" + rel_path + "/data.json"


def make_items(units):
    out = []
    for _, kanda, prashna, ref, body in units:
        out.append({
            "id": ref,
            "samhita_patha": convert(body),
            "pada_patha": "",
            "rishi": "",
            "devata": "",
            "chandas": "",
            "section": convert(prashna) if prashna else "",
            "section_roman": prashna or "",
            "translation": [],
            "commentaries": {},
            "audio": [],
            "references": [],
            "tags": [],
        })
    return out


def main():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    populated = []

    for kind, url in SOURCES.items():
        print(f"\n{kind.upper()}")
        print(f"  fetching {url}")
        r = requests.get(url, timeout=240, headers=HEADERS)
        r.raise_for_status()
        text = r.content.decode("utf-8", errors="replace")
        units = parse(text)
        print(f"  parsed {len(units):,} units")

        if kind == "samhita":
            by_kanda = {}
            for u in units:
                by_kanda.setdefault(u[0], []).append(u)
            for k in sorted(by_kanda):
                if k > 7:
                    print(f"  (skipping unexpected chapter {k})")
                    continue
                title = f"तैत्तिरीयसंहिता काण्डम् {deva(k)}"
                path = write_grantha(
                    f"vedas/yajurveda/krishna_yajurveda/taittiriya_shakha/samhita/kanda_{k:02d}",
                    title, make_items(by_kanda[k]))
                populated.append((path, title))
        elif kind == "brahmana":
            title = "तैत्तिरीयब्राह्मणम्"
            path = write_grantha(
                "vedas/yajurveda/krishna_yajurveda/taittiriya_shakha/brahmana/taittiriya_brahmana",
                title, make_items(units))
            populated.append((path, title))
        else:
            title = "तैत्तिरीयारण्यकम्"
            path = write_grantha(
                "vedas/yajurveda/krishna_yajurveda/taittiriya_shakha/aranyaka/taittiriya_aranyaka",
                title, make_items(units))
            populated.append((path, title))

    print("\nUpdating library.json ...")
    lib = requests.get(f"{SITE}/data/library.json", timeout=120, headers=HEADERS).json()
    index = {g["path"]: g for g in lib["granthas"]}
    added = updated = 0
    for path, title in populated:
        if path in index:
            index[path]["populated"] = True
            index[path]["title"] = title
            updated += 1
        else:
            lib["granthas"].append({"path": path, "title": title, "populated": True})
            added += 1
    print(f"  {updated} updated, {added} added")
    d = OUT_DIR / "data"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "library.json", "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=2)

    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in OUT_DIR.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(OUT_DIR))

    print("\n" + "=" * 60)
    print(f"Wrote {OUT_ZIP} ({OUT_ZIP.stat().st_size:,} bytes)")
    print("SPOT CHECK — first item of Taittiriya Samhita kanda 1:")
    first = json.loads((OUT_DIR / "data/vedas/yajurveda/krishna_yajurveda/"
                        "taittiriya_shakha/samhita/kanda_01/data.json").read_text(encoding="utf-8"))
    it = first["items"][0]
    print(f"  id  : {it['id']}")
    print(f"  text: {it['samhita_patha'][:150]}")
    print("  (should start इ॒षे त्वो॒र्जे त्वा॑ ... with NO invocation prefix)")
    print("=" * 60)


if __name__ == "__main__":
    main()
