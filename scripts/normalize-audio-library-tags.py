#!/usr/bin/env python3
"""
Normalize audio file tags from the folder layout.

This script is intentionally conservative:
- optionally normalize GENRE from the top-level music bucket
- normalize compilation/album-artist tags only for explicit Various folders
- remove STYLE tags
- remove compilation tags from non-Various folders
- do not touch TITLE unless handled elsewhere

Examples:
    # Dry-run exyu only
    python3 scripts/normalize-audio-library-tags.py \
      --music-root /Volumes/xnas/music \
      --include-bucket exyu

    # Apply only misc/Various Artists
    python3 scripts/normalize-audio-library-tags.py \
      --music-root /Volumes/xnas/music \
      --include-bucket misc \
      --artist-folder "Various Artists" \
      --apply

    # Apply exyu + misc changes
    python3 scripts/normalize-audio-library-tags.py \
      --music-root /Volumes/xnas/music \
      --include-bucket exyu \
      --include-bucket misc \
      --apply
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

try:
    from mutagen.id3 import ID3, TALB, TCON, TIT2, TPE1, TPE2, TRCK, TXXX
    from mutagen.wave import WAVE
except ImportError:  # pragma: no cover - optional dependency on the target host
    ID3 = TALB = TCON = TIT2 = TPE1 = TPE2 = TRCK = TXXX = WAVE = None


DEFAULT_BUCKET_MAP = {
    "esoteric": "Esoteric",
    "exyu": "ExYU",
    "metal": "Metal",
    "jazz": "Jazz",
    "classical": "Classical",
    "misc": "Pop Rock",
}

DEFAULT_COMPILATION_ARTISTS = {
    ("exyu", "various"): "Various",
    ("exyu", "various artists"): "Various Artists",
    ("misc", "various artists"): "Various Artists",
}

SUPPORTED_EXTENSIONS = {".wav", ".flac"}
FFPROBE_TIMEOUT = 20
WRITE_TIMEOUT = 120


class NormalizeTagsError(Exception):
    """User-facing error."""


class Logger:
    def __init__(self, file_handle: TextIO | None = None) -> None:
        self.file_handle = file_handle

    def emit(self, message: str, *, stderr: bool = False, flush: bool = True) -> None:
        stream = sys.stderr if stderr else sys.stdout
        print(message, file=stream, flush=flush)
        if self.file_handle is not None:
            print(message, file=self.file_handle, flush=True)


@dataclass(frozen=True)
class AudioTags:
    genre: str | None
    album_artist: str | None
    compilation: str | None
    style: str | None


@dataclass(frozen=True)
class PlannedUpdate:
    path: Path
    bucket: str
    artist_folder: str
    current_genre: str | None
    target_genre: str | None
    current_album_artist: str | None
    target_album_artist: str | None
    current_compilation: str | None
    target_compilation: str | None
    current_style: str | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--music-root", required=True, help="Music library root")
    parser.add_argument("--apply", action="store_true", help="Write changes")
    parser.add_argument(
        "--set-genre",
        action="store_true",
        help="Also normalize per-track GENRE tags. Disabled by default.",
    )
    parser.add_argument(
        "--include-bucket",
        action="append",
        default=[],
        help="Only process specific top-level bucket(s), e.g. exyu",
    )
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="BUCKET=GENRE",
        help="Override bucket genre mapping",
    )
    parser.add_argument(
        "--artist-folder",
        action="append",
        default=[],
        help="Only process specific artist folder name(s), e.g. 'Various Artists'",
    )
    parser.add_argument(
        "--log-file",
        help="Write progress and results to this log file as well as stdout",
    )
    return parser.parse_args(argv)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT)


def parse_bucket_map(raw_pairs: list[str]) -> dict[str, str]:
    mapping = dict(DEFAULT_BUCKET_MAP)
    for pair in raw_pairs:
        if "=" not in pair:
            raise NormalizeTagsError(f"Invalid --map value '{pair}'. Expected bucket=Genre")
        bucket, genre = pair.split("=", 1)
        bucket = bucket.strip().lower()
        genre = genre.strip()
        if not bucket or not genre:
            raise NormalizeTagsError(f"Invalid --map value '{pair}'. Expected bucket=Genre")
        mapping[bucket] = genre
    return mapping


def ffprobe_tags(path: Path) -> AudioTags:
    probe = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format_tags=genre,album_artist,compilation,style",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(probe.stdout or "{}")
    raw_tags = payload.get("format", {}).get("tags", {})
    tags = {str(key).lower(): value for key, value in raw_tags.items()}
    return AudioTags(
        genre=normalize_empty(tags.get("genre")),
        album_artist=normalize_empty(tags.get("album_artist") or tags.get("albumartist")),
        compilation=normalize_empty(tags.get("compilation")),
        style=normalize_empty(tags.get("style")),
    )


def ffprobe_tag_value(path: Path, field: str) -> str | None:
    probe = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            f"format_tags={field}",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(probe.stdout or "{}")
    raw_tags = payload.get("format", {}).get("tags", {})
    tags = {str(key).lower(): value for key, value in raw_tags.items()}
    return normalize_empty(tags.get(field.lower()))


def normalize_empty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def normalize_compare(value: str | None) -> str | None:
    normalized = normalize_empty(value)
    return normalized.casefold() if normalized else None


def iter_audio_files(root: Path, include_buckets: set[str]):
    for current_root, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        current_path = Path(current_root)

        try:
            relative_dir = current_path.relative_to(root)
        except ValueError:
            continue

        if not relative_dir.parts and include_buckets:
            dirnames[:] = [name for name in dirnames if name.lower() in include_buckets]
        elif relative_dir.parts:
            bucket = relative_dir.parts[0].lower()
            if include_buckets and bucket not in include_buckets:
                dirnames[:] = []
                continue

        for name in filenames:
            if name.startswith("._"):
                continue
            suffix = Path(name).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                continue
            yield current_path / name


def derive_bucket_and_artist(path: Path, root: Path) -> tuple[str | None, str | None]:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None, None
    if len(relative.parts) < 3:
        return None, None
    return relative.parts[0].lower(), relative.parts[1]


def desired_compilation_fields(bucket: str, artist_folder: str) -> tuple[str | None, str | None, bool]:
    target_album_artist = DEFAULT_COMPILATION_ARTISTS.get((bucket, artist_folder.lower()))
    if target_album_artist:
        return target_album_artist, "1", True
    return None, None, False


def plan_updates(
    root: Path,
    include_buckets: set[str],
    include_artist_folders: set[str],
    bucket_map: dict[str, str],
    set_genre: bool,
    logger: Logger,
) -> list[PlannedUpdate]:
    planned: list[PlannedUpdate] = []
    scanned = 0
    skipped_probe_failures = 0
    for path in iter_audio_files(root, include_buckets):
        scanned += 1
        if scanned % 500 == 0:
            logger.emit(
                f"Scanned {scanned} audio files... "
                f"(planned {len(planned)}, skipped probe failures {skipped_probe_failures})",
            )
        bucket, artist_folder = derive_bucket_and_artist(path, root)
        if not bucket or not artist_folder:
            continue
        if include_artist_folders and artist_folder.casefold() not in include_artist_folders:
            continue

        try:
            tags = ffprobe_tags(path)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            skipped_probe_failures += 1
            logger.emit(f"Skipping unreadable file: {path}")
            continue
        target_genre = bucket_map.get(bucket) if set_genre else None
        target_album_artist, target_compilation, should_update_album_artist = desired_compilation_fields(bucket, artist_folder)

        needs_genre = target_genre is not None and normalize_compare(tags.genre) != target_genre.casefold()
        needs_album_artist = should_update_album_artist and normalize_compare(tags.album_artist) != normalize_compare(target_album_artist)
        needs_compilation = normalize_compare(tags.compilation) != normalize_compare(target_compilation)
        needs_style = tags.style is not None

        if not (needs_genre or needs_album_artist or needs_compilation or needs_style):
            continue

        planned.append(
            PlannedUpdate(
                path=path,
                bucket=bucket,
                artist_folder=artist_folder,
                current_genre=tags.genre,
                target_genre=target_genre,
                current_album_artist=tags.album_artist,
                target_album_artist=target_album_artist if should_update_album_artist else tags.album_artist,
                current_compilation=tags.compilation,
                target_compilation=target_compilation,
                current_style=tags.style,
            )
        )
    return planned


def _ffmpeg_metadata_args(update: PlannedUpdate) -> list[str]:
    args: list[str] = []
    if update.target_genre is None:
        args.extend(["-metadata", "genre="])
    else:
        args.extend(["-metadata", f"genre={update.target_genre}"])

    if update.target_album_artist is None:
        args.extend(["-metadata", "album_artist="])
    else:
        args.extend(["-metadata", f"album_artist={update.target_album_artist}"])

    if update.target_compilation is None:
        args.extend(["-metadata", "compilation="])
    else:
        args.extend(["-metadata", f"compilation={update.target_compilation}"])

    args.extend(["-metadata", "style="])

    return args


def update_wav_tags(update: PlannedUpdate) -> None:
    if (update.target_album_artist is not None or update.target_compilation is not None) and WAVE is not None:
        update_wav_tags_with_mutagen(update)
        return

    path = update.path
    with tempfile.NamedTemporaryFile(
        suffix=path.suffix,
        prefix=path.stem + ".",
        dir=str(path.parent),
        delete=False,
    ) as tmp:
        temp_path = Path(tmp.name)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-map_metadata",
                "0",
                *_ffmpeg_metadata_args(update),
                "-codec",
                "copy",
                str(temp_path),
            ],
            check=True,
            timeout=WRITE_TIMEOUT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def update_wav_tags_with_mutagen(update: PlannedUpdate) -> None:
    if WAVE is None or ID3 is None:
        raise NormalizeTagsError("python3-mutagen is required for WAV compilation album fixes")

    audio = WAVE(str(update.path))
    tags = audio.tags
    if tags is None:
        tags = ID3()
        audio.tags = tags

    title = ffprobe_tag_value(update.path, "title")
    artist = ffprobe_tag_value(update.path, "artist")
    album = ffprobe_tag_value(update.path, "album")
    track = ffprobe_tag_value(update.path, "track")

    if title is not None:
        tags.delall("TIT2")
        tags.add(TIT2(encoding=3, text=[title]))
    if artist is not None:
        tags.delall("TPE1")
        tags.add(TPE1(encoding=3, text=[artist]))
    if album is not None:
        tags.delall("TALB")
        tags.add(TALB(encoding=3, text=[album]))
    if track is not None:
        tags.delall("TRCK")
        tags.add(TRCK(encoding=3, text=[track]))

    tags.delall("TCON")
    if update.target_genre is not None:
        tags.add(TCON(encoding=3, text=[update.target_genre]))

    tags.delall("TPE2")
    if update.target_album_artist is not None:
        tags.add(TPE2(encoding=3, text=[update.target_album_artist]))

    tags.delall("TXXX:TCMP")
    if update.target_compilation is not None:
        tags.add(TXXX(encoding=3, desc="TCMP", text=[update.target_compilation]))

    audio.save()


def update_flac_tags(update: PlannedUpdate) -> None:
    cmd = [
        "metaflac",
        "--remove-tag=GENRE",
        "--remove-tag=ALBUMARTIST",
        "--remove-tag=COMPILATION",
        "--remove-tag=STYLE",
    ]
    if update.target_genre is not None:
        cmd.append(f"--set-tag=GENRE={update.target_genre}")
    if update.target_album_artist is not None:
        cmd.append(f"--set-tag=ALBUMARTIST={update.target_album_artist}")
    if update.target_compilation is not None:
        cmd.append(f"--set-tag=COMPILATION={update.target_compilation}")
    cmd.append(str(update.path))

    subprocess.run(
        cmd,
        check=True,
        timeout=WRITE_TIMEOUT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def apply_update(update: PlannedUpdate) -> None:
    suffix = update.path.suffix.lower()
    if suffix == ".wav":
        update_wav_tags(update)
        return
    if suffix == ".flac":
        update_flac_tags(update)
        return
    raise NormalizeTagsError(f"Unsupported file type: {update.path}")


def summarize_changes(planned: list[PlannedUpdate]) -> tuple[int, int, int]:
    genre = 0
    album_artist = 0
    compilation = 0
    style = 0
    for update in planned:
        if normalize_compare(update.current_genre) != normalize_compare(update.target_genre):
            genre += 1
        if normalize_compare(update.current_album_artist) != normalize_compare(update.target_album_artist):
            album_artist += 1
        if normalize_compare(update.current_compilation) != normalize_compare(update.target_compilation):
            compilation += 1
        if update.current_style is not None:
            style += 1
    return genre, album_artist, compilation, style


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.music_root)
    log_handle = None
    try:
        if args.log_file:
            log_path = Path(args.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = log_path.open("a", encoding="utf-8")
        logger = Logger(log_handle)

        if not root.exists():
            logger.emit(f"ERROR: music root does not exist: {root}", stderr=True)
            return 2

        include_buckets = {bucket.strip().lower() for bucket in args.include_bucket if bucket.strip()}
        include_artist_folders = {
            artist_folder.strip().casefold()
            for artist_folder in args.artist_folder
            if artist_folder.strip()
        }

        bucket_map = parse_bucket_map(args.map)
        planned = plan_updates(root, include_buckets, include_artist_folders, bucket_map, args.set_genre, logger)
        mode = "APPLY" if args.apply else "DRY-RUN"
        genre_count, album_artist_count, compilation_count, style_count = summarize_changes(planned)
        bucket_label = ", ".join(sorted(include_buckets)) if include_buckets else "all buckets"
        artist_label = ", ".join(sorted(include_artist_folders)) if include_artist_folders else "all artist folders"
        logger.emit(
            f"{mode}: {len(planned)} file tag update(s) planned under {root} "
            f"[{bucket_label}] [{artist_label}]"
        )
        logger.emit(
            "Fields: "
            f"genre={genre_count}, album_artist={album_artist_count}, compilation={compilation_count}, style={style_count}"
        )

        for update in planned[:50]:
            logger.emit(str(update.path))
            if normalize_compare(update.current_genre) != normalize_compare(update.target_genre):
                logger.emit(f"  genre       : {update.current_genre!r} -> {update.target_genre!r}")
            if normalize_compare(update.current_album_artist) != normalize_compare(update.target_album_artist):
                logger.emit(f"  album_artist: {update.current_album_artist!r} -> {update.target_album_artist!r}")
            if normalize_compare(update.current_compilation) != normalize_compare(update.target_compilation):
                logger.emit(f"  compilation : {update.current_compilation!r} -> {update.target_compilation!r}")
            if update.current_style is not None:
                logger.emit(f"  style       : {update.current_style!r} -> None")

        if len(planned) > 50:
            logger.emit(f"... {len(planned) - 50} more file(s) omitted from preview")

        if args.apply:
            applied = 0
            skipped_write_failures = 0
            for update in planned:
                try:
                    apply_update(update)
                    applied += 1
                    if applied % 500 == 0:
                        logger.emit(
                            f"Applied {applied} file updates... "
                            f"(skipped write failures {skipped_write_failures})",
                        )
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    skipped_write_failures += 1
                    logger.emit(f"Skipping unwritable file: {update.path}")
            logger.emit(
                f"Applied {applied} file tag update(s). "
                f"Skipped write failures {skipped_write_failures}."
            )
        else:
            logger.emit("Dry-run only. Re-run with --apply to write changes.")

        return 0
    except subprocess.TimeoutExpired as exc:
        Logger(log_handle).emit(str(exc), stderr=True)
        return 2
    except subprocess.CalledProcessError as exc:
        Logger(log_handle).emit(exc.stderr or str(exc), stderr=True)
        return 2
    except NormalizeTagsError as exc:
        Logger(log_handle).emit(f"ERROR: {exc}", stderr=True)
        return 2
    finally:
        if log_handle is not None:
            log_handle.close()


if __name__ == "__main__":
    sys.exit(main())
