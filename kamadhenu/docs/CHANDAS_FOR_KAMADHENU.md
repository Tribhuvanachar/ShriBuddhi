# The DGE Chandas engine as Kamadhenu's analysis layer (Phase 5)

Decision: **the DGE Chandas engine (`js/chandas.js` + `data/vedanga/chandas/data.json`) is the authoritative
metre layer for Kamadhenu.** Vāgdhenu's own metre code is used only as a comparison. Reasons and evidence below.

## What the engine produces (checked by running it headlessly)

`tools/kamadhenu/chandas_runner.js` loads the site's engine unmodified under node and returns, for any Devanagari,
Kannada, Telugu or Malayalam verse:

| output | field | example (Gītā 1.1) |
|---|---|---|
| syllables per pāda | `padas[].sylls` | 8 · 8 · 8 · 8 |
| laghu/guru per akṣara | `padas[].pattern` | `GGGGLGGL` … (shown as L/G in the dataset) |
| gaṇa letters | `padas[].ganas` | `मयल` … |
| akṣara and mātrā counts | `padas[].aksharas`, `padas[].matras` | 8, 13 |
| metre name(s) and kind | `match.names`, `match.kind` | `अनुष्टुप् (श्लोकः) — पथ्या`, `छन्दः` |
| yati | `match.yati` | `[8, 7]` for मालिनी |
| anuṣṭubh vipulā class / rule breaks | `match.vipula`, `match.irregular` | `र-विपुला (पादे 1)` |
| pāda boundaries | `padas` (after `padaCandidates`: 4-equal, ardhasama a+b+a+b, two halves, as given) | 10 · 11 · 10 · 11 for वियोगिनी |
| akṣara-count family | `jaatiName(n)` | अनुष्टुप् / त्रिष्टुप् / … |

Coverage: 190 sama + 8 ardhasama + 5 viṣama + 42 upajāti vṛttas, 10 mātrā metres, 27 jāti names; anuṣṭubh by rule
with the four vipulās. On the 2,851 non-MBTN verse units of the Kamadhenu corpus it names 2,467 (86.5 %); the
remaining 384 are text defects, metres absent from the database, or prose (`kamadhenu_dataset/chandas_comparison.md` §3).

Tests: `tests/test_chandas_engine.py` (22 cases) and `tests/test_chandas_examples.py` (59 engine-verified example
verses, growing as the Gemini brief is answered).

## What it does not do yet, and what Kamadhenu does about it

| gap | handling |
|---|---|
| no duration model (it scans, it does not time) | Kamadhenu measures seconds-per-akṣara from verified recordings per metre (`kamadhenu_dataset/mapping.py` band 0.26–0.44 s today; `pace_by_chandas.json` planned) |
| pāda split of prose / gadya | `meter = गद्यम्`, no pādas; prosody from punctuation |
| Vedic svara | out of scope for both engines; separate track (`tts/ARCHITECTURE.md` §25) |
| verse defects in the corpus | flagged, sent to the Gemini brief; never "fixed" silently |

## Comparison with Vāgdhenu's metre code (differences only)

`tts_meter.py` has 13 metres, four with wrong templates (mālinī, śikhariṇī, pṛthvī, sragdharā); `chandas_labeler.py`
has 10 correct signatures and 5 hard-coded yatis; upajāti is "any indra/upendra pāda"; anuṣṭubh is "32 syllables";
last syllable ignored two-way; SLP1 input. Vāgdhenu's own report found its text-side gaṇa conditioner inert. Full
table: `kamadhenu_dataset/chandas_comparison.md` §2. Nothing there is needed once the DGE engine is the analysis layer;
what Kamadhenu keeps from Vāgdhenu is the *reference-audio-by-metre* idea and the pronunciation transforms
(`prep_text.py`), credited under Apache-2.0.

## How Kamadhenu calls it

Python → `tools/kamadhenu/chandas_bridge.py` (`analyse_texts`, cached by text hash) → `chandas_runner.js` → engine.
Browser → `window.DGEChandas.analyzeText(text)`; the Space receives the verdict from the browser
(`tools/kamadhenu/space/meter_map.json` maps it to a reference clip) and never re-detects it.
