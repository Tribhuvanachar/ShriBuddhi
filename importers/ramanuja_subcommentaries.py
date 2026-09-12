"""Phase 2 of the vishvasa/ramanujiyam import: sub-commentaries on
Ramanuja's Sri Bhashya, and Vedanta Desika's own verses out of a file that
also carries later commentary on them.
   -> darshana/vedanta/vishishtadvaita/<author>/<work>/bhashya

Continues importers/ramanuja_mula.py's Phase 1 (Ramanuja's own works).
That module's docstring covers the site, the permission this runs under,
and why Phase 1 stopped short of the site's ~15-author secondary-commentary
layer. This module imports the subset of that layer confirmed, one author
at a time, to be BOTH genuinely composed by who the folder name says AND
safely public domain -- confirmed by a dedicated research pass (web search
against archive.org records, matha lineage pages, biographical sources),
not assumed from a classical-sounding name. That research turned up a real
trap: several folders that read as ancient at a glance turned out to be
20th/21st-century scholars still under copyright -- notably the site's
"Mukkur Yatindra" (44th Ahobila Matha pontiff, d. 1992) and "Perukkaranai
Chakravarti" (a Sri Bhashya commentary published in 2000) -- so EVERY
inclusion below is confirmed classical, not merely "old-sounding".

INCLUDED (confirmed public domain):
  * Appayya Dikshita (1520-1593)  -- naya-mayukha-malika          -- Naya Mayukha Malika
  * Ranga Ramanuja (16th/17th c.) -- three works: Sharirika Shastrartha
      Dipika, Vishaya Vakya Dipika, and Bhava Prakashika (the last is
      physically filed under sudarshana-sUriH/shruta-prakAshikA/ on the
      site, but is Ranga Ramanuja's own work per its own folder name and
      content, not Sudarshana Suri's -- attributed to its actual author here)
  * Sudarshana Suri (c. 13th-14th c.) -- Shruta Pradipika. His other major
      work on the site, Shruta Prakashika, is NOT imported here: it's two
      ~large files with no clean per-adhikarana split point and the site's
      own text flags it "[[TODO: aparishkRtam]]" (unrefined) -- left as a
      follow-up needing more parsing work, not a copyright concern.
  * Vedanta Desika / Venkatanatha (1268-1369) -- his own verses ONLY, out of
      Adhikarana Saravali. That source file interleaves, per numbered verse,
      FOUR labelled layers under nested <details><summary> tags: the verse
      itself (twice, under "vishvAsa-prastutiH" and "mUlam" -- confirmed
      identical text, just duplicated for the site's own display purposes),
      a "34th Ahobila Yati" gloss, and a "kumAra-varadaH" gloss. Only "mUlam"
      is extracted -- the other two commentators were NOT in scope of the
      research pass (found only once already parsing the file) and are left
      out pending their own identification, not assumed safe.

EXCLUDED (checked, not merely skipped):
  * "44a-mukkUr-yatiH" (Mukkur Yatindra, d. 1992) -- in copyright.
  * "perukkAraNai-chakravartI" (published 2000, Sri Nrisimha Priya Trust)
    -- in copyright, same category as the Devanathan case in shankara_bhashya.
  * "uttamUr-vIra-rAghavaH" and shruta-prakAshikA's own
    "uttamUru-vIrarAghava-saMskaraNam" subfolder (Uttamur Viraraghavachariar,
    d. 1981/83) -- in copyright; his editorial apparatus on a classical text
    doesn't inherit that text's public-domain status.
  * "deshikAryaH_adhikaraNa-ratnamAlA" (likely Kapisthalam Desikachariar,
    b. 1855 -- exact death date NOT found), "laxmI-pura-shrInivAsaH"
    (early-to-mid 20th c., dates NOT found), "rAjagopAlaH" (author not
    identified), "rAmAnuja-tAtAryaH" (name reused across centuries INCLUDING
    by a specific, confirmed-modern namesake, N.S. Ramanuja Tatacharya,
    1928-2017 -- real risk of collision, and this folder's own content turned
    out to carry that exact title's colophon ambiguity) -- all excluded on
    the same standard used for the copyright research itself: an author who
    can't be confidently dated stays out until they can be, not in by default.
  * "seneshvara-nyAya-kalApa-sangrahaH" -- excluded for a content-type reason,
    not copyright: its "tIkA" layer turned out to be a modern ENGLISH
    exposition of the sutras, not Seneshvara's own Sanskrit commentary, so
    there is no genuine Sanskrit prose here to import as sanskrit_text.
  * "meghanAdAri-varadau" -- excluded for a data-quality reason: of its two
    real files, one is raw OCR noise off a book title page and the other is
    a ~12,000-line duplicate of Ramanuja's own root Sri Bhashya text (already
    imported in ramanuja_mula.py), not Meghanadari's own distinct commentary.
  * shruta-prakAshikA's own "mUlam_rA" subfolder -- redundant, a further copy
    of Ramanuja's root text already imported.
  * shruta-prakAshikA's "ta/gopAlAchAryaH.md" -- Tamil-language, author not
    researched, out of scope either way (this project imports Sanskrit).

See PENDING.md for the full research trail and what a later pass could add
once the still-uncertain authors are confidently dated.
"""
import os
import re

