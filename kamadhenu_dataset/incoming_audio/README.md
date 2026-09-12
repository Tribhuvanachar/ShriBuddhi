# incoming_audio — drop-zone

Copy recordings here (any sub-folder; wav / mp3 / m4a / flac / aac / ogg / opus). Files are read-only for the pipeline: nothing is modified, moved or re-encoded.

Then run `python3 tools/kamadhenu_audit.py` from the repo root.

Naming that the mapper understands automatically (anything else goes to the review queue, or add an entry in `../mapping_overrides.json`):
- `G.<adhyāya>.<verse>[.<1|2>].wav` — Bhagavad Gītā (optional half 1/2)
- `smv<sarga>.<verse>.wav` — Sumadhva Vijaya · `rv<sarga>.<verse>.wav` — Rāghavendra Vijaya · `NS<n>.wav` — Prahlāda-kṛta Narasiṃha
- `vs.ns.<verse>.<pāda>.wav` — Nakha Stuti pādas · `vs<verse>.<pāda>.wav` — Hari Vāyu Stuti pādas
- best: `<dge text id>.wav`, e.g. `sumadhva_vijaya_sarga_5_24.wav` or `tirtha_prabandha_TP_DAK_006.wav`

Audio here is git-ignored; the manifests one level up are committed, so `python3 tools/kamadhenu_audit.py --fetch` re-creates the public part on any machine.
