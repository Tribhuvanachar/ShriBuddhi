# Vendored third-party libraries

Copied into the repository rather than fetched from a CDN. A reader on a
patchy connection, behind a filtering proxy, or reading offline gets the same
app as everyone else, and the version cannot drift under us.

## sanscript-1.3.3.min.js

| | |
|---|---|
| Package | [`@indic-transliteration/sanscript`](https://github.com/indic-transliteration/sanscript.js) |
| Version | 1.3.3 |
| Licence | MIT — Arun Prasad and Sanskrit coders |
| Source | `https://cdn.jsdelivr.net/npm/@indic-transliteration/sanscript@1.3.3/sanscript.min.js` |
| Exports | `window.Sanscript` (`Sanscript.t(text, fromScheme, toScheme)`) |

Why it is here and not on jsDelivr, where it lived until 10 Sep 2026:

- **The reader's script setting depends on it.** Devanagari ⇄ IAST/Kannada/
  Telugu/Tamil/Malayalam is the transliteration engine for the whole site.
- **So does the धातु/कोश word marking.** `js/highlight-words.js` looks a word
  up in a Devanagari-keyed index; in any other display script the word on
  screen has to be transliterated back before the lookup can be attempted at
  all. A CDN that does not answer means no marks, silently.
- **The pages had drifted.** 20 pages loaded 1.3.3, four loaded 1.3.2, and one
  loaded `sanscript@0.1.3` — a different, unrelated package. One vendored file
  is one version everywhere.

To refresh:

    curl -sSo js/vendor/sanscript-<version>.min.js \
      https://cdn.jsdelivr.net/npm/@indic-transliteration/sanscript@<version>/sanscript.min.js
    grep -rl 'sanscript-1.3.3.min.js' dge --include='*.html' | \
      xargs sed -i 's/sanscript-1\.3\.3\.min\.js/sanscript-<version>.min.js/g'

Keep the version in the filename: a cached copy of an older build under the
same name is exactly the drift this is here to prevent.
