#!/usr/bin/env python3
"""
build_search_index.py — offline global-search index generator for DGE.

Fits the existing `veda_toolkit` pattern: a standalone Python script run locally
(or in Colab), NOT part of the live static app. It walks `data/`, reads each
grantha's `data.json`, and emits a compact STATIC index the browser loads on
demand. No backend — this is what makes corpus-wide fuzzy search possible on a
GitHub Pages site.

It reuses DGE's own conventions:
  * `schemas.json :: <schema>.primaryTextField` tells us which field holds the
    main searchable text (null => text lives in a nested array, which we flatten).
  * handles BOTH data shapes: new `{schema, items:[...]}` and legacy
    `{metadata, shlokas:{n:{...}}}`.
  * prefers an unaccented `*_plain` field when present (e.g. samhita_patha_plain).
  * cross-references come from each item's `references:[{target,unit_id,note}]`;
    we invert them into a global backlinks index ("what cites this verse").

Sanskrit-aware matching: every unit's text is canonicalized to SLP1 and folded
into a phonetic key (pkey) and coarse key (ckey) by the shared normalizer
(search_toolkit_pkg/, the tested reference core). The SAME fold runs in the
browser at query time (js/dge-normalize.js), so index and query always agree.

Emitted artifacts (all under --out):
  manifest.json                catalog: granthas, categories, unit counts, the
                                section list (manifest.sections), and per-trigram
                                GLOBAL document frequency (manifest.df)
  units/<slug>.json            per-grantha units: {u, pk, ck, s(nippet)}
  postings/<trigram>/<section>.json
                                one file per (trigram, section) pair:
                                [ [granthaIdx, unitIdx], ... ], holding only
                                that trigram's postings within that section.
                                An unscoped query fans out across every
                                section's file for a trigram in parallel; a
                                scoped query reads only its own section.
                                (trigram directory name is percent-safe --
                                see safe_trigram_filename())
  backlinks.json               target#unit_id -> [ {from, note}, ... ]

Usage:  python3 build_search_index.py --data data --out search_index
"""
from __future__ import annotations
import argparse, json, os, re, sys, unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from search_toolkit_pkg.translit import to_slp1
from search_toolkit_pkg.normalize import phonetic_key, coarse_key, trigrams

# Vedic accent marks + nasal sign: strip/normalize before transliteration,
# mirroring the app's own dgePrepareForScript() so keys match display text.
_VEDIC_MARKS = re.compile(r"[॒॑᳐-᳿]")
_HTML_TAG = re.compile(r"<[^>]+>")
_ZERO_WIDTH = re.compile(r"[​-‍﻿]")


_DEVANAGARI = re.compile(r"[ऀ-ॿ]")   # this corpus stores text in Devanagari


# ---- Indic-script fold: Kannada / Telugu / Malayalam -> Devanagari --------
# These blocks share the Devanagari block's layout codepoint-for-codepoint
# for every letter, matra and sign this corpus uses, so a plain block
# transposition (after NFC) yields correct Devanagari for INDEXING.
# Reported live (31 Aug 2026): the entire Kannada-script Yuktimallika
# (DvaitaVedanta/Itara/DasaSahitya/vyasakuta/vadiraja_tirtha, 5,542 units -- "ಭಕ್ತ್ಯಾ ಸ್ತುತ್ಯಾ...")
# was dropped by the has_devanagari stub gate below, so स्तुत्या could never
# find it. The fold runs only when a unit has no Devanagari of its own, and
# only feeds pk/ck/postings -- the stored snippet keeps the original script,
# since a reader of a Kannada grantha expects Kannada on screen.
_INDIC_FOLD_BLOCKS = (0x0C80, 0x0C00, 0x0D00)  # Kannada, Telugu, Malayalam


def fold_indic_to_devanagari(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "")
    out = []
    for ch in t:
        cp = ord(ch)
        for base in _INDIC_FOLD_BLOCKS:
            if base <= cp < base + 0x80:
                ch = chr(cp - base + 0x0900)
                break
        out.append(ch)
    return "".join(out)


def has_devanagari(text: str) -> bool:
    """True only for real Devanagari content — excludes template stubs like
    'Sanskrit text goes here...' and non-Devanagari-script text (e.g. Kannada
    dāsa-sāhitya, which needs a Sanscript pass in the real toolkit)."""
    return bool(_DEVANAGARI.search(text or ""))


