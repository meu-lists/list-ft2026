#!/usr/bin/env python3
"""Extract streaming URLs from librepelota.su and generate M3U files.

Scrapes channel cards from https://librepelota.su/es/, follows each
channel page to discover the stream ID, then fetches the iframe
backend (latamvidz1.com) to extract the raw m3u8 playback URL.

Generates both simple fifa2026-list.m3u and extended fifa2026-list-9xtream.m3u
from a single parallel fetch pass.

Usage:
  python extract_and_convert.py                          # auto-discover & output both files
  python extract_and_convert.py --output mylist.m3u      # custom output filenames
  python extract_and_convert.py urls.txt                 # legacy: read from file
"""

import argparse
import concurrent.futures
import re
import sys
from pathlib import Path

import requests

HOME_URL = "https://librepelota.su/es/"
IFRAME_BASE = "https://latamvidz1.com/canal.php"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
REFERER_URL = "https://librepelota.su/es/"


# ── helpers ──────────────────────────────────────────────────────────

def extract_playback_url(html: str) -> str | None:
    match = re.search(r'var playbackURL\s*=\s*"([^"]+)"', html)
    return match.group(1) if match else None


def extract_stream_id(html: str) -> str | None:
    match = re.search(
        r'<iframe[^>]*src="https://latamvidz1\.com/canal\.php\?stream=([^"]+)"',
        html,
    )
    return match.group(1) if match else None


def fetch_playback(channel_url: str, channel_name: str) -> str | None:
    """Fetch a channel page → extract stream ID → fetch iframe → extract playbackURL."""
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": REFERER_URL,
    }
    try:
        # Step 1: get channel page to find stream ID
        resp = requests.get(channel_url, headers=headers, timeout=30)
        resp.raise_for_status()
        stream_id = extract_stream_id(resp.text)
        if not stream_id:
            print(f"  [!] stream ID not found on page for {channel_name}", file=sys.stderr)
            return None

        # Step 2: fetch iframe backend to get m3u8 URL
        iframe_url = f"{IFRAME_BASE}?stream={stream_id}"
        print(f"  Fetching: {channel_name} ({stream_id})", file=sys.stderr)
        iframe_resp = requests.get(iframe_url, headers=headers, timeout=30)
        iframe_resp.raise_for_status()
        playback = extract_playback_url(iframe_resp.text)
        if playback:
            return playback
        print(f"  [!] playbackURL not found for {channel_name}", file=sys.stderr)
        return None
    except requests.RequestException as e:
        print(f"  [x] Error fetching {channel_url}: {e}", file=sys.stderr)
        return None


def clean_playback_url(url: str) -> str:
    return re.sub(r"^https://([^/]+):443/", r"https://\1/", url)


def validate_playback(playback: str) -> bool:
    try:
        resp = requests.get(
            playback,
            headers={"User-Agent": USER_AGENT, "Referer": REFERER_URL},
            timeout=5,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def validate_all_playbacks(
    results: list[dict], max_workers: int = 10
) -> list[dict]:
    total = len(results)
    ok_flags: list[bool] = [False] * total

    def check_one(idx: int, ch: dict) -> tuple[int, bool]:
        playback = ch.get("playback")
        if not playback:
            return idx, False
        return idx, validate_playback(playback)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_one, i, ch) for i, ch in enumerate(results)]
        for future in concurrent.futures.as_completed(futures):
            idx, ok = future.result()
            ok_flags[idx] = ok

    return [results[i] for i in range(total) if ok_flags[i]]


def make_simple_extinf(name: str) -> str:
    return f"#EXTINF:-1,{name}"


def make_9xtream_extinf(name: str, tvg_id: str, tvg_name: str, group: str) -> str:
    return (
        f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" '
        f'tvg-logo="" group-title="{group}",{name}'
    )


def make_vlcopts() -> str:
    return (
        f"#EXTVLCOPT:http-user-agent={USER_AGENT}\n"
        f"#EXTVLCOPT:http-referrer={REFERER_URL}\n"
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
        ("tudn", "TUDN"),
    ]
    for key, val in brands:
        if key.lower() in name_lower:
            return val
    return "General"


def generate_tvg_id(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", ".", name.lower()).strip(".")
    return f"{base}.ar"


def discover_channels() -> list[dict]:
    """Scrape librepelota.su/es/ homepage to discover channels from .card elements."""
    print(f"  Fetching channel list from {HOME_URL} ...", file=sys.stderr)
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(HOME_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    html = resp.text

    channels: list[dict] = []
    card_pattern = re.compile(
        r'<div class="card">.*?'
        r'<h3>(.*?)</h3>.*?'
        r'<a href="(/es/[^"]+/)" class="btn-watch">',
        re.DOTALL,
    )
    for match in card_pattern.finditer(html):
        name = match.group(1).strip()
        page_path = match.group(2)
        channel_url = f"https://librepelota.su{page_path}"
        channels.append({
            "name": name,
            "url": channel_url,
            "region": "Latam",
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
                })
            else:
                url = line
                stream = re.search(r"stream=([^&\s]+)", url)
                name = stream.group(1).replace("_", " ").title() if stream else "Unknown"
                channels.append({
                    "name": name,
                    "url": url,
                    "region": "Custom",
                })
    return channels


# ── parallel fetching ────────────────────────────────────────────────

def fetch_all_playbacks(channels: list[dict], max_workers: int = 10) -> list[dict]:
    total = len(channels)
    results: list[dict] = [None] * total

    def fetch_one(idx: int, ch: dict) -> tuple[int, dict]:
        name = ch["name"]
        url = ch["url"]
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
        description="Extract streaming URLs from librepelota.su and generate M3U playlists.",
    )
    parser.add_argument("input", nargs="?", help="Legacy urls.txt file (omit to auto-discover)")
    parser.add_argument("-o", "--output", default="fifa2026-list.m3u", help="Output M3U file (simple format; extended derives name)")
    parser.add_argument("--max-workers", type=int, default=10, help="Max concurrent fetches (default: 10)")
    args = parser.parse_args()

    # ── collect channels ──────────────────────────────────────────
    if args.input:
        channels = parse_urls_file(args.input)
        print(f"Loaded {len(channels)} channels from {args.input}", file=sys.stderr)
    else:
        channels = discover_channels()
        print(f"Found {len(channels)} channels on librepelota.su", file=sys.stderr)

    if not channels:
        print("No channels to process.", file=sys.stderr)
        sys.exit(0)

    # ── fetch all playbacks in parallel ───────────────────────────
    results = fetch_all_playbacks(channels, max_workers=args.max_workers)

    # ── validate playbacks (soft – tokens expire, so just warn) ──
    total_before = sum(1 for ch in results if ch.get("playback"))
    if total_before:
        working = validate_all_playbacks(results, max_workers=args.max_workers)
        failed = total_before - len(working)
        if failed:
            print(f"  [!] {failed}/{total_before} tokens already expired (normal)", file=sys.stderr)

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
        simple_lines.append(f"{make_simple_extinf(name)}\n{make_vlcopts()}{playback}\n")

        # Extended 9Xtream format
        group = extract_brand(name)
        groups_seen.add(group)
        tvg_id = generate_tvg_id(name)
        extinf = make_9xtream_extinf(name, tvg_id, name, group)
        ext_lines.append(f"{extinf}\n{make_vlcopts()}{playback}\n")

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