from common import write_grantha
from ramanuja_mula import (
    ensure_clone, collect_grid, to_tika_items, to_mula_items,
    strip_markup, _frontmatter_and_raw,
)

TARGET = "darshana/vedanta/vishishtadvaita"
SOURCE_NOTE = ("github.com/vishvasa/ramanujiyam (branch `content`); used with "
               "the explicit permission of its maintainer, Vishwas Vasukijah, "
               "given to the project lead directly (see PENDING.md). This "
               "specific work independently confirmed public domain -- see "
               "this importer's own module docstring for the research trail.")

# "[an unreadable/missing scan region] is not available." -- a recurring
# OCR/transcription placeholder in Ranga Ramanuja's Bhava Prakashika file,
# sometimes doubled or tripled in a row. Confirmed by direct inspection
# (grepped every occurrence) that it's always exactly this literal English
# phrase, never real content.
NOT_AVAILABLE = re.compile(r"is not available\.?")


def extract_label_blocks(text, label):
    """All <details ...><summary>LABEL[ - N]</summary>...</details> blocks
    for one label out of a file that interleaves several (Vedanta Desika's
    Adhikarana Saravali: mUlam / vishvAsa-prastutiH / two different later
    commentators, all under numbered verses in the same file)."""
    pattern = re.compile(
        r"<details[^>]*>\s*<summary>\s*" + re.escape(label) +
        r"\s*(?:-\s*\d+\s*)?</summary>(.*?)</details>", re.S)
    return [m.group(1) for m in pattern.finditer(text)]


def _labeled_or_whole(raw, label):
    """A file with no <details> tags at all is plain single-author prose (no
    other commentator's layer to separate it from) -- keep it whole. A file
    that DOES use <details> tags is multi-layered; only `label`'s own blocks
    belong to this author (empty if this adhikarana has none under that
    label, e.g. root text and translation only, no separate commentary here)."""
    if "<details" not in raw:
        return strip_markup(raw)
    blocks = extract_label_blocks(raw, label)
    return strip_markup(" ".join(blocks)) if blocks else ""


def collect_grid_labeled(root, subpath, label):
    """Like ramanuja_mula.collect_grid, but pulls only the blocks tagged
    `label` out of each file instead of the whole cleaned body -- for a
    source file that interleaves multiple commentators under the same
    adhikarana heading. shruta-pradIpikA mixes both kinds of file even
    within one pada: most adhikaranas are plain single-layer prose, a
    minority (wherever Thibaut's translation or a mUlam duplicate was also
    added) are labelled -- handled per-file by _labeled_or_whole."""
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
                body = _labeled_or_whole(raw, label)
                if not body:
                    continue
                units.append((f"{adhyaya}.{pada}.{title}", body))
    return units


def collect_tree_labeled(root, subpath, label):
    """Like collect_grid_labeled, but for a source tree organised by nested
    THEME/subtheme directories (arbitrary depth, non-numeric names) rather
    than a flat adhyaya/pada grid -- Vedanta Desika's Adhikarana Saravali,
    e.g. sarva-prastutiH/1_samanvayaH/2_aspaShTa-jIvAdi-lingakaH/16_foo.md.
    Walks every leaf .md file regardless of nesting depth."""
    base = os.path.join(root, subpath)
    units = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for fn in sorted(f for f in filenames if f.endswith(".md") and f != "_index.md"):
            text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
            title, raw = _frontmatter_and_raw(text)
            body = _labeled_or_whole(raw, label)
            if not body:
                continue
            rel = os.path.relpath(dirpath, base)
            units.append((f"{rel}/{title}" if rel != "." else title, body))
    return units


