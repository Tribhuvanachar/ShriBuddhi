"""Sri Ramanujacharya's own works
   -> darshana/vedanta/vishishtadvaita/ramanuja_bhashya/<work>/{bhashya,mula}

SOURCE: github.com/vishvasa/ramanujiyam (branch `content`; the site published
at vishvasa.github.io), maintained by Vishwas Vasukijah. Used with his
explicit permission, given directly to this project's lead and passed on for
this import (see PENDING.md for the exchange this traces back to). The
project's own "no explicit licence = do not use" default does not apply here
because that permission was actually obtained -- but it does NOT extend past
what he has the right to give.

SCOPE -- deliberately narrow (Phase 1 of this source, not the whole site):
The `rAmAnujaH` tree on that site holds far more than Ramanuja's own text --
roughly fifteen later acharyas' sub-commentaries on the Sri Bhashya (Sudarshana
Suri's Shrutaprakashika, Vedanta Desika's Adhikarana Saravali, etc.),
translations into English/Hindi/Tamil, and at least one directly modern,
still-in-copyright work (K.E. Devanathan's 2006 "Shribhashyabhavaprakasha",
published by Nrisimha Priya Trust, Chennai -- checked directly, the folder's
own _index.md names the book, author, publisher and year). Vishwas's own
permission to "take what you like" is permission for what's genuinely his to
give; it doesn't clear someone else's still-live copyright on a 2006 book he
merely hosts a copy of. That whole secondary-commentary layer needs a
per-author copyright/date check before it can be imported and is left as a
follow-up (see PENDING.md) -- NOT attempted here.

This importer covers only the five works directly composed by Ramanuja
himself (traditionally 11th c., long public domain), each confirmed by direct
inspection of the fetched source to carry no embedded modern commentary:
  * Sri Bhashya          (Brahma Sutra bhashya)      -- shrI-bhAShyam/mUlam/ma
  * Vedanta Dipa          (shorter BS bhashya)         -- vedAnta-dIpaH/sarva-prastutiH
  * Vedanta Sara          (shorter BS bhashya)         -- vedAnta-sAraH/sarva-prastutiH
  * Vedartha Sangraha     (independent treatise)       -- vedArtha-sangrahaH/mUlam
  * Sharanagati Gadyam    (devotional prose-poem)      -- kriyA/rAmAnujaH/sharaNAgati-gadyam/mUlam.md

`shrI-bhAShyam/mUlam` has TWO parallel editions of Ramanuja's SAME text on
this site, `ma` and `ra` -- confirmed by direct comparison (both open
"janmAdyadhikaraNam" identically) -- differing only in typesetting/orthography
(`ra`'s transcription conflates ब/व, a common South-Indian-source artifact)
and in whether traditional adhikaranartha (topic-gist) headers are present.
`ma` is used here: cleaner orthography, and those headers are useful, genuine
traditional apparatus (a one-line Sanskrit topic summary), not modern
commentary -- confirmed by inspecting every occurrence before trusting that.

`kriyA/rAmAnujaH/nitya-granthaH` (Ramanuja's daily-worship manual) is
EXCLUDED from this pass for a reason specific to that one file, not the
general policy above: its only copy on the site interleaves Francis X.
Clooney's copyrighted academic notes and the site owner's own editorial
framing directly into the same file as the mula text, which needs careful
per-block filtering this importer does not yet do. Left as a follow-up.
"""
import os
import re
import subprocess

from common import write_grantha

REPO_URL = "https://github.com/vishvasa/ramanujiyam"
REPO_BRANCH = "content"
CACHE_DIR = os.environ.get("RAMANUJIYAM_CACHE", ".reposcache/ramanujiyam")

