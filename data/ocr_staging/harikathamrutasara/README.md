# Harikathamrtasara — what is segmented, what is attached, what is not

## The mula is done and live

`data/Tattvavada/Itara/DasaSahitya/harikathamrutasara/data.json` — **1,010
padyas, all 33 sandhis**, 32 of them closing on Jagannatha Dasa's ankita
(the thirty-third is the phalashruti, which closes the work rather than a
sandhi). Sandhi 24, absent from the Android app's resources, was recovered
from the printed mula and is complete.

`mula_segmented.json` is the segmenter's own output, kept because it records
which page each padya came from and which engine read it.

## The commentary is segmented but NOT attached

`commentary_segmented.json` — 634 blocks from 22 volumes, **575 of them
keyed to a padya the mula has (57% of the work)**.

The edition is the ಸರ್ವವ್ಯಾಖ್ಯಾನಸಾರಸಂಗ್ರಹ and lives up to the name: six
separate commentaries run under each padya, announced by numbered headings.
83% of blocks carry at least one.

| commentary | blocks |
|---|---|
| ಭಾವಪ್ರಕಾಶಿಕೆ | 416 |
| ಶ್ರೀಸಂಕರ್ಷಣ ಒಡೆಯರ ವ್ಯಾಖ್ಯಾನ | 412 |
| ಶ್ರೀಗುರುಹೃದಯಪ್ರಕಾಶಿಕೆ | 296 |
| ಶ್ರೀವ್ಯಾಸದಾಸ ಸಿದ್ಧಾಂತ ಕೌಮುದೀ | 259 |
| ಭಾವದರ್ಪಣ | 169 |
| ಭಾವದರ್ಶನ | 160 |

**It is not attached to the mula, and that is deliberate.** 67 blocks are
keyed to padyas the mula does not have — sandhi 12 has commentary on padyas
81 and 83 where the mula has 45 padyas in all. Until that is understood,
attaching would hang commentary on the wrong verse, which is worse than
having none: it reads as authoritative and nothing on the page says
otherwise.

## Two gaps, of different kinds

**Sandhis 2–9 have no commentary volume at all.** Not a segmentation
failure — those eight volumes were never scanned. Nothing in this repository
can fix that; the PDFs have to be found and OCR'd.

**Sandhis 26 and 27 come out at 0%** because they share a volume with
sandhi 25 and nothing inside it marks where one ends and the next begins.
Sandhi 30 had the same problem and is now fixed: those volumes write the
heading with the number AFTER the title (`ದೈತ್ಯತಾರತಮ್ಯ ಸಂಧಿ (ಸಂಧಿ-30)`) and
run it as a page header through the section, which states on every page
which sandhi the page belongs to. 26 and 27 are 12 padyas between them and
are still open.

The printed number is read but not trusted. The cover of `hks__29_30_hks`
prints "ಅಣುತಾರತಮ್ಯ ಸಂಧಿ (ಸಂಧಿ-30)" while the book's own contents page makes
Anutaratamya the twenty-ninth. Where they disagree the title decides,
because a title cannot be off by one.

## The appended works

Several volumes carry other dasas' compositions after the commentary proper,
each numbering its own padyas from 1. Volume 33 has three texts in it:
Jagannatha Dasa's Phalastuti, then **ಶ್ರೀ ಮನೋಹರವಿಠ್ಠಲಾಂಕಿತ ದಾಸವರ್ಯ**'s
Phalastuti Sandhi (17 padyas), then **ಶ್ರೀ ಭೀಮೇಶವಿಠಲಾಂಕಿತ ದಾಸ**'s
ಸಂಧಿಮಾಲಾ ಸಂಧಿ — Dasaru's own disciple. These are separate works that deserve
their own entries. They are counted and reported, never merged into the mula.
