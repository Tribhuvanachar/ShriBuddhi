"""DGE Ashtadhyayi importer — Stream 5.

Populates the three still-missing commentary/translation layers of the DGE
Ashtadhyayi reader and enriches the sutrapatha with padaccheda / anvaya /
anuvritti / adhikara / sutra-type / English gloss:

  * Siddhanta-Kaumudi  (siddhanta_kaumudi)   -> grantha_tika_text
  * Mahabhashya         (mahabhashya)         -> grantha_tika_text
  * Vasu English (1891) (vasu)                -> grantha_tika_text, language=en
  * sutrapatha enrichment (in place)

Source: github.com/ashtadhyayi-com/data  (sutraani/*.txt).  That repo has no
formal LICENSE file, but the DGE project lead holds the ashtadhyayi.com
curator's e-mail permission for non-commercial / educational reuse (recorded
in the project notes); this is the same source convention the project's other
Ashtadhyayi layers already use, and it is the only cleanly *sutra-aligned*
machine-readable source for these commentaries (GRETIL / sanskritdocuments
carry them as running text, not keyed per sutra).  Vasu's 1891 translation is
additionally public-domain in its own right.

Run against a local clone:
    python importers/ashtadhyayi_layers.py --local /path/to/ashtadhyayi-com-data
Or let it fetch the raw files from GitHub:
    python importers/ashtadhyayi_layers.py

Writes into data/ (falls back to data/).  Non-destructive: only the four
target files are rewritten.
"""
import os, re, json, argparse, urllib.request

RAW = "https://raw.githubusercontent.com/ashtadhyayi-com/data/master/sutraani/"
FILES = ["data.txt", "kaumudi.txt", "bhashya.txt",
         "vasu_english.txt", "vasu_english_summary.txt", "sutrartha_english.txt"]

# --- id helpers ----------------------------------------------------------
def ash_id(ref):
    """DGE sutrapatha id '1.1.1' -> ashtadhyayi.com id '11001'."""
    a, p, n = ref.split(".")
    return f"{a}{p}{int(n):03d}"

def data_base():
    for c in ("data", "data"):
        if os.path.isdir(c):
            return c
    return "data"

# --- field parsers -------------------------------------------------------
def parse_padaccheda(pc):
    """'वृद्धिः$S$1$1$##आत्-ऐच्$S$1$1$' -> ['वृद्धिः','आत्-ऐच्']."""
    if not pc:
        return []
    out = []
    for tok in pc.split("##"):
        tok = tok.strip()
        if not tok:
            continue
        w = tok.split("$")[0].strip()
        if w:
            out.append(w)
    return out

def parse_anuvritti(an):
    """'वृद्धिः$11001##गुणः$11002' -> [{'word':..,'from':'1.1.1'}, ...]."""
    if not an:
        return []
    out = []
    for tok in an.split("##"):
        tok = tok.strip()
        if not tok:
            continue
        parts = tok.split("$")
        w = parts[0].strip()
        src = parts[1].strip() if len(parts) > 1 else ""
        ref = ""
        if src.isdigit() and len(src) >= 4:
            ref = f"{src[0]}.{src[1]}.{int(src[2:])}"
        if w:
            out.append({"word": w, "from": ref} if ref else {"word": w})
    return out

def parse_adhikara(ad):
    """'आकडारात् एका संज्ञा$1$4$1' -> 'आकडारात् एका संज्ञा' (a bare adhikara
    with no $-suffix, e.g. 'अनभिहिते', passes through unchanged). The
    trailing $adhyaya$pada$sutra is the source's own reference to the
    sutra that first states this adhikara -- same $-delimited convention
    'pc'/'an'/'type' already use -- but this field was being stored
    unparsed, so the literal "$2$3$1" rendered straight into the reader.
    A sutra can sit under more than one adhikara at once, "##"-joined
    ('आकडारात् एका संज्ञा$1$4$1##कारके$1$4$23'); each segment gets the
    same $-suffix stripped, then they're rejoined for display."""
    if not ad:
        return ""
    parts = [tok.split("$")[0].strip() for tok in ad.split("##")]
    return " · ".join(p for p in parts if p)

TYPE_LABELS = {  # ashtadhyayi.com sutra-type code -> (english, devanagari)
    "S":  ("Definition (saṃjñā)", "संज्ञा"),
    "P":  ("Meta-rule (paribhāṣā)", "परिभाषा"),
    "V":  ("Operational rule (vidhi)", "विधि"),
    "N":  ("Restriction (niyama)", "नियम"),
    "A":  ("Governing heading (adhikāra)", "अधिकार"),
    "AD": ("Extension (atideśa)", "अतिदेश"),
    "AT": ("Extension (atideśa)", "अतिदेश"),
    "NI": ("Negation (niṣedha)", "निषेध"),
    "PR": ("Counter-example rule (pratiṣedha)", "प्रतिषेध"),
}
def parse_type(t):
    """'S$वृद्धिसंज्ञा$' -> {'code','label','label_dev','topic'}."""
    if not t:
        return None
    parts = t.split("$")
    code = parts[0].strip().upper()
    topic = parts[1].strip() if len(parts) > 1 else ""
    lab = TYPE_LABELS.get(code)
    d = {"code": code}
    if lab:
        d["label"], d["label_dev"] = lab[0], lab[1]
    if topic:
        d["topic"] = topic
    return d