FRONTMATTER = re.compile(r"^\+\+\+\s*\ntitle\s*=\s*\"(.*?)\"\s*\n\+\+\+\s*\n", re.S)
DETAILS_TAG = re.compile(r"</?details[^>]*>|</?summary[^>]*>", re.I)
MD_HEADER = re.compile(r"^#{1,6}\s*", re.M)
MD_BOLD = re.compile(r"\*\*(.*?)\*\*", re.S)
# A handful of later authors' sources have an odd total count of "**" (a
# forgotten close somewhere upstream), leaving one unpaired after MD_BOLD
# above has paired up the rest -- and separately, a bare "***" thematic-break
# divider (standard Markdown, unrelated to bold). Both stripped as a
# fallback, run after MD_BOLD. NOT extended to a single "*": several of
# these printed editions use a lone asterisk as the source's own footnote-
# reference marker (confirmed genuine -- checked directly against several
# already-imported works before narrowing this to 2-3 only), so stripping
# it would delete real editorial apparatus, not markup noise.
MD_STRAY_ASTERISKS = re.compile(r"\*{2,3}")
# The site's own inline-gloss shortcode, e.g. "+++(=viShNu-pUjaika-chittasya)+++"
# -- an editorial parenthetical aside, not the TOML frontmatter delimiter
# (which only ever appears once, matched whole by FRONTMATTER above).
HUGO_GLOSS = re.compile(r"\+\+\+\((.*?)\)\+\+\+", re.S)
# A one-sided variant of the same shortcode seen in nitya-granthaH, e.g.
# "chetanAchetana+++(->prakRti-kAla-nitya-vibhUtayaH)-svarUpa..." -- opens
# with "+++(" but never closes with a matching "+++", just a bare ")".
# Applied AFTER HUGO_GLOSS above, so it only catches what the paired form
# didn't already consume.
HUGO_GLOSS_UNPAIRED = re.compile(r"\+\+\+\(([^)]*)\)")
# A citation quote hyperlinked out to an external site, e.g.
# "[yenAxaraM puruShaM veda...](http://srivaishnavan.com/...)" -- the bracket
# text is a genuine Sanskrit quote (found in sri_bhashya and vedartha_sangraha,
# both citing the Gita mid-bhashya); keep the quote, drop the URL.
MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# An English critical-apparatus note on manuscript variants, e.g. "(M 3 reads
# the following verse after the colophon: \"...\" M 1 reads ...)" -- editorial
# apparatus about the text, not the text itself (paralleling how GRETIL's
# editorial asides were excluded from shankara_bhashya). Only matches a
# parenthetical that itself contains "reads"/"omitted" in English, so it can't
# swallow a genuine Sanskrit parenthetical aside (this corpus has none using
# those English words).
# No \b before/after: this note is sometimes glued directly onto the
# preceding Devanagari word with no space (e.g. "(saMvargaomitted M.3.)"),
# and since both Devanagari letters and Latin letters count as \w in
# Unicode regex, \b would not fire at that junction. Safe without it anyway
# -- "reads"/"omitted" as bare Latin substrings can't occur inside genuine
# Devanagari text.
VARIANT_NOTE = re.compile(r"\([^()]*(?:reads?|omitted)[^()]*\)", re.I)
# The site's own draft-status marker: bracketed, e.g. "[[TODO: aparishkRtam]]"
# (unrefined) or "[TODO: parishkAryam]" (needs polishing) -- content runs up
# to the closing bracket(s), so this form can be multiple words; OR bare,
# e.g. "TODO: MISSING??" with no brackets at all -- limited to one token
# since there's no bracket to mark where the note ends. Both forms seen
# across later authors' files. Editorial metadata about the transcription's
# state, not the text itself.
TODO_MARKER = re.compile(r"\[{1,2}\s*TODO\s*:[^\]]*\]{1,2}|TODO\s*:\s*\S+", re.I)
# A standalone citation line, e.g. "source: [TW](url)" or "Source: [TW double
# page scan](url)", right after the frontmatter in several later authors'
# files. MD_LINK above already strips the URL, leaving "source: TW" as
# plain text -- this catches the citation line as a whole (run first).
SOURCE_LINE = re.compile(r"^\s*[Ss]ource\s*:.*$", re.M)
# A Markdown footnote -- definition ("[^12]: The text quotes from ...") or
# inline reference ("...as shown[^12]") -- seen in Devanathan's 2006 book,
# a proper modern academic edition with real footnote apparatus. The
# footnote body is English scholarly commentary, not Sanskrit; dropped from
# sanskrit_text on that basis like Thibaut's/Clooney's English elsewhere.
MD_FOOTNOTE_DEF = re.compile(r"^\[\^\d+\]:.*$", re.M)
MD_FOOTNOTE_REF = re.compile(r"\[\^\d+\]")
DASH_RUN = re.compile(r"[–—-]{3,}")
# vedAnta-sAraH's very last file appends, after the traditional "the whole
# treatise is concluded" line, a scribal donor-dedication note in Tamil
# (transliterated to Devanagari) -- not Ramanuja's text at all, and not
# present in any other work's ending (sri_bhashya's own ending uses the
# slightly different "shAstraM cha parisamAptam", so this exact phrase is
# safe to cut on: it only ever appears once, genuinely at the true end).
# "shAstraM" is spelled without the conjunct (shAsraM) in this specific
# source file -- matched permissively so either spelling is caught.
WORK_CONCLUDED = re.compile(r"शास्(?:त्)?रं\s+च\s+समाप्तम्\s*।?")
VERSE_MARKER = re.compile(r"॥\s*(\d+)\s*॥")


