#!/usr/bin/env python3
"""
Convert one music bucket from WAV to FLAC while preserving folder structure.

Typical use:
    # After renaming /music/metal -> /music/metal-wav
    python3 scripts/convert-wav-bucket-to-flac.py \
      --music-root /Volumes/xnas/music \
      --source-bucket metal-wav \
      --dest-bucket metal \
      --apply

    # Resume after a partial run
    python3 scripts/convert-wav-bucket-to-flac.py \
      --music-root /Volumes/xnas/music \
      --source-bucket metal-wav \
      --dest-bucket metal \
      --resume \
      --apply

This script:
- converts `.wav` files to `.flac`
- copies existing `.flac` files by default
- preserves relative folder layout
- copies common sidecar files (artwork, cue sheets, logs)
- writes a manifest of destination album folders for later MusicBrainz/beets work

It does not retag through MusicBrainz by itself. That stays a second pass because
external tagging is much riskier than the audio conversion step.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


DISC_DIR_RE = re.compile(r"^(cd|disc|disk)[ _-]?\d+$", re.IGNORECASE)
DEFAULT_SIDECAR_EXTENSIONS = {
    ".cue",
    ".gif",
    ".jpeg",
    ".jpg",
    ".log",
    ".m3u",
    ".m3u8",
    ".md5",
    ".nfo",
    ".pdf",
    ".png",
    ".sfv",
    ".txt",
    ".xml",
}


class ConvertBucketError(Exception):
    """User-facing error."""


class Logger:
    def __init__(self, file_handle: TextIO | None = None) -> None:
        self.file_handle = file_handle

    def emit(self, message: str, *, stderr: bool = False) -> None:
        stream = sys.stderr if stderr else sys.stdout
        print(message, file=stream, flush=True)
        if self.file_handle is not None:
            print(message, file=self.file_handle, flush=True)


@dataclass(frozen=True)
class PlannedAction:
    source: Path
    dest: Path
    kind: str  # convert | copy
    album_dir: Path | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--music-root", required=True, help="Root folder containing the music buckets")
    parser.add_argument("--source-bucket", required=True, help="Source bucket name, e.g. metal-wav")
    parser.add_argument(
        "--dest-bucket",
        help="Destination bucket name. If omitted and source ends with -wav, that suffix is removed.",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip destination files that already exist so a rerun resumes from partial output",
    )
    parser.add_argument("--log-file", help="Also write progress and summary to this log file")
    parser.add_argument(
        "--album-manifest",
        help="Write destination album directories (one per line) for later beets/MusicBrainz tagging",
    )
    parser.add_argument(
        "--skip-flac",
        action="store_true",
        help="Do not copy existing FLAC files from the source tree",
    )
    return parser.parse_args(argv)


def derive_dest_bucket(source_bucket: str, dest_bucket: str | None) -> str:
    if dest_bucket:
        return dest_bucket
    if source_bucket.lower().endswith("-wav"):
        return source_bucket[:-4]
    raise ConvertBucketError("--dest-bucket is required unless --source-bucket ends with -wav")


def album_dir_from_relative_path(relative_path: Path) -> Path | None:
    parent = relative_path.parent
    if not parent.parts:
        return None
    if DISC_DIR_RE.match(parent.name):
        parent = parent.parent
    return parent if parent.parts else None


def is_sidecar(path: Path) -> bool:
    return path.suffix.lower() in DEFAULT_SIDECAR_EXTENSIONS


def iter_source_files(root: Path):
    for current_root, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        base = Path(current_root)
        for name in filenames:
            if name.startswith("._"):
                continue
            yield base / name


def plan_actions(source_root: Path, dest_root: Path, copy_flac: bool, resume: bool = False) -> list[PlannedAction]:
    planned: list[PlannedAction] = []
    for source in iter_source_files(source_root):
        relative = source.relative_to(source_root)
        suffix = source.suffix.lower()
        album_dir = album_dir_from_relative_path(relative)

        if suffix == ".wav":
            dest = (dest_root / relative).with_suffix(".flac")
            if resume and dest.exists():
                continue
            planned.append(
                PlannedAction(
                    source=source,
                    dest=dest,
                    kind="convert",
                    album_dir=(dest_root / album_dir) if album_dir is not None else None,
                )
            )
            continue

        if suffix == ".flac" and copy_flac:
            dest = dest_root / relative
            if resume and dest.exists():
                continue
            planned.append(
                PlannedAction(
                    source=source,
                    dest=dest,
                    kind="copy",
                    album_dir=(dest_root / album_dir) if album_dir is not None else None,
                )
            )
            continue

        if is_sidecar(source):
            dest = dest_root / relative
            if resume and dest.exists():
                continue
            planned.append(
                PlannedAction(
                    source=source,
                    dest=dest,
                    kind="copy",
                    album_dir=None,
                )
            )

    return planned


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def convert_wav_to_flac(source: Path, dest: Path) -> None:
    ensure_parent(dest)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-map_metadata",
            "0",
            "-c:a",
            "flac",
            str(dest),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def copy_file(source: Path, dest: Path) -> None:
    ensure_parent(dest)
    shutil.copy2(source, dest)


def write_manifest(manifest_path: Path, album_dirs: list[Path]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("\n".join(str(path) for path in album_dirs) + "\n", encoding="utf-8")


def summarize(planned: list[PlannedAction]) -> tuple[int, int]:
    converts = sum(1 for action in planned if action.kind == "convert")
    copies = sum(1 for action in planned if action.kind == "copy")
    return converts, copies


def execute_actions(planned: list[PlannedAction], logger: Logger) -> tuple[int, int]:
    completed = 0
    skipped_failures = 0

    for action in planned:
        try:
            if action.kind == "convert":
                convert_wav_to_flac(action.source, action.dest)
            else:
                copy_file(action.source, action.dest)
            completed += 1
            if completed % 250 == 0:
                logger.emit(
                    f"Completed {completed}/{len(planned)} actions "
                    f"(skipped failures {skipped_failures})"
                )
        except (subprocess.CalledProcessError, OSError) as exc:
            skipped_failures += 1
            logger.emit(f"Skipping failed {action.kind}: {action.source} -> {action.dest}")
            logger.emit(f"  reason: {exc}")

    return completed, skipped_failures


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log_handle = None
    try:
        if args.log_file:
            log_path = Path(args.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = log_path.open("a", encoding="utf-8")
        logger = Logger(log_handle)

        music_root = Path(args.music_root)
        if not music_root.exists():
            raise ConvertBucketError(f"music root does not exist: {music_root}")

        source_bucket = args.source_bucket
        dest_bucket = derive_dest_bucket(source_bucket, args.dest_bucket)
        if source_bucket == dest_bucket:
            raise ConvertBucketError("source and destination buckets must differ")

        source_root = music_root / source_bucket
        dest_root = music_root / dest_bucket

        if not source_root.exists():
            raise ConvertBucketError(f"source bucket does not exist: {source_root}")

        planned = plan_actions(source_root, dest_root, not args.skip_flac, args.resume)
        converts, copies = summarize(planned)
        album_dirs = sorted({action.album_dir for action in planned if action.album_dir is not None})

        mode = "APPLY" if args.apply else "DRY-RUN"
        logger.emit(f"{mode}: source={source_root} dest={dest_root}")
        logger.emit(f"Resume mode: {'on' if args.resume else 'off'}")
        logger.emit(
            f"Planned actions: total={len(planned)} convert_wav_to_flac={converts} copy_sidecars_or_flac={copies}"
        )
        logger.emit(f"Album directories: {len(album_dirs)}")

        for action in planned[:40]:
            logger.emit(f"{action.kind}: {action.source} -> {action.dest}")
        if len(planned) > 40:
            logger.emit(f"... {len(planned) - 40} more action(s) omitted from preview")

        if args.album_manifest:
            write_manifest(Path(args.album_manifest), album_dirs)
            logger.emit(f"Wrote album manifest: {args.album_manifest}")

        if not args.apply:
            logger.emit("Dry-run only. Re-run with --apply to write changes.")
            return 0

        completed, skipped_failures = execute_actions(planned, logger)
        logger.emit(
            f"Completed {completed}/{len(planned)} actions. "
            f"Skipped failures {skipped_failures}."
        )
        return 0

    except (ConvertBucketError, subprocess.CalledProcessError) as exc:
        Logger(log_handle).emit(f"ERROR: {exc}", stderr=True)
        return 2
    finally:
        if log_handle is not None:
            log_handle.close()


if __name__ == "__main__":
    sys.exit(main())
