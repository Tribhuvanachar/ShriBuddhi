#!/usr/bin/env bash
# Push a processed job's output into the separate audio-data repo.
# Run from the Codespace terminal, where your GH token already exists.
#
#   ./scripts/push_to_repo.sh out/ chanting/sarga-9
#
# Reads repo/branch from config.yaml (push.repo, push.branch). Keeps the token
# out of the browser/panel on purpose.
set -euo pipefail

SRC="${1:?usage: push_to_repo.sh <out-dir> <subfolder-in-target-repo>}"
SUB="${2:?usage: push_to_repo.sh <out-dir> <subfolder-in-target-repo>}"

REPO=$(python3 -c "import yaml;print(yaml.safe_load(open('config.yaml'))['push']['repo'])")
BRANCH=$(python3 -c "import yaml;print(yaml.safe_load(open('config.yaml'))['push'].get('branch','main'))")

TMP=$(mktemp -d)
echo "Cloning $REPO ($BRANCH)…"
git clone --depth 1 -b "$BRANCH" "https://github.com/${REPO}.git" "$TMP"
mkdir -p "$TMP/$SUB"
cp -v "$SRC"/* "$TMP/$SUB/"
cd "$TMP"
git add -A
git -c user.name="dge-audio-admin" -c user.email="actions@users.noreply.github.com" \
    commit -m "Add shlokas: $SUB"
git push origin "$BRANCH"
echo "Pushed to $REPO/$SUB"