def clean_devanagari(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    t = _HTML_TAG.sub(" ", t)          # legacy shlokas embed <br> etc.
    t = t.replace("ꣳ", "ं")  # ꣳ -> anusvara
    t = _VEDIC_MARKS.sub("", t)        # drop udatta/anudatta/svarita
    t = _ZERO_WIDTH.sub("", t)
    t = re.sub(r"[।॥\|]+", " ", t)     # dandas -> space
    return re.sub(r"\s+", " ", t).strip()


def snippet(text: str, n: int = 4000) -> str:
    """Stored verbatim (Devanagari, not the pk/ck folded keys) so the CLIENT
    can locate the actual match and center a short excerpt on it at render
    time — impossible to do here, since the query hasn't been typed yet. A
    fixed-position prefix (this used to be text[:140]) only ever highlighted
    a match that happened to fall in a unit's first 140 characters; most
    units are short verses where that was true by luck, but any longer
    commentary/tika paragraph with its match further in silently showed an
    unrelated, unhighlighted prefix instead — confirmed directly: a real,
    exact match at character 758 of a 797-character unit. The cap is a
    guard against the rare pathologically long unit, not a normal ceiling
    — the overwhelming majority of units are far shorter and are stored in
    full. n=4000 (was 2000): the pk/ck keys are capped at MAX_KEY=2500
    FOLDED chars, and Devanagari spends more codepoints per sound than the
    folded SLP1 (matras, viramas, geminates the fold collapses), so a
    2000-char snippet could END before the pk did — a word-index hit found
    near the pk's tail then had no snippet text to display, highlight, or
    pass the exact post-filter with. 4000 Devanagari chars comfortably
    covers 2500 folded chars.
    """
    t = clean_devanagari(text)
    return t[:n]


def load_schemas(data_dir: str) -> dict:
    with open(os.path.join(data_dir, "schemas.json"), encoding="utf-8") as f:
        return json.load(f)


def primary_field(schemas: dict, schema_name: str):
    s = schemas.get(schema_name, {})
    return s.get("primaryTextField")


def _flatten_text_field(v, _depth=0):
    """Coerce a schema's primaryTextField value into one plain string.

    Normally already a string -- but dāsa-sāhitya's `dasa_pada_text` schema
    turned out to store its `text` field as {script: [[line, ...], ...]}
    instead (most padas have no "devanagari" variant at all, only
    "kannada"). Passing that dict straight to clean_devanagari() crashed
    unicodedata.normalize() on the FIRST such grantha the walk met, which
    took build()'s single pass down for every grantha still to come, not
    just this one -- silently leaving the corpus-wide search index every
    reader's search depends on built from before whatever last change
    introduced this shape, with no error visible anywhere a reader would
    see it. Flattening here instead lets has_devanagari()'s existing
    stub-skip rule decide per unit as it always has: a pure-Kannada string
    still isn't Devanagari, so it's still correctly skipped as a stub --
    this fixes the crash, not the Kannada-script indexing gap itself,
    which is a separate, larger problem (dāsa-sāhitya needs a transliteration
    pass, not just a bugfix, to become searchable in its own script).
    """
    if _depth > 4:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        for key in ("devanagari", "sa", "sanskrit"):
            flat = _flatten_text_field(v.get(key), _depth + 1)
            if flat:
                return flat
        for val in v.values():
            flat = _flatten_text_field(val, _depth + 1)
            if flat:
                return flat
        return ""
    if isinstance(v, list):
        parts = [p for p in (_flatten_text_field(e, _depth + 1) for e in v) if p]
        return "\n".join(parts)
    return ""


def extract_text(item: dict, pfield, schema_name: str, commentaries=False) -> str:
    """Return the best searchable Devanagari text for one unit.

    `commentaries` also folds in what each shloka's bhashya[] carries. Off by
    default: that is where the Sanjivini, Sayana and Medhatithi live, so it is
    the difference between finding a verse and finding what was said about it,
    and it costs index size in proportion.
    """
    # prefer an explicit unaccented *_plain variant of the primary field
    if pfield:
        plain = f"{pfield}_plain"
        flat = _flatten_text_field(item.get(plain))
        if flat:
            return flat
        flat = _flatten_text_field(item.get(pfield))
        if flat:
            return flat
    # primaryTextField is null -> nested-array schemas; try common holders
    bhashya = []
    if commentaries:
        for e in item.get("shlokas") or []:
            if not isinstance(e, dict):
                continue
            for b in e.get("bhashya") or []:
                if isinstance(b, dict) and b.get("text"):
                    bhashya.append(b["text"])
            if e.get("artha"):
                bhashya.append(e["artha"])

    for key in ("shlokas", "verses", "lines", "text", "sanskrit_text",
                "mula_text", "samhita_patha", "sa"):
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, list) and v:
            parts = []
            for e in v:
                if isinstance(e, str):
                    parts.append(e)
                elif isinstance(e, dict):
                    # sanskrit_text and sa are what DGE's own granthas use --
                    # every shloka of every itihasa, purana, kavya and stotra.
                    # Without them this returned "" for each one, so a chapter
                    # of the Ramayana indexed as an empty stub and corpus
                    # search could never have found a verse in it. The two
                    # names above stay first so nothing that works today
                    # changes.
                    parts.append(e.get("text") or e.get("sanskrit")
                                 or e.get("sanskrit_text") or e.get("sa") or "")
            if any(parts) or bhashya:
                return " ".join(parts + bhashya)
    return " ".join(bhashya)


