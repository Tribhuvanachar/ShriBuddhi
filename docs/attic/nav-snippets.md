# Two one-line edits, left for you to make by hand

`index.html` and `js/library.js` are untouched by this package on purpose —
they are the two files most likely to have moved on since the corpus zip was
built, and a blind patch to either is how a nav bar breaks.

## 1. `dge/index.html` — add काव्यानि to the section nav

Next to the existing सूत्राणि / धातु / कोश links:

```html
<a href="kavya.html">काव्यानि <small>Kāvya &amp; Poetics</small></a>
```

## 2. `dge/js/library.js` — label the category

Wherever the category labels are declared (the same map that carries
`vyakarana`, `kosha`, `itihasa`), add:

```js
kavya_alankara: { sa: "काव्यानि", iast: "Kāvyāni", en: "Kavya & Poetics",
                  href: "kavya.html" },
```

If library.js v3.0's override layer is in place, the label can instead be set
from `dge/data/library-overrides.json` through library-admin.html, with no
code change at all — that is the preferred route.

## 3. Taxonomy

Do NOT hand-edit `dge/data/taxonomy.json`. Run:

```bash
python3 patches/apply_taxonomy_patch.py --taxonomy dge/data/taxonomy.json --dry-run
python3 patches/apply_taxonomy_patch.py --taxonomy dge/data/taxonomy.json
```

The dry run prints exactly which existing children get re-parented and flags
anything it could not place. It writes a `.bak` before touching the file.
