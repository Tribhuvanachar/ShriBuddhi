# Sumadhva Vijaya — Sri Narayana Panditacharya

The foundational hagiography of Sri Madhvacharya's life, 16 sargas. This
folder currently holds **audio only** — no verse text yet (see below).

## Status

- **Audio**: `assets/` — 1,041 mp3 files, renamed using an authoritative
  filename↔verse mapping (`sumadhvijaya_sarga_audio_mapping.json`,
  user-supplied, derived directly from the original app's own playback
  list `indplaylist.txt`) rather than the earlier heuristic guess. Naming:
  - Numbered verse recitations: `smv<sarga>.<verse_no>.mp3` (e.g.
    `smv1.1.mp3` … `smv16.58.mp3`), where `<verse_no>` is the app's own
    true verse number for that sarga, not just sequential file position.
  - Per-sarga chapter-opening announcement (1 per sarga, sargas 2–16):
    `smv<sarga>.0.mp3`.
  - Sarga 1's four preliminary tracks (app-level intro content preceding
    the chapter-opening announcement, distinct from sargas 2–16 which only
    have one): `smv1.0a.mp3` … `smv1.0d.mp3`.
  - Closing colophon/phalashruti clip(s) after the last verse of a sarga:
    `smv<sarga>.end.mp3` (sarga 16 has two: `smv16.end.mp3`,
    `smv16.end2.mp3`).
  - Full mapping (sarga, verse_no, track_type, new_name, original 6-digit
    source code) for every file: `rename_manifest.json`.
  - Extracted from `smv-assets-audio.7z.001/.002/.003` (joined, then a 7z
    containing a nested `smv-assets-audio.zip`).
- **3 verses have no audio file** — a real gap in the source app itself,
  not a processing error. The app's own playlist references
  `105008.mp3`, `105014.mp3`, `105016.mp3` (sarga 5, verses 8, 14, and 16)
  but no corresponding file exists in the extracted archive. See
  `rename_manifest.json` → `missing_from_source_archive`.
- **Text**: not yet available. Two attempts so far:
  - `smv-assets-text.zip` — Android `res/` resources only (layouts,
    ExoPlayer UI), no `assets/` folder, no verse content at all.
  - `smvassetstext2.zip` — sarga-name UI labels in six scripts, the audio
    filename manifest (used above), and a Kannada tātparya (meaning)
    fragment covering only the opening maṅgalācaraṇa (~8 lines); the
    remaining ~1,040 lines are an empty, unfilled placeholder template.
    No Sanskrit mūla text anywhere in the bundle.

  A proper source (the app's actual verse-text `assets/` folder, or
  another edition) is still needed before this grantha can be populated
  with text the way Yukti Mallika / Svapna-Vrindavanakhyana were.

## History

The audio was first renamed by a heuristic (sequential position per sarga,
guessed from the numeric gaps in the source codes) which got the sarga
groupings right but mis-ordered 4 files at the start of sarga 1 and
couldn't distinguish "duplicate index" front-matter tracks from real
verses. That heuristic was superseded once the user supplied the app's
actual playlist-derived mapping, which resolved every prior ambiguity:
the "duplicate index" pairs turned out to be two distinct track types
(front-matter vs. numbered verse), not alternate takes of the same verse,
and the "high-numbered outlier per sarga" guess (colophon/phalashruti)
was confirmed correct by the mapping's own `sarga-ending/special` label.
