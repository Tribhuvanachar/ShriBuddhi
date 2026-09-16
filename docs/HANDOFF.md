# HANDOFF — written 16 Sep 2026, ~12:40 pm IST

This replaces the 7 Sep handoff, which is stale. One long session ends here. Everything it did is
pushed; nothing lives only in chat. Go-live is **~28 Sep 2026** (moved from the 17th).

From here the work splits into **three sessions**, by the lead's decision:

| Session | Owns |
|---|---|
| **A — Pratīka & formatting** | `format_commentary.py`, the P1/P2 rules, the commentary contract |
| **B — OCR workflows** | Sarvam / Vision / archive.org runs, staging branches, layer merges |
| **C — Buddhi & go-live** | the public repo, the catalogue, the footer, deploys |

Each section below says what is done, what is next, and what only the lead can decide.

---

## 0. Paste-ready opening prompt

> Read `docs/HANDOFF.md` first, then the files it names. I am running session **[A / B / C]** — work
> only that section unless I say otherwise. Standing rules in §5 apply to everything. Report times in
> IST. Ask me only for decisions that are mine: money, publishing, deleting data, and anything that
> changes the public repository.

---

## 1. State of the branches

| Repo / branch | Where it is |
|---|---|
| `ShriBuddhi/main` | green. Workflow repairs, the mirror-deletion fix across 19 workflows, `audit_library.py` licence preservation |
| `ShriBuddhi/catalogue-repair` | **open, awaiting the lead's review.** The catalogue repair + the full provenance strip + the tools written since. Not merged |
| `ShriBuddhi/ocr-staging/manimanjari` | Sarvam + Vision pages, and the three split layers |
| `ParaBuddhi/main` | custody of all provenance removed from the public data |
| `Buddhi` | untouched this session |

`catalogue-repair` is the one thing needing a decision before anything else lands on top of it:
https://github.com/Tribhuvanachar/ShriBuddhi/compare/main...catalogue-repair

---

## 2. Session A — pratīka and formatting

**Done.** A scholar reported twelve pratīkas as untagged. All twelve were tagging correctly all along —
six by P1C, eight by P2, fourteen tags across twelve lines. Two things made a working formatter look
broken, and both now have tests:

- `format_commentary.py` **without `--corpus` reads its input as prose** — handed a `data.json` it
  formats the braces and the `"items":` key, and the pratīka rules never see a Sanskrit sentence.
- `--corpus` **without `--in-place` writes nothing** while printing `12 units, 12 changed`.

The correct invocation is `--corpus --in-place`. Run once without `--in-place` to read the report.

**Fixed defect:** corpus mode called `format()`, which always ran the paragraph wrapper, so every unit
it touched had `<p class="rule">` written *into* its stored text. `format(paragraphs=False)` now.

**Next:** the Kannada explanation for the scholar is written (`ಪ್ರತೀಕ-ಟ್ಯಾಗ್-ವಿವರಣೆ.md`, delivered to the
lead). Optional: drop `त्यर्थः` from the Pattern-2 suffix list — it produced two gloss false positives
over 40 characters.

---

## 3. Session B — OCR

### Maṇimañjarī — three layers staged, one more parsed

Author **श्रीनारायणपण्डिताचार्यः**. Two commentators, confirmed by the lead: **Rāghavendrācārya**
(Sanskrit + Kannada) and **Chalāri Ācārya** (Gūḍhabhāvaprakāśikā).

| layer | units | from |
|---|---|---|
| `mula` | 305 | Sarvam, `tools/split_manimanjari_layers.py` |
| `tika_raghavendra_sanskrit` | 306 | same |
| `tika_raghavendra_kannada` | 306 | same |
| `tika_chalari` | 300 | a keyed .docx, `tools/parse_chalari_manimanjari.py` |

**Verse counts agree across two independent sources in seven sargas of eight:**
31, 32, 31, 39, 51, **52 / 51**, 29, 41. Sarga 6 is the disagreement — worth one look at the page.

Three things about that scan, all named in the tools' `--report`:

- **The PDF photographs three leaves twice** (folio ६४ is PDF page 183 *and* 185, twice more later).
  Each repeat invented ~4 verses.
- **Verse 4.30 has its gloss but no verse** — the scan read its mūla in Kannada glyphs.
- The Chalāri .docx is a **normalised edition, not diplomatic**: it splits sandhi the book prints
  joined, adds hyphens and avagraha, writes anusvāra as the conjunct nasal. Substance matches.

### Rukmiṇīśa Vijaya — not in the corpus, being brought in

Vādirāja's text with **Nārāyaṇa Bhaṭṭa's Gurubhāvaprakāśikā**. **19 sargas.** 2019 print, no licence
stated, so it follows the case-by-case discipline — the record goes to ParaBuddhi.

**The page map matters and is not obvious.** The scan has unnumbered pages the book does not count,
and the offset *grows*:

| PDF | 26 | 30 | 100 | 200 | 400 | 500 | 600 | 700 |
|---|---|---|---|---|---|---|---|---|
| printed | 8 | 10 | 72 | 166 | 348 | 434 | 528 | 624 |
| offset | +18 | +20 | +28 | +34 | +52 | +66 | +72 | +76 |

- Sanskrit text + commentary: **PDF 19 → 712** (printed 1 → 636)
- **PDF 713–724 is a Kannada appendix** — half-verses with Kannada meanings. Different content; do not
  run it with `sa-IN`.
