"""Phase 3 of the vishvasa/ramanujiyam import: everything Phase 1/2 held
back purely on author-date/copyright grounds.
   -> darshana/vedanta/vishishtadvaita/<author>/<work>/{bhashya,mula}

The project lead explicitly authorized this (24 Aug): stop gating on
authors' dates or timelines, import all of it, and he will pursue licensing
directly with authors/rightsholders afterward where needed. That removes
the copyright gate Phase 1/2 applied -- it does NOT remove the content-
quality bar those phases also applied. Every work below was still checked
directly against the fetched source and is genuine, readable Sanskrit
prose or verse correctly separated from non-Sanskrit material (English
translations/apparatus, Tamil, raw OCR noise, indices/errata tables) --
those are excluded here for what they *are*, not for who wrote them, and
are listed at the bottom of this docstring.

INCLUDED (authorship as given by the source folder, dates not verified):
  * Mukkur Yatindra (44th Ahobila Matha pontiff) -- Brahma Sutrartha Padya
    Malika, 156 units (grid).
  * Rajagopala -- his own Brahma Sutrartha Padya Malika (a different text
    from Mukkur's despite the shared genre title -- different source,
    different content, confirmed by direct comparison), 1 unit (single file).
  * "Ramanuja Tatacharya" (as the source folder names it; the text itself
    is headed "composed by Bhagavan Ramanuja", so this may be the editor of
    an edition rather than the author -- left as the source states it,
    per the project lead's instruction not to chase this down further) --
    Nyaya Kalapa Sangraha, 1 unit (single file).
  * Deshikacharya -- Adhikarana Ratnamala, one unit per pada (16 units;
    each pada is a single short file on this source, not further split).
  * Devanathan (K.E. Devanathan, 2006) -- Shribhashya Bhavaprakasha, 28
    units (flat, front-matter/bibliography/index files excluded as apparatus,
    not commentary -- see EXCLUDED below).
  * Lakshmipuram Srinivasacharya -- three works: Bhushanam (1 unit),
    Nayasangatimalika (1 unit), and a THIRD independent Nyaya Kalapa
    Sangraha distinct from the two above (confirmed by direct comparison --
    three different authors/sources genuinely share this generic genre
    title), ~140 units (grid-like, numbered subfolders).
  * Perukkaranai Chakravarti -- his Sri Bhashya Sariraka Mimamsa Bhashya
    (grid; front-matter folder "0" excluded, see below).
  * Seneshvara -- Nyaya Kalapa Sangraha, root verses ONLY (the file's own
    "tIkA" commentary layer is a modern English exposition, not
    Seneshvara's own Sanskrit prose -- excluded as non-Sanskrit content,
    not for its date; see EXCLUDED below).
  * Sudarshana Suri -- Shruta Prakashika (his other major work, alongside
    Phase 2's Shruta Pradipika), 2 units (v1/v2 -- no clean per-adhikarana
    split point was found in this source, so each volume is one large unit;
    a finer split is left as a follow-up, not attempted here) + Uttamur
    Viraraghavachariar's own prastavikam/vijnaptiH introduction to his
    edition of it (~2 units; his purely tabular apparatus -- index, errata --
    is excluded as non-prose, see below).
  * Uttamur Viraraghavachariar -- his own prose works (bhumika 1/2,
    bhashyartha-darpana, sangati-samgraha, shastravibhaga-namanirdesha,
    shastravantara-vibhaga), ~6 units; his purely tabular apparatus
    (vishaya-suchi topic-index, pada-sutra-samkhya table, errata list) is
    excluded as non-prose, not for its date.
  * Vedanta Desika's OTHER two commentators on Adhikarana Saravali, left out
    of Phase 2 pending identification and now included as the source names
    them: "34th Ahobila Yati" (~90 units) and "Kumara Varada" (~90 units),
    plus the 34th Ahobila Yati's separate standalone introduction
    (injimeDu-yati-bhUmikA, 1 unit).
  * Nitya Grantha (Ramanuja's daily-worship manual, held back from Phase 1
    specifically because its main file interleaves Francis X. Clooney's
    notes) -- now included via label-extraction: Vishwas's own
    "vishvAsa-prastutiH" layer only (the genuine mula text), Clooney's
    English notes and Vishwas's own separate "vishvAsa-TippaNI" aside both
    excluded as non-Sanskrit/non-mula content, not for Clooney's copyright
    specifically -- plus Ramabhadracharya's separate vivRtiH commentary file.

EXCLUDED (content-type or data-quality reasons, not copyright):
  * Abhinava Ranganatha's Gudhartha Sangraha -- direct inspection found
    genuine OCR corruption (stray Latin letters/digits spliced into
    Devanagari prose, broken diacritics) that no markup-stripping regex can
    safely repair.
  * Meghanadari-varadau -- of its two real files, one is raw OCR noise off
    a book title page, the other a ~12,000-line duplicate of Ramanuja's own
    root Sri Bhashya text already imported in ramanuja_mula.py. Neither is
    Meghanadari's own distinct commentary.
  * shruta-prakAshikA's "mUlam_rA" subfolder -- a further duplicate of
    Ramanuja's root text, already imported.
  * shruta-prakAshikA's "ta/gopAlAchAryaH.md" and nitya-granthaH's
    "nRsiMhapriyA.md" -- Tamil-language, out of scope (this project imports
    Sanskrit).
  * nitya-granthaH's "Clooney.md"-labelled block -- English academic prose,
    not Sanskrit text, excluded on that basis regardless of its copyright
    status (which is a separate, live concern the project lead is aware of).
  * Uttamur Viraraghavachariar's tabular apparatus (topic-index tables,
    sutra-count tables, errata lists) and Devanathan's own bibliography/
    source-index/preface files -- navigational apparatus, not prose
    commentary; would render as a jumble of table fragments if imported as
    running Sanskrit text.
  * Perukkaranai Chakravarti's and Devanathan's own front-matter folders
    (author bio, table of contents) -- apparatus, not commentary text.

See PENDING.md for the fuller trail.
"""
import os
import re

