#!/usr/bin/env python3
"""Extract streaming URLs from la18hd.com and generate M3U files.

Auto-discovers channels from https://la18hd.com/status.json,
groups them by region, and only processes active channels.

Generates both simple fifa2026-list.m3u and extended fifa2026-list-9xtream.m3u
from a single parallel fetch pass.

Usage:
  python extract_and_convert.py                          # auto-discover & output both files
  python extract_and_convert.py --inactive               # include inactive channels too
  python extract_and_convert.py --output mylist.m3u      # custom output filenames
  python extract_and_convert.py urls.txt                 # legacy: read from file
"""

import argparse
import concurrent.futures
import json
import re
import sys
from pathlib import Path

import requests

STATUS_JSON_URL = "https://la18hd.com/status.json"
BASE_URL = "https://la18hd.com"


# ── helpers ──────────────────────────────────────────────────────────

def extract_playback_url(html: str) -> str | None:
    match = re.search(r'var playbackURL\s*=\s*"([^"]+)"', html)
    return match.group(1) if match else None


def fetch_playback(channel_url: str, channel_name: str) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://la18hd.com/",
    }
    try:
        resp = requests.get(channel_url, headers=headers, timeout=30)
        resp.raise_for_status()
        playback = extract_playback_url(resp.text)
        if playback:
            return playback
        print(f"  [!] playbackURL not found for {channel_name}", file=sys.stderr)
        return None
    except requests.RequestException as e:
        print(f"  [x] Error fetching {channel_url}: {e}", file=sys.stderr)
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
        ("win sports", "Win Sports"),
        ("premiere", "Premiere"),
        ("sportv", "Sportv"),
        ("sport tv", "Sport TV"),
        ("dazn", "DAZN"),
        ("movistar", "Movistar"),
        ("liga1", "Liga1 MAX"),
        ("goltv", "GOLTV"),
        ("beinsports", "beIN Sports"),
        ("tvc deportes", "TVC Deportes"),
        ("tudn", "TUDN"),
    ]
    for key, val in brands:
        if key.lower() in name_lower:
            return val
    return "General"


def generate_tvg_id(name: str, region: str = "") -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", ".", name.lower()).strip(".")
    suffix = region.lower().strip() if region else "ar"
    return f"{base}.{suffix}"


def discover_channels() -> list[dict]:
    """Fetch status.json and return a list of {name, url, region, status}."""
    print(f"  Fetching channel list from {STATUS_JSON_URL} ...", file=sys.stderr)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    resp = requests.get(STATUS_JSON_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    data: dict[str, list[dict]] = resp.json()

    channels: list[dict] = []
    for region, items in data.items():
        for item in items:
            channels.append({
                "name": item["Canal"],
                "url": item["Link"],
                "region": region,
                "active": item["Estado"] == "Activo",
            })
    return channels


def parse_urls_file(path: str) -> list[dict]:
    """Legacy: parse a urls.txt file into the same dict format."""
    channels: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                name, url = line.split("|", 1)
                channels.append({
                    "name": name.strip(),
                    "url": url.strip(),
                    "region": "Custom",
                    "active": True,
                })
            else:
                url = line
                stream = re.search(r"stream=([^&\s]+)", url)
                name = stream.group(1).replace("_", " ").title() if stream else "Unknown"
                channels.append({
                    "name": name,
                    "url": url,
                    "region": "Custom",
                    "active": True,
                })
    return channels


# ── parallel fetching ────────────────────────────────────────────────

def fetch_all_playbacks(channels: list[dict], max_workers: int = 10) -> list[dict]:
    """Fetch playback URLs for all channels in parallel, preserving original order."""
    total = len(channels)
    results: list[dict] = [None] * total

    def fetch_one(idx: int, ch: dict) -> tuple[int, dict]:
        name = ch["name"]
        url = ch["url"]
        region = ch["region"]
        print(f"  Fetching: [{region}] {name}", file=sys.stderr)
        playback = fetch_playback(url, name)
        if playback:
            playback = clean_playback_url(playback)
        return idx, {**ch, "playback": playback}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_one, i, ch) for i, ch in enumerate(channels)]
        for future in concurrent.futures.as_completed(futures):
            idx, result = future.result()
            results[idx] = result

    return results


# ── main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract streaming URLs from la18hd.com and generate M3U playlists.",
    )
    parser.add_argument("input", nargs="?", help="Legacy urls.txt file (omit to auto-discover)")
    parser.add_argument("-o", "--output", default="fifa2026-list.m3u", help="Output M3U file (simple format; extended derives name)")
    parser.add_argument("--inactive", action="store_true", help="Include inactive channels")
    parser.add_argument("--max-workers", type=int, default=10, help="Max concurrent fetches (default: 10)")
    args = parser.parse_args()

    # ── collect channels ──────────────────────────────────────────
    if args.input:
        channels = parse_urls_file(args.input)
        print(f"Loaded {len(channels)} channels from {args.input}", file=sys.stderr)
    else:
        channels = discover_channels()
        print(f"Found {len(channels)} channels on la18hd.com", file=sys.stderr)

    if not args.inactive:
        total = len(channels)
        channels = [c for c in channels if c["active"]]
        print(f"  {len(channels)}/{total} active (use --inactive to include all)", file=sys.stderr)

    if not channels:
        print("No channels to process.", file=sys.stderr)
        sys.exit(0)

    # ── fetch all playbacks in parallel ───────────────────────────
    results = fetch_all_playbacks(channels, max_workers=args.max_workers)

    # ── build both M3U outputs from the same data ─────────────────
    simple_lines = ["#EXTM3U\n"]
    ext_lines = ["#EXTM3U\n"]
    groups_seen: set[str] = set()
    success = 0

    for ch in results:
        playback = ch.get("playback")
        if not playback:
            continue
        name = ch["name"]
        region = ch["region"]
        success += 1

        # Simple format
        simple_lines.append(f"{make_simple_extinf(name)}\n{playback}\n")

        # Extended 9Xtream format
        group = extract_brand(name) if region == "Custom" else region
        groups_seen.add(group)
        tvg_id = generate_tvg_id(name, region)
        extinf = make_9xtream_extinf(name, tvg_id, name, group)
        ext_lines.append(f"{extinf}\n{playback}\n")

    # ── derive extended filename ──────────────────────────────────
    out_path = Path(args.output)
    ext_output = str(out_path.with_stem(f"{out_path.stem}-9xtream"))

    with open(args.output, "w", encoding="utf-8") as f:
        f.writelines(simple_lines)

    with open(ext_output, "w", encoding="utf-8") as f:
        f.writelines(ext_lines)

    print(f"\nDone! {success} channels written:", file=sys.stderr)
    print(f"  Simple:   {args.output}", file=sys.stderr)
    print(f"  9Xtream:  {ext_output}", file=sys.stderr)
    if groups_seen:
        print(f"  Groups: {sorted(groups_seen)}", file=sys.stderr)


if __name__ == "__main__":
    main()
