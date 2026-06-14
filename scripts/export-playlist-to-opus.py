#!/usr/bin/env python3
"""
Export playlist tracks directly to Opus in dedicated output folders.

Examples:
    # Dry run one playlist from a mounted NAS share
    python3 scripts/export-playlist-to-opus.py \
      --playlists-root /mnt/nas/playlists \
      --unc-root /mnt/nas \
      --output-root /mnt/nas/portable-opus \
      --playlist exyu

    # Convert multiple playlists to Opus
    python3 scripts/export-playlist-to-opus.py \
      --playlists-root /mnt/nas/playlists \
      --unc-root /mnt/nas \
      --output-root /mnt/nas/portable-opus \
      --playlist exyu \
      --playlist easy \
      --apply
"""

from __future__ import annotations

import argparse
import base64
import math
import mimetypes
import re
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlparse


SUPPORTED_SUFFIXES = (".m3u", ".m3u8")
UNC_PATH_RE = re.compile(r"^[\\/]{2}([^\\/]+)[\\/]+([^\\/]+)(?:[\\/]+(.*))?$")
TRACK_PREFIX_RE = re.compile(r"^\d+\s+")
FOLDER_ART_CANDIDATES = ("Folder.jpg", "folder.jpg", "Cover.jpg", "cover.jpg")
LOUDNESS_RE = re.compile(r"^\s*I:\s*(-?\d+(?:\.\d+)?) LUFS\s*$", re.MULTILINE)
PEAK_RE = re.compile(r"^\s*Peak:\s*(-?\d+(?:\.\d+)?) dBFS\s*$", re.MULTILINE)
TEMP_FILE_PATTERNS = (
    "playlist-opus-audio-*",
    "playlist-opus-final-*",
    "playlist-opus-meta-*",
)


class PlaylistExportError(Exception):
    """User-facing error."""


@dataclass(frozen=True)
class ParsedPlaylist:
    paths: list[Path]
    entries_read: int
    blank_lines: int
    comment_lines: int
    duplicate_entries: int


@dataclass(frozen=True)
class ValidationResult:
    existing_files: list[Path]
    missing_paths: list[Path]
    non_file_paths: list[Path]


@dataclass(frozen=True)
class FilenameCollision:
    filename: str
    sources: list[Path]


@dataclass(frozen=True)
class ExportAction:
    source: Path
    dest: Path
    renamed: bool
    art_path: Path | None


@dataclass(frozen=True)
class ReplayGainResult:
    gain_db: float
    peak_linear: float


@dataclass(frozen=True)
class ExecuteResult:
    converted: int
    skipped_existing: int
    artwork_embedded: int
    artwork_missing: int
    replaygain_written: int
    replaygain_failed: int
    failed: int
    artwork_missing_albums: list[Path]
    failures: list[str]


class Logger:
    def __init__(self, file_handle=None) -> None:
        self.file_handle = file_handle

    def emit(self, message: str, *, stderr: bool = False) -> None:
        stream = sys.stderr if stderr else sys.stdout
        print(message, file=stream, flush=True)
        if self.file_handle is not None:
            print(message, file=self.file_handle, flush=True)


