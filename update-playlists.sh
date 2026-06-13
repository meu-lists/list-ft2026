#!/usr/bin/env bash
set -euo pipefail

cd /home/giondo/Documents/files/m3u-lists/list-ft2026

python3 extract_and_convert.py

git add fifa2026-list.m3u fifa2026-list-9xtream.m3u
if git diff --cached --quiet; then
    echo "$(date): No changes to commit"
else
    git commit -m "chore: update M3U playlists [skip ci]"
    git push
    echo "$(date): Updated and pushed"
fi
