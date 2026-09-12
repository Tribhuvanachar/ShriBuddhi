# Audio inventory (Kamadhenu Phase 1)

Built 6 Sep 2026 (refreshed 8:45 pm IST: smv.zip takes identified) by `kamadhenu/scripts/build_audio_inventory.py` from the per-file measurements in
`kamadhenu_dataset/audio_inventory.json` and the text mapping in `kamadhenu_dataset/metadata.jsonl`. The CSV is
`kamadhenu/data/audio_inventory.csv` (one row per file, 31 columns). No audio was copied.

## Totals

| | files | hours |
|---|---|---|
| everything reachable | 3,892 | 37.83 |
| grade A (clean, no clipping, SNR good) | 757 | 8.78 |
| grade B (usable) | 2,045 | 24.34 |
| grade C/D/F (clipped, noisy, very low bitrate, or unreadable) | 1,090 | 4.71 |
| paired with a text at confidence ≥ 0.9 | 2,530 | 11.02 |
| **usable for training today** | **1,721** | **6.46** |

"Usable" = grade A or B, text confidence ≥ 0.9, duration plausible for the text, not a byte-identical duplicate.

## By source

| folder | files | hours | grades | sample rate | what it is |
|---|---|---|---|---|---|
| dge_linked/sumadhva_vijaya | 989 | 3.65 | all B | 11.025 kHz MP3 | one file per verse, already linked in the reader; low bitrate |
| dge_linked/raghavendra_vijaya | 576 | 3.20 | 486 D, 85 B | 48 kHz | one file per verse; most clipped |
| dge_linked/PrahladaKrutaNarasimha | 11 | 0.06 | A/B | 44.1 kHz | vasantatilakā stotra |
| drive/Bhagavata Saroddhara | 436 | 2.13 | 425 A | 44.1 kHz | one file per verse; best audio we have; text verified 6 Sep 2026 |
| drive/Gita Shlokas (7 adhyāyas) | 406 | 8.82 | mostly A/B | 44.1/48 kHz | 46–120 s per file: lead (6 Sep) — recited pāda by pāda with some words repeated twice; segment per pāda, drop repeats |
| drive/Audio* ('vsn' series) | 106 | 3.86 | B, some D | 48 kHz | Viṣṇu Sahasranāma, mapped at 0.55 confidence, unconfirmed |
| drive/Vayu Stuti | 20 | 0.45 | 18 A | 44.1 kHz | pāda-level files, text not yet in DGE |
| drive/Shlokas (Tīrthaprabandha) | 21 | 0.09 | 19 A | 48 kHz | Dakṣiṇa-prabandha verses 1–19 + 2 intro clips; mapped |
| drive/Prahlada Narasimha Stotra | 43 | 0.21 | 6 A, 37 B | 48 kHz | Bhāgavata 7.9.8–50, one verse per file; mapped |
| drive/Sripadaraja AshTottara Shatanamavali | 110 | 0.12 | 68 A | 48 kHz | one name per clip; text not in DGE yet |
| drive/single-file/smv (`smv.zip`, shared 6 Sep) | 1,106 | 9.86 | 554 B, 552 D | 48 kHz AAC | the lead's phone takes of Sumadhva Vijaya at **pāda** level (4–7 s each): 34 named `SMV.<sarga>.<verse>.<pāda>` (30 mapped, exact), 1,058 numbered `New recording N` identified by Whisper + the sequential-pāda rule (909 assigned, 149 to listen, `smv_takes_listen_list.csv`), 51 dated hour-long session files (long-form); same reciter, higher fidelity than the 11 kHz site files, but half clip (peak > 0 dBFS) |
| drive/single-file/Vedavyasa Gadya.mp3 | 1 | 0.16 | B | 44.1 kHz | prose recitation of Yādavārya's Vedavyāsa Gadyam; text imported 6 Sep (100 epithet units) — needs per-epithet segmentation |
| drive/AShThAdhyAyi (pārāyaṇa) | 32 | 3.89 | 13 A, 19 B | 44.1 kHz | whole-pāda Aṣṭādhyāyī pārāyaṇa by **other reciters (not the lead, no consent)** — kept in the inventory, excluded from every training subset (`speakers.json` → EXTERNAL) |
| drive/Brahmasutra | 2 | 0.08 | B | 48 kHz | Brahmasūtra 1.1 and 1.2 recited whole; long-form |
| drive/HKS (Harikathāmṛtasāra) | 31 | 1.34 | 14 A, 16 B, 1 D | 48 kHz | Kannada ṣaṭpadi, one verse per file, 1.5–2.5 min each — lead confirmed plain full recitation (sung pace, no meaning); mapped to `hks-<sandhi>-<n>` and accepted |
| drive/Sripadaraja Seva Sangha | 1 | 0.07 | C | video | Aṣṭottara-śata-nāmāvali sung in one video (mp4); the 108-name text is still missing. The second file in that folder (Kṣīrābhiṣeka, 400 MB event video) was downloaded, judged not a recitation, and the local copy removed |

Two of the nine new folders (`1o5-yqK_…`, `1-716NX8…`) redirect to Google sign-in; the lead says they are someone else's, so they were dropped from the source list.
The seven others overlap heavily with folders shared earlier (the Gītā, Tīrthaprabandha and Viṣṇu Sahasranāma folders are
parents/duplicates of ones already fetched); the pipeline now de-duplicates by Drive file id, so nothing is counted twice.

## Text, metre and laghu/guru association

Of the 2,472 files paired at confidence ≥ 0.7: 85.4 % carry a metre name from the DGE Chandas engine, 100 %
carry a laghu/guru scan and pāda count, 11.3 % of metres have an exact pāda-level reference recording. Speaker: every file is **3BHU1** (the project lead; consent to train the voice recorded 6 Sep 2026).

## Known defects (marked, not deleted)

* 46 files are byte-identical to another file (Sumadhva Vijaya pairs such as smv1.12 = smv1.16).
* 5 links in the audio repo are dead (`smv5.8`, `smv5.14`, `smv5.16`, `rv02.54`, `rv10.06`).
* 486 Rāghavendra Vijaya files show clipping runs.
* 1 decode error (`single-file/smv/SMV/New recording 20250618 150650.m4a`).
* 551 of the `smv.zip` phone takes clip (recorded too hot); the other 554 are grade B.

## Columns of the CSV

file_path, filename, format, codec, sample_rate, channels, bit_depth, duration_s, file_size, peak_dbfs, rms_dbfs,
snr_db_est, clipping_runs, quality_grade, qc_flags, exact_duplicate_of, source, folder, speaker, recording_type,
text_id, text_first_words, mapping_confidence, mapping_signal, review_status, meter, meter_confidence, laghu_guru,
pada_count, part, usable_for_training.
