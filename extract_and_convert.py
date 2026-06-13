#!/usr/bin/env python3
"""Extract streaming URLs from la18hd.com and generate M3U files."""

import re
import sys
import time
from pathlib import Path

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


def clean_playback_url(url: str) -> str:
    """Remove redundant default HTTPS port from URL."""
    return re.sub(r"^https://([^/]+):443/", r"https://\1/", url)


def make_simple_extinf(name: str) -> str:
    return f"#EXTINF:-1,{name}"


def make_9xtream_extinf(name: str, tvg_id: str, tvg_name: str, group: str) -> str:
    return (
        f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" '
        f'tvg-logo="" group-title="{group}",{name}'
    )


def extract_brand(name: str) -> str:
    name_lower = name.lower()
    brands = [
        ("tnt sports", "TNT Sports"),
        ("espn premium", "ESPN"),
        ("espn", "ESPN"),
        ("tyc sports", "TyC Sports"),
        ("directv sports", "DirecTV Sports"),
        ("fox sports", "Fox Sports"),
    ]
    for key, val in brands:
        if key.lower() in name_lower:
            return val
    return "General"


def generate_tvg_id(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", ".", name.lower()).strip(".")
    return f"{base}.ar"


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_and_convert.py <urls.txt> [output.m3u]", file=sys.stderr)
        print("  Generates a clean simple M3U (Streamers Pro compatible).", file=sys.stderr)
        print("  Add --9xtream flag for extended tvg-id/group-title format.", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = "fifa2026-list.m3u"
    use_9xtream = False

    for arg in sys.argv[2:]:
        if arg == "--9xtream":
            use_9xtream = True
        elif arg.startswith("--"):
            pass
        else:
            output_path = arg

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
    brands_seen: set[str] = set()

    for name, url in entries:
        print(f"  Fetching: {name}", file=sys.stderr)
        playback = fetch_url(url, name)
        if playback:
            playback = clean_playback_url(playback)
            if use_9xtream:
                tvg_id = generate_tvg_id(name)
                group = extract_brand(name)
                brands_seen.add(group)
                extinf = make_9xtream_extinf(name, tvg_id, name, group)
            else:
                extinf = make_simple_extinf(name)
            m3u_lines.append(f"{extinf}\n{playback}\n")
        time.sleep(1)

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)

    print(f"\nDone! {len(m3u_lines) - 1} channels written to {output_path}", file=sys.stderr)
    if brands_seen:
        print(f"   Groups: {sorted(brands_seen)}", file=sys.stderr)


if __name__ == "__main__":
    main()
