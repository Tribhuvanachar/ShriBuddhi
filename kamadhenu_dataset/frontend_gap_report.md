# Sanskrit TTS frontend — gap report (DGE × Vāgdhenu)

Evidence file: `kamadhenu_dataset/frontend_gap_report.json`; regenerate with `python3 -m tools.kamadhenu.frontend_gap`
(the script runs 22 probe inputs through every existing text path and derives the findings mechanically).
Paths probed — DGE: `search_toolkit_pkg.translit.to_slp1` + `normalize.phonetic_key` (site search), `js/subanta-steps.js slp()` (vyākaraṇa tool), `js/chandas.js` syllabifier (guru marked with ̲);
Vāgdhenu: `prep_text.align_slp1 / model_text / model_text_sandhi / mfa_text`, `tts_normalize + tts_g2p + tts_syllabify + tts_weight`.

## Checklist (section 11 of the task)

| requirement | state |
|---|---|
| Unicode normalization | DGE: NFC in clean_devanagari + subanta slp; Vāgdhenu: none explicit (sanscript tolerates NFC) — PARTIAL |
| Devanagari | both — DONE |
| Kannada | DGE search folds by code-point shift; Vāgdhenu detect_script→sanscript; chandas.js NO — PARTIAL |
| SLP1/internal | both use SLP1 (DGE search_toolkit; Vāgdhenu sanscript) — DONE |
| akṣara segmentation | chandas.js (JS only) / Vāgdhenu ×2 — PARTIAL |
| vowels & length | preserved in SLP1 by both; DGE phonetic_key deliberately folds length (search only, never for TTS) — DONE for TTS path |
| anusvāra | kept as M by both; homorganic-nasal rewrite only in Vāgdhenu — PARTIAL |
| visarga | kept as H; Vāgdhenu sandhi/echo transforms optional — PARTIAL |
| jihvāmūlīya/upadhmānīya | Vāgdhenu tts_normalize emits them; DGE drops them — NOT STARTED in DGE |
| retroflex | preserved by both — DONE |
| aspirates | preserved — DONE |
| geminates | preserved in SLP1; DGE phonetic_key collapses them (search only) — DONE for TTS path |
| conjuncts | preserved; chandas.js counts cluster weight — DONE |
| word boundaries | spaces preserved; hyphenated compounds in Sumadhva Vijaya source need joining — PARTIAL |
| pāda boundaries | line/daṇḍa based only — PARTIAL |
| daṇḍa | stripped by both (kept as pause token only in Vāgdhenu tts_g2p) — DONE |
| sandhi | Vāgdhenu word-boundary visarga sandhi only; no general sandhi engine anywhere — PARTIAL |
| pronunciation transformations | Vāgdhenu: ṝ→rū, hna metathesis, echo visarga, vocalic ḷ; DGE: none — PARTIAL |
| Vedic svara | nowhere — NOT STARTED |

## Findings — every place Sanskrit pronunciation can be damaged

