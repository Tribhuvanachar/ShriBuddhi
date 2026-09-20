# End-to-end: works addressed by an opaque id

Proves the thing that cannot be proved by reading code: that a reader can
search the text of a structure-private work, cannot reach its path, and that
an admin can.

## Build the two sites

A miniature corpus is enough and a full stage is not -- `search_index` alone
is 2.7 GB and will not fit beside a checkout.

```sh
E=/tmp/dge-e2e
# 1. a few works from each side, public and id-addressed
python3 tools/e2e/make_fixture.py --out $E/src
# 2. a real index over them
PYTHONPATH=$PWD python3 tools/build_search_index.py --data $E/src/data --out $E/site/search_index
# 3. the site shell, minus anything publish_clean_repo drops
cp -r js css wasm vyakarana images render.html index.html $E/site/
cp -r $E/src/data/* $E/site/data/
rm -f $E/site/js/private-names.js $E/site/js/test-*.js $E/site/js/*.test.js
# 4. the transform that makes it publishable
python3 tools/publish_opaque_rewrite.py --staged $E/site

(cd $E/site && python3 -m http.server 8911 &)   # the published site
(cd $PWD     && python3 -m http.server 8912 &)   # the private checkout
python3 tools/e2e/opaque_ids_e2e.py
```

## The browser

Chromium is already installed at `/opt/pw-browsers`. Do NOT run
`playwright install` -- the pip package expects a newer build than the one
present, and the script passes `executable_path` for exactly that reason.
