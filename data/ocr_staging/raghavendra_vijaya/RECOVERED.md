# Raghavendra Vijaya — three Sanskrit tippanis, recovered from history

`recovered_tippani_master.json` was `local_drive/Raghavendra_Vijaya/raghavendra_vijaya_master_full.json`,
last seen in commit d224f622d6 before `local_drive/` was deleted. It was
generated on the lead's Android phone and pushed straight to the repository
with a token, which is why it never went through the normal importer.

It holds **578 records, one per shloka**, and the sarga counts match the live
work exactly — 42, 54, 58, 49, 44, 76, 49, 78, 62, 66 — so it aligns
one-to-one with `data/Tattvavada/Itara/Kavya/raghavendra_vijaya/sarga_*`.

What it carries that the live work does NOT:

| layer | populated of 578 |
|---|---|
| `mula_shloka.sandhi_split` | 570 |
| `commentaries.balabodhini` | 462 |
| `commentaries.gurupadaseva` | 370 |
| `commentaries.venkoba_tika` | 57 |
| `mangalacarana.*` (3 sets) | per sarga |

The live work today has only `pavamanacharya_english` (578) and three Gemini
layers labelled "unreviewed" (573 each). **All three Sanskrit tippanis and the
sandhi split are missing from the site.** The PDF this came from is
"Raghavendra Vijaya of Narayana Pandita with Three Tippani"; those three are
these.

So `local_drive/` in git history is NOT redundant, and purging history before
these are merged would destroy the only copy. That is why this file is here.

Not yet merged into the work because merging is a content decision: 462 / 370 /
57 is uneven coverage, and a commentary that is present for some shlokas and
absent for others needs a display rule before it goes live, not after.

No pratika boldening and no bidirectional links are present in this file
(0 bold markers). The structure supports both — separate commentary fields
per shloka — but neither has been applied yet.