def run_captured(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playlists-root", required=True, help="Folder containing playlist files")
    parser.add_argument("--unc-root", required=True, help="Mounted share root, e.g. /mnt/nas")
    parser.add_argument("--output-root", required=True, help="Root folder for final Opus exports")
    parser.add_argument(
        "--playlist",
        action="append",
        help="Playlist file or stem name. May be passed multiple times. If omitted, all .m3u/.m3u8 files are processed.",
    )
    parser.add_argument("--bitrate-kbps", type=int, default=128, help="Target Opus bitrate in kbps. Default: %(default)s")
    parser.add_argument(
        "--mode",
        choices=("vbr", "cvbr", "cbr"),
        default="vbr",
        help="Opus bitrate mode. Default: %(default)s",
    )
    parser.add_argument(
        "--replaygain-target-lufs",
        type=float,
        default=-18.0,
        help="Target loudness for Track Gain tags. Default: %(default)s",
    )
    parser.add_argument("--apply", action="store_true", help="Write output files")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing destination files")
    parser.add_argument("--no-replaygain", action="store_true", help="Do not analyze or write ReplayGain tags")
    parser.add_argument("--no-artwork", action="store_true", help="Do not embed folder artwork")
    parser.add_argument("--log-file", help="Also write progress and warnings to this file")
    return parser.parse_args(argv)


def resolve_playlist_file(playlists_root: Path, requested: str) -> Path:
    requested_path = Path(requested).expanduser()
    if requested_path.exists():
        return requested_path

    candidates = [playlists_root / requested]
    if not Path(requested).suffix:
        for suffix in SUPPORTED_SUFFIXES:
            candidates.append(playlists_root / f"{requested}{suffix}")

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    raise PlaylistExportError(f"Playlist not found for '{requested}' in {playlists_root}")


def resolve_playlists(playlists_root: Path, requested: list[str] | None) -> list[Path]:
    if requested:
        return [resolve_playlist_file(playlists_root, item) for item in requested]

    if not playlists_root.exists():
        raise PlaylistExportError(f"Playlist root does not exist: {playlists_root}")

    playlists = sorted(
        path for path in playlists_root.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not playlists:
        raise PlaylistExportError(f"No playlist files found in {playlists_root}")
    return playlists


def normalize_windows_path(raw_value: str, unc_root: Path | None, playlist_path: Path) -> Path | None:
    match = UNC_PATH_RE.match(raw_value)
    if not match:
        return None

    _server, _share, remainder = match.groups()
    if unc_root is None:
        raise PlaylistExportError(
            f"Playlist contains Windows UNC path but --unc-root was not provided: {raw_value}"
        )

    mapped = unc_root
    if remainder:
        for part in re.split(r"[\\/]+", remainder):
            if part:
                mapped /= part
    return mapped


def decode_playlist_path(raw_value: str, playlist_path: Path, unc_root: Path | None) -> Path:
    if raw_value.startswith("file://"):
        parsed = urlparse(raw_value)
        if parsed.scheme != "file":
            raise PlaylistExportError(f"Unsupported URI in {playlist_path}: {raw_value}")
        if parsed.netloc not in ("", "localhost"):
            raise PlaylistExportError(f"Unsupported file URI host in {playlist_path}: {raw_value}")
        resolved = Path(unquote(parsed.path))
    else:
        windows_path = normalize_windows_path(raw_value, unc_root, playlist_path)
        resolved = windows_path if windows_path is not None else Path(raw_value).expanduser()

    if not resolved.is_absolute():
        resolved = (playlist_path.parent / resolved).resolve()

    return resolved


def parse_playlist(playlist_path: Path, unc_root: Path | None) -> ParsedPlaylist:
    try:
        lines = playlist_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise PlaylistExportError(f"Could not read playlist {playlist_path}: {exc}") from exc

    entries_read = 0
    blank_lines = 0
    comment_lines = 0
    duplicate_entries = 0
    unique_paths: list[Path] = []
    seen: set[Path] = set()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            blank_lines += 1
            continue
        if line.startswith("#"):
            comment_lines += 1
            continue
        entries_read += 1
        path = decode_playlist_path(line, playlist_path, unc_root)
        if path in seen:
            duplicate_entries += 1
            continue
        seen.add(path)
        unique_paths.append(path)

    return ParsedPlaylist(
        paths=unique_paths,
        entries_read=entries_read,
        blank_lines=blank_lines,
        comment_lines=comment_lines,
        duplicate_entries=duplicate_entries,
    )


def playlist_folder_name(playlist_path: Path) -> str:
    return playlist_path.stem if playlist_path.suffix else playlist_path.name


def destination_filename(source: Path) -> str:
    stripped = TRACK_PREFIX_RE.sub("", source.stem, count=1)
    return f"{stripped}.opus"


def unique_dest_path(dest_dir: Path, filename: str, reserved: set[Path]) -> tuple[Path, bool]:
    candidate = dest_dir / filename
    if candidate not in reserved:
        return candidate, False

    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        renamed = dest_dir / f"{stem}-{index}{suffix}"
        if renamed not in reserved:
            return renamed, True
        index += 1


def validate_source_paths(paths: list[Path]) -> ValidationResult:
    existing_files: list[Path] = []
    missing_paths: list[Path] = []
    non_file_paths: list[Path] = []

    for source in paths:
        if not source.exists():
            missing_paths.append(source)
            continue
        if not source.is_file():
            non_file_paths.append(source)
            continue
        existing_files.append(source)

    return ValidationResult(
        existing_files=existing_files,
        missing_paths=missing_paths,
        non_file_paths=non_file_paths,
    )


def source_folder_art(source: Path) -> Path | None:
    for candidate in FOLDER_ART_CANDIDATES:
        path = source.parent / candidate
        if path.exists() and path.is_file():
            return path
    return None


def unique_missing_art_albums(source_paths: list[Path]) -> list[Path]:
    missing_albums: list[Path] = []
    seen: set[Path] = set()
    for source in source_paths:
        if source_folder_art(source) is not None:
            continue
        album_dir = source.parent
        if album_dir in seen:
            continue
        seen.add(album_dir)
        missing_albums.append(album_dir)
    return sorted(missing_albums)


def find_filename_collisions(source_paths: list[Path]) -> list[FilenameCollision]:
    by_name: dict[str, list[Path]] = {}
    for source in source_paths:
        by_name.setdefault(destination_filename(source), []).append(source)

    collisions: list[FilenameCollision] = []
    for filename, sources in sorted(by_name.items()):
        if len(sources) > 1:
            collisions.append(FilenameCollision(filename=filename, sources=sources))
    return collisions


def build_export_actions(source_paths: list[Path], dest_dir: Path) -> list[ExportAction]:
    actions: list[ExportAction] = []
    reserved: set[Path] = set()

    for source in source_paths:
        dest, renamed = unique_dest_path(dest_dir, destination_filename(source), reserved)
        reserved.add(dest)
        actions.append(ExportAction(source=source, dest=dest, renamed=renamed, art_path=source_folder_art(source)))

    return actions


def cleanup_stale_temp_files(dest_dir: Path) -> list[Path]:
    if not dest_dir.exists():
        return []

    removed: list[Path] = []
    seen: set[Path] = set()
    for pattern in TEMP_FILE_PATTERNS:
        for path in dest_dir.glob(pattern):
            if path in seen or not path.is_file():
                continue
            path.unlink(missing_ok=True)
            seen.add(path)
            removed.append(path)
    return sorted(removed)


def ffmpeg_mode_args(mode: str) -> list[str]:
    if mode == "vbr":
        return ["-vbr", "on"]
    if mode == "cvbr":
        return ["-vbr", "constrained"]
    return ["-vbr", "off"]


def analyze_replaygain(source: Path, target_lufs: float) -> ReplayGainResult:
    result = run_captured(
        [
            "ffmpeg",
            "-nostats",
            "-hide_banner",
            "-i",
            str(source),
            "-filter_complex",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ]
    )
    matches_loudness = LOUDNESS_RE.findall(result.stderr)
    matches_peak = PEAK_RE.findall(result.stderr)
    if not matches_loudness or not matches_peak:
        raise PlaylistExportError(f"Could not parse loudness analysis for {source}")

    integrated_lufs = float(matches_loudness[-1])
    peak_dbfs = float(matches_peak[-1])
    gain_db = target_lufs - integrated_lufs
    peak_linear = math.pow(10.0, peak_dbfs / 20.0)

    return ReplayGainResult(gain_db=gain_db, peak_linear=peak_linear)


def picture_block_base64(image_path: Path) -> str:
    image_bytes = image_path.read_bytes()
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    description = b""
    block = b"".join(
        [
            struct.pack(">I", 3),
            struct.pack(">I", len(mime_type)),
            mime_type.encode("utf-8"),
            struct.pack(">I", len(description)),
            description,
            struct.pack(">I", 0),
            struct.pack(">I", 0),
            struct.pack(">I", 0),
            struct.pack(">I", 0),
            struct.pack(">I", len(image_bytes)),
            image_bytes,
        ]
    )
    return base64.b64encode(block).decode("ascii")


def build_ffmetadata_lines(
    replaygain: ReplayGainResult | None,
    art_path: Path | None,
) -> list[str]:
    lines = [";FFMETADATA1"]
    if replaygain is not None:
        lines.extend(
            [
                f"REPLAYGAIN_TRACK_GAIN={replaygain.gain_db:+.2f} dB",
                f"REPLAYGAIN_TRACK_PEAK={replaygain.peak_linear:.6f}",
                "REPLAYGAIN_REFERENCE_LOUDNESS=89.0 dB",
            ]
        )
    if art_path is not None:
        lines.append(f"METADATA_BLOCK_PICTURE={picture_block_base64(art_path)}")
    return lines


def convert_to_temp_opus(source: Path, temp_path: Path, bitrate_kbps: int, mode: str) -> None:
    run_captured(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-map_metadata",
            "0",
            "-vn",
            "-c:a",
            "libopus",
            "-b:a",
            f"{bitrate_kbps}k",
            "-application",
            "audio",
            *ffmpeg_mode_args(mode),
            str(temp_path),
        ]
    )


def finalize_opus(
    temp_audio: Path,
    dest: Path,
    replaygain: ReplayGainResult | None,
    art_path: Path | None,
) -> tuple[bool, bool]:
    if replaygain is None and art_path is None:
        temp_audio.replace(dest)
        return False, False

    with NamedTemporaryFile(prefix="playlist-opus-meta-", suffix=".ffmeta", dir=dest.parent, delete=False) as temp_file:
        metadata_path = Path(temp_file.name)
    metadata_path.write_text("\n".join(build_ffmetadata_lines(replaygain, art_path)) + "\n", encoding="utf-8")

    command = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-i",
        str(temp_audio),
        "-f",
        "ffmetadata",
        "-i",
        str(metadata_path),
        "-map",
        "0:a:0",
        "-map_metadata",
        "1",
        "-c",
        "copy",
    ]
    replaygain_written = replaygain is not None
    artwork_embedded = art_path is not None

    with NamedTemporaryFile(prefix="playlist-opus-final-", suffix=dest.suffix, dir=dest.parent, delete=False) as temp_file:
        final_temp = Path(temp_file.name)

    command.append(str(final_temp))

    try:
        run_captured(command)
        final_temp.replace(dest)
    except subprocess.CalledProcessError as exc:
        final_temp.unlink(missing_ok=True)
        stderr = exc.stderr.strip().splitlines()[-1] if exc.stderr else str(exc)
        raise PlaylistExportError(f"Could not finalize {dest}: {stderr}") from exc
    finally:
        metadata_path.unlink(missing_ok=True)

    return replaygain_written, artwork_embedded