| severity | component | case | problem | evidence | fix |
|---|---|---|---|---|---|
| medium | Vāgdhenu prep_text.model_text | explicit jihvāmūlīya U+1CF5 | explicit jihvāmūlīya/upadhmānīya passes through to the Kannada model text where it is out-of-vocabulary | `ದುᳵಖಮ್` | fold to plain visarga before Kannada routing (Vāgdhenu does this only in the phonetic_mfa kannada_safe arm) |
| high | DGE search_toolkit.to_slp1 | explicit upadhmānīya U+1CF6 | explicit jihvāmūlīya/upadhmānīya is dropped (not mapped to H/Z/V) | `antaᳶpuram` | map U+1CF5→'Z', U+1CF6→'V' (Vāgdhenu tts_g2p convention) or at least to 'H' |
| medium | Vāgdhenu prep_text.model_text | explicit upadhmānīya U+1CF6 | explicit jihvāmūlīya/upadhmānīya passes through to the Kannada model text where it is out-of-vocabulary | `ಅನ್ತᳶಪುರಮ್` | fold to plain visarga before Kannada routing (Vāgdhenu does this only in the phonetic_mfa kannada_safe arm) |
| medium | DGE chandas.js | candrabindu | candrabindu does not make the syllable guru (only ं/ः are tested) | `सँ यो̲ गः̲` | extend the nasal test at chandas.js:58 to /[ँंः]/ |
| low | Vāgdhenu prep_text.phonetic_mfa | anusvāra before y | anusvāra before y kept as ं (tts_normalize.py turns it into candrabindu) — the two Vāgdhenu normalisers disagree | `संयोगः` | pick one rule for Kamadhenu and document it |
| medium | DGE search_toolkit.to_slp1 | ZWJ/ZWNJ inside conjunct | zero-width joiners survive into SLP1 | `'k\u200dza k\u200cza'` | strip U+200C/U+200D before transliteration (texts.py does) |
| high | DGE search_toolkit.to_slp1 (as used by texts.py) | Kannada script input | Kannada input is not transliterated by the Devanagari path; build_search_index folds Kannada→Devanagari by code-point shift first, texts.py must do the same before Chandas | `ಧರ್ಮಕ್ಷೇತ್ರೇ ಕುರುಕ್ಷೇತ್ರೇ` | always run fold_indic_to_devanagari() before to_slp1/Chandas |
| high | DGE chandas.js | Kannada script input | Kannada-script verse yields zero syllables (engine is Devanagari-only, silent) | `padas: []` | transliterate to Devanagari upstream (kamadhenu texts.py does; the site page does not) |
| low | DGE search_toolkit.to_slp1 | Vedic svara marks | svara marks leak into SLP1 | `a॒gnimI॑Le pu॒rohi॑tam` | strip U+0951/U+0952 (build_search_index.clean_devanagari already does) |
| info | all | Vedic svara marks | no path preserves udātta/anudātta/svarita — Vedic accent is out of scope for every existing frontend | `` | separate Vedic annotation track (tts/ARCHITECTURE.md §Vedic) — Stage 6 only |
| info | Vāgdhenu prep_text.visarga_echo_final | word-final visarga (echo/lengthening) | chant echo-vowel (rāmaḥ→rāmaha) is applied to the last word — a tradition-specific pronunciation choice, must be a per-project switch | `ರಾಮಹ` | expose as a parameter in the Kamadhenu frontend; default follows the lead's recitation style |
| info | Vāgdhenu prep_text.model_text_sandhi | visarga sandhi context aḥ+voiced | applies utva/rutva/lopa visarga sandhi at word boundaries — changes the text that will be spoken; DGE has no equivalent, and this must NOT be applied when the recording already has plain visarga | `ರಾಮೋ ಗಚ್ಛತಿ` | keep as an explicit, logged pronunciation transform; never rewrite DGE canonical text |
| high | DGE (everywhere) | akṣara segmentation | DGE has no reusable Sanskrit syllabifier outside chandas.js (browser JS, Devanagari-only, ल/ग alphabet); Vāgdhenu has two (tts_syllabify.py maximize-onset, chandas_labeler.py orthographic) that count the same but split codas differently | `see rows` | Kamadhenu wraps chandas.js headlessly (done: tools/kamadhenu/chandas_runner.js); a Python port is NOT needed for the dataset stage |
| high | both | G2P | neither project has a phonemic G2P beyond SLP1 = one char per phone; Vāgdhenu deliberately feeds Kannada script to IndicF5 and lets the model learn pronunciation acoustically | `prep_text.model_text` | for Kamadhenu keep SLP1 as the internal representation; script routing (Devanagari vs Kannada) is a model-side choice to re-test on the lead's voice |
| medium | both | pāda boundaries | pāda boundaries come only from line breaks / daṇḍas in the source text; where a verse is stored as two hemistich lines the engine splits at the syllable midpoint, which is wrong for uneven ardhasama/viṣama metres | `chandas.js toPadas()` | store pāda-split text in DGE for reference-bank verses (human-checked), or derive from the metre's per-pāda syllable count |
| medium | DGE data | text defects surface as metre failures | unequal pāda counts / typos in the corpus (e.g. सिधुः for सिन्धुः in Tīrthaprabandha TP_DAK_003; 23/22-syllable halves in Sumadhva Vijaya 1.17) make the engine return अज्ञातम् | `text_index.json chandas_analysis.inferred_reason` | route these to the DGE correction workflow; they are corpus bugs, not engine bugs |

## Probe table

