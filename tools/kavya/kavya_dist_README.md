# `kavya-dist` — the built Kāvya corpus

Data only. No site, no code, no history in common with `main`. It exists so the
Kāvya reader can load 50 MB of text without those files counting against the
published site, which sits about 1% under the GitHub Pages 1 GB limit.

`dge/js/kavya.js` reads it over jsDelivr:

```
https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@kavya-dist
```

which is what `appConfig.kavyaDataBase` in `dge/js/config.js` is set to — the
same arrangement the kośa corpus and the Sanskrit WordNet already use. Pages
publishes `main` and nothing else, so nothing here is served from the site.

## What is in it

```
kavya_alankara/_index.json                     works, layers, counts
kavya_alankara/<work>/<layer>/data.json        one itihasa_purana_text grantha
```

**43 works, 68 layers, 94,949 entries.** Every layer is a separate grantha in
DGE's existing `itihasa_purana_text` shape, so `core.js` reads it unchanged:
mūla in `sanskrit_text`, commentary in `bhashya[]`, padaccheda and translations
in `artha`.

Among them: Raghuvaṃśa, Kumārasambhava, Kirātārjunīya and Śiśupālavadha each
with **Mallinātha's commentary** (Sañjīvinī, Ghaṇṭāpatha, Sarvaṅkaṣā),
padaccheda, anvaya and translations; Meghadūta with Vallabhadeva;
Kathāsaritsāgara (21,538 verses); the Nāṭyaśāstra, Kāvyādarśa, Dhvanyāloka,
Kāvyālaṅkāra, Sāhityadarpaṇa, Daśarūpaka and Vakroktijīvita; Bhāsa's
Svapnavāsavadattā, Kālidāsa's Abhijñānaśākuntala, Harṣa's three nāṭikās.

## Where it comes from

Tier A `sanskritsahitya-com/data` (no LICENSE file; educational/non-commercial
permission from the curator, attribution kept visible), tier B GRETIL
corpusTEI (per-file, non-commercial), tier C **ambuda.org** (proofed TEI, one
whole-library export; CC0/CC-BY per text) and tier D **sa.wikisource.org**
(CC BY-SA 4.0, attribution required). `tools/kavya/config/sources.json` on
`main` records every tier with its licence position.

## Rebuilding it

```
export PYTHONPATH=tools
python3 -m kavya.import_kavya --all --data-root <root>
python3 -m kavya.build_kavya_index --data-root <root>
python3 -m kavya.verify_kavya      --data-root <root>
```

`.github/workflows/import-kavya.yml` on `main` does that and republishes this
branch. The corpus is never written into `dge/data/` on `main`.
