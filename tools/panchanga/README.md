# Panchāṅga acquisition scripts

One script per source, each taking a fresh copy of that source's APK and
reproducing the acquisition documented in `dge/sources/README.md` and
`dge/PENDING.md` (11 Sep 2026 entries) as a re-runnable tool instead of a
one-off manual pass.

```
python3 tools/panchanga/acquire_uttaradi.py  --apk path/to/uttaradi.apk
python3 tools/panchanga/acquire_srs.py       --apk path/to/srs.apk
python3 tools/panchanga/acquire_vishwesha.py --apk path/to/vishwesha.apk
```

Each script:
- verifies the APK's package name matches the expected source (refuses to
  run against the wrong app rather than silently extracting garbage);
- pulls the packaged asset(s) and derives the actual date range from the
  data itself, not the app's version string;
- writes to `dge/sources/<institution>/panchanga/<derived-date-range>/`
  with a `source-manifest.json` per architecture doc §24.

**Idempotent, and safe against silent overwrites**: re-running against the
exact same APK is a no-op (`already_acquired`). Running against a genuinely
different acquisition that would land in the same folder (same year range,
different content) raises rather than overwrites — per §24, a real content
change needs a new folder (a `-v2` suffix, say), a deliberate choice by
whoever runs it, not something this script decides on its own.

**Not covered yet, because the source itself is incomplete or blocked**
(see `dge/sources/README.md` for the details on each):
- Udupi Panchanga — no APK has been supplied at all.
- Tithi Nirṇaya, Vyāsarāja Matha Sosale — ship without any native code in
  the copies acquired so far; nothing to statically extract until a
  complete app bundle arrives.
- Sode Matha — server/API-backed, not a packaged asset; needs either an
  authorized API or a website-crawl approach, not this kind of script.