def iter_units(data: dict, pfield, schema_name: str, commentaries=False):
    """Yield (unit_id, devanagari_text, references) for BOTH data shapes."""
    if isinstance(data.get("items"), list):                 # new shape
        for it in data["items"]:
            if not isinstance(it, dict):
                continue
            uid = str(it.get("id", ""))
            txt = extract_text(it, pfield, schema_name, commentaries)
            yield uid, txt, it.get("references") or []
    elif isinstance(data.get("shlokas"), dict):             # legacy shape
        for uid, it in data["shlokas"].items():
            if not isinstance(it, dict):
                continue
            txt = it.get("sa") or it.get("sanskrit_text") or it.get("text") or ""
            yield str(uid), txt, it.get("references") or []


def grantha_slug(data_dir: str, path: str) -> str:
    rel = os.path.relpath(os.path.dirname(path), data_dir)
    return rel.replace(os.sep, "/")


def category_of(slug: str) -> str:
    return slug.split("/", 1)[0] if slug else "unknown"


"""Word-index tokenizer contract (mirrored EXACTLY by dge-search.js's
wordTokens/wordBucket -- test-parity.js asserts the tokenizer half):

  * split on ANY char outside [0-9A-Za-z] plus ॐ -- not just
    whitespace/hyphen. Measured against the real corpus (Fable review,
    30 Aug 2026): 5.6% of postings (412k) carried punctuation baked into
    the token ("[sriyan", "`devya", "(nahahavi", bare ","/"()") under a
    whitespace-only split, making those words unfindable by exact lookup
    forever. ॐ is kept: it is a real, queryable word of one char.
  * pure-digit tokens are dropped (8,557 of them in the corpus): verse
    numbers, not vocabulary.
"""
_WORD_SPLIT = re.compile(r"[^0-9A-Za-zॐ]+")
_PURE_DIGITS = re.compile(r"^[0-9]+$")


def word_tokens(pk: str):
    """Split a unit's (or a query's) phonetic key into whole-word tokens for
    the EXACT word-level index -- a second, separate index alongside the
    trigram one, built to answer a different question. Trigram postings
    answer "which units share this 3-letter fragment", which is what makes
    fuzzy/typo-tolerant matching possible but is fundamentally imprecise at
    corpus scale: a common query's fragments (e.g. "kan"/"nta"/"tay" for
    kAntAya) are each shared by tens of thousands of units, so an exact
    query drowns in ties the trigram system alone can never fully resolve
    without either opening most of the corpus or arbitrarily capping how
    much it looks at (see SEARCH_ARCHITECTURE.md's postscript on this).
    A word index instead answers "which units contain this EXACT token",
    which is a MUCH more selective question -- a real word occurs in a
    bounded, usually small number of units, so there is no tie to break and
    no shard-open budget needed to find it.

    Splits on punctuation and hyphen as well as whitespace (see the
    tokenizer-contract comment above _WORD_SPLIT). This is deliberately NOT
    how phonetic_key()'s own pk field is tokenized elsewhere
    (dge-normalize.js's normalizeQuery().words splits on whitespace only)
    -- changing that would ripple into the existing trigram/fuzzy scoring
    and its parity test, which this only-additive index doesn't need to
    touch."""
    return [t for t in _WORD_SPLIT.split(pk) if t and not _PURE_DIGITS.match(t)]


