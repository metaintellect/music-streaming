# PLAN: Music Library Organization & Consistency

**Date**: 2026-01-17
**Objective**: Standardize music library folder structure across all collections and automate cleanup tasks
**Status**: ✅ ALL PHASES COMPLETE - Library fully standardized + reorganized by genre

## Context

**Starting state:**
- 375 albums in Roon (mixed genres, inconsistent naming)
- Metal albums in `/CD_RIP/` with mixed naming patterns
- Exyu albums in old format: `Artist - Year Album/tracks`
- Multi-disc albums inconsistently named (CD1, CD2, ", Disc 1", etc.)
- macOS ._ files scattered throughout

**Current state (after completion):**
- **Metal:** 23 artists, 64 albums in `/music/metal/`
- **Exyu:** 241 albums in `/music/exyu/`
- **Classical:** Available but not yet imported to Roon
- **Jazz:** To be organized when ripping begins
- **CD_RIP:** Empty staging area for new rips
- **All albums:** Consistent `Artist/Album (Year)/` format
- **Multi-disc:** All use `/CD01/`, `/CD02/` subfolders with zero-padding

### Issues Discovered

1. **Multi-disc folder naming inconsistency:**
   - New rips: `CD1`, `CD2`, `CD10` (no zero-padding)
   - Old albums: Some have `Disc 1` in album name instead of separate folders
   - dbpoweramp can't do conditional zero-padding in naming string

2. **macOS AppleDouble pollution:**
   - `._*` files scattered throughout NAS SMB shares
   - Created automatically by macOS on non-HFS+ filesystems

3. **Exyu collection uses old naming convention:**
   - Format: `Artist - Year Album/` (flat structure)
   - Should match new standard: `Artist/Album (Year)/`

