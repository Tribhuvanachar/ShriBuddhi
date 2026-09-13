# Files from Tribhuvanachar/bhumandala (Buddhi) that reached none of the new repositories

Snapshot taken 13 Sep 2026 from bhumandala commit `054e9a414` (9 Sep 2026, the last state
before the restructuring) after a content-level sweep: every file blob of that commit was
looked for in ShriBuddhi, BrahmaBuddhi, ParaBuddhi and today's Buddhi main, by content and
then by path. Of 24,797 files, 58 had no home. These are the ones worth keeping; paths are
in the flattened layout (`dge/…` → `…`).

| Here | What it is | Why it matters |
|---|---|---|
| `HANDOFF.md` | The 7 Sep session handoff: standing rules (§3), where state lives, what shipped | ParaBuddhi's MIGRATION_LOG says it "needs human judgment (split, don't delete)" — it was dropped from Buddhi and not copied anywhere |
| `data/dasa_sahitya/_dump/` | The raw Dāsa Sāhitya fetch (`dasa_sahitya.jsonl`, 9.4 MB; `_full.txt`; `COUNTS.txt`; `pending_review.json`) | `admin/dasa-capture.html` (now in BrahmaBuddhi) reads `_dump/pending_review.json` and writes `_dump/manual_captures.json`; the capture queue needs this folder wherever `data/dasa_sahitya` lives |
| `data/dasa_sahitya/{dasakuta,vyasakuta,…}/_meta.json`, `data/…/SarvaMula/stotra/_meta.json`, `data/…/SetuTila/_meta.json` | Folder descriptions for the library tree | Small; the folders they describe were restructured — keep if the folders come back |
| `images/genie/favicon-{16,32,96,512}.png`, `images/icon-*.png`, `images/guru/pranam-blessing.gif`, `images/TemplateA.png`, `images/template-01-jade-meander.jpg` | Favicons and UI icons | Buddhi kept only favicon-48/192 and the mp4; if any page still references these sizes they 404 |

Not kept, on purpose: the 16 `dasa_sahitya/vyasakuta/**/data.json` (all 0 items — empty
placeholders from the taxonomy restructure), `dge/legacy/PrahladaKrutaNarasimhaStotra.html`
and `patches/*` (deleted deliberately per MIGRATION_LOG), and 190 files that exist under a
new path (pages/, data/DvaitaVedanta/Itara/…, content/) with edits.