def bucket_key(word: str, depth: int) -> str:
    """Case-safe, filesystem/URL-safe bucket name from a word's first
    `depth` chars. pkey retains uppercase (aspirates K/G/C/J/T/D/P/B,
    diphthongs E/O -- 'Bavati' is one of the corpus's most common tokens),
    and 'Ba' vs 'ba' are DIFFERENT buckets that a case-insensitive
    filesystem (macOS/Windows checkout of search-dist, or a local build
    there) would silently merge -- the same latent landmine the trigram
    tree has always carried, not repeated here. Each uppercase letter
    encodes as lowercase + '-' ('Ba' -> 'b-a', 'ba' -> 'ba'), so no two
    distinct buckets collide case-insensitively. Anything outside
    [0-9A-Za-z] (ॐ, corpus mojibake) maps to '_', same spirit as
    safe_trigram_filename(). Mirrored exactly by dge-search.js
    bucketKey()."""
    out = []
    for ch in word[:depth]:
        if "0" <= ch <= "9" or "a" <= ch <= "z":
            out.append(ch)
        elif "A" <= ch <= "Z":
            out.append(ch.lower() + "-")
        else:
            out.append("_")
    return "".join(out) or "_"


# Adaptive bucket depth (Fable review, 30 Aug 2026, measured against the
# real corpus): fixed 2-char buckets fail the ~1MB-per-file budget (sa/
# darshana hit 4.76MB raw), and even fixed 3-char still fails (pra/darshana
# 3.22MB, 65,707 words in one file) -- the fat buckets are vocabulary-
# driven, so no per-word cap helps. Fixed 4-char works but costs ~114k
# files. The measured sweet spot: START at 2 chars, deepen only the few
# buckets whose GLOBAL (cross-section) size exceeds this threshold to 3,
# and any still-oversized 3-char bucket to 4 -- lands at ~13k files, max
# file ~0.86MB, with a deepening map of only a few dozen entries shipped
# in manifest.json for the client to consult.
WORD_BUCKET_DEEPEN_BYTES = 1_000_000


_UNSAFE_TG_CHARS = re.compile(r"[^0-9A-Za-z^$]")


def safe_trigram_filename(tg: str) -> str:
    """The literal on-disk/in-git filename for one trigram's postings file.
    One file per TRIGRAM, not per 2-char prefix -- see the "one file per
    trigram" note in SEARCH_ARCHITECTURE.md: filing by the first two
    characters put every "ram"/"ran"/"raj"/... trigram in one multi-MB file
    that a query for any of them had to download whole (16 MB for a राम
    search). A query now fetches exactly the trigram files it needs.

    Real trigrams are always drawn from {A-Za-z^$} (search_toolkit_pkg
    .normalize.trigrams pads with ^/$ at word boundaries) -- every one of
    those is already a safe literal filename on any filesystem/git, so they
    are used as-is, NOT percent-encoded here. The client (dge-search.js
    safeTrigram()) percent-encodes ^ and $ only when building the fetch URL,
    the same way any URL references a file whose name contains characters
    special to URLs but not to filesystems; the CDN decodes that back to
    this exact literal name. Baking a custom "%XX" escape into the filename
    ITSELF, instead, was tried first and was a real bug: a browser's fetch()
    percent-DEcodes "%XX" sequences in a URL before requesting it, so a
    filename already containing a literal "%" was requested as something
    else entirely and 404'd. Only a genuinely unexpected character (none
    should occur) falls back to '_', same spirit as the old bucket_of()."""
    return _UNSAFE_TG_CHARS.sub("_", tg) or "_"