def execute_actions(
    actions: list[ExportAction],
    bitrate_kbps: int,
    mode: str,
    replaygain_target_lufs: float,
    write_replaygain: bool,
    embed_artwork: bool,
    overwrite: bool,
    logger: Logger,
) -> ExecuteResult:
    converted = 0
    skipped_existing = 0
    artwork_embedded = 0
    artwork_missing = 0
    replaygain_written = 0
    replaygain_failed = 0
    failed = 0
    artwork_missing_albums: list[Path] = []
    artwork_missing_seen: set[Path] = set()
    failures: list[str] = []

    for action in actions:
        action.dest.parent.mkdir(parents=True, exist_ok=True)
        if action.dest.exists() and not overwrite:
            skipped_existing += 1
            continue

        replaygain_result: ReplayGainResult | None = None
        if write_replaygain:
            try:
                replaygain_result = analyze_replaygain(action.source, replaygain_target_lufs)
            except Exception as exc:
                replaygain_failed += 1
                logger.emit(f"  REPLAYGAIN FAILED: {action.source}: {exc}")

        if embed_artwork and action.art_path is None:
            album_dir = action.source.parent
            if album_dir not in artwork_missing_seen:
                artwork_missing_seen.add(album_dir)
                artwork_missing_albums.append(album_dir)
            artwork_missing += 1

        with NamedTemporaryFile(prefix="playlist-opus-audio-", suffix=".opus", dir=action.dest.parent, delete=False) as temp_file:
            temp_audio = Path(temp_file.name)

        try:
            convert_to_temp_opus(action.source, temp_audio, bitrate_kbps, mode)
            rg_written, art_written = finalize_opus(
                temp_audio,
                action.dest,
                replaygain=replaygain_result,
                art_path=action.art_path if embed_artwork else None,
            )
            converted += 1
            if rg_written:
                replaygain_written += 1
            if art_written:
                artwork_embedded += 1
        except Exception as exc:
            failed += 1
            failures.append(f"{action.source} -> {action.dest}: {exc}")
            logger.emit(f"  FAILED: {action.source} -> {action.dest}: {exc}", stderr=True)
        finally:
            temp_audio.unlink(missing_ok=True)

    return ExecuteResult(
        converted=converted,
        skipped_existing=skipped_existing,
        artwork_embedded=artwork_embedded,
        artwork_missing=artwork_missing,
        replaygain_written=replaygain_written,
        replaygain_failed=replaygain_failed,
        failed=failed,
        artwork_missing_albums=sorted(artwork_missing_albums),
        failures=failures,
    )


