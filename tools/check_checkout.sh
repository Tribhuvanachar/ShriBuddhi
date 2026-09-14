#!/usr/bin/env bash
# check_checkout.sh — is this working copy safe to commit from?
#
# A case-insensitive filesystem (Windows NTFS, default macOS APFS) cannot
# hold this repository's SLP1-named files: `gaD.json` (ड) and `gad.json` (द)
# are one name to it. A checkout there overwrites one with the other and says
# nothing, and a commit made from it deletes the loser for everyone. This
# script is the check nobody can be expected to remember to do by hand.
#
#     bash tools/check_checkout.sh
#
# Exits 0 when the working copy is safe, 1 when it is not.
set -u

cd "$(dirname "$0")/.." || exit 1
fail=0

say()  { printf '%s\n' "$*"; }
bad()  { printf '\033[31m✗ %s\033[0m\n' "$*"; fail=1; }
good() { printf '\033[32m✓ %s\033[0m\n' "$*"; }

# 1. Is the filesystem case-sensitive? Ask it rather than guess from $OSTYPE —
#    a case-sensitive APFS volume on a Mac and a WSL2 ext4 mount both answer
#    correctly here, and both are legitimate places to hold the full tree.
probe=$(mktemp -d) || exit 1
trap 'rm -rf "$probe"' EXIT
: > "$probe/CaseProbe"
if [ -e "$probe/caseprobe" ]; then
  case_sensitive=no
  say "filesystem: case-INsensitive"
else
  case_sensitive=yes
  good "filesystem: case-sensitive"
fi

# 2. Is the risky data actually present in the working tree? Sparse checkout
#    leaves it in the index but not on disk, which is the supported setup.
present=0
for d in data/kosha search_index; do
  [ -d "$d" ] && present=1 && say "present on disk: $d"
done

if [ "$case_sensitive" = no ] && [ "$present" = 1 ]; then
  bad "data/kosha and/or search_index are checked out on a case-insensitive
  filesystem. Files have very likely already overwritten each other. Do NOT
  commit from this working copy — see docs/DEVELOPER_SETUP.md."
elif [ "$case_sensitive" = no ]; then
  good "the colliding trees are excluded (sparse checkout) — safe to work here"
else
  good "full tree is safe on this filesystem"
fi

# 3. Whatever is on disk, prove it round-trips: git's own view of what differs
#    from HEAD is the authoritative answer to "did the checkout lose files".
deleted=$(git ls-files -d 2>/dev/null | wc -l | tr -d ' ')
if [ "$deleted" != "0" ]; then
  bad "$deleted tracked file(s) missing from the working tree that git expects
  to be there. On a case-insensitive filesystem this is the collision damage.
  'git ls-files -d | head' will show which."
else
  good "no tracked file is missing from the working tree"
fi

# 4. Sparse config, reported rather than enforced — someone may have a good
#    reason to hold the full tree on a case-sensitive volume.
if git config --get core.sparseCheckout >/dev/null 2>&1; then
  say "sparse-checkout: on ($(git ls-files -t | grep -c '^H') of $(git ls-files | wc -l | tr -d ' ') files materialised)"
else
  say "sparse-checkout: off"
fi

# 5. protectNTFS must stay on. Turning it off is the one "fix" that converts
#    the loud failure into a silent one.
if [ "$(git config --get core.protectNTFS || echo true)" = "false" ]; then
  bad "core.protectNTFS is disabled. Re-enable it: git config --unset core.protectNTFS"
fi

echo
[ "$fail" = 0 ] && good "OK to commit from this working copy." \
                || printf '\033[31m%s\033[0m\n' "NOT safe to commit — see docs/DEVELOPER_SETUP.md"
exit $fail
