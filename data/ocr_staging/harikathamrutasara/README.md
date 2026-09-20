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

**643 of 1,010 padyas carry commentary - 86% of everything that was scanned.**
664 blocks were cut from 22 volumes; 643 attached and 21 were refused.

| layer | padyas |
|---|---|
| ವ್ಯಾಖ್ಯಾನ (the edition's own) | 625 |
| ಪ್ರತಿಪದಾರ್ಥ | 545 |
| ಭಾವಪ್ರಕಾಶಿಕೆ | 421 |
| ಶ್ರೀಸಂಕರ್ಷಣ ಒಡೆಯರ ವ್ಯಾಖ್ಯಾನ | 415 |
| ಶ್ರೀಗುರುಹೃದಯಪ್ರಕಾಶಿಕೆ | 302 |
| ಶ್ರೀವ್ಯಾಸದಾಸ ಸಿದ್ಧಾಂತ ಕೌಮುದೀ | 255 |
| ಭಾವದರ್ಪಣ | 174 |
| ಭಾವದರ್ಶನ | 154 |

Attached by **the verse each block quotes**, never by the number it prints.
Both printed numbers are unreliable:

* The padya number is misread. Sandhi 12's commentary prints ಪದ್ಯ ೮೧ and
  ಪದ್ಯ ೮೩ over verses that are padya 41 and 43 - ೪ read as ೮, one stroke.
  56 blocks printed a padya number the verse underneath contradicts.
* The sandhi number is worse, because **the two editions order the sandhis
  differently**. The commentary set makes the eighteenth ಸರ್ವಸ್ವಾತಂತ್ರ್ಯ and
  the nineteenth ಕರ್ಮವಿಮೋಚನ; the mula's own contents page makes the
  eighteenth ಕ್ರೀಡಾವಿಲಾಸ and puts ಕರ್ಮವಿಮೋಚನ twenty-first. No offset
  corrects it - the twentieth is ಗುಣತಾರತಮ್ಯ in both. Several volumes number
  themselves ಸಂಪುಟ, a volume in a series, which never had to agree with a
  sandhi at all. **249 blocks sat under a sandhi number their own verse
  disagreed with.**

Scoring is the total of the matching runs over the shorter string, not
similarity. This library's sandhi 17 padya 1 carries the avataranika and the
pallavi ahead of the verse, so it runs 243 characters where the commentary
quotes 155 - the same verse, one with a preamble. Ratio similarity scores
that correct pair at 0.20; containment reads it above 0.9.

Two blocks claiming one padya are both refused: one of them is wrong and
nothing here knows which. Every attachment keeps `commentary_source`, the
page and the padya number the book printed, so a reader checking against the
printed edition has both.

## What is still missing, and why

**Sandhis 2-9: 264 padyas, no commentary.** Those eight volumes were never
scanned. Nothing in this repository can fix it; the PDFs have to be found.
This is the single biggest remaining gap in the work.

**Sandhis 26 and 27: 12 padyas, no commentary.** Not a matching failure.
Each of those padyas' best match across all 664 blocks scores between 0.38
and 0.65 and lands on an unrelated sandhi - the signature of nothing being
there. The volume named for 25-27 does not in fact carry them.

**Sandhi 32 is at 79%**, the only scanned sandhi below 80%.

## The appended works

Several volumes carry other dasas' compositions after the commentary proper,
each numbering its own padyas from 1. Volume 33 has three texts in it:
Jagannatha Dasa's Phalastuti, then **ಶ್ರೀ ಮನೋಹರವಿಠ್ಠಲಾಂಕಿತ ದಾಸವರ್ಯ**'s
Phalastuti Sandhi (17 padyas), then **ಶ್ರೀ ಭೀಮೇಶವಿಠಲಾಂಕಿತ ದಾಸ**'s
ಸಂಧಿಮಾಲಾ ಸಂಧಿ — Dasaru's own disciple. These are separate works that deserve
their own entries. They are counted and reported, never merged into the mula.
