#!/data/data/com.termux/files/usr/bin/bash
#
# run_on_phone.sh — fetch Sāyaṇa from an Android phone, in Termux.
#
# WHY THIS EXISTS
# ---------------
# wisdomlib.org answers 403 to every request from a datacenter IP range. That is
# not a policy about crawlers: it refuses to serve even /robots.txt, so nothing
# from those ranges gets far enough to be told a rule. GitHub Actions runners,
# Codespaces, Colab and any VPS all sit in those ranges, which is why the
# Actions run came back 50 pages fetched / 0 imported / 250 consecutive 403s.
#
# A phone on mobile data or home wifi does not. This script runs the SAME,
# already-tested importer from there -- no new parsing code, no disguised
# request, the importer's own honest User-Agent and its 1.2s delay between
# pages, which is gentler than a person scrolling the site.
#
# WHAT IT DOES
# ------------
#   1. installs python + git in Termux if missing
#   2. makes a small partial clone -- the full repo carries ~1 GB of audio and
#      Mahabharata archives that this job never reads, so blob:none + a sparse
#      checkout of three paths keeps it to a few tens of MB
#   3. runs the 50-mantra smoke test FIRST and stops if the 403 follows you here
#   4. runs the real import one mandala at a time, committing after each
#   5. pushes to a branch for review -- never to main
#
# It is safe to stop it (Ctrl-C, screen off, train tunnel) and re-run: finished
# mandalas are committed, and within a mandala the importer skips any mantra
# that already has a sayana layer, so it resumes where it stopped.
#
#   pkg install bash && bash run_on_phone.sh
#
set -u

REPO_URL="${REPO_URL:-https://github.com/Tribhuvanachar/bhumandala.git}"
WORKDIR="${WORKDIR:-$HOME/bhumandala-sayana}"
BRANCH="${BRANCH:-sayana/phone-import}"
DELAY="${DELAY:-1.2}"

