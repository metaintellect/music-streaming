#!/usr/bin/env python3
"""
Normalize Plex music album genres based on the top-level folder bucket.

Examples:
    # Preview changes only
    PLEX_TOKEN=... python3 scripts/plex-normalize-genres.py \
      --plex-url http://192.168.100.67:32400 \
      --library-name Music

    # Apply changes and lock the genre field
    PLEX_TOKEN=... python3 scripts/plex-normalize-genres.py \
      --plex-url http://192.168.100.67:32400 \
      --library-name Music \
      --apply
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass


DEFAULT_BUCKET_MAP = {
    "esoteric": "Esoteric",
    "esoteric-flac": "Esoteric",
    "exyu": "ExYU",
    "metal": "Metal",
    "jazz": "Jazz",
    "classical": "Classical",
    "misc": "Pop Rock",
}

DEFAULT_CONTAINER_SIZE = 200


class PlexGenreError(Exception):
    """User-facing error."""


@dataclass(frozen=True)
class LibrarySection:
    key: str
    title: str
    section_type: str
    locations: tuple[str, ...]


@dataclass(frozen=True)
class AlbumSummary:
    rating_key: str
    title: str
    parent_title: str
    genres: tuple[str, ...]


@dataclass(frozen=True)
class PlannedChange:
    album: AlbumSummary
    file_path: str
    bucket: str
    target_genre: str


def build_plex_url(base_url: str, endpoint: str, query: dict[str, str | int]) -> str:
    base = base_url.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{base}{path}?{urllib.parse.urlencode(query)}"


def plex_get_xml(base_url: str, endpoint: str, token: str, timeout: int, query: dict[str, str | int] | None = None) -> ET.Element:
    params = {"X-Plex-Token": token}
    if query:
        params.update(query)
    request = urllib.request.Request(
        build_plex_url(base_url, endpoint, params),
        headers={"Accept": "application/xml"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return ET.fromstring(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise PlexGenreError(f"Plex GET failed for {endpoint} with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise PlexGenreError(f"Plex server is unreachable at {base_url}: {exc}") from exc
    except ET.ParseError as exc:
        raise PlexGenreError(f"Plex returned invalid XML for {endpoint}: {exc}") from exc


def plex_put(base_url: str, endpoint: str, token: str, timeout: int, query: dict[str, str | int]) -> None:
    params = {"X-Plex-Token": token}
    params.update(query)
    request = urllib.request.Request(
        build_plex_url(base_url, endpoint, params),
        method="PUT",
        headers={"Accept": "application/xml"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise PlexGenreError(f"Plex PUT failed for {endpoint} with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise PlexGenreError(f"Plex server is unreachable at {base_url}: {exc}") from exc


def find_music_section(base_url: str, token: str, library_name: str, timeout: int) -> LibrarySection:
    root = plex_get_xml(base_url, "/library/sections", token, timeout)
    for directory in root.findall("Directory"):
        title = directory.attrib.get("title", "")
        if title.lower() != library_name.lower():
            continue

        locations = tuple(location.attrib.get("path", "") for location in directory.findall("Location") if location.attrib.get("path"))
        return LibrarySection(
            key=directory.attrib.get("key", ""),
            title=title,
            section_type=directory.attrib.get("type", ""),
            locations=locations,
        )

    available = ", ".join(item.attrib.get("title", "<unnamed>") for item in root.findall("Directory"))
    raise PlexGenreError(f"No Plex library named '{library_name}' found. Available libraries: {available or 'none'}")


def iter_albums(base_url: str, token: str, section_key: str, timeout: int, container_size: int) -> list[AlbumSummary]:
    albums: list[AlbumSummary] = []
    start = 0

    while True:
        root = plex_get_xml(
            base_url,
            f"/library/sections/{section_key}/all",
            token,
            timeout,
            query={
                "type": 9,
                "X-Plex-Container-Start": start,
                "X-Plex-Container-Size": container_size,
            },
        )
        directories = root.findall("Directory")
        if not directories:
            break

        for directory in directories:
            albums.append(
                AlbumSummary(
                    rating_key=directory.attrib.get("ratingKey", ""),
                    title=directory.attrib.get("title", ""),
                    parent_title=directory.attrib.get("parentTitle", ""),
                    genres=tuple(
                        genre.attrib.get("tag", "")
                        for genre in directory.findall("Genre")
                        if genre.attrib.get("tag")
                    ),
                )
            )

        if len(directories) < container_size:
            break
        start += container_size

    return albums


def get_album_file_path(base_url: str, token: str, rating_key: str, timeout: int) -> str | None:
    root = plex_get_xml(base_url, f"/library/metadata/{rating_key}/children", token, timeout)
    for track in root.findall("Track"):
        media = track.find("Media")
        if media is None:
            continue
        part = media.find("Part")
        if part is None:
            continue
        file_path = part.attrib.get("file")
        if file_path:
            return file_path
    return None


def normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip().rstrip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized.lower()


def derive_bucket(file_path: str, library_locations: tuple[str, ...]) -> str | None:
    normalized_file = normalize_path(file_path)
    matched_root = None

    for location in library_locations:
        normalized_location = normalize_path(location)
        if normalized_file == normalized_location or normalized_file.startswith(normalized_location + "/"):
            if matched_root is None or len(normalized_location) > len(matched_root):
                matched_root = normalized_location

    if matched_root is None:
        return None

    relative = normalized_file[len(matched_root) :].lstrip("/")
    if not relative:
        return None

    return relative.split("/", 1)[0]


def parse_bucket_map(raw_pairs: list[str]) -> dict[str, str]:
    mapping = dict(DEFAULT_BUCKET_MAP)
    for pair in raw_pairs:
        if "=" not in pair:
            raise PlexGenreError(f"Invalid --map value '{pair}'. Expected bucket=Genre")
        bucket, genre = pair.split("=", 1)
        bucket = bucket.strip().lower()
        genre = genre.strip()
        if not bucket or not genre:
            raise PlexGenreError(f"Invalid --map value '{pair}'. Expected bucket=Genre")
        mapping[bucket] = genre
    return mapping


def plan_changes(
    base_url: str,
    token: str,
    section: LibrarySection,
    timeout: int,
    container_size: int,
    bucket_map: dict[str, str],
) -> tuple[list[PlannedChange], int, int]:
    planned: list[PlannedChange] = []
    skipped_without_path = 0
    skipped_without_bucket = 0

    for album in iter_albums(base_url, token, section.key, timeout, container_size):
        if not album.rating_key:
            continue

        file_path = get_album_file_path(base_url, token, album.rating_key, timeout)
        if not file_path:
            skipped_without_path += 1
            continue

        bucket = derive_bucket(file_path, section.locations)
        if not bucket:
            skipped_without_bucket += 1
            continue

        target_genre = bucket_map.get(bucket)
        if not target_genre:
            continue

        if album.genres == (target_genre,):
            continue

        planned.append(
            PlannedChange(
                album=album,
                file_path=file_path,
                bucket=bucket,
                target_genre=target_genre,
            )
        )

    return planned, skipped_without_path, skipped_without_bucket


def update_album_genre(base_url: str, token: str, section_key: str, timeout: int, change: PlannedChange, lock_genre: bool) -> None:
    query: dict[str, str | int] = {
        "type": 9,
        "id": change.album.rating_key,
        "genre[0].tag.tag": change.target_genre,
        "genre.locked": 1 if lock_genre else 0,
    }
    plex_put(base_url, f"/library/sections/{section_key}/all", token, timeout, query)


def resolve_token(args: argparse.Namespace) -> str:
    token = args.plex_token or os.environ.get("PLEX_TOKEN")
    if not token:
        raise PlexGenreError("Plex token is required. Pass --plex-token or set PLEX_TOKEN.")
    return token


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plex-url", required=True, help="Plex base URL, for example http://192.168.100.67:32400")
    parser.add_argument("--library-name", default="Music", help="Plex music library name (default: Music)")
    parser.add_argument("--plex-token", help="Plex auth token. If omitted, PLEX_TOKEN env var is used.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds (default: 20)")
    parser.add_argument(
        "--container-size",
        type=int,
        default=DEFAULT_CONTAINER_SIZE,
        help=f"How many albums to fetch per Plex page (default: {DEFAULT_CONTAINER_SIZE})",
    )
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="BUCKET=GENRE",
        help="Override a bucket mapping, for example --map misc='Pop Rock'",
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    parser.add_argument(
        "--no-lock-genre",
        action="store_true",
        help="Do not lock the Plex genre field after updating it.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)

    try:
        token = resolve_token(args)
        bucket_map = parse_bucket_map(args.map)
        section = find_music_section(args.plex_url, token, args.library_name, args.timeout)
        if section.section_type != "artist":
            raise PlexGenreError(f"Library '{section.title}' is not a music library (type={section.section_type!r}).")

        planned, skipped_without_path, skipped_without_bucket = plan_changes(
            args.plex_url,
            token,
            section,
            args.timeout,
            args.container_size,
            bucket_map,
        )

        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"{mode}: {len(planned)} album genre change(s) planned for library '{section.title}'")
        print(f"Mapped buckets: {', '.join(f'{bucket}={genre}' for bucket, genre in sorted(bucket_map.items()))}")
        if skipped_without_path:
            print(f"Skipped albums without readable track path: {skipped_without_path}")
        if skipped_without_bucket:
            print(f"Skipped albums outside known library roots: {skipped_without_bucket}")

        for change in planned:
            current = ", ".join(change.album.genres) if change.album.genres else "<none>"
            artist_prefix = f"{change.album.parent_title} - " if change.album.parent_title else ""
            print(
                f"{artist_prefix}{change.album.title}: "
                f"{current} -> {change.target_genre} "
                f"[bucket={change.bucket}]"
            )

        if args.apply:
            for change in planned:
                update_album_genre(
                    args.plex_url,
                    token,
                    section.key,
                    args.timeout,
                    change,
                    lock_genre=not args.no_lock_genre,
                )
            print(f"Applied {len(planned)} album genre change(s).")
        else:
            print("Dry-run only. Re-run with --apply to persist changes.")

        return 0
    except PlexGenreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
