# Editing the Sarvamūla corpus on your desktop

**For Pradeep, and anyone else cleaning up OCR text.**
Nothing in this guide needs a developer. Version 1.0 · 15 September 2026

---

## 1. What you are editing, and why it is fiddly

The texts live in files called `data.json`. JSON is good at structure and bad at
prose, and that mismatch causes every problem in this guide.

Two rules of JSON explain almost everything:

1. **A line break inside the text must be written `\n`, not the Enter key.**
   Press Enter and the file stops being valid JSON — the browser refuses the
   whole file and the page goes blank. *You no longer have to care: the setup in
   §2 translates it for you. Press Enter normally.*

2. **The text of a unit is always one long line**, no matter how the file is
   formatted. A JSON string cannot wrap. This is why §5 exists.

Everything else is ordinary text editing.

---

## 2. One-time setup

Do this once per machine, per clone.

### 2.1 Open a terminal in the repository

**Windows:** right-click the repository folder → **Git Bash Here**.
(GitHub Desktop already installed Git Bash. Do not use Command Prompt or
PowerShell — the commands below assume Git Bash.)

**Mac/Linux:** open Terminal and `cd` into the folder.

### 2.2 Check Python is present

```
python3 --version
```

If it says *command not found*, try:

```
python --version
```

If **that** also fails, install Python from <https://www.python.org/downloads/>
and tick **"Add Python to PATH"** during installation. Close and reopen Git Bash
afterwards.

> If `python` works but `python3` does not, use `python` everywhere below.

### 2.3 Install the safety hooks

```
sh tools/install_hooks.sh
```

You should see:

```
installed pre-commit

Done. Committing a data.json now escapes raw line breaks automatically.
```

**That is the whole setup.** Git does not carry hooks inside the repository, so
a fresh clone on the same machine needs this again.

---

## 3. What the hook does for you

When you commit, the hook quietly does two jobs.

**It fixes your line breaks.** Press Enter wherever you want a line break on the
page. On commit it is rewritten into the `\n` form JSON requires, and your line
break is kept. You will see:

```
fixed     data/.../data.json: 6 raw control character(s) inside strings
Your line breaks are kept -- each one renders as <br> on the page.
```

This is not an error. It is the hook doing its job.

**It keeps the file reviewable.** Each unit is put on its own line, so the
pull request shows *which units you changed* instead of "the whole file
changed". Before this, a reviewer could not see your changes at all.

**It stops you only for real damage.** If a file is broken in a way that cannot
be repaired automatically — a deleted bracket, a truncated save — the commit is
refused and the problem is named. Nothing is lost; fix it and commit again.

You can run the same checks by hand at any time:

```
python3 tools/normalize_data_json.py --check --all     # report problems, change nothing
python3 tools/normalize_data_json.py --all             # fix them
python3 tools/format_data_json.py --check --all        # check the one-unit-per-line shape
```

---

## 4. The everyday routine

```
1. GitHub Desktop → Fetch origin → Pull
2. Edit
3. GitHub Desktop → write a short summary → Commit
4. Push origin
5. Open a Pull Request; Tribhuvanachar reviews and merges
```

Work on a branch, not on `main`. In GitHub Desktop: **Current Branch → New
Branch**, name it for the work (`karma-nirnaya-cleanup`), and push that.

**Write what you actually changed** in the commit summary. "test" tells a
reviewer nothing. "Karmanirṇaya ṭīkā: paragraph breaks in maṅgalācaraṇam" tells
them everything.

---

## 5. Bulk editing: explode and implode

Direct editing of a `data.json` is fine for a small fix. For real work — regular
expressions, multi-file find-and-replace, reading a whole commentary — take the
text out, edit it as text, and put it back.

### 5.1 Explode

One file:

```
python3 tools/dge_text.py explode data/darshana/vedanta/dvaita/DvaitaVedantaIn/dasha_prakarana_granthas/karma_nirnaya/tika_bhavadipa/data.json --out work/
```

A whole grantha — point it at the folder and it does every `data.json` beneath:

```
python3 tools/dge_text.py explode data/darshana/vedanta/dvaita/DvaitaVedantaIn/dasha_prakarana_granthas/karma_nirnaya --out work/
```

It reports what it wrote:

```
work/tika_bhavadipa/data.md  (53 units)

1 file(s), 53 units. Edit the .md, then: python3 tools/dge_text.py implode work/ --all
```

### 5.2 Edit

Open the `.md` files under `work/` in Atom, VS Code, Notepad++ — anything. A unit
looks like this:

```
<!-- dge:unit 0 id=SM9:2 -->
<!-- reference: दशप्रकरणानि > 9. कर्मनिर्णयः > टीका_टिप्पणि > ... -->
<!-- section: मङ्गलाचरणम् -->

भावदीपः
श्रीराघवेन्द्रयतिविरचितो भावदीपः
लक्ष्मीनारायणं नत्वा पूर्णबोधादिकान् गुरून् ।
```

Now it is an ordinary text file:

* a line break is the Enter key
* a blank line starts a new paragraph
* `^` and `$` match the start and end of **a line**, so regular expressions work
* multi-file find-and-replace across the whole grantha works
* column selection works

**Two kinds of line are structure. Leave them exactly as they are:**

| line | meaning |
| --- | --- |
| `<!-- dge:file ... -->` | once at the very top — says which `data.json` this came from |
| `<!-- dge:unit 7 id=SM9:9 -->` | marks where each unit begins |

Delete or renumber one of those and implode will refuse to write, rather than
put your text into the wrong unit.

The `<!-- reference: ... -->` and `<!-- section: ... -->` lines are shown so you
can see what you are working on. They are **ignored** coming back — editing them
changes nothing. Titles and references are edited in the admin editor instead.

### 5.3 Implode

```
python3 tools/dge_text.py implode work/ --all
```

or a single file:

```
python3 tools/dge_text.py implode work/tika_bhavadipa/data.md
```

It reports what changed:

```
data/.../tika_bhavadipa/data.json  (1 unit(s) changed)
```

Then commit and push as usual. **Do not commit the `work/` folder** — it is a
scratch area. If you like, delete it afterwards.

### 5.4 Why this cannot lose the corpus

Implode never rebuilds the `data.json`. It opens the original file, replaces the
body text of each unit, and writes that back. Ids, references, provenance,
breadcrumbs, footnotes, ordering and schema are never taken out, so they cannot
be lost.

It refuses to write if a unit marker is missing, if the number of units does not
match, or if an id no longer lines up. A damaged `.md` can cost you your edits;
it cannot damage the corpus.

---

## 6. Styling the text

### What works everywhere, today

| you type | what the reader sees |
| --- | --- |
| Enter (a line break) | a line break |
| a blank line | a new paragraph |

That is it, for now — and it covers most OCR cleanup.

### What needs switching on first

Bold, italic, headings and verse indentation exist, but they are **off by
default** and must be enabled per work. If you type `**bold**` in a work that
has not been switched on, the reader sees the asterisks, not bold text.

Why off by default: `*` already appears 6,305 times in the corpus as an
editorial mark — in the Śatapatha Brāhmaṇa, for instance. Treating every one of
those as italic would silently mangle thousands of passages.

**So: ask before styling a work.** Say which grantha you want to style and it
will be enabled for that work, after which:

| you type | you get |
| --- | --- |
| `**text**` | **bold** |
| `*text*` | *italic* |
| `# text` | a heading |
| `> text` | a verse line |
| `---` | a colophon |

---

## 7. Things to avoid

| don't | why |
| --- | --- |
| Open a `data.json` in Word, WordPad or Google Docs | They replace `"` with curly quotes and destroy the file beyond automatic repair. Use a **code** editor. |
| Save with a different encoding | Always UTF-8. Atom and VS Code do this by default; don't change it. |
| Commit the `work/` folder | It is scratch. Only `data/` changes belong in a commit. |
| Edit directly on `main` | Use a branch, so your work can be reviewed before it reaches the site. |
| Renumber or delete `<!-- dge:unit ... -->` lines | Implode will refuse, and rightly. |
| Skip `sh tools/install_hooks.sh` on a new clone | Without it the hook is not there, and a broken file reaches the pull request. |

---

## 8. If something goes wrong

**The commit was refused.** Read the message — it names the file and the
problem. Then:

```
python3 tools/normalize_data_json.py --check --all
```

Nine times out of ten the hook was never installed in that clone. Run
`sh tools/install_hooks.sh` and commit again.

**The page is blank after my change.** The file is not valid JSON. Run the
command above; it will say where.

**"python3: command not found".** See §2.2 — use `python`, or install Python.

**Implode refuses: "has N units, data.json has M".** A `<!-- dge:unit ... -->`
line was deleted or duplicated. Re-explode into a fresh folder and redo the edit,
or restore the marker. Nothing in the corpus has been touched.

**I have made a mess and want to start over.** In GitHub Desktop, right-click the
changed file → **Discard Changes**. That restores the last committed version.

**Still stuck.** Say what you ran and paste the message. Do not push a file you
suspect is broken — the checks will stop it anyway, and it is easier to fix
before it reaches a pull request.

---

## 9. Command reference

| command | what it does |
| --- | --- |
| `sh tools/install_hooks.sh` | one-time setup per clone |
| `python3 tools/dge_text.py explode PATH --out work/` | text out of a file or folder, into `.md` |
| `python3 tools/dge_text.py implode work/ --all` | `.md` back into the `data.json` files |
| `python3 tools/dge_text.py implode FILE.md` | one file back |
| `python3 tools/normalize_data_json.py --check --all` | report invalid JSON, change nothing |
| `python3 tools/normalize_data_json.py --all` | fix raw line breaks everywhere |
| `python3 tools/format_data_json.py --check --all` | check the one-unit-per-line shape |
| `python3 tools/format_data_json.py --all` | restore that shape |

All of these are run from the **top of the repository**, in Git Bash on Windows.

---

*Sarvamula.org · Digital Grantha Engine*