def strip_markup(body):
    body = SOURCE_LINE.sub(" ", body)
    body = MD_FOOTNOTE_DEF.sub(" ", body)
    body = MD_FOOTNOTE_REF.sub(" ", body)
    body = HUGO_GLOSS.sub(r"(\1)", body)
    body = HUGO_GLOSS_UNPAIRED.sub(r"(\1)", body)
    body = MD_LINK.sub(r"\1", body)
    body = VARIANT_NOTE.sub(" ", body)
    body = TODO_MARKER.sub(" ", body)
    body = DETAILS_TAG.sub(" ", body)
    body = MD_HEADER.sub("", body)
    body = MD_BOLD.sub(r"\1", body)
    body = MD_STRAY_ASTERISKS.sub(" ", body)
    body = DASH_RUN.sub(" ", body)
    m = WORK_CONCLUDED.search(body)
    if m:
        body = body[:m.end()]
    return re.sub(r"\s+", " ", body).strip()


def ensure_clone():
    """Shallow clone of the `content` branch -- the Hugo site's own source
    tree, not the rendered site. Anonymous git read works from this sandbox
    even where the GitHub API doesn't (checked directly); re-cloning is
    skipped if the cache from a previous run is already present."""
    if not os.path.isdir(os.path.join(CACHE_DIR, ".git")):
        parent = os.path.dirname(CACHE_DIR)
        if parent:
            os.makedirs(parent, exist_ok=True)
        env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", REPO_BRANCH, REPO_URL, CACHE_DIR],
            check=True, env=env,
        )
    return CACHE_DIR


def clean_body(text):
    """Frontmatter title + Hugo/Markdown body -> (title, plain Sanskrit text).
    Strips TOML frontmatter, <details>/<summary> wrapper tags (keeping their
    content -- the traditional adhikaranartha one-liners are real content,
    not junk), Markdown ## headers and **bold** markup, and the site's own
    "+++(gloss)+++" shortcode (keeping the text/gloss in all three cases),
    then collapses whitespace."""
    m = FRONTMATTER.match(text)
    title = m.group(1) if m else ""
    body = text[m.end():] if m else text
    return title.strip(), strip_markup(body)


def collect_grid(root, subpath):
    """adhyaya/pada/NN_name.md layout shared by Sri Bhashya, Vedanta Dipa and
    Vedanta Sara -- numbering restarts at 01 within each pada, so the
    reference is built from the folder path, not just the filename."""
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
                title, body = clean_body(text)
                if not body:
                    continue
                # ma's own titles already carry "shrIbhAshyam NN-NN-NN <name>";
                # dIpa/sAra's titles are just "NN <name>" -- prepend adhyaya.pada
                # for those so every reference is self-describing on its own.
                ref = title if re.match(r"^\S+\s+\d+-\d+-\d+", title) else f"{adhyaya}.{pada}.{title}"
                units.append((ref, body))
    return units


def collect_flat(root, subpath):
    """A directory of NNb.md-style files, each split on its own "## "
    section headers into per-topic units (Vedartha Sangraha's mUlam: two
    ~60k-character files, ~100 genuine topical headers apiece, e.g. "##
    शाङ्करमतसंक्षिप्तानुवादः" -- confirmed these are the source's own
    content-organizing headers, not commentary, before splitting on them)."""
    base = os.path.join(root, subpath)
    units = []
    for fn in sorted(f for f in os.listdir(base) if f.endswith(".md") and f != "_index.md"):
        text = open(os.path.join(base, fn), encoding="utf-8").read()
        part_title, raw_body = _frontmatter_and_raw(text)
        # Split on level-2 "## " headers only, ahead of the general markup
        # strip below -- a stray "##### ..." (a different heading level, seen
        # once in vedArtha-sangrahaH's Part II) doesn't split here and is
        # caught instead by strip_markup()'s own MD_HEADER pass.
        sections = re.split(r"^## +(.+)$", raw_body, flags=re.M)
        # re.split with a capturing group yields [pre, header1, body1, header2, body2, ...]
        pre = strip_markup(sections[0])
        if pre:
            units.append((part_title, pre))
        i = 1
        while i < len(sections) - 1:
            header, body = sections[i], strip_markup(sections[i + 1])
            if body:
                units.append((f"{part_title} — {header.strip()}", body))
            i += 2
    return units


