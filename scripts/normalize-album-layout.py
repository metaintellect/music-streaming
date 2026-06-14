#!/usr/bin/env python3
"""
Normalize in-place album folder and track file naming from audio tags.

This script is intentionally filesystem-first:
- finds leaf album folders that directly contain audio files
- renames tracks to `NN Artist - Title.ext`
- optionally renames album folders to `Album (Year)`
- does not move albums across artist/grouping folders
- does not touch sidecar files except by moving them with the folder rename

Examples:
    # Dry-run one artist folder
    python3 scripts/normalize-album-layout.py \
      --root "/Volumes/xnas/music/metal/Vicious Rumors"

    # Apply changes for one artist folder
    python3 scripts/normalize-album-layout.py \
      --root "/Volumes/xnas/music/metal/Vicious Rumors" \
      --apply

    # Dry-run on a messy CD_RIP discography tree
    python3 scripts/normalize-album-layout.py \
      --root "/Volumes/xnas/CD_RIP/Armored Saint - Discography"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".flac", ".wav"}


class NormalizeLayoutError(Exception):
    """User-facing error."""


@dataclass(frozen=True)
class TrackInfo:
    path: Path
    artist: str | None
    album: str | None
    title: str | None
    album_artist: str | None
    date: str | None
    track: str | None


@dataclass(frozen=True)
class FileRename:
    src: Path
    dst: Path


@dataclass(frozen=True)
class AlbumPlan:
    album_dir: Path
    target_dir: Path
    file_renames: tuple[FileRename, ...]
    album_name: str | None
    year: str | None


@dataclass(frozen=True)
class SkippedAlbum:
    album_dir: Path
    reason: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Root folder to inspect recursively")
    parser.add_argument("--apply", action="store_true", help="Write changes")
    parser.add_argument(
        "--no-rename-folders",
        action="store_true",
        help="Only rename track files, leave album folder names as-is",
    )
    parser.add_argument(
        "--no-rename-tracks",
        action="store_true",
        help="Only rename album folders, leave track file names as-is",
    )
    return parser.parse_args(argv)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def normalize_key_map(payload: dict[str, object]) -> dict[str, str]:
    return {
        str(key).lower(): str(value)
        for key, value in payload.items()
        if value is not None and str(value).strip()
    }


def ffprobe_tags(path: Path) -> TrackInfo:
    probe = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format_tags=artist,album,title,album_artist,albumartist,date,track,tracknumber",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(probe.stdout or "{}")
    tags = normalize_key_map(payload.get("format", {}).get("tags", {}))
    return TrackInfo(
        path=path,
        artist=clean_value(tags.get("artist")),
        album=clean_value(tags.get("album")),
        title=clean_value(tags.get("title")),
        album_artist=clean_value(tags.get("album_artist") or tags.get("albumartist")),
        date=clean_value(tags.get("date")),
        track=clean_value(tags.get("track") or tags.get("tracknumber")),
    )


def clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().replace("\r", "")
    return stripped or None


def sanitize_path_part(value: str) -> str:
    value = value.replace("/", "_")
    value = value.replace(":", " -")
    value = re.sub(r"\s+", " ", value).strip()
    return value.rstrip(".")


def parse_track_number(value: str | None, fallback_name: str) -> str | None:
    if value:
        match = re.search(r"(\d{1,3})", value)
        if match:
            return f"{int(match.group(1)):02d}"
    match = re.match(r"^(\d{1,3})[\s._-]", fallback_name)
    if match:
        return f"{int(match.group(1)):02d}"
    return None


def derive_title_from_filename(path: Path, artist: str | None) -> str:
    stem = path.stem
    stem = re.sub(r"^\d{1,3}[\s._-]+", "", stem)
    if artist:
        stem = re.sub(rf"^{re.escape(artist)}[\s._-]+", "", stem, flags=re.IGNORECASE)
    return stem.strip()


def choose_common(values: list[str | None]) -> str | None:
    filtered = [value for value in values if value]
    if not filtered:
        return None
    return Counter(filtered).most_common(1)[0][0]


def infer_year(album_dir: Path, tracks: list[TrackInfo]) -> str | None:
    tag_year = choose_common([extract_year(track.date) for track in tracks])
    if tag_year:
        return tag_year
    for candidate in (album_dir.name, album_dir.parent.name):
        inferred = extract_year(candidate)
        if inferred:
            return inferred
    return None


def extract_year(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", value)
    if match:
        return match.group(0)
    return None


def find_album_dirs(root: Path) -> list[Path]:
    album_dirs: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        current = Path(current_root)
        has_audio = any(
            not name.startswith("._") and Path(name).suffix.lower() in SUPPORTED_EXTENSIONS
            for name in filenames
        )
        if has_audio:
            album_dirs.append(current)
    return sorted(album_dirs)


def plan_album(album_dir: Path, rename_folders: bool, rename_tracks: bool) -> AlbumPlan:
    audio_files = sorted(
        path
        for path in album_dir.iterdir()
        if path.is_file() and not path.name.startswith("._") and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    cue_files = sorted(path for path in album_dir.iterdir() if path.is_file() and path.suffix.lower() == ".cue")
    if len(audio_files) == 1 and cue_files:
        raise NormalizeLayoutError("single-image FLAC/WAV + CUE; use promote-cd-rip-album.sh instead")
    tracks = [ffprobe_tags(path) for path in audio_files]
    album_name = choose_common([track.album for track in tracks])
    album_artist = choose_common([track.album_artist for track in tracks])
    common_artist = choose_common([track.artist for track in tracks])
    year = infer_year(album_dir, tracks)

    if not album_name:
        album_name = strip_year_prefix(album_dir.name)

    if not album_name:
        raise NormalizeLayoutError(f"Could not infer album name for {album_dir}")

    target_dir = album_dir
    if rename_folders:
        folder_name = sanitize_path_part(album_name)
        if year:
            folder_name = f"{folder_name} ({year})"
        target_dir = album_dir.with_name(folder_name)

    file_renames: list[FileRename] = []
    if rename_tracks:
        for track in tracks:
            track_artist = track.artist or album_artist or common_artist
            track_number = parse_track_number(track.track, track.path.name)
            title = track.title or derive_title_from_filename(track.path, track_artist)

            if not track_number or not track_artist or not title:
                raise NormalizeLayoutError(f"Could not infer track naming data for {track.path}")

            target_name = sanitize_path_part(f"{track_number} {track_artist} - {title}") + track.path.suffix.lower()
            target_path = album_dir / target_name
            file_renames.append(FileRename(src=track.path, dst=target_path))

    return AlbumPlan(
        album_dir=album_dir,
        target_dir=target_dir,
        file_renames=tuple(file_renames),
        album_name=album_name,
        year=year,
    )


def strip_year_prefix(value: str) -> str:
    value = re.sub(r"^(19|20)\d{2}\s*-\s*", "", value)
    return value.strip()


def validate_plan(plans: list[AlbumPlan]) -> None:
    target_dirs: set[Path] = set()
    for plan in plans:
        if plan.target_dir in target_dirs and plan.target_dir != plan.album_dir:
            raise NormalizeLayoutError(f"Two albums would rename to the same folder: {plan.target_dir}")
        target_dirs.add(plan.target_dir)

        target_files: set[Path] = set()
        for rename in plan.file_renames:
            if rename.dst in target_files and rename.dst != rename.src:
                raise NormalizeLayoutError(f"Two tracks would rename to the same file: {rename.dst}")
            target_files.add(rename.dst)

        if plan.target_dir != plan.album_dir and plan.target_dir.exists():
            raise NormalizeLayoutError(f"Target folder already exists: {plan.target_dir}")
        for rename in plan.file_renames:
            if rename.dst != rename.src and rename.dst.exists():
                raise NormalizeLayoutError(f"Target file already exists: {rename.dst}")


def apply_plan(plans: list[AlbumPlan]) -> None:
    for plan in plans:
        temp_pairs: list[tuple[Path, Path]] = []
        for index, rename in enumerate(plan.file_renames):
            if rename.src == rename.dst:
                continue
            temp_path = rename.src.with_name(f".normalize-layout.{index:03d}.{rename.src.name}")
            rename.src.rename(temp_path)
            temp_pairs.append((temp_path, rename.dst))

        for temp_path, final_path in temp_pairs:
            temp_path.rename(final_path)

    for plan in sorted(plans, key=lambda item: len(item.album_dir.parts), reverse=True):
        if plan.album_dir != plan.target_dir:
            plan.album_dir.rename(plan.target_dir)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root does not exist: {root}", file=sys.stderr)
        return 2

    rename_folders = not args.no_rename_folders
    rename_tracks = not args.no_rename_tracks
    if not rename_folders and not rename_tracks:
        print("ERROR: nothing to do; both folder and track renames are disabled", file=sys.stderr)
        return 2

    try:
        album_dirs = find_album_dirs(root)
        total_album_dirs = len(album_dirs)
        plans: list[AlbumPlan] = []
        skipped: list[SkippedAlbum] = []
        for album_dir in album_dirs:
            try:
                plans.append(plan_album(album_dir, rename_folders, rename_tracks))
            except NormalizeLayoutError as exc:
                skipped.append(SkippedAlbum(album_dir=album_dir, reason=str(exc)))
        validate_plan(plans)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or str(exc), file=sys.stderr)
        return 2
    except NormalizeLayoutError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    album_changes = sum(1 for plan in plans if plan.target_dir != plan.album_dir)
    track_changes = sum(
        1
        for plan in plans
        for rename in plan.file_renames
        if rename.src != rename.dst
    )
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"{mode}: {total_album_dirs} album folder(s) scanned under {root}")
    print(f"Planned changes: album_folders={album_changes}, track_files={track_changes}")
    if skipped:
        print(f"Skipped album folders: {len(skipped)}")

    for plan in plans[:50]:
        if plan.target_dir != plan.album_dir:
            print(f"ALBUM: {plan.album_dir}")
            print(f"  -> {plan.target_dir}")
        changed_files = [rename for rename in plan.file_renames if rename.src != rename.dst]
        for rename in changed_files[:10]:
            print(f"TRACK: {rename.src.name}")
            print(f"  -> {rename.dst.name}")

    for skipped_album in skipped[:20]:
        print(f"SKIP: {skipped_album.album_dir}")
        print(f"  reason: {skipped_album.reason}")

    if args.apply:
        apply_plan(plans)
        print("Applied layout changes.")
    else:
        print("Dry-run only. Re-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