from common import write_grantha
from ramanuja_mula import (
    ensure_clone, collect_grid, to_tika_items, to_mula_items,
    strip_markup, _frontmatter_and_raw,
)
from ramanuja_subcommentaries import extract_label_blocks, collect_tree_labeled

TARGET = "darshana/vedanta/vishishtadvaita"
SOURCE_NOTE = ("github.com/vishvasa/ramanujiyam (branch `content`); used with "
               "the explicit permission of its maintainer, Vishwas Vasukijah, "
               "given to the project lead directly (see PENDING.md). Included "
               "without an independent authorship/date verification, per the "
               "project lead's explicit instruction (24 Aug) to import "
               "regardless and pursue licensing directly afterward.")

RB = "tattvam/rAmAnujaH/shrI-bhAShyam"


def _single_file_units(path, split_headers=True):
    """One markdown file -> [(ref, body)], split on its own "## " headers
    if it has any, else kept as one unit."""
    text = open(path, encoding="utf-8").read()
    title, raw = _frontmatter_and_raw(text)
    if split_headers and re.search(r"^## +", raw, re.M):
        sections = re.split(r"^## +(.+)$", raw, flags=re.M)
        units = []
        pre = strip_markup(sections[0])
        if pre:
            units.append((title, pre))
        i = 1
        while i < len(sections) - 1:
            header, body = sections[i], strip_markup(sections[i + 1])
            if body:
                units.append((f"{title} — {header.strip()}", body))
            i += 2
        return units
    body = strip_markup(raw)
    return [(title, body)] if body else []


def collect_dir_units(dirpath, exclude=()):
    """Every top-level .md file in one flat directory -> one unit each,
    sorted by filename. `exclude` names files/subfolders to skip (apparatus:
    prefaces, indices, bibliographies -- not primary text)."""
    units = []
    for fn in sorted(f for f in os.listdir(dirpath)
                      if f.endswith(".md") and f != "_index.md" and f not in exclude):
        text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
        title, body = _frontmatter_and_raw(text)
        body = strip_markup(body)
        if body:
            units.append((title, body))
    return units