- PDF total 725.

The dry-run confirmed **694 pages**, and refused: `cap is 200 (raise --max-pages deliberately)`.
So the real run goes in **four chunks**: `19-218`, `219-418`, `419-618`, `619-712`. Chunking also
isolates a failure to one quarter of the spend.

archive.org's own OCR is already staged as a **third engine to vote with** — free, 177 pages,
981,031 chars (`tools/fetch_archive_djvu.py`). It is *not* a reading of the book: it fails on
conjuncts, which is where the meaning is (पादचतुष्टय → पादचतुटय, विख्याताश्व → विख्याताइब).

### Dispatching a workflow from a session

`tools/dispatch_workflow.py` exists and `.claude/settings.json` permits it. **It does not work from a
Claude Code web session** — the environment's egress proxy refuses:

> HTTP 403 — Dispatching, enabling or disabling workflows … are not permitted for this session type.

That is not GitHub, not the token (which has `admin: true`), and not a Claude Code permission. Until a
session type allows it, the lead presses the button.

---

## 4. Session C — Buddhi and go-live

**`sarvamula.org` currently serves "coming soon."** Nothing public is broken; everything below is
pre-go-live work.

### Done, on `catalogue-repair`, awaiting review

- **27,201 items were on disk and unreachable** — 52 orphans, 34 dead catalogue links, 709 folders the
  browse tree never named. Now 0 / 0 / 0. Yuktimallikā's Kannada edition (5,542 verses), Svāpna-
  Vṛndāvana-Ākhyāna (2,355), Harikathāmṛtasāra (947), the Bhāgavata Saroddhāra set, eleven Aṣṭādhyāyī
  commentary layers.
- **No source, URL or licence anywhere in the published data** — 356 catalogue blocks and 321
  `data.json` files stripped, *after* being captured into ParaBuddhi. The footer Credits section is
  the single credit surface.
- 17 removed entries were `populated:false` placeholders (Rukmiṇīśa Vijaya, Chandrikā, Nyāyāmṛta under
  DasaSahitya). The lead confirmed these should not appear; a separate catalogue page will advertise
  what is coming.

### Decided by the lead, do not re-open

- **dvaitavedanta.in and Anandamakaranda are not to be credited.** The data will be modified before
  presentation. They are absent from the footer; leave it.
- **Do not merge Anandamakaranda / DvaitaVedantaIn into `Tattvavada/SarvaMula`.** The lead is doing
  that by hand, ShriBuddhi → BrahmaBuddhi → Buddhi.

### Still open

- **`BRAHMABUDDHI_TOKEN` cannot open pull requests.** It pushes fine; the PR step is allowed to fail
  and the run summary now says so with a compare link. Fix: add **Pull requests: Read and write** for
  BrahmaBuddhi at https://github.com/settings/personal-access-tokens — the token value does not change,
  so nothing needs re-pasting.
- **`reindex.yml`'s nightly schedule is off**, deliberately. Everything after its rebuild force-pushes
  330 MB to Buddhi's `search-dist` and bumps a jsDelivr pin; neither target exists any more, and
  Buddhi's `js/config.js` now reads `searchIndexBase`, `kavyaDataBase`, `wordnetDataBase` and
  `koshaDataBase` from the site itself. **Where the built index should be published now is a decision,
  not a guess to repeat nightly.** Restore the cron in the same breath as making it.
- `breadcrumb` (637 files, 18.4 MB) and `reference` (857 files, 17.7 MB) still carry the origin sites'
  navigation hierarchy. `js/core.js:838` reads `item.breadcrumb`, so removing it is a reader change.
  The harder half of that cutover — renumbering every unit id — **is already done**; no `DV_` id remains.

---

## 5. Standing rules

1. **Never** put a model identifier in a commit, PR, code comment or any artifact pushed to a repo.
2. You never see GitHub secrets. Never ask for a token to be pasted into chat.
3. Nothing from ParaBuddhi's `source/` is ever copied into a public repo, gist, artifact, issue or log.
4. Give a cost estimate and wait for the lead before any paid API run.
5. Staged OCR stays staged. A scholar reviews before anything merges into the corpus.
6. **Any workflow edit needs `python3 tools/build_repo_inventory.py` committed alongside it** — CI gates
   the manifest, and the admin page renders each workflow's form from it.
7. This clone's fetch refspec was single-branch and is now `+refs/heads/*:refs/remotes/origin/*`. If a
   pushed branch ever looks "unpushed", check the refspec before believing it.
8. Never `pkill -f "http.server"`. Never disable TLS verification or unset `HTTPS_PROXY`.

---

## 6. Longer-running items, not urgent

- Maṇimañjarī round 2 — the rest of the PDF beyond pages 122–312.
- Sarvam-vs-Vision **text** conflict pass on Maṇimañjarī (so far the two engines have only arbitrated
  the numbering, not the wording).
- The Sumadhva Vijaya commentary reconciliation: the Kāvya copy is verse-aligned and the better read,
  the `Itara/` copy has 4–15% more text (~160 KB). Reconcile before deleting either. Three folders
  there are colophon fragments, not commentaries.
- Yukti Mallika layer merge: the Kannada edition holds the only complete mūla, the Devanagari set the
  only Satyapramoda and Surottama ṭīkās. Neither is a duplicate.
- 277 Itara/Muṇḍaka ids still on placeholders.
- BrahmaBuddhi's mirror predates the recent merges; re-mirror when convenient.