4. **Roon tagging requirements:**
   - Need bulk genre tagging: `metal`, `exyu`, `jazz`, `classical`
   - Favorites (heart) + single tag works as AND
   - Multiple tags work as OR (acceptable for user's workflow)

## Completed Work

### ✅ Phase 1: Multi-Disc Standardization Script (COMPLETED)
- Created `scripts/fix-multidisc.sh`
- Successfully renames `CD1`-`CD9` → `CD01`-`CD09` (zero-padded)
- Deployed to RPi: `/root/fix-multidisc.sh`
- Tested and working on Metallica albums (Hardwired, Garage Inc)

### ✅ Phase 2: macOS Junk Cleanup (COMPLETED)
- Integrated into `fix-multidisc.sh` with `--clean-apple-files` flag
- Deleted 404 `._*` files from CD_RIP
- Exyu-cdrip has 3,548 `._*` files (deferred - needs investigation)

### ✅ Phase 3: Fix Old Multi-Disc Albums (COMPLETED)
Fixed 3 albums with ", Disc X" pattern:
1. **Fates Warning/Darkness in a Different Light (2013)**
   - Restructured to: base folder with CD01/ and CD02/ subfolders
2. **Fates Warning/Live Over Europe (2018)**
   - Created base folder with CD01/ and CD02/ subfolders
3. **Anthrax/State Of Euphoria (2018)**
   - Renamed to remove ", Disc 1" (single disc, waiting for more rips)
4. **Fates Warning/No Exit [Special Edition] (1988)**
   - Renamed to remove ", Disc 1" (partial rip)

**Result:** Zero folders with ", Disc X" pattern remain in CD_RIP

### ✅ Phase 4: Exyu Collection Restructure (COMPLETED)
Successfully restructured **241 exyu albums** using `scripts/restructure-exyu.sh`:
- **80 top-level albums** converted from flat `Artist - Year Album/` format
- **161 nested albums** renamed to remove redundant artist prefix
- Stripped disc count suffixes: `(2CD)`, `(Single)`, `(3CD)`
- All albums now follow: `Artist/Album (Year)/` format
- Examples verified:
  - `Azra/Filigranski Plocnici (1995)`
  - `Cubi/Moj Ce-De (1995)` (Single removed)
  - `Leb I Sol/Anthology (1995)` (2CD removed)
- Roon rescan required (user confirmed OK with losing stats)

### ✅ Phase 5: Genre-Based Reorganization (COMPLETED)
Reorganized permanent collection into genre-specific folders:

**Final Structure:**
```
/mnt/nas/CD_RIP/              → Empty staging area (rip here first)
/mnt/nas/music/metal/         → 23 metal artists (64 albums)
/mnt/nas/music/exyu/          → 241 exyu albums (renamed from exyu-cdrip)
/mnt/nas/music/Basil Poledouris → Conan soundtrack (non-metal)
/mnt/nas/music/Miyako         → Metal on piano
/mnt/nas/music/classical/     → (future)
/mnt/nas/music/jazz/          → (future)
```

**Moved from CD_RIP → music/metal/:**
- Accept, Annihilator, Anthrax, Arch-Matheos, Bolt Thrower, Coroner, Death Angel, Fates Warning, Heathen, Megadeth, Metallica, Overkill, Pantera, Ray Alder, Sabbat, Sanctuary, Sepultura, Slayer, Sodom, Testament, Time Decay, Venom, Vicious Rumors

**Benefits:**
- CD_RIP is staging only - not watched by Roon
- Genre folders enable easy bulk tagging by location
- Clean separation: temporary (CD_RIP) vs. permanent (music/*)
- Scalable for future genres (jazz, classical, etc.)

## Scripts Created

### fix-multidisc.sh
Location: `/root/fix-multidisc.sh` on RPi, `scripts/fix-multidisc.sh` locally

**Purpose:** Zero-pad multi-disc folders and clean AppleDouble files

**Usage:**
```bash
# Dry run
ssh root@192.168.100.83 "/root/fix-multidisc.sh --dry-run"

# Execute
ssh root@192.168.100.83 "/root/fix-multidisc.sh"

# With ._ file cleanup
ssh root@192.168.100.83 "/root/fix-multidisc.sh --clean-apple-files"
```

**What it does:**
- Renames CD1-CD9 → CD01-CD09 (zero-padded)
- Leaves CD10+ unchanged
- Optionally deletes ._ files with flag
- Safe: checks for conflicts before moving

### restructure-exyu.sh
Location: `/root/restructure-exyu.sh` on RPi, `scripts/restructure-exyu.sh` locally

**Purpose:** Restructure album folders from old to new naming format

**Usage:**
```bash
# Dry run
ssh root@192.168.100.83 "/root/restructure-exyu.sh --dry-run"

# Execute
ssh root@192.168.100.83 "/root/restructure-exyu.sh"
```

**What it does:**
- Parses `Artist - Year Album` → `Artist/Album (Year)/`
- Strips disc count suffixes: (2CD), (Single), (3CD)
- Removes redundant artist name from nested folders
- Processes both top-level and nested albums
- Safe: checks for conflicts, skips if target exists

## Verification

After Phase 1-2 (script):
- All multi-disc folders follow `CD01`, `CD02` format
- No `._*` files in music directories
- Roon rescans and maintains album grouping

After Phase 3 (old multi-disc fix):
- Albums properly separated into disc folders
- Roon correctly identifies multi-disc sets

After Phase 4 (exyu restructure - if done):
- All exyu albums match `Artist/Album (Year)` format
- Roon rescan successful
- OK to lose play stats (user confirmed)

## Open Questions & Decisions Made

1. ~~Should we run cleanup script manually after each rip, or automate?~~
   - **Decision:** Manual execution after each multi-disc rip session
   - User can run: `ssh root@192.168.100.83 "/root/fix-multidisc.sh"`

2. ~~What's the threshold for fixing old multi-disc albums?~~
   - **Decision:** Fix all albums with ", Disc X" pattern regardless of disc count
   - Completed: All CD_RIP albums now follow standard format

3. Classical tagging strategy TBD once collection is imported
   - User will experiment first to determine natural categorization
   - Possible dimensions: composer, period, form, instrument, performer

4. Exyu ._ file cleanup (3,548 files)
   - Deferred until after restructure
   - Most ripped from Windows, so ._ files from recent macOS activity only

## Ongoing Workflow

### CD Ripping & Organization
1. **Rip new CDs** to `/mnt/nas/CD_RIP/Artist/Album (Year)/`
   - dbpoweramp naming: `[Artist]\[Album] ([year])[][IFMULTI]\CD[disc][]\[track] [artist] - [title][]`
   - Multi-disc albums automatically create CD1, CD2, etc.

2. **Post-rip cleanup** (optional, for multi-disc only):
   ```bash
   ssh root@192.168.100.83 "/root/fix-multidisc.sh"
   ```
   - Renames CD1-CD9 → CD01-CD09
   - Optionally cleans ._ files with `--clean-apple-files` flag

3. **Move to permanent location:**
   - Metal → `/mnt/nas/music/metal/`
   - Exyu → `/mnt/nas/music/exyu/`
   - Jazz → `/mnt/nas/music/jazz/` (when started)
   - Classical → `/mnt/nas/music/classical/` (when started)

4. **Roon auto-detects** new albums in watched folders

### Roon Configuration
**Watched folders:**
- `/mnt/nas/music/metal/`
- `/mnt/nas/music/exyu/`
- Add genre folders as created

**Not watched:**
- `/mnt/nas/CD_RIP/` (staging only)

### Tagging Strategy in Roon
- ❤️ **Heart (Favorites)** = essential albums across all genres
- **Custom tags** = `metal`, `exyu`, `jazz`, `classical`, etc.
- **Filtering** = Favorites + single tag works as AND
- **Multiple tags** = OR behavior (acceptable for broader searches)
- Genre tags can be applied by folder location using future Python script

## Notes

- User prefers Favorites (heart) + genre tags workflow
- Roon's multi-tag filtering uses OR logic (acceptable for user's use case)
- All album folders follow consistent `Artist/Album (Year)/` format
- Multi-disc albums use `/CD01/`, `/CD02/` subfolders
- No disc count suffixes in folder names (e.g., no "(2CD)", "(Single)")