def collect_grid_excluding(root, subpath, skip_dirs=()):
    """Like ramanuja_mula.collect_grid, but for a source that has an extra
    non-numeric-content top-level "adhyaya" folder holding front matter
    (e.g. perukkAraNai-chakravartI's "0" folder) rather than real content."""
    base = os.path.join(root, subpath)
    units = []
    for adhyaya in sorted(d for d in os.listdir(base) if d.isdigit() and d not in skip_dirs):
        adhyaya_dir = os.path.join(base, adhyaya)
        for pada in sorted(d for d in os.listdir(adhyaya_dir) if d.isdigit()):
            pada_dir = os.path.join(adhyaya_dir, pada)
            files = sorted(f for f in os.listdir(pada_dir)
                            if f.endswith(".md") and f != "_index.md")
            for fn in files:
                text = open(os.path.join(pada_dir, fn), encoding="utf-8").read()
                title, body = _frontmatter_and_raw(text)
                body = strip_markup(body)
                if not body:
                    continue
                units.append((f"{adhyaya}.{pada}.{title}", body))
    return units


def collect_grid_mula_only(root, subpath):
    """Like collect_grid, but keeps only the text BEFORE the first <details>
    tag in each file -- Seneshvara's source pairs each root verse with a
    "tIkA" block that turns out to be modern English exposition, not his
    own Sanskrit commentary; this keeps the genuine verse, drops that."""
    base = os.path.join(root, subpath)
    units = []
    for adhyaya in sorted(d for d in os.listdir(base) if d.isdigit()):
        adhyaya_dir = os.path.join(base, adhyaya)
        for pada in sorted(d for d in os.listdir(adhyaya_dir) if d.isdigit()):
            pada_dir = os.path.join(adhyaya_dir, pada)
            files = sorted(f for f in os.listdir(pada_dir)
                            if f.endswith(".md") and f != "_index.md")
            for fn in files:
                text = open(os.path.join(pada_dir, fn), encoding="utf-8").read()
                title, raw = _frontmatter_and_raw(text)
                head = raw.split("<details", 1)[0]
                body = strip_markup(head)
                if not body:
                    continue
                units.append((f"{adhyaya}.{pada}.{title}", body))
    return units


def collect_pada_files(root, subpath):
    """<adhyaya>/<pada>.md layout (Deshikacharya's Adhikarana Ratnamala) --
    one whole pada's verses per file, no further per-adhikarana split on
    this source."""
    base = os.path.join(root, subpath)
    units = []
    for adhyaya in sorted(d for d in os.listdir(base) if d.isdigit()):
        adhyaya_dir = os.path.join(base, adhyaya)
        for fn in sorted(f for f in os.listdir(adhyaya_dir) if f.endswith(".md")):
            pada = fn[:-3]
            text = open(os.path.join(adhyaya_dir, fn), encoding="utf-8").read()
            _, raw = _frontmatter_and_raw(text)
            body = strip_markup(raw)
            if body:
                units.append((f"{adhyaya}.{pada}", body))
    return units


# Sudarshana Suri's Shruta Prakashika (v1.md/v2.md) carries no Markdown
# structure at all (checked directly: 2 "### " headers total across both
# ~2M-character files, 0 of any other level) -- explaining its own
# "[[TODO: aparishkRtam]]" self-flag. But it DOES carry the original printed
# edition's own running page-headers: a Devanagari adhyaya-pada-sutra
# reference ("१-४-३." etc.) followed by a short topic phrase, recurring
# every page (101 times in v1, 47 in v2) -- found by direct inspection of
# a middle slice of the file, not assumed from the TODO flag. Splitting on
# these gives 148 real per-topic units instead of 2 giant blobs, and
# incidentally drops the English publisher's front-matter block noted as a
# residual limitation in the first pass: it sits entirely before the first
# marker, so it falls into the discarded "pre" segment below.
DEVANAGARI_DIGITS = "०१२३४५६७८९"
SP_PAGE_NUM_LINE = re.compile(r"^[ \t]*[०-९]{1,4}[ \t]*$", re.M)
SP_RUNNING_MARKER = re.compile(r"([०-९]+\s*-\s*[०-९]+\s*-\s*[०-९]+)\.\s*([^\n।]{0,80})")