| case | input | DGE search SLP1 | DGE subanta SLP1 | DGE chandas syllables (̲ = guru) | Vāgdhenu align_slp1 | Vāgdhenu normalize→g2p | Vāgdhenu model text (Kannada) |
|---|---|---|---|---|---|---|---|
| visarga before k (jihvāmūlīya context) | `दुःखम्` | `duHKam` | `duHKam` | दुः̲ ख̲ | `duHKam` | `duZKam` | ದುಃಖಮ್ |
| visarga before p (upadhmānīya context) | `तपःफलम्` | `tapaHPalam` | `tapaHPalam` | त पः̲ फ ल̲ | `tapaHPalam` | `tapaVPalam` | ತಪಃಫಲಮ್ |
| explicit jihvāmūlīya U+1CF5 | `दुᳵखम्` | `duᳵKam` | `duᳵKam` | दु ख̲ | `duᳵKam` | `duZKam` | ದುᳵಖಮ್ |
| explicit upadhmānīya U+1CF6 | `अन्तᳶपुरम्` | `antaᳶpuram` | `antaᳶpuram` | अ̲ न्त पु र̲ | `antaᳶpuram` | `antaVpuram` | ಅನ್ತᳶಪುರಮ್ |
| candrabindu | `सँयोगः` | `sa~yogaH` | `sa~yogaH` | सँ यो̲ गः̲ | `sa~yogaH` | `say~ogaH` | ಸಁಯೋಗಃ |
| anusvāra before sibilant | `संसारः` | `saMsAraH` | `saMsAraH` | सं̲ सा̲ रः̲ | `saMsAraH` | `saMsAraH` | ಸಂಸಾರಃ |
| anusvāra before y | `संयोगः` | `saMyogaH` | `saMyogaH` | सं̲ यो̲ गः̲ | `saMyogaH` | `say~ogaH` | ಸಂಯೋಗಃ |
| anusvāra before stop (homorganic) | `अङ्कः अंकः` | `aNkaH aMkaH` | `aNkaH aMkaH` | अ̲ ङ्कः̲ अं̲ कः̲ | `aNkaH aMkaH` | `aNkaH aNkaH` | ಅಙ್ಕಃ ಅಂಕಃ |
| long vocalic ṝ | `पितॄणाम्` | `pitFRAm` | `pitFRAm` | पि तॄ̲ णा̲ | `pitrURAm` | `pitFRAm` | ಪಿತ್ರೂಣಾಮ್ |
| vocalic ḷ | `कॢप्तम्` | `kxptam` | `kxptam` | कॢ̲ प्त̲ | `kxptam` | `kxptam` | ಕೢಪ್ತಮ್ |
| avagraha | `सोऽहम्` | `so'ham` | `so'ham` | सो̲ ह̲ | `soham` | `so'ham` | ಸೋಽಹಮ್ |
| ZWJ/ZWNJ inside conjunct | `क्‍ष क्‌ष` | `k‍za k‌za` | `kza kza` | क् ष̲ ष | `kza kza` | `k‍za kza` | ಕ್ಷ ಕ್ಷ |
| nukta consonants | `क़ ख़ ग़ ज़ ड़ ढ़ फ़` | `ka Ka ga ja qa Qa Pa` | `ka़ Ka़ ga़ ja़ qa़ Qa़ Pa़` | क ख ग ज ड ढ फ | `k0a K0a g0a j0a q0a Q0a P0a` | `k0a K0a g0a j0a q0a Q0a P0a` | ಕ಼ ಖ಼ ಗ಼ ಜ಼ ಡ಼ ಢ಼ ಫ಼ |
| geminate | `सत्त्वम् उत्पत्तिः` | `sattvam utpattiH` | `sattvam utpattiH` | स̲ त्त्व̲ उ̲ त्प̲ त्तिः̲ | `sattvam utpattiH` | `sattvam utpattiH` | ಸತ್ತ್ವಮ್ ಉತ್ಪತ್ತಿಃ |
| retroflex series | `षट् षष्ठः ढक्का` | `zaw zazWaH QakkA` | `zaw zazWaH QakkA` | ष̲ ष̲ ष्ठः̲ ढ̲ क्का̲ | `zaw zazWaH QakkA` | `zaw zazWaH QakkA` | ಷಟ್ ಷಷ್ಠಃ ಢಕ್ಕಾ |
| aspirate cluster | `कृष्ण ब्रह्मा वृद्धिः` | `kfzRa brahmA vfdDiH` | `kfzRa brahmA vfdDiH` | कृ̲ ष्ण̲ ब्र̲ ह्मा̲ वृ̲ द्धिः̲ | `kfzRa brahmA vfdDiH` | `kfzRa brahmA vfdDiH` | ಕೃಷ್ಣ ಬ್ರಹ್ಮಾ ವೃದ್ಧಿಃ |
| Kannada script input | `ಧರ್ಮಕ್ಷೇತ್ರೇ ಕುರುಕ್ಷೇತ್ರೇ` | `ಧರ್ಮಕ್ಷೇತ್ರೇ ಕುರುಕ್ಷೇತ್ರೇ` | `ಧರ್ಮಕ್ಷೇತ್ರೇ ಕುರುಕ್ಷೇತ್ರೇ` |  | `Darmakzetre kurukzetre` | `ಧರ್ಮಕ್ಷೇತ್ರೇ ಕುರುಕ್ಷೇತ್ರೇ` | ಧರ್ಮಕ್ಷೇತ್ರೇ ಕುರುಕ್ಷೇತ್ರೇ |
| daṇḍa and verse number | `किमकुर्वत सञ्जय ॥१.१॥` | `kimakurvata saYjaya  || 1.1 || ` | `kimakurvata saYjaya ॥१.१॥` | कि म कु̲ र्व त स̲ ञ्ज य | `kimakurvata saYjaya` | `kimakurvata saYjaya |||||` | ಕಿಮಕುರ್ವತ ಸಞ್ಜಯ |
| ॐ praṇava | `ॐ नमो नारायणाय` | `ॐ namo nArAyaRAya` | `ॐ namo nArAyaRAya` | ॐ̲ न मो̲ ना̲ रा̲ य णा̲ य | `AUM namo nArAyaRAya` | `om namo nArAyaRAya` | ಓಂ ನಮೋ ನಾರಾಯಣಾಯ |
| Vedic svara marks | `अ॒ग्निमी॑ळे पु॒रोहि॑तम्` | `a॒gnimI॑Le pu॒rohi॑tam` | `a॒gnimI॑ळे pu॒rohi॑tam` | अ̲ ग्नि मी̲ ळे̲ पु रो̲ हि त̲ | `a॒gnimI॑le pu॒rohi॑tam` | `a॒gnimI॑Le pu॒rohi॑tam` | ಅ॒ಗ್ನಿಮೀ॑ಳೇ ಪು॒ರೋಹಿ॑ತಮ್ |
| word-final visarga (echo/lengthening) | `रामः` | `rAmaH` | `rAmaH` | रा̲ मः̲ | `rAmaH` | `rAmaH` | ರಾಮಃ |
| visarga sandhi context aḥ+voiced | `रामः गच्छति` | `rAmaH gacCati` | `rAmaH gacCati` | रा̲ मः̲ ग̲ च्छ ति | `rAmaH gacCati` | `rAmaH gacCati` | ರಾಮಃ ಗಚ್ಛತಿ |

