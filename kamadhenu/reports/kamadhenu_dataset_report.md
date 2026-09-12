# Kamadhenu dataset validation

06 Sep 2026, 08:35 PM IST · inputs: /home/user/bhumandala/kamadhenu_dataset/metadata.jsonl

* records: **3892**
* clean (or only 'speaker unattributed'): **0**

| issue | records |
|---|---|
| missing_source | 3892 |
| missing_split | 3892 |
| qc | 2308 |
| sample_rate_below_16k | 989 |
| too_fast_for_text | 942 |
| meter_missing | 858 |
| text_audio_confidence_low | 574 |
| too_slow_for_text_or_repeated | 550 |
| audio_over_60s | 508 |
| text_missing | 405 |
| laghu_guru_missing | 405 |
| duplicate_text_of | 224 |
| duplicate_audio_of | 23 |
| text_non_devanagari_chars | 15 |
| duration_mismatch | 12 |
| text_has_trailing_number | 1 |
| audio_unreadable | 1 |

Nothing was changed or deleted; each record's flags are in the JSON report under `per_record`.