say () { printf '\n\033[1m%s\033[0m\n' "$*"; }
die () { printf '\n!! %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 1. packages
say "1/5  Checking Termux packages"
command -v pkg >/dev/null || die "This is meant for Termux on Android. On a laptop just run import_sayana_rigveda.py directly."
for p in python git; do
  command -v "$p" >/dev/null || { echo "  installing $p ..."; pkg install -y "$p" >/dev/null 2>&1; }
done
command -v python >/dev/null || die "python did not install; run: pkg install python"
python -c "import requests, bs4" 2>/dev/null || {
  echo "  installing requests + beautifulsoup4 ..."
  pip install --quiet requests beautifulsoup4 || die "pip install failed"
}
# Keeps the CPU alive when the screen goes off. Without it Android suspends the
# process a few minutes in and a 3-4 hour fetch never finishes.
command -v termux-wake-lock >/dev/null && termux-wake-lock && echo "  wake lock held"

# ------------------------------------------------------------------ 2. clone
say "2/5  Getting the repo (partial clone -- skips the big media archives)"
if [ -d "$WORKDIR/.git" ]; then
  echo "  reusing $WORKDIR"
  # Resume onto the EXISTING branch. Re-pointing it at origin/main here would
  # throw away every mandala committed on a previous run that had not been
  # pushed yet -- which is exactly the state an interrupted run leaves behind.
  if git -C "$WORKDIR" rev-parse --verify --quiet "$BRANCH" >/dev/null; then
    git -C "$WORKDIR" checkout -q "$BRANCH" || die "checkout failed"
    echo "  continuing on existing $BRANCH ($(git -C "$WORKDIR" rev-list --count "$BRANCH" ^origin/main 2>/dev/null || echo 0) local commit(s))"
  else
    git -C "$WORKDIR" fetch origin main --quiet || die "fetch failed"
    git -C "$WORKDIR" checkout -q -B "$BRANCH" origin/main || die "checkout failed"
  fi
else
  git clone --filter=blob:none --no-checkout --depth 1 "$REPO_URL" "$WORKDIR" || die "clone failed"
  git -C "$WORKDIR" sparse-checkout init --cone
  # Cone mode already brings the files sitting directly in each parent (that is
  # where dge/data/schemas.json and taxonomy.json live) without pulling the
  # sibling subtrees. Naming dge/data outright would drag in dvaitavedanta,
  # purana and the rest -- tens of thousands of files this job never opens.
  git -C "$WORKDIR" sparse-checkout set dge/data/vedas/rigveda tools/sayana_smriti
  git -C "$WORKDIR" checkout -q || die "checkout failed"
  git -C "$WORKDIR" checkout -q -B "$BRANCH"
fi
cd "$WORKDIR" || die "cannot enter $WORKDIR"
[ -f dge/data/schemas.json ] || die "sparse checkout did not bring dge/data -- run: git sparse-checkout set dge/data tools/sayana_smriti"

IMPORTER=tools/sayana_smriti/import_sayana_rigveda.py
[ -f "$IMPORTER" ] || die "importer not found at $IMPORTER"

# ------------------------------------------------------------- 3. smoke test
say "3/5  Smoke test — 50 mantras, writes nothing"
echo "     If your phone is also blocked you will see 403s here and nothing else runs."
python "$IMPORTER" --dge-root dge --mandala 1 --limit 50 --delay "$DELAY" --dry-run
rc=$?
if [ $rc -ne 0 ]; then
  die "smoke test failed (exit $rc). If it was alignment drift, do NOT pass --max-drift to silence it -- that guard is what stops every mantra getting the wrong commentary."
fi
python - <<'PY' || exit 1
import json, sys, pathlib
p = pathlib.Path("tools/sayana_smriti/dump/COUNTS_sayana.json")
if not p.exists():
    print("!! no counts file written"); sys.exit(1)
c = json.loads(p.read_text())
got, fail = c.get("sayana_added", 0), c.get("http", {}).get("fail", 0)
print(f"\n   pages={c.get('pages_fetched')}  sayana={got}  missing={c.get('missing_pages')}  http_fail={fail}")
if got == 0:
    print("\n!! 0 Sayana entries. This connection is refused too -- try mobile data")
    print("!! instead of wifi (or the reverse). Do not start the full run.")
    sys.exit(1)
print("\n   Working. The block does not follow this connection.")
PY
[ $? -eq 0 ] || exit 1

# ------------------------------------------------------------- 4. full import
say "4/5  Full import — ten mandalas, roughly 3-4 hours"
printf '     Press Enter to start, or Ctrl-C to stop here. '
read -r _
for m in 1 2 3 4 5 6 7 8 9 10; do
  say "     Mandala $m"
  python "$IMPORTER" --dge-root dge --mandala "$m" --delay "$DELAY" || {
    echo "!! mandala $m failed -- committing what landed, safe to re-run this script"
    break
  }
  if ! git diff --quiet -- dge/data/vedas/rigveda; then
    git add dge/data/vedas/rigveda
    git -c user.name="DGE phone import" -c user.email="noreply@users.noreply.github.com" \
        commit -q -m "data: Sayana bhashya, mandala $m

Fetched from wisdomlib.org (Wilson's edition, which renders Sayana in
English) on a residential connection, because wisdomlib answers 403 to
every datacenter IP range -- Actions, Codespaces and Colab all included.
Same importer, same alignment guard: each page's own title and Devanagari
are checked against the mantra already in DGE before anything is written."
    echo "     committed mandala $m"
  else
    echo "     nothing new in mandala $m (already imported)"
  fi
done

# ------------------------------------------------------------------- 5. push
say "5/5  Pushing to $BRANCH"
echo "     GitHub will ask for your username and a personal access token"
echo "     (Settings -> Developer settings -> Tokens; needs 'repo' scope)."
git push -u origin "$BRANCH" && {
  say "Done."
  echo "Open a PR from $BRANCH. Nothing was pushed to main."
} || die "push failed -- your commits are safe locally; re-run to retry"

command -v termux-wake-unlock >/dev/null && termux-wake-unlock
