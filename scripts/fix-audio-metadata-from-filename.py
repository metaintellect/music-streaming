#!/usr/bin/env python3
"""
Repair suspicious audio metadata by deriving safer values from filenames.

This is intended for cases where embedded tags contain mojibake or replacement
characters, while filenames are already cleaner and closer to the desired text.

Examples:
    # Dry-run one folder
    python3 scripts/fix-audio-metadata-from-filename.py \
      --root "/Volumes/xnas/music/exyu/Dalibor Brun/Mega mix - 29 hitova (1992)"

    # Apply title repair for WAV files in one folder
    python3 scripts/fix-audio-metadata-from-filename.py \
      --root "/Volumes/xnas/music/exyu/Dalibor Brun/Mega mix - 29 hitova (1992)" \
      --apply
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


SUSPICIOUS_MARKERS = (
    "\ufffd",  # replacement character
    "�",
    "",
    "",
    "",
    "",
    "",
)


class MetadataFixError(Exception):
    """User-facing error."""


@dataclass(frozen=True)
class AudioTags:
    title: str | None
    artist: str | None
    album: str | None
    album_artist: str | None
    date: str | None
    genre: str | None


@dataclass(frozen=True)
class PlannedFix:
    path: Path
    current_title: str | None
    new_title: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Folder to inspect recursively")
    parser.add_argument("--apply", action="store_true", help="Write changes to files")
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".wav", ".flac"],
        help="Audio extensions to inspect (default: .wav .flac)",
    )
    return parser.parse_args(argv)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def ffprobe_tags(path: Path) -> AudioTags:
    probe = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format_tags=title,artist,album,album_artist,date,genre",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(probe.stdout or "{}")
    tags = payload.get("format", {}).get("tags", {})
    return AudioTags(
        title=tags.get("title"),
        artist=tags.get("artist"),
        album=tags.get("album"),
        album_artist=tags.get("album_artist"),
        date=tags.get("date"),
        genre=tags.get("genre"),
    )


def contains_suspicious_text(value: str | None) -> bool:
    if not value:
        return False
    return any(marker in value for marker in SUSPICIOUS_MARKERS)


def derive_title_from_filename(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^\d{2}\s+", "", stem)
    stem = re.sub(r"^[^-]+ - ", "", stem, count=1)
    return stem.strip()


def find_audio_files(root: Path, extensions: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("._"):
            continue
        if path.suffix.lower() in extensions:
            files.append(path)
    return files


def plan_fixes(root: Path, extensions: set[str]) -> list[PlannedFix]:
    planned: list[PlannedFix] = []
    for path in find_audio_files(root, extensions):
        tags = ffprobe_tags(path)
        if not contains_suspicious_text(tags.title):
            continue
        new_title = derive_title_from_filename(path)
        if not new_title:
            continue
        if tags.title == new_title:
            continue
        planned.append(
            PlannedFix(
                path=path,
                current_title=tags.title,
                new_title=new_title,
            )
        )
    return planned


def update_audio_title(path: Path, new_title: str) -> None:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
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
                    "-metadata",
                    f"title={new_title}",
                    "-codec",
                    "copy",
                    str(temp_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            temp_path.replace(path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
        return

    if suffix == ".flac":
        subprocess.run(
            [
                "metaflac",
                "--remove-tag=TITLE",
                f"--set-tag=TITLE={new_title}",
                str(path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    raise MetadataFixError(f"Unsupported file type for metadata rewrite: {path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: root does not exist: {root}", file=sys.stderr)
        return 2

    extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in args.extensions}

    try:
        planned = plan_fixes(root, extensions)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or str(exc), file=sys.stderr)
        return 2
    except MetadataFixError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"{mode}: {len(planned)} suspicious title tag(s) under {root}")
    for fix in planned:
        print(f"{fix.path}")
        print(f"  title: {fix.current_title!r}")
        print(f"  file : {fix.new_title!r}")

    if args.apply:
        for fix in planned:
            update_audio_title(fix.path, fix.new_title)
        print(f"Applied {len(planned)} title fix(es).")
    else:
        print("Dry-run only. Re-run with --apply to write changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
