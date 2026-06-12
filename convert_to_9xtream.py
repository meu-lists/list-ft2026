#!/usr/bin/env python3
"""Convert a basic M3U file to 9Xtream-compatible format."""

import re
import sys
from pathlib import Path


def parse_m3u(filepath: str) -> list[dict]:
    channels = []
    with open(filepath) as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            # Extract display name after the last comma
            name = line.rsplit(",", 1)[-1].strip()
            # Next line should be the URL
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            channels.append({"name": name, "url": url, "raw_extinf": line})
            i += 2
        else:
            i += 1
    return channels


def extract_brand(name: str) -> str:
    name_lower = name.lower()
    brands = [
        ("tnt sports", "TNT Sports"),
        ("espn premium", "ESPN"),
        ("espn", "ESPN"),
        ("tyc sports", "TyC Sports"),
        ("direcTV sports", "DirecTV Sports"),
        ("fox sports", "Fox Sports"),
    ]
    for key, val in brands:
        if key.lower() in name_lower:
            return val
    return "General"


def clean_name(name: str) -> str:
    # Remove "en vivo por internet" and trailing whitespace
    cleaned = re.sub(r"\s*en vivo por internet\s*", "", name, flags=re.IGNORECASE).strip()
    return cleaned


def generate_tvg_id(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", ".", clean_name(name)).lower().strip(".")
    return f"{base}.ar"


def to_9xtream_extinf(name: str, tvg_id: str, tvg_name: str, group: str) -> str:
    return (
        f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" '
        f'tvg-logo="" group-title="{group}",{name}'
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_to_9xtream.py <input.m3u> [output.m3u]", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_stem(f"{input_path.stem}_9xtream")

    channels = parse_m3u(str(input_path))

    lines = ["#EXTM3U\n"]
    for ch in channels:
        brand = extract_brand(ch["name"])
        tvg_name = clean_name(ch["name"])
        tvg_id = generate_tvg_id(ch["name"])
        extinf = to_9xtream_extinf(ch["name"], tvg_id, tvg_name, brand)
        lines.append(f"{extinf}\n{ch['url']}\n")

    output_path.write_text("".join(lines))
    print(f"✅ Converted {len(channels)} channels to 9Xtream format → {output_path}")
    print(f"   Groups: {sorted(set(extract_brand(c['name']) for c in channels))}")


if __name__ == "__main__":
    main()