def build(data_dir: str, out_dir: str, extra_dirs=(), commentaries=False) -> dict:
    schemas = load_schemas(data_dir)
    os.makedirs(os.path.join(out_dir, "units"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "postings"), exist_ok=True)

    granthas = []                       # manifest rows
    postings = defaultdict(lambda: defaultdict(list))  # trigram -> section -> [[gi,ui], ...]
    # word -> section -> [[gi,ui], ...] -- the EXACT index (see word_tokens()'s
    # own docstring for why this exists alongside, not instead of, postings).
    word_postings = defaultdict(lambda: defaultdict(list))
    backlinks = defaultdict(list)       # "target#unit_id" -> [{from, note}]
    stats = {"granthas": 0, "populated": 0, "units": 0, "unit_chars": 0,
             "refs": 0, "skipped_stub_units": 0, "skipped_stub_granthas": 0,
             "folded_indic_units": 0, "truncated_units": 0,
             "distinct_trigrams": 0, "distinct_words": 0}

    # (root, path) pairs: the slug is relative to the root the file came from,
    # so a corpus indexed from elsewhere still slugs as though it sat in
    # data. That is what lets the Kavya corpus be searchable while its 50 MB
    # stays on the kavya-dist branch: pass the checkout with --extra-data, and
    # core.js resolves a kavya_alankara/ grantha to the CDN when the hit is
    # opened.
    data_files = []
    for base in [data_dir, *extra_dirs]:
        found = []
        for root, _dirs, files in os.walk(base):
            if "data.json" in files:
                found.append((base, os.path.join(root, "data.json")))
        found.sort()
        if base is not data_dir:
            print(f"  + {len(found)} granthas from {base}")
        data_files.extend(found)

    for base, path in data_files:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  ! skip {path}: {e}", file=sys.stderr)
            continue
        slug = grantha_slug(base, path)
        category = category_of(slug)
        schema_name = data.get("schema") or (
            "stotra_text" if "shlokas" in data else "generic")
        pfield = primary_field(schemas, schema_name)

        units = list(iter_units(data, pfield, schema_name, commentaries))
        if not units:
            continue
        gi = len(granthas)
        title = (data.get("metadata", {}) or {}).get("title") or slug.split("/")[-1]
        unit_rows = []
        for uid, dev_text, refs in units:
            clean = clean_devanagari(dev_text)
            # skip template stubs / non-Devanagari placeholder text -- but a
            # unit written in an aligned Indic script (Kannada dasa-sahitya)
            # folds to Devanagari for indexing instead of being dropped.
            if not has_devanagari(clean):
                folded = clean_devanagari(fold_indic_to_devanagari(dev_text))
                if has_devanagari(folded):
                    clean = folded
                    stats["folded_indic_units"] += 1
                else:
                    stats["skipped_stub_units"] += 1
                    continue
            slp1 = to_slp1(clean, "devanagari")
            # cap indexed key length: enough to locate a passage, and it stops a
            # few very large merged/prose blocks from bloating the static index.
            # A truncated key drops its final token -- a severed half-word
            # would index as a "word" no one can type, and a query word that
            # happens to equal the severed half would false-match.
            MAX_KEY = 2500
            pk_full = phonetic_key(slp1)
            pk = pk_full
            if len(pk) > MAX_KEY:
                pk = pk[:MAX_KEY].rsplit(" ", 1)[0]
                stats["truncated_units"] += 1
            ck = coarse_key(slp1)[:MAX_KEY]
            ui = len(unit_rows)
            unit_rows.append({"u": uid, "pk": pk, "ck": ck, "s": snippet(dev_text)})
            stats["unit_chars"] += len(pk)
            # postings on pkey trigrams (candidate generation), partitioned
            # by section (see the "Partition the postings tree" note in
            # SEARCH_ARCHITECTURE.md): an unscoped/global query fans out
            # across every section's file for a trigram in parallel, and a
            # section-scoped query reads only its own partition -- neither
            # has to download postings for sections it doesn't care about.
            for tg in trigrams(pk):
                postings[tg][category].append([gi, ui])
            # Exact word-level postings (see word_tokens()'s own docstring).
            # Deduplicated per unit first -- a word repeated within one verse
            # (rare, but real) would otherwise post the same [gi,ui] pair
            # more than once for no benefit, just a bigger file.
            # Word postings come from the FULL key, not the capped one: an
            # exact word lookup needs no pk verification afterwards, and
            # capping here made every word past ~2,500 chars of a mega-unit
            # unfindable -- reported live (1 Sep 2026): गुरुराजेन sits at
            # ~7,000 chars into three 8-20K-char Vakyartharatnamala units
            # and exact search returned zero. Trigram postings stay on the
            # capped pk deliberately -- the fuzzy scorer can only verify a
            # candidate against the STORED pk, so posting beyond it would
            # manufacture candidates the scorer must always reject.
            for w in set(word_tokens(pk_full)):
                word_postings[w][category].append([gi, ui])
            # cross-references -> backlinks
            for r in refs:
                if isinstance(r, dict) and r.get("target"):
                    key = f"{r['target']}#{r.get('unit_id','')}"
                    backlinks[key].append(
                        {"from": f"{slug}#{uid}", "note": r.get("note", ""),
                         "type": r.get("type", "reference")})
                    stats["refs"] += 1

        # a grantha with no real Devanagari units is an empty taxonomy stub — skip it
        if not unit_rows:
            stats["skipped_stub_granthas"] += 1
            continue

        # write per-grantha unit shard
        shard_name = slug.replace("/", "__") + ".json"
        with open(os.path.join(out_dir, "units", shard_name),
                  "w", encoding="utf-8") as f:
            json.dump(unit_rows, f, ensure_ascii=False, separators=(",", ":"))

        granthas.append({
            "gi": gi, "slug": slug, "title": title, "schema": schema_name,
            "category": category_of(slug), "units": len(unit_rows),
            "populated": True, "shard": f"units/{shard_name}",
        })
        stats["granthas"] += 1
        stats["units"] += len(unit_rows)
        stats["populated"] += 1

    # write one postings file per (TRIGRAM, SECTION) pair -- see
    # safe_trigram_filename() for the trigram-as-filename half, and the
    # "Partition the postings tree" comment above for the section half. Each
    # file is just the [[gi,ui],...] list for that trigram within that one
    # section; the path already identifies both, so there is no wrapping dict.
    df = {}       # trigram -> GLOBAL posting count (all sections), i.e. document frequency
    sections = set()
    for tg, by_section in postings.items():
        tg_dir = os.path.join(out_dir, "postings", safe_trigram_filename(tg))
        os.makedirs(tg_dir, exist_ok=True)
        total = 0
        for section, rows in by_section.items():
            sections.add(section)
            with open(os.path.join(tg_dir, f"{section}.json"),
                      "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
            total += len(rows)
        df[tg] = total
    stats["distinct_trigrams"] = len(df)

    # write one file per (BUCKET, SECTION) pair for the exact word index --
    # unlike trigram postings (one file per trigram, since a real query
    # only ever needs its rarest 2-3), an exact query looks up EVERY one of
    # its own words directly, so the file has to be found by a cheap,
    # deterministic function of the word alone (bucket_key() + the
    # deepening map below) rather than by picking among many small files.
    # Each file holds every word sharing that bucket+section as one dict,
    # so a query fetches exactly one file per (distinct bucket, section)
    # its words touch. Bucket depth is ADAPTIVE (see
    # WORD_BUCKET_DEEPEN_BYTES): estimate each 2-char bucket's global raw
    # size; the few oversized ones deepen to 3 chars, any still-oversized
    # of those to 4 -- the deepening decisions ship in manifest.json as
    # wordBucketDeepen (a {prefix: 1} presence-set the client walks:
    # 2-char key present -> use 3 chars; that 3-char key also present ->
    # use 4).
    def est_bytes(w, by_section):
        # close-enough serialized size: word key + ~12 bytes per posting row
        return len(w) + 4 + sum(12 * len(rows) for rows in by_section.values())

    size2 = defaultdict(int)
    for w, by_section in word_postings.items():
        size2[bucket_key(w, 2)] += est_bytes(w, by_section)
    deepen = {}   # prefix-key -> 1 (presence means "go one char deeper")
    size3 = defaultdict(int)
    for w, by_section in word_postings.items():
        k2 = bucket_key(w, 2)
        if size2[k2] > WORD_BUCKET_DEEPEN_BYTES:
            deepen[k2] = 1
            size3[bucket_key(w, 3)] += est_bytes(w, by_section)
    for k3, sz in size3.items():
        if sz > WORD_BUCKET_DEEPEN_BYTES:
            deepen[k3] = 1

    def word_bucket_final(w):
        k2 = bucket_key(w, 2)
        if k2 not in deepen:
            return k2
        k3 = bucket_key(w, 3)
        return bucket_key(w, 4) if k3 in deepen else k3

    word_buckets = defaultdict(lambda: defaultdict(dict))  # bucket -> section -> {word: rows}
    for w, by_section in word_postings.items():
        b = word_bucket_final(w)
        for section, rows in by_section.items():
            word_buckets[b][section][w] = rows
    os.makedirs(os.path.join(out_dir, "words"), exist_ok=True)
    for b, by_section in word_buckets.items():
        b_dir = os.path.join(out_dir, "words", b)
        os.makedirs(b_dir, exist_ok=True)
        for section, word_map in by_section.items():
            with open(os.path.join(b_dir, f"{section}.json"),
                      "w", encoding="utf-8") as f:
                json.dump(word_map, f, ensure_ascii=False, separators=(",", ":"))
    stats["distinct_words"] = len(word_postings)
    stats["word_buckets_deepened"] = len(deepen)

    # vocab/<i>.txt -- the complete sorted vocabulary as plain newline-
    # separated text, split into VOCAB_CHUNKS sequential files. This is the
    # substring-recall layer the word index alone cannot provide: a query
    # word buried in the MIDDLE or at the END of a compound (nilakAntAya,
    # divyakAntAya for a kAntAya query) lives in the compound's own bucket,
    # which a lookup keyed on the query's prefix never fetches. Scanning
    # the corpus for substrings is out of the question (300MB+), but the
    # VOCABULARY is small (~34MB raw, ~10MB gzipped over the CDN, fetched
    # once and then HTTP-cached against this immutable commit-pinned URL):
    # the client greps this word list for containment, then jumps straight
    # to the matched words' bucket postings -- exhaustive substring recall
    # at exact-lookup precision. Plain text, not JSON: best compression,
    # trivial split('\n') parse. Chunked so the client can fetch in
    # parallel and surface matches progressively as chunks land.
    VOCAB_CHUNKS = 16
    vocab_sorted = sorted(word_postings.keys())
    os.makedirs(os.path.join(out_dir, "vocab"), exist_ok=True)
    per_chunk = (len(vocab_sorted) + VOCAB_CHUNKS - 1) // VOCAB_CHUNKS
    vocab_bytes = 0
    for i in range(VOCAB_CHUNKS):
        chunk = vocab_sorted[i * per_chunk:(i + 1) * per_chunk]
        blob = "\n".join(chunk)
        vocab_bytes += len(blob.encode("utf-8"))
        with open(os.path.join(out_dir, "vocab", f"{i}.txt"),
                  "w", encoding="utf-8") as f:
            f.write(blob)
    stats["vocab_bytes"] = vocab_bytes
    # bucket_key() encodes case into the name, but assert the guarantee
    # anyway -- a future naming change that reintroduces the trigram tree's
    # case-collision landmine should fail the build, not corrupt a macOS/
    # Windows checkout silently.
    lowered = defaultdict(list)
    for b in word_buckets:
        lowered[b.lower()].append(b)
    for lb, names in lowered.items():
        assert len(names) == 1, f"case-colliding word buckets: {names}"

    # df is the GLOBAL (cross-section) posting count -- still what decides
    # which trigrams are rarest and therefore worth fetching (see
    # SEARCH_ARCHITECTURE.md "What does fix it"); the section partition only
    # changes WHICH FILES answer a chosen trigram, not which trigrams get
    # chosen, so an unscoped search still needs just the df table, and a
    # scoped one already knows its one section without ranking across them.
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"granthas": granthas, "df": df,
                   "sections": sorted(sections), "stats": stats,
                   "wordBucketDeepen": deepen,
                   "vocabChunks": VOCAB_CHUNKS},
                   f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "backlinks.json"), "w", encoding="utf-8") as f:
        json.dump(backlinks, f, ensure_ascii=False, separators=(",", ":"))

    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="bhumandala/data")
    ap.add_argument("--out", default="search_index_out")
    ap.add_argument("--commentaries", action="store_true",
                    help="also index each shloka's bhashya[] and artha -- the "
                         "commentaries themselves, at a size cost")
    ap.add_argument("--extra-data", action="append", default=[],
                    metavar="DIR",
                    help="another data root to index, slugged relative to "
                         "itself (e.g. a kavya-dist checkout)")
    args = ap.parse_args()
    stats = build(args.data, args.out, args.extra_data, args.commentaries)
    print("Index built. Stats:")
    for k, v in stats.items():
        print(f"  {k:18} {v}")


if __name__ == "__main__":
    main()
