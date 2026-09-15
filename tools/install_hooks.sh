#!/bin/sh
# Install this repository's git hooks into the clone you are standing in.
#
# Run once per desktop clone:   sh tools/install_hooks.sh
#
# Hooks live in .git/hooks, which git does not track, so every clone has to do
# this for itself -- including a fresh clone on a machine that has done it
# before. Re-running is safe.
set -e
repo=$(git rev-parse --show-toplevel)
dir="$repo/.git/hooks"
mkdir -p "$dir"
for hook in "$repo"/tools/hooks/*; do
  name=$(basename "$hook")
  if [ -e "$dir/$name" ] && ! cmp -s "$hook" "$dir/$name"; then
    cp "$dir/$name" "$dir/$name.replaced-$(date +%Y%m%d%H%M%S)"
    echo "kept your existing $name as $name.replaced-*"
  fi
  cp "$hook" "$dir/$name"
  chmod +x "$dir/$name"
  echo "installed $name"
done
echo
echo "Done. Committing a data.json now escapes raw line breaks automatically."
