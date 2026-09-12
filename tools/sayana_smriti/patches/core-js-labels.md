# App patches — two small, additive edits to `dge/js/core.js`

Neither is required for the import to run. The first is cosmetic; the second is
the difference between the Smṛti commentaries being *in the data* and being
*visible in the app*.

---

## 1. Label the new commentary layers  (cosmetic)

`dgeNormalizeGranthaData()` auto-titlecases any unrecognised commentary key, so
`sayana` would render as "Sayana" and `wilson` as "Wilson". Add proper labels to
the existing `KNOWN_COMMENTARY_LABELS` map (around line 235):

```js
  const KNOWN_COMMENTARY_LABELS = {
    griffith: 'Griffith (English Translation)',
    macdonell: 'Macdonell (English Translation)',
    oldenberg: 'Oldenberg (English Translation)',
    geldner: 'Geldner (German Translation)',
    grassmann: 'Grassmann (German Translation)',
    elizarenkova: 'Elizarenkova (Russian Translation)',
+   sayana: 'सायणभाष्यम् — Sāyaṇa (Ṛgveda-bhāṣya)',
+   wilson: 'Wilson (English Translation, after Sāyaṇa)'
  };
```

---

## 2. Surface `artha` and `bhashya[]` on nested-shloka granthas  (functional)

The `itihasa_purana_text` / `smriti_dharmashastra_text` branch of
`dgeNormalizeGranthaData()` flattens each chapter's `shlokas[]` but hard-codes
`commentaries: {}` — so every commentary the Smṛti importer writes would be
loaded and then silently thrown away by the normaliser. The Itihāsa/Gītā
commentary import has the same problem, so this fix pays for both.

Replace the body of the nested-shlokas branch (around line 255):

```js
  if (Array.isArray(data.items) && data.items.length && Array.isArray(data.items[0].shlokas)) {
    const shlokas = {};
+   const availableCommentaries = {};
    let n = 0;
    data.items.forEach(chapter => {
      (chapter.shlokas || []).forEach(v => {
        n++;
+       // shlokas[].bhashya[] is [{commentator, text, language, source}] per
+       // schemas.json; artha is the plain translation. Both are folded into the
+       // same flat `commentaries` dict every renderer already understands, so
+       // Manu-with-Medhatithi displays exactly like Rigveda-with-Sayana.
+       const commentaries = {};
+       if (v.artha) commentaries.artha = v.artha;
+       (v.bhashya || []).forEach(b => {
+         if (!b || !b.text) return;
+         const key = (b.commentator || 'bhashya')
+           .toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
+         commentaries[key] = b.text;
+         availableCommentaries[key] = b.commentator || key;
+       });
+       if (v.artha) availableCommentaries.artha = 'Translation';
        shlokas[n] = {
          sa: dgeSanitizeVedicAccents(v.sanskrit_text || v.sa || ''),
          vedicId: chapter.reference ? (chapter.reference + (v.number != null ? ' · ' + v.number : '')) : '',
-         commentaries: {}
+         commentaries: commentaries
        };
      });
    });
    …
    return {
      metadata: {
        …
-       availableCommentaries: {}
+       availableCommentaries: availableCommentaries
      },
      shlokas,
      totalShlokas: n
    };
  }
```

The key is derived from the commentator string rather than hard-coded, so
adding Kullūka or Govindarāja later needs no further JS change.

---

## 3. Taxonomy — two new folders

`patches/taxonomy_patch.py` adds `vasistha_smriti` and `baudhayana_smriti` under
`smriti_dharma.smriti` (the other 26 folders already exist). Idempotent:

```bash
python patches/taxonomy_patch.py --dge-root ../bhumandala/dge
```

No change to `schemas.json` is needed anywhere — `vedic_text.bhashya[]`,
`smriti_dharmashastra_text.shlokas[].bhashya[]` and `.artha` are all already
defined.
