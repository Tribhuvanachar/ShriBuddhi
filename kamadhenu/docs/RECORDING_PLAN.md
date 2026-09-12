# Targeted recording plan (Phase 18) — what to record, and why

Derived from the measured data (`kamadhenu/docs/AUDIO_INVENTORY.md`, `kamadhenu_dataset/chandas_coverage.json`,
`kamadhenu_dataset/RECORDING_REQUESTS.csv` with 249 rows). Nothing here is "more audio"; each line closes a gap
the numbers show.

## Protocol (unchanged from the master audit)

One room, one microphone, 48 kHz / 24-bit WAV, peaks near −6 dB, no tanpura, no gaps inside a pāda, pause only at
pāda ends and at yati, hold long vowels, sustain final visarga, articulate retroflexes and aspirates, one clean take
per verse, file named `<dge text id>.wav`. Drop files in `kamadhenu_dataset/incoming_audio/reference_takes/`.

## Priority 1 — one clean reference verse for each core metre that has only poor audio (17 texts)

इन्द्रवंशा, पृथ्वी, भुजङ्गप्रयात, मन्दाक्रान्ता, शिखरिणी, स्रग्धरा, हरिणी and the other P0 rows of
`RECORDING_REQUESTS.csv`: their only recordings are 11 kHz/16 kbps or clipped. Texts are given in the CSV.

## Priority 2 — metres with no recording at all that occur in Mādhva kāvya (about 25 metres)

The coverage file lists 219 metres with no audio; only those that actually occur in Sumadhva Vijaya, Rāghavendra
Vijaya, Tīrthaprabandha and the stotras matter first (P1/P2 rows of the CSV).

## Priority 3 — pronunciation coverage (short phrases, 10–20 minutes total)

Recorded as a single "phonetic sheet" session, each item once, slowly and once at normal pace:
* every vowel in long and short form in initial, medial and final position (अ/आ, इ/ई, उ/ऊ, ऋ/ॠ, ए, ऐ, ओ, औ);
* visarga before each consonant class and word-final before a pause (echo-vowel decision applies);
* anusvāra before every consonant class (homorganic realisation);
* retroflex series ट ठ ड ढ ण and ष in clusters (ष्ट, ष्ठ, ण्ड, ण्ठ);
* aspirate pairs in minimal contrast (क/ख, ग/घ, च/छ, ज/झ, ट/ठ, ड/ढ, त/थ, द/ध, प/फ, ब/भ);
* heavy conjuncts (क्ष्म, त्स्न्य, ङ्क्ष, र्त्स्न्य, ष्ट्र);
* jihvāmūlīya and upadhmānīya written and spoken;
* avagraha, pluta and the pāda-final consonant (यत् / तत् / विद्वान्) before a pause;
* 20 difficult words from the corpus (list to be generated from the syllable-frequency table).

## Priority 4 — pace and structure

For 10 verses already recorded well: slow, medium and fast renditions of the same verse; pāda-by-pāda renditions
with a clear stop at each pāda end; long-metre verses (śārdūlavikrīḍita, sragdharā, mandākrāntā) with the yati
audibly observed.

## Priority 5 — gadya

Two prose passages (Prātaḥ Saṅkalpa Gadya, a Bhāṣya paragraph) for the "ordinary Sanskrit reading" voice.

## What the recordings unlock

P1+P2 give a verified reference clip per metre (the mechanism Vāgdhenu showed to be the real lever). P3 fills the
phoneme coverage a fine-tune needs. P4 gives duration targets per metre and pace. All are prerequisites for
Experiment B onward; Experiment A can run on the existing pilot.