def process_playlist(playlist_path: Path, args: argparse.Namespace, logger: Logger) -> int:
    parsed = parse_playlist(playlist_path, unc_root=Path(args.unc_root).expanduser())
    validation = validate_source_paths(parsed.paths)
    dest_dir = Path(args.output_root).expanduser() / playlist_folder_name(playlist_path)
    cleaned_temp_files: list[Path] = []
    if args.apply:
        dest_dir.mkdir(parents=True, exist_ok=True)
        cleaned_temp_files = cleanup_stale_temp_files(dest_dir)
    actions = build_export_actions(validation.existing_files, dest_dir)
    collisions = find_filename_collisions(validation.existing_files)
    missing_art_albums = unique_missing_art_albums(validation.existing_files) if not args.no_artwork else []
    renamed_count = sum(1 for action in actions if action.renamed)

    logger.emit(f"Playlist: {playlist_path}")
    logger.emit(f"  Destination: {dest_dir}")
    logger.emit(f"  Entries read: {parsed.entries_read}")
    logger.emit(f"  Unique files: {len(parsed.paths)}")
    logger.emit(f"  Existing source files: {len(validation.existing_files)}")
    if validation.missing_paths:
        logger.emit(f"  Missing source files: {len(validation.missing_paths)}")
    if validation.non_file_paths:
        logger.emit(f"  Non-file source paths: {len(validation.non_file_paths)}")
    if parsed.duplicate_entries:
        logger.emit(f"  Duplicate playlist entries skipped: {parsed.duplicate_entries}")
    if renamed_count:
        logger.emit(f"  Filename collisions auto-renamed: {renamed_count}")
    if cleaned_temp_files:
        logger.emit(f"  Removed stale temp files: {len(cleaned_temp_files)}")
    if missing_art_albums:
        logger.emit(f"  Album folders without folder art: {len(missing_art_albums)}")
    for collision in collisions:
        logger.emit(f"  COLLISION: {collision.filename}")
        for source in collision.sources:
            logger.emit(f"    SOURCE: {source}")
    for album_dir in missing_art_albums:
        logger.emit(f"  NO FOLDER ART: {album_dir}")
    for missing in validation.missing_paths:
        logger.emit(f"  MISSING: {missing}")
    for non_file in validation.non_file_paths:
        logger.emit(f"  NOT A FILE: {non_file}")
    for removed in cleaned_temp_files:
        logger.emit(f"  REMOVED STALE TEMP: {removed}")

    if not args.apply:
        logger.emit("  Dry run only. Re-run with --apply to convert files.")
        return 0

    if validation.missing_paths or validation.non_file_paths:
        raise PlaylistExportError("Refusing to convert because some playlist entries are missing or not regular files")

    result = execute_actions(
        actions=actions,
        bitrate_kbps=args.bitrate_kbps,
        mode=args.mode,
        replaygain_target_lufs=args.replaygain_target_lufs,
        write_replaygain=not args.no_replaygain,
        embed_artwork=not args.no_artwork,
        overwrite=args.overwrite,
        logger=logger,
    )
    logger.emit(f"  Converted files: {result.converted}")
    if result.skipped_existing:
        logger.emit(f"  Skipped existing files: {result.skipped_existing}")
    if result.replaygain_written:
        logger.emit(f"  ReplayGain tags written: {result.replaygain_written}")
    if result.replaygain_failed:
        logger.emit(f"  ReplayGain analysis failed: {result.replaygain_failed}")
    if result.artwork_embedded:
        logger.emit(f"  Embedded folder art: {result.artwork_embedded}")
    if result.artwork_missing:
        logger.emit(f"  Files without folder art: {result.artwork_missing}")
    for album_dir in result.artwork_missing_albums:
        logger.emit(f"  NO FOLDER ART: {album_dir}")
    if result.failed:
        logger.emit(f"  Failed exports: {result.failed}", stderr=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    playlists_root = Path(args.playlists_root).expanduser()

    log_handle = None
    if args.log_file:
        log_path = Path(args.log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("w", encoding="utf-8")

    logger = Logger(file_handle=log_handle)
    try:
        playlists = resolve_playlists(playlists_root, args.playlist)
        for playlist_path in playlists:
            process_playlist(playlist_path, args, logger)
    except PlaylistExportError as exc:
        logger.emit(f"ERROR: {exc}", stderr=True)
        return 1
    finally:
        if log_handle is not None:
            log_handle.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