def _devanagari_num(s):
    """'१-४-३' -> '1-4-3' -- Devanagari digits to ASCII, for a readable ref."""
    return "".join(str(DEVANAGARI_DIGITS.index(c)) if c in DEVANAGARI_DIGITS else c
                    for c in s)


def collect_shruta_prakashika(root, base_subpath, filenames):
    units = []
    for fn in filenames:
        text = open(os.path.join(root, base_subpath, fn), encoding="utf-8").read()
        _, raw = _frontmatter_and_raw(text)
        raw = SP_PAGE_NUM_LINE.sub("", raw)
        parts = SP_RUNNING_MARKER.split(raw)
        # split() with 2 capturing groups yields [pre, ref1, topic1, body1, ref2, topic2, body2, ...]
        # "pre" (everything before the first marker) is front matter -- title
        # page, publisher's notice, sutra index -- not commentary; dropped.
        i = 1
        while i < len(parts) - 2:
            devref, topic, body = parts[i], parts[i + 1], parts[i + 2]
            i += 3
            body = strip_markup(SP_PAGE_NUM_LINE.sub("", body))
            if not body:
                continue
            ref = _devanagari_num(devref.replace(" ", ""))
            topic = topic.strip()
            units.append((f"{ref}. {topic}" if topic else ref, body))
    return units


