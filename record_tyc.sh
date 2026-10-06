#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="${1:-tyc_sports_$(date +%Y%m%d_%H%M%S).ts}"
STREAM_URL="https://YXdlc29tZQ.fubo18.com/tycsports/mono.m3u8?token=44da5ce5b54e1dca58363e387cde458d7f9d27df-a6-1791332430-1791314430"
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REFERER="https://pelotalibre.la/"

echo "Recording TyC Sports stream to '$OUTPUT_FILE'..."
echo "Press Ctrl+C to stop recording."

cvlc "$STREAM_URL" \
  --http-user-agent="$USER_AGENT" \
  --http-referrer="$REFERER" \
  --sout="#std{access=file,mux=ts,dst=\"$OUTPUT_FILE\"}" \
  vlc://quit
