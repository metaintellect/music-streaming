#!/usr/bin/env python3
"""
Move CD_RIP classical albums to classical/cd-rip/ with composer-first naming.

Uses esoteric-style format: Composer - Work (Conductor/Performer)
- No label suffix (per user preference)
- WAV preserved (no conversion)
- CD1→CD01 normalized (run fix-multidisc.sh first if needed)

Usage:
    python move-cd-rip-classical.py --dry-run    # Show what would be done
    python move-cd-rip-classical.py               # Execute moves

Run on NAS (or with NAS mounted):
    ssh root@192.168.100.83 "cd /root && python3 move-cd-rip-classical.py --dry-run"
    # Copy script + cd-rip-classical-mapping.json to /root/ on NAS first
"""

import argparse
import json
import re
import shutil
from pathlib import Path

# Paths (NAS - default)
CD_RIP_BASE = Path("/mnt/nas/CD_RIP")
CLASSICAL_BASE = Path("/mnt/nas/music/classical")
TARGET_SUBFOLDER = "cd-rip"

SCRIPT_DIR = Path(__file__).resolve().parent
MAPPING_FILE = SCRIPT_DIR / "cd-rip-classical-mapping.json"


def load_mapping():
    """Load mapping config."""
    with open(MAPPING_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data["mappings"]


def find_album_folder(artist: str, album_from_config: str, cd_rip_base: Path) -> Path | None:
    """Find album folder. Exact match first; fallback to prefix match for encoding/truncation."""
    artist_path = cd_rip_base / artist
    if not artist_path.exists():
        return None
    exact = artist_path / album_from_config
    if exact.is_dir():
        return exact
    # Prefix match: folder starts with config or config starts with folder (truncation)
    for item in artist_path.iterdir():
        if not item.is_dir():
            continue
        if item.name == album_from_config:
            return item
        if item.name.startswith(album_from_config[:50]) or album_from_config.startswith(item.name[:50]):
            return item
    return None


def normalize_disc_folders(album_path: Path, dry_run: bool) -> list[str]:
    """CD1→CD01 if needed. Returns list of renames done."""
    renames = []
    for item in album_path.iterdir():
        if not item.is_dir():
            continue
        m = re.match(r"^CD([1-9])$", item.name, re.I)
        if m:
            new_name = f"CD0{m.group(1)}"
            new_path = item.parent / new_name
            if dry_run:
                renames.append(f"  Would rename: {item.name} → {new_name}")
            else:
                item.rename(new_path)
                renames.append(f"  Renamed: {item.name} → {new_name}")
    return renames


def main():
    parser = argparse.ArgumentParser(description="Move CD_RIP classical to classical/cd-rip/")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without executing")
    parser.add_argument("--cd-rip", type=str, help="Override CD_RIP path (e.g. /Volumes/xnas/CD_RIP)")
    parser.add_argument("--classical", type=str, help="Override classical path")
    args = parser.parse_args()

    cd_rip = Path(args.cd_rip) if args.cd_rip else CD_RIP_BASE
    classical = Path(args.classical) if args.classical else CLASSICAL_BASE

    if not cd_rip.exists():
        print(f"ERROR: CD_RIP not found: {cd_rip}")
        print("Run on NAS or use --cd-rip /path/to/CD_RIP")
        return 1

    mappings = load_mapping()
    target_base = classical / TARGET_SUBFOLDER

    print("=" * 60)
    print("CD_RIP Classical → classical/cd-rip/")
    print("=" * 60)
    print(f"Source: {cd_rip}")
    print(f"Target: {target_base}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print()

    moved = 0
    skipped = 0
    not_found = []

    for m in mappings:
        artist = m["artist"]
        album = m["album"]
        target_name = m["target"]

        src = find_album_folder(artist, album, cd_rip)
        if not src:
            not_found.append(f"  {artist} / {album}")
            skipped += 1
            continue

        dst = target_base / target_name
        if dst.exists():
            print(f"SKIP (target exists): {target_name}")
            skipped += 1
            continue

        if args.dry_run:
            print(f"Would move:")
            print(f"  From: {src}")
            print(f"  To:   {dst}")
            disc_renames = normalize_disc_folders(src, dry_run=True)
            for r in disc_renames:
                print(r)
        else:
            target_base.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"MOVED: {target_name}")
            normalize_disc_folders(dst, dry_run=False)
        moved += 1

    print()
    print("=" * 60)
    print(f"Summary: {moved} moved, {skipped} skipped")
    if not_found:
        print()
        print("Not found (check album names in mapping):")
        for n in not_found:
            print(n)
    if args.dry_run and moved:
        print()
        print("Run without --dry-run to execute.")

    return 0


if __name__ == "__main__":
    exit(main())
