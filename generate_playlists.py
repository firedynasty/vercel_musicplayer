#!/usr/bin/env python3
"""Generate playlists.json from .txt files in playlists/ subdirectories.

Each subdirectory becomes a category (e.g. classical, adhd).
Each .txt file contains one or more entries delimited by URLs.

Supported formats:
  - URL on its own line, followed by timestamped tracks below
  - name,URL on a single line
  - Multiple URLs in one file (each starts a new entry)

Usage:
  python generate_playlists.py
  python generate_playlists.py -i playlists -o playlists.json
"""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse, unquote


def time_to_seconds(time_str):
    """Convert time string like '1:03:35', '05:50', '0:00' to seconds."""
    parts = time_str.split(':')
    parts = [int(p) for p in parts]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def name_from_url(url):
    """Extract a human-readable name from a Dropbox URL path."""
    try:
        path = urlparse(url).path
        filename = unquote(path.split('/')[-1])
        # Strip extension
        filename = re.sub(r'\.\w{2,4}$', '', filename)
        # Strip video ID in brackets like [VmImA0YKsJg]
        filename = re.sub(r'\s*\[[\w-]+\]$', '', filename)
        # Replace hyphens and underscores with spaces
        filename = filename.replace('-', ' ').replace('_', ' ')
        # Strip trailing YouTube video ID (11 alphanumeric chars at end)
        filename = re.sub(r'\s+[A-Za-z0-9_-]{11}$', '', filename)
        # Collapse whitespace
        filename = re.sub(r'\s+', ' ', filename).strip()
        return filename
    except Exception:
        return 'Untitled'


def is_timestamp_line(line):
    """Check if line starts with a timestamp like 00:00, 1:03:35, etc."""
    return bool(re.match(r'^\d{1,2}:\d{2}(:\d{2})?\s', line))


def is_all_caps_header(line):
    """Check if line is an ALL CAPS section header like ANTONIO VIVALDI."""
    stripped = line.strip()
    if not stripped or len(stripped) < 3:
        return False
    # Must be mostly uppercase letters/spaces, no digits at start (not a timestamp)
    alpha = re.sub(r'[^a-zA-Z]', '', stripped)
    return len(alpha) >= 3 and alpha == alpha.upper() and not re.match(r'^\d', stripped)


def is_url_line(line):
    """Check if line contains an http URL."""
    return bool(re.search(r'https?://', line))


def parse_timestamp_line(line):
    """Parse a timestamp line into time string and title."""
    m = re.match(r'^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.*)$', line)
    if not m:
        return None, None
    time_str = m.group(1)
    title = m.group(2).strip()
    # Strip leading track number like "1 ", "25 "
    title = re.sub(r'^\d+\s+', '', title)
    return time_str, title


def parse_url_line(line):
    """Parse a line that contains a URL, returning (name, url)."""
    line = line.strip()
    # Check for name,url format
    m = re.match(r'^(.+?)\s*,\s*(https?://.+)$', line)
    if m:
        name = m.group(1).strip()
        url = m.group(2).strip()
        return name, url
    # Just a URL
    m = re.match(r'^(https?://.+)$', line)
    if m:
        url = m.group(1).strip()
        return '', url
    return '', ''


def parse_file(filepath):
    """Parse a .txt file into a list of entries."""
    entries = []
    current_entry = None

    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='latin-1') as f:
            lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if is_url_line(line):
            # Start a new entry
            name, url = parse_url_line(line)
            if not url:
                continue
            if not name:
                name = name_from_url(url)
            current_entry = {'name': name, 'url': url, 'tracks': []}
            entries.append(current_entry)

        elif is_timestamp_line(line) and current_entry is not None:
            time_str, title = parse_timestamp_line(line)
            if time_str and title:
                current_entry['tracks'].append({
                    'time': time_str,
                    'seconds': time_to_seconds(time_str),
                    'title': title
                })

        elif is_all_caps_header(line) and current_entry is not None:
            # Section header like ANTONIO VIVALDI
            current_entry['tracks'].append({'header': line})

        elif current_entry is not None and current_entry['tracks']:
            # Non-timestamp, non-URL, non-header line → artist for previous track
            last_track = None
            for t in reversed(current_entry['tracks']):
                if 'time' in t:
                    last_track = t
                    break
            if last_track:
                if 'artist' in last_track:
                    last_track['artist'] += ', ' + line
                else:
                    last_track['artist'] = line

    # For files with multiple URL-only entries and no tracks,
    # use the filename stem as a group name
    return entries


def main():
    parser = argparse.ArgumentParser(description='Generate playlists.json from playlists/ directory')
    parser.add_argument('-i', '--input', default='playlists',
                        help='Input folder containing category subdirectories (default: playlists)')
    parser.add_argument('-o', '--output', default='playlists.json',
                        help='Output JSON file (default: playlists.json)')
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        print(f'No {input_dir}/ directory found.')
        return 1

    playlists = {}

    for category_dir in sorted(input_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        all_entries = []

        for txt_file in sorted(category_dir.glob('*.txt')):
            entries = parse_file(txt_file)
            all_entries.extend(entries)
            track_count = sum(len(e['tracks']) for e in entries)
            print(f'  {category}/{txt_file.name}: {len(entries)} entry(ies), {track_count} tracks')

        if all_entries:
            playlists[category] = all_entries

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(playlists, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in playlists.values())
    print(f'\n-> Wrote {len(playlists)} categories, {total} entries to {output_path}')

    base = Path(__file__).resolve().parent
    print(f'\nrclone copyto {base / output_path}  dropbox:/vercel/music.json')
    print(f'rclone link dropbox:/vercel/music.json')
    print(f'\n# Then update Vercel with the link (append &raw=1):')
    print(f'vercel env rm MUSIC_PLAYLISTS_URL production -y')
    print(f'echo "<LINK>&raw=1" | vercel env add MUSIC_PLAYLISTS_URL production')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