def run(only=None):
    root = ensure_clone()

    if not only or only == "appayya_naya_mayukha_malika":
        units = collect_grid(root, "tattvam/rAmAnujaH/shrI-bhAShyam/appayya-naya-mayUkha-mAlikA")
        items = to_tika_items(units, "Naya Mayukha Malika")
        write_grantha(f"{TARGET}/appayya_dikshita/naya_mayukha_malika/bhashya",
                       "grantha_tika_text", "Appayya Dikshita", items, source_note=SOURCE_NOTE)
        print(f"appayya_naya_mayukha_malika: {len(items)} units")

    if not only or only == "rangaramanuja_sharirika":
        units = collect_grid(root, "tattvam/rAmAnujaH/shrI-bhAShyam/rangarAmAnujaH/shArIrika-shAstrArtha-dIpikA")
        items = to_tika_items(units, "Sharirika Shastrartha Dipika")
        write_grantha(f"{TARGET}/rangaramanuja/sharirika_shastrartha_dipika/bhashya",
                       "grantha_tika_text", "Ranga Ramanuja", items, source_note=SOURCE_NOTE)
        print(f"rangaramanuja_sharirika: {len(items)} units")

    if not only or only == "rangaramanuja_vishayavakya":
        units = collect_grid(root, "tattvam/rAmAnujaH/shrI-bhAShyam/rangarAmAnujaH/viShaya-vAkya-dIpikA")
        items = to_tika_items(units, "Vishaya Vakya Dipika")
        write_grantha(f"{TARGET}/rangaramanuja/vishaya_vakya_dipika/bhashya",
                       "grantha_tika_text", "Ranga Ramanuja", items, source_note=SOURCE_NOTE)
        print(f"rangaramanuja_vishayavakya: {len(items)} units")

    if not only or only == "rangaramanuja_bhavaprakashika":
        units = collect_grid(root, "tattvam/rAmAnujaH/shrI-bhAShyam/sudarshana-sUriH/shruta-prakAshikA/rangarAmAnuja--bhAva-prakAshikA")
        units = [(ref, NOT_AVAILABLE.sub(" ", body).strip()) for ref, body in units]
        units = [(ref, re.sub(r"\s+", " ", body)) for ref, body in units if body]
        items = to_tika_items(units, "Bhava Prakashika")
        write_grantha(f"{TARGET}/rangaramanuja/bhava_prakashika/bhashya",
                       "grantha_tika_text", "Ranga Ramanuja", items, source_note=SOURCE_NOTE)
        print(f"rangaramanuja_bhavaprakashika: {len(items)} units")

    if not only or only == "sudarshana_suri_shruta_pradipika":
        units = collect_grid_labeled(
            root, "tattvam/rAmAnujaH/shrI-bhAShyam/sudarshana-sUriH/shruta-pradIpikA",
            "श्रुत-प्रदीपिका")
        items = to_tika_items(units, "Shruta Pradipika")
        write_grantha(f"{TARGET}/sudarshana_suri/shruta_pradipika/bhashya",
                       "grantha_tika_text", "Sudarshana Suri", items, source_note=SOURCE_NOTE)
        print(f"sudarshana_suri_shruta_pradipika: {len(items)} units")

    if not only or only == "vedanta_desika_adhikarana_saravali":
        units = collect_tree_labeled(
            root, "tattvam/rAmAnujaH/shrI-bhAShyam/venkaTa-nAthaH/adhikaraNa-sArAvalI/sarva-prastutiH",
            "मूलम्")
        items = to_mula_items(units)
        write_grantha(f"{TARGET}/vedanta_desika/adhikarana_saravali/mula",
                       "grantha_mula_text", "Vedanta Desika", items, source_note=SOURCE_NOTE)
        print(f"vedanta_desika_adhikarana_saravali: {len(items)} units")


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else None)
