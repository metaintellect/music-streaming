#!/usr/bin/env python3
"""
Search a playlist CSV by artist and song title.

Examples:
    python3 scripts/search-playlist-csv.py \
      --playlist exyu \
      --query vuco

    python3 scripts/search-playlist-csv.py \
      --playlist easy \
      --query "mariah emotions" \
      --csv-dir ~/Documents/playlists
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path


class PlaylistSearchError(Exception):
    """User-facing error."""


@dataclass(frozen=True)
class PlaylistMatch:
    artist: str
    song: str
    filename: str
    path: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playlist", required=True, help="Playlist stem name, for example exyu or easy")
    parser.add_argument("--query", required=True, help="Case-insensitive search text matched against artist and song")
    parser.add_argument(
        "--csv-dir",
        default="~/Documents/playlists",
        help="Directory containing playlist CSV files. Default: %(default)s",
    )
    parser.add_argument("--csv", help="Exact CSV file path. Overrides --playlist and --csv-dir.")
    return parser.parse_args(argv)


def resolve_csv_path(playlist: str, csv_dir: Path, csv_path: Path | None) -> Path:
    if csv_path is not None:
        return csv_path
    return csv_dir / f"{playlist}.csv"


def load_rows(csv_path: Path) -> list[PlaylistMatch]:
    if not csv_path.exists():
        raise PlaylistSearchError(f"CSV file does not exist: {csv_path}")

    try:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [
                PlaylistMatch(
                    artist=row.get("artist", ""),
                    song=row.get("song", ""),
                    filename=row.get("filename", ""),
                    path=row.get("path", ""),
                )
                for row in reader
            ]
    except OSError as exc:
        raise PlaylistSearchError(f"Could not read {csv_path}: {exc}") from exc


def normalize_terms(query: str) -> list[str]:
    return [term.casefold() for term in query.split() if term.strip()]


def search_rows(rows: list[PlaylistMatch], query: str) -> list[PlaylistMatch]:
    terms = normalize_terms(query)
    if not terms:
        return []

    matches: list[PlaylistMatch] = []
    for row in rows:
        haystack = f"{row.artist} {row.song}".casefold()
        if all(term in haystack for term in terms):
            matches.append(row)
    return matches


def format_matches(matches: list[PlaylistMatch]) -> list[str]:
    if not matches:
        return []

    artist_width = max(len(row.artist) for row in matches)
    song_width = max(len(row.song) for row in matches)
    return [
        f"{row.artist:<{artist_width}} | {row.song:<{song_width}} | {row.filename} | {row.path}"
        for row in matches
    ]


def print_matches(matches: list[PlaylistMatch]) -> None:
    for line in format_matches(matches):
        print(line)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    csv_dir = Path(args.csv_dir).expanduser()
    csv_path = Path(args.csv).expanduser() if args.csv else None

    try:
        resolved_csv = resolve_csv_path(args.playlist, csv_dir, csv_path)
        matches = search_rows(load_rows(resolved_csv), args.query)
        if not matches:
            print(f"No matches in {resolved_csv} for: {args.query}")
            return 1
        print_matches(matches)
    except PlaylistSearchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
