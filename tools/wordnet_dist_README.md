# `wordnet-dist` — the built Sanskrit WordNet

This branch is **data only**. It carries no site, no code, and no history in
common with `main`; it exists so the reader can load the Sanskrit WordNet
without the files counting against the published site.

`dge/js/intellisense.js` reads it over jsDelivr:

```
https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@wordnet-dist/_wordnet
```

which is what `appConfig.wordnetDataBase` in `dge/js/config.js` is set to. The
same arrangement the kośa corpus already uses, one step smaller: the koshas
needed their own repository at ~1.8 GB, this needs 24 MB, and an orphan branch
is enough. GitHub Pages publishes only `main`, so nothing here is served from
the site itself — which is the whole point. The site measured 1,017 MB with
this tree committed to `main` against a 1 GB Pages limit, and about 991 MB
without it.

## What is in it

`_wordnet/<bucket>.json`, 589 buckets plus `manifest.json`. A bucket is

```json
{ "s": [ [pos, gloss, example, [words], hypernym, [kannada]], … ],
  "w": { "अश्वः": [0, 3], "अश्व": [0, 3] } }
```

— the synsets a word belongs to, oldest sense first, stored once per bucket
with the words pointing at them by index. Buckets are named for the first two
SLP1 characters of the word, the same rule `dge/data/_morph` and
`dge/data/_synonyms` use, so one lookup rule serves all three. `manifest.json`
carries the counts, the source and the licence.

## Where it comes from

IndoWordNet (CFILT, IIT Bombay), Sanskrit half, via the data dump distributed
with [`pyiwn`](https://github.com/cfiltnlp/pyiwn) — 37,734 synsets, 80,009
indexed words. The pyiwn distribution carries **CC BY-SA 4.0**; attribution is
in `manifest.json` and on screen in the popover that shows it.

## Rebuilding it

The builder is `tools/build_wordnet.py` on `main`. From a checkout of this
repository's `main`:

```
python3 tools/build_wordnet.py --download      # fetches the dump, ~30 MB, once
```

then commit `dge/data/_wordnet/**` here as `_wordnet/**`. `.github/workflows/
publish-wordnet.yml` on `main` does exactly that on a manual run.