def run(only=None):
    root = ensure_clone()

    def emit(slug, target, schema, author, items, tag=None):
        if not items:
            print(f"  ~ {slug}: no units parsed")
            return
        write_grantha(target, schema, author, items, source_note=SOURCE_NOTE)
        print(f"{slug}: {len(items)} units")

    if not only or only == "mukkur_yatindra":
        units = collect_grid(root, f"{RB}/44a-mukkUr-yatiH_brahma-sUtrArtha-padya-mAlikA")
        items = to_tika_items(units, "Brahma Sutrartha Padya Malika")
        emit("mukkur_yatindra", f"{TARGET}/mukkur_yatindra/brahmasutrartha_padyamalika/bhashya",
             "grantha_tika_text", "Mukkur Yatindra", items)

    if not only or only == "rajagopala":
        units = _single_file_units(os.path.join(root, f"{RB}/rAjagopAlaH/brahmasUtrArthapadyamAlikA.md"))
        items = to_tika_items(units, "Brahma Sutrartha Padya Malika")
        emit("rajagopala", f"{TARGET}/rajagopala/brahmasutrartha_padyamalika/bhashya",
             "grantha_tika_text", "Rajagopala", items)

    if not only or only == "ramanuja_tatacharya":
        units = _single_file_units(os.path.join(root, f"{RB}/rAmAnuja-tAtAryaH/nyAyakalApasangrahaH.md"))
        items = to_tika_items(units, "Nyaya Kalapa Sangraha")
        emit("ramanuja_tatacharya", f"{TARGET}/ramanuja_tatacharya/nyaya_kalapa_sangraha/bhashya",
             "grantha_tika_text", "Ramanuja Tatacharya", items)

    if not only or only == "deshikacharya":
        units = collect_pada_files(root, f"{RB}/deshikAryaH_adhikaraNa-ratnamAlA")
        items = to_tika_items(units, "Adhikarana Ratnamala")
        emit("deshikacharya", f"{TARGET}/deshikacharya/adhikarana_ratnamala/bhashya",
             "grantha_tika_text", "Deshikacharya", items)

    if not only or only == "devanathan":
        exclude = {"29_AkarasUchI.md", "30_upayukta_granthasUchI.md"}
        base = os.path.join(root, f"{RB}/devanAtha-bhAva-prakAshaH")
        units = collect_dir_units(base, exclude=exclude)
        items = to_tika_items(units, "Shribhashya Bhavaprakasha")
        emit("devanathan", f"{TARGET}/devanathan/shribhashya_bhavaprakasha/bhashya",
             "grantha_tika_text", "K.E. Devanathan", items)

    if not only or only == "lakshmipuram_srinivasacharya":
        u1 = _single_file_units(os.path.join(root, f"{RB}/laxmI-pura-shrInivAsaH/bhUShaNam.md"))
        emit("lakshmipuram_bhushanam", f"{TARGET}/lakshmipuram_srinivasacharya/bhushanam/bhashya",
             "grantha_tika_text", "Lakshmipuram Srinivasacharya", to_tika_items(u1, "Bhushanam"))

        u2 = _single_file_units(os.path.join(root, f"{RB}/laxmI-pura-shrInivAsaH/nayasangatimAlikA.md"))
        emit("lakshmipuram_nayasangatimalika", f"{TARGET}/lakshmipuram_srinivasacharya/nayasangatimalika/bhashya",
             "grantha_tika_text", "Lakshmipuram Srinivasacharya", to_tika_items(u2, "Nayasangatimalika"))

        base = os.path.join(root, f"{RB}/laxmI-pura-shrInivAsaH/nyAyakalApasangrahaH")
        u3 = []
        for sub in sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))):
            u3.extend(collect_dir_units(os.path.join(base, sub)))
        emit("lakshmipuram_nyayakalapasangraha", f"{TARGET}/lakshmipuram_srinivasacharya/nyaya_kalapa_sangraha/bhashya",
             "grantha_tika_text", "Lakshmipuram Srinivasacharya", to_tika_items(u3, "Nyaya Kalapa Sangraha"))

    if not only or only == "perukkaranai_chakravarti":
        units = collect_grid_excluding(root, f"{RB}/perukkAraNai-chakravartI", skip_dirs={"0"})
        items = to_tika_items(units, "Sri Bhashya Sariraka Mimamsa Bhashya")
        emit("perukkaranai_chakravarti", f"{TARGET}/perukkaranai_chakravarti/sri_bhashya_sariraka_mimamsa_bhashya/bhashya",
             "grantha_tika_text", "Perukkaranai Chakravarti", items)

    if not only or only == "seneshvara":
        units = collect_grid_mula_only(root, f"{RB}/seneshvara-nyAya-kalApa-sangrahaH")
        items = to_mula_items(units)
        emit("seneshvara", f"{TARGET}/seneshvara/nyaya_kalapa_sangraha/mula",
             "grantha_mula_text", "Seneshvara", items)

    if not only or only == "sudarshana_suri_shruta_prakashika":
        base = os.path.join(root, f"{RB}/sudarshana-sUriH/shruta-prakAshikA")
        units = collect_shruta_prakashika(
            root, f"{RB}/sudarshana-sUriH/shruta-prakAshikA", ("v1.md", "v2.md"))
        items = to_tika_items(units, "Shruta Prakashika")
        emit("sudarshana_suri_shruta_prakashika", f"{TARGET}/sudarshana_suri/shruta_prakashika/bhashya",
             "grantha_tika_text", "Sudarshana Suri", items)

        uv_base = os.path.join(base, "uttamUru-vIrarAghava-saMskaraNam")
        uv_exclude = {"anukramaNikA.md", "adhyAyapAdanAmAni.md", "prathamapAdadvaya-viShayasUchI.md",
                      "pratisUtra-viShaya-vAkya-sthala-sUchI.md"}
        uv_units = collect_dir_units(uv_base, exclude=uv_exclude)
        emit("uttamuru_shruta_prakashika_edition", f"{TARGET}/uttamur_viraraghavachariar/shruta_prakashika_edition/bhashya",
             "grantha_tika_text", "Uttamur Viraraghavachariar",
             to_tika_items(uv_units, "Shruta Prakashika Samskaranam"))

    if not only or only == "uttamur_own_works":
        base = os.path.join(root, f"{RB}/uttamUr-vIra-rAghavaH")
        exclude = {"viShayasUchI.md", "pAdasUtrasaMkhyA_koShThakaH.md", "shodhanikA_Errata_List.md"}
        units = collect_dir_units(base, exclude=exclude)
        items = to_tika_items(units, "Bhashyartha Darpana")
        emit("uttamur_own_works", f"{TARGET}/uttamur_viraraghavachariar/bhashyartha_darpana/bhashya",
             "grantha_tika_text", "Uttamur Viraraghavachariar", items)

    if not only or only == "vedanta_desika_other_commentators":
        subpath = f"{RB}/venkaTa-nAthaH/adhikaraNa-sArAvalI/sarva-prastutiH"
        ahobila = collect_tree_labeled(root, subpath, "३४-तमाहोबिल-यतिः")
        emit("ahobila_yati_gloss", f"{TARGET}/ahobila_yati_34/adhikarana_saravali_padayojana/bhashya",
             "grantha_tika_text", "34th Ahobila Yati", to_tika_items(ahobila, "Adhikarana Saravali Pada Yojana"))

        kumaravarada = collect_tree_labeled(root, subpath, "कुमार-वरदः")
        emit("kumara_varada_gloss", f"{TARGET}/kumara_varada/adhikarana_saravali_vyakhya/bhashya",
             "grantha_tika_text", "Kumara Varada", to_tika_items(kumaravarada, "Adhikarana Saravali Vyakhya"))

        intro_path = os.path.join(root, f"{RB}/venkaTa-nAthaH/adhikaraNa-sArAvalI/34-ahobila-yatiH_pada-yojanA/injimeDu-yati-bhUmikA.md")
        intro = _single_file_units(intro_path)
        emit("ahobila_yati_bhumika", f"{TARGET}/ahobila_yati_34/pada_yojana_bhumika/bhashya",
             "grantha_tika_text", "34th Ahobila Yati", to_tika_items(intro, "Pada Yojana Bhumika"))

    # abhinava-ranganAtha-gUDhArtha-sangrahaH is NOT imported: unlike every
    # other source here, direct inspection found genuine OCR corruption
    # (stray Latin letters/digits spliced into Devanagari prose, e.g. "r 1 7
    # J", "IS क", broken diacritics) that no markup-stripping regex can
    # safely repair -- a data-quality exclusion, not an authorship one.

    if not only or only == "nitya_grantha":
        ng_base = f"kriyA/rAmAnujaH/nitya-granthaH"
        text = open(os.path.join(root, ng_base, "sarva-prastutiH.md"), encoding="utf-8").read()
        _, raw = _frontmatter_and_raw(text)
        blocks = extract_label_blocks(raw, "विश्वास-प्रस्तुतिः")
        units = []
        for n, block in enumerate(blocks, 1):
            body = strip_markup(block)
            if body:
                units.append((str(n), body))
        emit("nitya_grantha", f"{TARGET}/ramanuja_bhashya/gadya_traya/nitya_grantha/mula",
             "grantha_mula_text", "Sri Ramanujacharya", to_mula_items(units))

        # Section "0" of this file is the edition's own masthead (editorial
        # committee names, an English "Ack 1" acknowledgments note) -- front
        # matter, not Ramabhadracharya's commentary; excluded by name.
        vivrti_units = _single_file_units(os.path.join(root, ng_base, "rAmabhadrAchArya-vivRtiH.md"))
        vivrti_units = [(ref, body) for ref, body in vivrti_units if not ref.endswith("— 0")]
        emit("nitya_grantha_ramabhadracharya", f"{TARGET}/ramabhadracharya/nitya_grantha_vivrti/bhashya",
             "grantha_tika_text", "Ramabhadracharya", to_tika_items(vivrti_units, "Nitya Grantha Vivrti"))


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else None)
