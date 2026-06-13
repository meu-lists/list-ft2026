#!/usr/bin/env python3
"""Extract streaming URLs from la18hd.com pages and generate an M3U playlist."""

import re
import sys
import time

import requests


def extract_playback_url(html: str) -> str | None:
    match = re.search(r'var playbackURL\s*=\s*"([^"]+)"', html)
    return match.group(1) if match else None


def channel_name_from_stream(stream: str) -> str:
    names = {
        "tntsports": "TNT Sports Argentina",
        "espnpremium": "ESPN Premium Argentina",
        "tycsports": "TyC Sports Argentina",
        "dsports": "DirecTV Sports Argentina",
        "dsports2": "DirecTV Sports 2 Argentina",
        "dsportsplus": "DirecTV Sports + Argentina",
        "espn": "ESPN 1 Argentina",
        "espn2": "ESPN 2 Argentina",
        "espn3": "ESPN 3 Argentina",
        "foxsports2": "Fox Sports 2 Argentina",
        "foxsports3": "Fox Sports 3 Argentina",
    }
    return names.get(stream, stream.replace("_", " ").title())


def fetch_url(url: str, stream: str) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://la18hd.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        playback = extract_playback_url(resp.text)
        if playback:
            return playback
        print(f"  [!] playbackURL not found for {stream}", file=sys.stderr)
        return None
    except requests.RequestException as e:
        print(f"  [x] Error fetching {url}: {e}", file=sys.stderr)
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_m3u.py <urls.txt> [output.m3u]", file=sys.stderr)
        print("       urls.txt: one URL per line, or format: channel_name|url", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "playlist.m3u"

    with open(input_path) as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    entries = []
    for line in lines:
        if "|" in line:
            name, url = line.split("|", 1)
            entries.append((name.strip(), url.strip()))
        else:
            url = line
            stream = re.search(r"stream=([^&\s]+)", url)
            name = channel_name_from_stream(stream.group(1)) if stream else "Unknown Channel"
            entries.append((name, url))

    print(f"Processing {len(entries)} URLs...", file=sys.stderr)

    m3u_lines = ["#EXTM3U\n"]
    for name, url in entries:
        print(f"  Fetching: {name}", file=sys.stderr)
        playback = fetch_url(url, name)
        if playback:
            m3u_lines.append(f"#EXTINF:-1,{name}\n{playback}\n")
        time.sleep(1)

    with open(output_path, "w") as f:
        f.writelines(m3u_lines)

    print(f"\nDone! {len(m3u_lines) - 1} channels written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