def _frontmatter_and_raw(text):
    """Like clean_body but keeps the ## headers in place for collect_flat's
    own header-based split, instead of stripping them."""
    m = FRONTMATTER.match(text)
    title = m.group(1) if m else ""
    body = text[m.end():] if m else text
    return title.strip(), body


def collect_verses(root, relpath):
    """A single short file (Sharanagati Gadyam), split on its own ॥ N ॥
    verse-end markers into individually referenceable units."""
    text = open(os.path.join(root, relpath), encoding="utf-8").read()
    _, body = clean_body(text)
    units, last_end = [], 0
    for m in VERSE_MARKER.finditer(body):
        seg = body[last_end:m.end()].strip()
        if seg:
            units.append((m.group(1), seg))
        last_end = m.end()
    tail = body[last_end:].strip()
    if tail:
        units.append((str(len(units) + 1), tail))
    return units


def to_mula_items(units):
    return [{"id": f"unit_{n:04d}", "reference": ref, "sanskrit_text": body}
            for n, (ref, body) in enumerate(units, 1)]


def to_tika_items(units, tika_title):
    return [{"id": f"unit_{n:04d}", "reference": ref, "tika_title": tika_title,
              "sanskrit_text": body}
            for n, (ref, body) in enumerate(units, 1)]


TARGET = "darshana/vedanta/vishishtadvaita/ramanuja_bhashya"
AUTHOR = "Sri Ramanujacharya"
SOURCE_NOTE = ("github.com/vishvasa/ramanujiyam (branch `content`); used with "
               "the explicit permission of its maintainer, Vishwas Vasukijah, "
               "given to the project lead directly (see PENDING.md).")


def run(only=None):
    root = ensure_clone()

    def do(slug, fn):
        if only and slug != only:
            return
        units = fn()
        if not units:
            print(f"  ~ {slug}: no units parsed")
            return
        print(f"{slug}: {len(units)} units")
        yield units

    if not only or only == "sri_bhashya":
        units = collect_grid(root, "tattvam/rAmAnujaH/shrI-bhAShyam/mUlam/ma")
        items = to_tika_items(units, "Sri Bhashya")
        write_grantha(f"{TARGET}/sri_bhashya/bhashya", "grantha_tika_text", AUTHOR, items,
                       source_note=SOURCE_NOTE)
        print(f"sri_bhashya: {len(items)} units")

    if not only or only == "vedanta_dipa":
        units = collect_grid(root, "tattvam/rAmAnujaH/vedAnta-dIpaH/sarva-prastutiH")
        items = to_tika_items(units, "Vedanta Dipa")
        write_grantha(f"{TARGET}/vedanta_dipa/bhashya", "grantha_tika_text", AUTHOR, items,
                       source_note=SOURCE_NOTE)
        print(f"vedanta_dipa: {len(items)} units")

    if not only or only == "vedanta_sara":
        units = collect_grid(root, "tattvam/rAmAnujaH/vedAnta-sAraH/sarva-prastutiH")
        items = to_tika_items(units, "Vedanta Sara")
        write_grantha(f"{TARGET}/vedanta_sara/bhashya", "grantha_tika_text", AUTHOR, items,
                       source_note=SOURCE_NOTE)
        print(f"vedanta_sara: {len(items)} units")

    if not only or only == "vedartha_sangraha":
        units = collect_flat(root, "tattvam/rAmAnujaH/vedArtha-sangrahaH/mUlam")
        items = to_mula_items(units)
        write_grantha(f"{TARGET}/vedartha_sangraha/mula", "grantha_mula_text", AUTHOR, items,
                       source_note=SOURCE_NOTE)
        print(f"vedartha_sangraha: {len(items)} units")

    if not only or only == "sharanagati_gadyam":
        units = collect_verses(root, "kriyA/rAmAnujaH/sharaNAgati-gadyam/mUlam.md")
        items = to_mula_items(units)
        write_grantha(f"{TARGET}/gadya_traya/sharanagati_gadyam/mula", "grantha_mula_text",
                      AUTHOR, items, source_note=SOURCE_NOTE)
        print(f"sharanagati_gadyam: {len(items)} units")


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else None)
