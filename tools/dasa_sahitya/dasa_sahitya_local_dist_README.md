# `dasa-sahitya-local-dist` — pending Dasa Sahitya local-asset imports

Data only, no history in common with `main`. Nothing reads this branch yet —
there is no `dasa_sahitya_local` UI. It exists so the imports collected here
stay reviewable via git without their size counting against `main`'s GitHub
Pages footprint, the same reason `wordnet-dist`, `kavya-dist` and
`search-dist` exist.

## Why it is not on main

The published site has very little headroom left under GitHub Pages' 1GB
ceiling (see `dge/search_index_dist_README.md` and
`dge/data/_wordnet`'s exclusion in `.gitignore` for the same story playing
out twice already). This tree grows with every new asset a session imports,
so it moved off `main` the first time it got large enough to matter — see
`dge/data/dasa_sahitya_local/ARCHITECTURE.md`'s "Publishing-size flag"
section for the reasoning at the time.

## What is in it

```
dasa1/                      -- Android app SQLite asset (dasa1.db), minus the
                                12 composers already merged into DvaitaVedanta/Itara/DasaSahitya/
collection_padagalu/        -- Firestore-style personal-collection export, ditto
raw_dump/                   -- flat JSON text dump, ditto
ALL_SOURCES_composer_registry.json  -- cross-source composer-identity review
ARCHITECTURE.md             -- the merge plan, category->form mapping, and why
                                these sources stay separate from DvaitaVedanta/Itara/DasaSahitya/
```

Each asset folder's own `index.json` carries a `note_confirmed_composers_
merged_out` field once composers have been promoted out of it, naming the
tool that did it and where to find the result.

## Where it comes from

Each asset is a one-off file (an Android app's SQLite DB, a Firestore
export, a flat JSON dump) uploaded directly into an editing session and
imported there with `tools/DvaitaVedanta/Itara/DasaSahitya/import_dasa_sahitya_{local_db,
collection_json,flat_json}.py` — there is no live external source this
branch can be rebuilt from the way `wordnet-dist` re-fetches IndoWordNet.
A new asset arriving goes: import it locally in a session, commit
`dge/data/dasa_sahitya_local/<new-asset>/` to a branch, then run
`.github/workflows/publish-dasa-sahitya-local.yml` against that branch to
move it here.

## Promoting a composer out of here

Once a composer's identity is confirmed as the same person already in
`dge/data/DvaitaVedanta/Itara/DasaSahitya/composers/` (see `ALL_SOURCES_composer_registry.json`
for what's already confirmed vs. still `needs_human_review`), add it to the
`CONFIRMED` table in `tools/DvaitaVedanta/Itara/DasaSahitya/merge_confirmed_composers.py` and
run it — it merges the compositions (deduped against what's already there)
into the canonical composer file on `main` and removes the now-redundant
copy from here. Composers that stay unconfirmed, or are new to the corpus
entirely, simply stay in this branch until they're reviewed.
