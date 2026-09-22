# What the corpus claims versus what it holds

Written 22 Sep 2026. Three findings, one fixed, two open. All three are
the same shape: an index or a flag asserting something the files do not
support, which nothing checked.

## 1 · 328 dead links, fixed

`data/library.json` marks each grantha `populated`. Downstream repos had
that flag recomputed by `tools/site_parity.py`, which tested **whether the
file exists**. The Ānandamakaranda shelf carries an empty
`tika_jayatirtha` and an empty `tippani` beside **every one** of its ten
upaniṣad books — files that exist and contain `"items": []`. So 328
entries in each of BrahmaBuddhi and JagatTest advertised texts that open
to nothing.

`has_units()` now opens the file and counts, across the three shapes the
corpus uses (`items` list, `shlokas` dict, bare list). Downstream reads
**650 populated instead of 978**, with none that open to nothing.

ShriBuddhi's own hand-maintained library had nine of the same:
`vedanga/chandas`, and all eight layers of
`sutra_prasthana/anuvyakhyana_sudha`. Flipped to `populated: false`. The
library now says **1,305** rather than 1,314, and says it truthfully.

`tests/test_site_parity.py` guards it — including a test that drives
`repopulate_library` itself, because four tests of the helper all passed
with the caller reverted to `is_file()`.

## 2 · 20 empty layer directories — open

Independent of the flag: those directories are real and empty. Every
`Anandamakaranda/upanishad_prasthana` book has a `tika_jayatirtha` and a
`tippani` holding zero items — 20 files shelf-wide. They are now correctly
marked unpopulated, so no reader is sent to them, but the question of
whether the text exists anywhere to fill them is open.

`sutra_prasthana/anuvyakhyana_sudha` is the same, eight layers deep.

## 3 · 74 orphaned dhātu-prayoga indexes — open, harmless

`data/vedanga/vyakarana/dhatu_prayoga/by_grantha/` holds 1,038 index
files. **74 name a grantha that does not exist.** The cause is two shelf
renames the index was never rebuilt after:

| stale path in the index | count | the shelf that exists now |
|---|---|---|
| `darshana/vedanta/dvaita/DvaitaVedanta/…` | 33 | `DvaitaVedantaIn` |
| `darshana/vedanta/dvaita/SarvaMula/…` | 27 | `Tattvavada/SarvaMula` |
| `DvaitaVedantaIn/…` (shelf exists, grantha does not) | 13 | — |
| one `dasa_sahitya` path with a hex-encoded name | 1 | — |

These are dead weight rather than broken links: nothing fetches them,
because no reader page exists at those paths. Rebuilding the index with
`tools/build_dhatu_prayoga_index.py` would clear them.

**A correction while recording this.** An earlier note said "162
references target a nonexistent `sutra_prasthana/anuvyakhyana`". That
conflated two things and was wrong on both. The 162 is the *item count* of
`Anandamakaranda/sutra_prasthana/anuvyakhyana/tika_jayatirtha`, which
exists and has content; and `Tattvavada/SarvaMula/sutra_prasthana/anuvyakhyana`
exists too, with 525 items. The real defect is the 74 orphaned indexes
above.

## The pattern worth noticing

In all three, a derived artefact — a flag, an index — outlived the thing it
described, and nothing compared the two. The cheap guard is a test that
opens the file rather than trusting the name, which is what §1 now has and
§3 does not.