## Reading the table
* **What is safe today**: plain Devanagari verse text with anusvāra/visarga/conjuncts/retroflexes/aspirates/geminates round-trips losslessly to SLP1 in every path. Vowel length is preserved in SLP1 (DGE's `phonetic_key` folds it, but that key is for search ranking only and is never used for TTS).
* **What is lost in DGE**: explicit jihvāmūlīya/upadhmānīya (U+1CF5/U+1CF6), candrabindu weight in Chandas, zero-width joiners leaking, Kannada input to Chandas. None of these appear in the current recordings' texts (Gītā, Sumadhva/Rāghavendra Vijaya, Tīrthaprabandha are plain Devanagari), so they block nothing *now*; they block Vedic and Kannada-script granthas later.
* **What Vāgdhenu changes on purpose**: visarga sandhi at word boundaries (utva/rutva/lopa), chant echo-vowel on the final visarga, ṝ→rū, ह्ण→ण्ह metathesis, kannada routing. These are *pronunciation policies* of one reciter tradition. For Kamadhenu they must be explicit, switchable and logged, and must never be written back into DGE canonical text.
* **Do not trust generic Hindi G2P**: `tools/voice_lab/tts_clone.py` (XTTS-v2 via the "hi" mode) is the only place DGE ever proposed it, and its own docstring warns that Hindi schwa-deletion and phoneme set damage Sanskrit. Vāgdhenu's Kannada-routing exists precisely to avoid this. Keep that decision.

## What Kamadhenu should do (engineering, in order)
1. `tools/kamadhenu/texts.py`: strip U+200C/U+200D, map U+1CF5→`Z`, U+1CF6→`V`, keep `~` for candrabindu, strip Vedic svara marks, strip editorial parentheses (done), join hyphenated compounds (done) — with unit tests on the 22 probe cases.
2. `js/chandas.js`: nasal test → `/[ँंःᳵᳶ]/`; add vipulā classes; generic indra/upendra mix; accept Kannada by transliterating on input. Add `tests/test_chandas_engine.py` driving `tools/kamadhenu/chandas_runner.js`.
3. A single `kamadhenu_frontend.py` that produces, per verse: canonical Devanagari (DGE), SLP1 (lossless), rendering text (policy transforms from `prep_text.py`, each one logged), akṣara list + L/G (DGE Chandas). No second text database.
4. Pāda-split text for reference-bank verses stored in DGE (human-checked), because line-based pāda splitting is wrong for uneven metres.
5. Vedic: nothing until Stage 6.
