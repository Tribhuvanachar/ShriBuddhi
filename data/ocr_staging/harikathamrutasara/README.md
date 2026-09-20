# Harikathamrtasara — what is segmented, what is attached, what is not

## The mula is done and live

`data/Tattvavada/Itara/DasaSahitya/harikathamrutasara/data.json` — **1,010
padyas, all 33 sandhis**, 32 of them closing on Jagannatha Dasa's ankita
(the thirty-third is the phalashruti, which closes the work rather than a
sandhi). Sandhi 24, absent from the Android app's resources, was recovered
from the printed mula and is complete.

`mula_segmented.json` is the segmenter's own output, kept because it records
which page each padya came from and which engine read it.

## The commentary is attached

**925 of 1,010 padyas carry commentary - 92% of the work.** 935 blocks cut
from 30 volumes; 925 attached, 10 refused.

| layer | padyas |
|---|---|
| ವ್ಯಾಖ್ಯಾನ (the edition's own) | 878 |
| ಪ್ರತಿಪದಾರ್ಥ | 746 |
| ಭಾವಪ್ರಕಾಶಿಕೆ | 456 |
| ಶ್ರೀಸಂಕರ್ಷಣ ಒಡೆಯರ ವ್ಯಾಖ್ಯಾನ | 444 |
| ಶ್ರೀಗುರುಹೃದಯಪ್ರಕಾಶಿಕೆ | 330 |
| ಶ್ರೀವ್ಯಾಸದಾಸ ಸಿದ್ಧಾಂತ ಕೌಮುದೀ | 279 |
| ಭಾವದರ್ಪಣ | 186 |
| ಭಾವದರ್ಶನ | 157 |

Sandhis 2-9 were at zero until 20 Sep 2026, when their eight volumes were
uploaded and OCR'd - 2,969 pages through Vision. They now run 94-100% each.

Those eight have ONE engine behind them where the other 23 have two. That
was taken to mean they are the weak part of the work, and a second Sarvam
pass over all 2,969 of their pages was about to be paid for. Measured
(`tools/hks/ocr_quality.py`), the assumption is backwards:

| | sandhis 2-9 | the other 23 volumes |
|---|---|---|
| quoted-verse fidelity vs the canonical mula | **0.957** | 0.953 |
| blocks whose quoted verse scores under 0.90 | **1.6%** | 4.8% |
| Vision mean per-word confidence | **0.873** | 0.843 |
| pages under 0.80 confidence | **5.8%** | 18.9% |

**These are the cleanest scans in the book.** The volumes that genuinely
read badly -- 21, 22, 25_26_27, 29_30 and the unnumbered one, at 30-57%
weak pages -- are all in the two-engine set, and have already had Sarvam
and Gemini spent on them. A second engine over 2-9 would be buying a second
opinion on the pages that need it least.

What is weak in 2-9 is 173 pages, and two thirds of those are tables --
tattva charts and ಭಗವದ್ರೂಪ name-grids where the letters are legible and
only the grid is lost. That is a layout problem, and the tool for it is a
layout-preserving engine, not a language model. 112 prose pages across
eight volumes, 3.8% of them, read poorly enough to want a second reading.

One thing 2-9 do NOT get is a single-engine model pass. With two readings
and a disagreement, a model adjudicates between two witnesses. With one
reading it has nothing to adjudicate and generates instead, and invented
Kannada in a Dvaita commentary reads as authoritative when it is not.

Attached by **the verse each block quotes**, never by the number it prints.
Both printed numbers are unreliable: 57 blocks printed a padya number the
verse underneath contradicts, and 307 sat under a sandhi number their own
verse disagreed with - the two editions order the sandhis differently.

## What is still missing, and why

**Sandhis 26 and 27: 12 padyas, no commentary.** Not a matching failure.
Each of those padyas' best match across all 935 blocks scores between 0.38
and 0.65 and lands on an unrelated sandhi - the signature of nothing being
there. The volume named for 25-27 does not in fact carry them.

**Sarvam on sandhis 2-9** - 2,969 pages, about Rs1,306 at the measured rate.
That buys the second reading, the conflict detection, and the Gemini pass
those eight sandhis have not had.

## The appended works

Several volumes carry other dasas' compositions after the commentary proper,
each numbering its own padyas from 1. Volume 33 has three texts in it:
Jagannatha Dasa's Phalastuti, then **ಶ್ರೀ ಮನೋಹರವಿಠ್ಠಲಾಂಕಿತ ದಾಸವರ್ಯ**'s
Phalastuti Sandhi (17 padyas), then **ಶ್ರೀ ಭೀಮೇಶವಿಠಲಾಂಕಿತ ದಾಸ**'s
ಸಂಧಿಮಾಲಾ ಸಂಧಿ — Dasaru's own disciple. These are separate works that deserve
their own entries. They are counted and reported, never merged into the mula.
