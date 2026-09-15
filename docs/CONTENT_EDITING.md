# Editing content on the desktop

For whoever is cleaning up OCR text and styling it for the page. Nothing here
needs a developer.

## Set up once per machine

After cloning, in a terminal at the top of the clone:

```
sh tools/install_hooks.sh
```

On Windows use **Git Bash** (right-click the folder → "Git Bash Here"). GitHub
Desktop installs it.

That is the whole setup, and it only has to be done once per clone. Git does not
carry hooks in the repository, so a fresh clone on the same machine needs it
again.

## What the hook does for you

A line break in the text is a real feature: it becomes a `<br>` on the page.
But these files are JSON, and JSON insists that a line break inside text be
written as the two characters `\n`. A line break typed with the Enter key is
against the rules, and the browser refuses the whole file — the page simply
stops loading.

So the hook translates. Press Enter where you want a line break; when you
commit, it is silently rewritten into the form JSON accepts. Your line break is
kept. You will see:

```
fixed     data/.../data.json: 6 raw control character(s) inside strings
Your line breaks are kept -- each one renders as <br> on the page.
```

If a file is broken in a way escaping cannot repair — a deleted bracket, a
truncated file — the hook stops the commit and says so, rather than committing
something that will not load.

You can run the same thing by hand at any time:

```
python3 tools/normalize_data_json.py --check --all     # report only
python3 tools/normalize_data_json.py data/.../data.json # fix one file
```

## Bulk editing: explode and implode

A `data.json` now holds one unit per line, so a diff shows exactly which units
you changed and `^`/`$` work per unit. But the text of a unit is still a single
long line -- a JSON string cannot wrap, however the file is formatted -- so for
real work on the text itself, take it out.

So take the text out, edit it as text, and put it back.

**1. Explode** — in a terminal at the top of the clone:

```
python3 tools/dge_text.py explode data/darshana/vedanta/dvaita/DvaitaVedantaIn/dasha_prakarana_granthas/karma_nirnaya/tika_bhavadipa/data.json --out work/
```

A whole grantha at once works too — point it at the folder:

```
python3 tools/dge_text.py explode data/.../karma_nirnaya --out work/
```

**2. Edit** the `.md` files under `work/` in Atom, VS Code, Notepad++, anything.
This is an ordinary text file:

* a line break is the Enter key
* a blank line starts a new paragraph
* `^` and `$` mean what your editor thinks they mean, so regex passes,
  multi-file find-and-replace and column selection all work normally

Two kinds of line are structure, not content, and must be left exactly as they
are:

```
<!-- dge:file ... -->      once at the top
<!-- dge:unit 7 id=SM9:9 --> before each unit
```

The `<!-- reference: ... -->` and `<!-- section: ... -->` lines are there so you
can see what you are working on. They are ignored on the way back, so editing
them changes nothing — edit those in the admin editor instead.

**3. Implode** — put it back:

```
python3 tools/dge_text.py implode work/ --all
```

It tells you how many units changed. Then commit and push as usual.

### Why this is safe

Implode never rebuilds the `data.json`. It opens the original, replaces the body
text of each unit, and writes that. Ids, provenance, breadcrumbs, footnotes,
ordering and schema are never taken out, so they cannot be lost. If a marker
line has been deleted, or an id no longer matches, it refuses to write rather
than guess.

## Styling

Inside the text you can use:

| you write | you get |
| --- | --- |
| `**text**` | **bold** |
| `*text*` | *italic* |
| a blank line | a new paragraph |
| `> text` | a verse line |
| `# text` | a heading |
| `---` | a colophon |
| `**"word"**` | a tappable cross-reference to that word |

**One caveat.** This styling only renders for a commentary marked
`"format": "gold_v2_2"`. Elsewhere, a line break renders as a line break — but
`**bold**` would show the asterisks as themselves. Ask before styling a work
that has not been switched over, or the page will show your markup instead of
your meaning.

## If a push is refused

Nothing is lost. Run:

```
python3 tools/normalize_data_json.py --check --all
```

It names the file and the problem. Most of the time the hook was not installed
in that clone — run `sh tools/install_hooks.sh`, then commit again.
