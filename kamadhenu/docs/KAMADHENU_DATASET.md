# The Kamadhenu dataset format (Phase 3)

One JSON object per text↔audio pair, one per line (`*.jsonl`). The schema is
`kamadhenu/data/schema/kamadhenu_schema.json`; the validator (`kamadhenu/scripts/kamadhenu_validate_dataset.py`)
checks every line against it and against the audio on disk.

Only six fields are required: `id`, `text`, `audio`, `speaker`, `source`, `split`. Everything else may be `null`;
the validator counts what is missing so gaps are visible, and nothing is ever deleted automatically.

| group | fields | filled by |
|---|---|---|
| identity | id (= `km_` + SHA-1 prefix of the audio), text_id, work, part | mapping stage |
| text | text (Devanagari, one pāda per line), normalized_text (SLP1) | `tools/kamadhenu/texts.py` |
| audio | audio, audio_sha1, duration, sample_rate, channels, recording_quality, snr_db, peak_dbfs, clipping | `tools/kamadhenu/inventory.py` (ffprobe + decode) |
| who / where | speaker, source, script, language | human decision (speaker) + folder |
| metre | meter, meter_confidence, meter_kind, pada_count, pada_text, laghu_guru, gana, syllables, syllables_per_pada, yati, chandas_source | DGE Chandas engine via `tools/kamadhenu/chandas_bridge.py` |
| trust | text_audio_confidence, verified_by | mapping + human/ASR verification |
| use | split (train / validation / test / reference / review / excluded), exclusion_reason, notes | pilot builder / validator |

Conventions: Devanagari only in `text`; pādas on separate lines; `laghu_guru` uses `L`/`G` with `|` between pādas
(the same string the site's chandas page shows); `meter` is the Devanagari name the engine prints, so the 245-vṛtta
database is the vocabulary, not a fixed short list.

The current master file `kamadhenu_dataset/metadata.jsonl` (2,544 records) predates this schema and uses slightly
different names (`chandas` → `meter`, `audio_quality` → `recording_quality`, `mapping_confidence` →
`text_audio_confidence`, `speaker` as folder proxy). `kamadhenu/scripts/build_pilot.py` converts on the fly; the
next audit run will emit the schema names directly.