def clean_html(s):
    """Vasu entries carry light <i>/<br> markup — keep readable text."""
    if not s:
        return ""
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()

# --- source loading ------------------------------------------------------
def load_sources(local):
    src = {}
    for f in FILES:
        if local:
            path = os.path.join(local, "sutraani", f)
            with open(path, encoding="utf-8") as fh:
                src[f] = json.load(fh)
        else:
            req = urllib.request.Request(RAW + f, headers={"User-Agent": "DGE-importer/1.0 (educational)"})
            with urllib.request.urlopen(req, timeout=120) as r:
                src[f] = json.loads(r.read().decode("utf-8", "replace"))
    return src

# --- writers -------------------------------------------------------------
def write_layer(rel, meta, items):
    base = data_base()
    folder = os.path.join(base, rel)
    os.makedirs(folder, exist_ok=True)
    fp = os.path.join(folder, "data.json")
    out = dict(meta)
    out["items"] = items
    json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  wrote {fp}  ({len(items)} items)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="path to a local clone of ashtadhyayi-com/data")
    # The 'english' field (sutrartha_english.txt, verbatim ashtadhyayi.com
    # text) was removed from the published sutrapatha/data.json on 23 Aug
    # 2026 -- it was shown to readers with zero attribution, held only under
    # an informal curator e-mail permission (no formal licence). Off by
    # default so a routine re-run of this importer (e.g. to refresh
    # padaccheda/anvaya/anuvritti/sutra_type from a newer upstream commit)
    # does not silently reintroduce it. See PENDING.md and
    # admin/content/ashtadhyayi-layers.json -- do not pass this flag until
    # real licensing is resolved with ashtadhyayi.com.
    ap.add_argument("--allow-ashtadhyayi-com-english", action="store_true",
                     help="Re-include the sutrartha_english.txt 'english' gloss field. "
                          "Deliberately off by default -- see the comment above this flag.")
    args = ap.parse_args()

    base = data_base()
    sut_fp = os.path.join(base, "vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json")
    sutrapatha = json.load(open(sut_fp, encoding="utf-8"))
    sutras = sutrapatha["items"]
    print(f"sutrapatha: {len(sutras)} sutras (canonical id set)")

    src = load_sources(args.local)
    data_by_id = {e["i"]: e for e in src["data.txt"]["data"]}
    kaumudi = src["kaumudi.txt"]
    bhashya = src["bhashya.txt"]
    vasu    = src["vasu_english.txt"]
    vasu_s  = src["vasu_english_summary.txt"]
    sut_en  = src["sutrartha_english.txt"]

    sk_items, mb_items, vasu_items = [], [], []
    enriched = 0

    for row in sutras:
        ref = row["id"]
        aid = ash_id(ref)
        meta = data_by_id.get(aid)

        # ---- enrich sutrapatha in place ----
        if meta:
            pc = parse_padaccheda(meta.get("pc", ""))
            if pc:
                row["padaccheda"] = pc
            anv = (meta.get("ss") or "").strip()
            if anv:
                row["anvaya"] = anv          # ss = word-order / prose form
            anu = parse_anuvritti(meta.get("an", ""))
            if anu:
                row["anuvritti"] = anu
            ad = parse_adhikara(meta.get("ad") or "")
            if ad:
                row["adhikara"] = ad
            st = parse_type(meta.get("type", ""))
            if st:
                row["sutra_type"] = st
        if args.allow_ashtadhyayi_com_english:
            en = (sut_en.get(aid) or "").strip() or clean_html(vasu_s.get(aid, ""))
            if en:
                row["english"] = en
        elif "english" in row:
            del row["english"]  # a stale field from a pre-23-Aug data.json, not this run's output
        if any(k in row for k in ("padaccheda", "anvaya", "anuvritti", "sutra_type", "english")):
            enriched += 1

        ref_note = [{"note": "comments_on",
                     "target": "vedanga/vyakarana/ashtadhyayi/sutrapatha",
                     "unit_id": ref}]

        # ---- Siddhanta-Kaumudi ----
        sk = (kaumudi.get(aid) or "").strip()
        if sk:
            sk_items.append({"id": ref, "reference": ref, "sanskrit_text": sk,
                             "references": ref_note,
                             "tags": ["ashtadhyayi", "siddhanta_kaumudi", f"adhyaya_{ref.split('.')[0]}"],
                             "author": "Bhaṭṭoji Dīkṣita", "tika_title": "Siddhānta-Kaumudī"})
        # ---- Mahabhashya ----
        mb = (bhashya.get(aid) or "").strip()
        if mb:
            mb_items.append({"id": ref, "reference": ref, "sanskrit_text": mb,
                             "references": ref_note,
                             "tags": ["ashtadhyayi", "mahabhashya", f"adhyaya_{ref.split('.')[0]}"],
                             "author": "Patañjali", "tika_title": "Mahābhāṣya"})
        # ---- Vasu English ----
        ve = clean_html(vasu.get(aid, ""))
        if ve:
            vasu_items.append({"id": ref, "reference": ref, "sanskrit_text": ve,
                               "references": ref_note, "language": "en",
                               "tags": ["ashtadhyayi", "vasu", "english", f"adhyaya_{ref.split('.')[0]}"],
                               "author": "Śrīśa Chandra Vasu", "tika_title": "Vasu — English translation"})

    # write sutrapatha back (enriched)
    fields = ["padaccheda", "anvaya", "anuvritti", "adhikara", "sutra_type"]
    if args.allow_ashtadhyayi_com_english:
        fields.append("english")
    previous = sutrapatha.get("enrichment") or {}
    sutrapatha["enrichment"] = {
        "source": "ashtadhyayi.com sutraani/data.txt + sutrartha_english.txt",
        "fields": fields
    }
    # The id join misaligns ~930 sutras (the source numbers 1.1.17 उञ ऊँ as
    # two); tools/realign_sutra_enrichment.py --apply repairs that by text
    # and records how, and that record must survive a re-import — the sync
    # workflow runs realign right after this script.
    if previous.get("alignment"):
        sutrapatha["enrichment"]["alignment"] = previous["alignment"]
    if not args.allow_ashtadhyayi_com_english:
        # Preserve the 23-Aug removal note across re-runs rather than
        # silently dropping it -- see the --allow-ashtadhyayi-com-english
        # comment above for the full story.
        sutrapatha["enrichment"]["removed_field_note"] = (
            "'english' (verbatim ashtadhyayi.com sutrartha_english.txt) is deliberately "
            "not imported by default -- pass --allow-ashtadhyayi-com-english to this "
            "script to re-include it, only once real licensing is resolved. See "
            "PENDING.md and admin/content/ashtadhyayi-layers.json."
        )
    json.dump(sutrapatha, open(sut_fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  enriched sutrapatha in place  ({enriched}/{len(sutras)} sutras got >=1 new field)")

    lic_ash = ("used with ashtadhyayi.com curator's e-mail permission for "
               "non-commercial/educational use (source repo has no formal LICENSE); "
               "keep visible attribution to ashtadhyayi.com; resolve before public launch")

    # Siddhānta-Kaumudī is NOT written any more: on 29 Aug 2026 that layer was
    # re-sourced to Dhaval Patel's MIT-licensed TEI (github.com/drdhaval2785/
    # siddhantakaumudi) — see the licence_note in
    # data/vedanga/vyakarana/ashtadhyayi/siddhanta_kaumudi/data.json.
    # Rewriting it from kaumudi.txt would be a regression to the superseded
    # source. sk_items is still built so the count below stays comparable.
    # (The paniniya_vyakarana/ folder the earlier version wrote to was folded
    # into ashtadhyayi/ by commit 5bc757783; the paths below are the live ones.)
    write_layer("vedanga/vyakarana/ashtadhyayi/mahabhashya_patanjali",
                {"schema": "grantha_tika_text", "default_author": "Patañjali",
                 "title": "Mahābhāṣya", "title_devanagari": "महाभाष्यम्",
                 "source": "ashtadhyayi.com sutraani/bhashya.txt", "licence": lic_ash},
                mb_items)
    write_layer("vedanga/vyakarana/ashtadhyayi/vasu",
                {"schema": "grantha_tika_text", "default_author": "Śrīśa Chandra Vasu",
                 "title": "Vasu — English translation", "title_devanagari": "Vasu (Eng.)",
                 "language": "en",
                 "source": "S.C. Vasu, The Ashṭādhyāyī of Pāṇini (1891, Pāṇini Office) — public domain; "
                           "digitised text via ashtadhyayi.com sutraani/vasu_english.txt",
                 "licence": "public domain (Vasu 1891); digitisation via ashtadhyayi.com"},
                vasu_items)

    print(f"\nDONE.  SK={len(sk_items)}  Mahabhashya={len(mb_items)}  Vasu={len(vasu_items)}")

if __name__ == "__main__":
    main()
