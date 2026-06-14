#!/usr/bin/env python3
"""
Export playlist entries to CSV.

Examples:
    python3 scripts/export-playlist-to-csv.py \
      --playlists-root /mnt/nas/playlists \
      --playlist exyu

    python3 scripts/export-playlist-to-csv.py \
      --playlists-root /mnt/nas/playlists \
      --playlist exyu \
      --output /mnt/nas/playlists/exyu.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import unquote, urlparse


SUPPORTED_SUFFIXES = (".m3u", ".m3u8")
UNC_PATH_RE = re.compile(r"^[\\/]{2}([^\\/]+)[\\/]+([^\\/]+)(?:[\\/]+(.*))?$")
TRACK_PREFIX_RE = re.compile(r"^\d+\s+")
ALBUM_YEAR_RE = re.compile(r"^(?P<album>.+?) \((?P<year>\d{4})\)$")
DISC_FOLDER_RE = re.compile(r"^(?:CD|DISC)\d+$", re.IGNORECASE)


class PlaylistCsvError(Exception):
    """User-facing error."""


@dataclass(frozen=True)
class PlaylistRow:
    artist: str
    song: str
    album: str
    year: str
    filename: str
    path: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playlists-root", required=True, help="Folder containing playlist files")
    parser.add_argument(
        "--playlist",
        action="append",
        help="Playlist file or stem name. May be passed multiple times. If omitted, all .m3u/.m3u8 files are processed.",
    )
    parser.add_argument("--output", help="Exact output CSV path. Only valid when processing one playlist.")
    parser.add_argument(
        "--output-dir",
        help="Directory for generated CSV files. Defaults to --playlists-root when --output is not used.",
    )
    return parser.parse_args(argv)


def resolve_playlist_file(playlists_root: Path, requested: str) -> Path:
    requested_path = Path(requested).expanduser()
    if requested_path.exists():
        return requested_path

    candidates = [playlists_root / requested]
    if not requested_path.suffix:
        for suffix in SUPPORTED_SUFFIXES:
            candidates.append(playlists_root / f"{requested}{suffix}")

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    raise PlaylistCsvError(f"Playlist not found for '{requested}' in {playlists_root}")


def resolve_playlists(playlists_root: Path, requested: list[str] | None) -> list[Path]:
    if requested:
        return [resolve_playlist_file(playlists_root, item) for item in requested]

    if not playlists_root.exists():
        raise PlaylistCsvError(f"Playlist root does not exist: {playlists_root}")

    playlists = sorted(
        path for path in playlists_root.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not playlists:
        raise PlaylistCsvError(f"No playlist files found in {playlists_root}")
    return playlists


def normalize_windows_path(raw_value: str) -> Path | None:
    match = UNC_PATH_RE.match(raw_value)
    if not match:
        return None

    _server, _share, remainder = match.groups()
    mapped = Path("/")
    if remainder:
        for part in re.split(r"[\\/]+", remainder):
            if part:
                mapped /= part
    return mapped


def canonical_library_path(path: Path) -> Path:
    parts = list(path.parts)
    try:
        music_index = next(index for index, part in enumerate(parts) if part == "music")
    except StopIteration:
        return path
    return Path("/") / Path(*parts[music_index:])


def decode_playlist_path(raw_value: str, playlist_path: Path) -> Path:
    if raw_value.startswith("file://"):
        parsed = urlparse(raw_value)
        if parsed.scheme != "file":
            raise PlaylistCsvError(f"Unsupported URI in {playlist_path}: {raw_value}")
        if parsed.netloc not in ("", "localhost"):
            raise PlaylistCsvError(f"Unsupported file URI host in {playlist_path}: {raw_value}")
        resolved = Path(unquote(parsed.path))
    else:
        windows_path = normalize_windows_path(raw_value)
        resolved = windows_path if windows_path is not None else Path(raw_value).expanduser()

    if not resolved.is_absolute():
        resolved = (playlist_path.parent / resolved).resolve()

    return canonical_library_path(resolved)


def parse_artist_song(filename: str) -> tuple[str, str]:
    stem = TRACK_PREFIX_RE.sub("", Path(filename).stem, count=1)
    if " - " not in stem:
        return "", stem
    artist, song = stem.split(" - ", 1)
    return artist, song


def album_dir_for_source(source: Path) -> Path:
    parent = source.parent
    if DISC_FOLDER_RE.match(parent.name):
        return parent.parent
    return parent


def parse_album_year(source: Path) -> tuple[str, str]:
    album_dir = album_dir_for_source(source)
    match = ALBUM_YEAR_RE.match(album_dir.name)
    if match:
        return match.group("album"), match.group("year")
    return album_dir.name, ""


def playlist_rows(playlist_path: Path) -> list[PlaylistRow]:
    try:
        lines = playlist_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise PlaylistCsvError(f"Could not read playlist {playlist_path}: {exc}") from exc

    rows: list[PlaylistRow] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        source = decode_playlist_path(line, playlist_path)
        artist, song = parse_artist_song(source.name)
        album, year = parse_album_year(source)
        rows.append(
            PlaylistRow(
                artist=artist,
                song=song,
                album=album,
                year=year,
                filename=source.name,
                path=str(source.parent),
            )
        )

    return sorted(
        rows,
        key=lambda row: (
            row.artist.casefold(),
            row.song.casefold(),
            row.filename.casefold(),
            row.path.casefold(),
        ),
    )


def output_path_for_playlist(
    playlist_path: Path,
    *,
    output: Path | None,
    output_dir: Path | None,
    multiple: bool,
) -> Path:
    if output is not None:
        if multiple:
            raise PlaylistCsvError("--output can only be used with a single playlist")
        return output

    base_dir = output_dir if output_dir is not None else playlist_path.parent
    return base_dir / f"{playlist_path.stem}.csv"


def write_csv(rows: list[PlaylistRow], output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["artist", "song", "album", "year", "filename", "path"])
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "artist": row.artist,
                        "song": row.song,
                        "album": row.album,
                        "year": row.year,
                        "filename": row.filename,
                        "path": row.path,
                    }
                )
    except OSError as exc:
        raise PlaylistCsvError(f"Could not write CSV to {output_path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    playlists_root = Path(args.playlists_root).expanduser()
    output = Path(args.output).expanduser() if args.output else None
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None

    try:
        playlists = resolve_playlists(playlists_root, args.playlist)
        multiple = len(playlists) > 1
        for playlist_path in playlists:
            rows = playlist_rows(playlist_path)
            csv_path = output_path_for_playlist(
                playlist_path,
                output=output,
                output_dir=output_dir,
                multiple=multiple,
            )
            write_csv(rows, csv_path)
            print(f"Wrote {len(rows)} rows to {csv_path}")
    except PlaylistCsvError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
