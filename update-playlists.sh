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

    branch=$(git rev-parse --abbrev-ref HEAD)
    for i in $(seq 1 100); do
        sleep 5
        git fetch origin "$branch" 2>/dev/null
        if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/$branch 2>/dev/null)" ]; then
            echo "$(date): Updated and pushed (confirmed after $i attempts)"
            exit 0
        fi
    done

    echo "$(date): ERROR: push not confirmed after 100 attempts" >&2
    exit 1
fi
