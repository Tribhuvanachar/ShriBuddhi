# Recovered from `local_drive/`, before that path is purged from history

`local_drive/` was deleted from the working tree but is still in git history,
where it costs about 57 MB across its versions. The obvious move is to purge
it. **Do not** — two of its files hold content that is not anywhere else.

Both were generated on the lead's Android phone and pushed straight to the
repository with a token, so neither went through an importer that would have
merged them into `data/`. The consolidation that removed `local_drive/` took
the folder, not the content.

## panini_dhatu_master.json — 2,290 dhatus (5.6 MB)

`local_drive/Panini_Dhatu/data.json` at commit b1cf87a6fd.

`data/vedanga/vyakarana/dhatu_lexicon/data.json` has 2,229 entries carrying
only `id, meanings, model, pedagogy, sources_used`. This file has 2,290
entries carrying, for every one of them:

    aupadeshika  stripped_root  gana  pada  it_status  transitivity
    canonical_dhatvartha  dhaturupanandini (2,289)  vritti_extracts (2,289)

**331 dhatu_ids are in this file and not in the live lexicon** (01.0933
onward). The live lexicon has 270 the file does not, so neither is a superset
— they need merging, not replacing.

## ../raghavendra_vijaya/recovered_tippani_master.json — see RECOVERED.md there

Three Sanskrit tippanis and the sandhi split for all 578 shlokas. None of it
is on the live work.

## The rule this is an instance of

History is the backup of last resort for anything pushed straight to the
repository rather than imported. Before purging ANY path from history, read
what is in it and confirm the content exists elsewhere. `dge/`,
`_migration/patches/` and `kamadhenu_dataset/text_index.json` have not been
checked this way yet.
