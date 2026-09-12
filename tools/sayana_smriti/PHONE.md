# Getting Sāyaṇa when the servers are refused

## The shape of the problem

`wisdomlib.org` answers **HTTP 403 to every request from a datacenter IP range**.
Measured, not guessed — a 50-mantra run from GitHub Actions returned:

```
pages_fetched: 50      sayana_added: 0
missing_pages: 50      http: { hit: 0, miss: 0, fail: 50 }
```

250 attempts, 250 × `HTTP 403`, no other failure mode.

The decisive detail: **`/robots.txt` is refused too**, under both the importer's
declared bot User-Agent and curl's default. A site cannot state a crawler policy
to an address it will not talk to. So this is not wisdomlib declining crawlers —
it is an edge rule against cloud IP ranges that never inspects who is asking.

That distinction matters for what to do next. There is no policy here to work
around, and nothing needs disguising. The same request from an ordinary consumer
connection is simply not pre-blocked.

## What will and will not work

| Route | Verdict |
|---|---|
| GitHub Actions | **Blocked.** Measured: 250/250 × 403. |
| GitHub Codespaces | **Almost certainly blocked** — Azure datacenter ranges, same category as Actions. Two minutes to test; do not plan around it. |
| Google Colab | **Almost certainly blocked** — Google Cloud ranges. |
| Any VPS / cloud box | **Blocked.** Datacenter by definition. |
| **Android phone (Termux)** | **Works.** Mobile-carrier or home-wifi address. |
| **Home laptop / desktop** | **Works**, and is the least fiddly if you have one. |
| Asking wisdomlib directly | **The real fix.** The text is public domain and DGE is a non-commercial library; an allowlist or a bulk export solves this permanently and for everyone. |

Nothing about the importer changes between these. Same code, same honest
User-Agent, same 1.2 s delay between pages — gentler than a person scrolling.

## On a laptop

```bash
git clone https://github.com/Tribhuvanachar/bhumandala.git
cd bhumandala
pip install -r tools/sayana_smriti/requirements.txt

# 50 mantras, writes nothing — confirms your connection is not refused
python tools/sayana_smriti/import_sayana_rigveda.py --dge-root dge \
       --mandala 1 --limit 50 --dry-run

# the real run, ~3.5 hours
python tools/sayana_smriti/import_sayana_rigveda.py --dge-root dge
```

Then commit `dge/data/vedas/rigveda/` on a branch and open a PR.

## On an Android phone

Install **Termux** — from [F-Droid](https://f-droid.org/packages/com.termux/),
not the Play Store; the Play Store build is frozen at an old version and its
`pkg install` no longer resolves.

```bash
pkg install bash curl
curl -O https://raw.githubusercontent.com/Tribhuvanachar/bhumandala/main/tools/sayana_smriti/run_on_phone.sh
bash run_on_phone.sh
```

The script installs python and git, makes a **partial clone** (the full repo
carries ~1 GB of audio and Mahābhārata archives this job never opens; a
`blob:none` clone with a two-path sparse checkout brings the working tree to
about 100 MB), runs the smoke test, and only then offers to start the real run.

It commits after each maṇḍala and pushes to `sayana/phone-import` — **never to
main**. Pushing asks for your GitHub username and a personal access token with
`repo` scope (Settings → Developer settings → Personal access tokens).

### Practicalities

- **Keep it charging.** Three to four hours of continuous network.
- The script takes a Termux wake lock, so the screen can go off. Without it
  Android suspends the process a few minutes in and the run never finishes.
- **Interrupting it is safe.** Finished maṇḍalas are committed, and within a
  maṇḍala the importer skips any mantra that already carries a `sayana` layer.
  Re-running the script resumes where it stopped.
- Wifi and mobile data are worth trying independently — some ISPs route
  through address space that carries the same reputation as a datacenter.

### If the smoke test reports `sayana_added: 0`

Your connection is refused as well. The script stops there deliberately rather
than starting a four-hour run that would fetch nothing. Try the other network
(mobile data instead of wifi, or the reverse) before anything else.

### Do not silence the drift guard

If a run aborts with `ALIGNMENT DRIFT EXCEEDED`, that is the importer refusing
to write. `rigveda_docmap.json` maps each mantra to a wisdomlib page id, and
those ids are contiguous — so if the site's numbering ever shifts, every mantra
past the shift silently receives the *wrong* commentary and the result looks
entirely plausible. The guard checks each page's own title and its Devanagari
against the mantra already in DGE, and stops past 2% mismatch.

Raising `--max-drift` to get past it converts a loud failure into ten thousand
quiet ones. Report the drift examples it prints instead.

## What comes back

Per mantra, written into `items[].commentaries` on the ten maṇḍala files:

- `sayana` — Sāyaṇa's Ṛgveda-bhāṣya as rendered in Wilson's edition (English)
- `wilson` — Wilson's translation of the mantra itself

`dge/js/core.js` already labels and renders both, and
`tools/sayana_smriti/verify_import.py` will check coverage before you merge.

## The other corpora do not need any of this

Only wisdomlib and sacred-texts refuse runners. A probe from Actions found
**archive.org, sanskritdocuments.org, sa.wikisource and GRETIL all reachable**
(200). So the Smṛti importer, the phase-2 Veda layers and the minor-smṛti
import via sa.wikisource can all run in Actions as normal — it is specifically
and only Sāyaṇa-on-the-Ṛgveda that needs a residential connection.
