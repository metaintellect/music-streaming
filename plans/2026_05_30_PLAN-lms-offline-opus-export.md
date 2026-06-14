# PLAN: LMS Playlist to iPhone Offline Opus Export

**Date**: 2026-05-30  
**Objective**: Export selected LMS playlists from the NAS-backed library into compact offline `Opus` files for iPhone use  
**Status**: Draft plan approved for later implementation

## Goal

Build a local export workflow that:

- reads playlist files from `/Volumes/xnas/playlists`
- resolves the referenced source music files
- transcodes selected tracks from `FLAC` to `Opus`
- writes the results to a Mac-local export folder
- leaves the output ready to drag into `foobar2000` on iPhone through Finder

This is for `offline car use`, so file size matters more than lossless fidelity.

## Recommendation

The general idea is reasonable, but the target folder should be a little more structured than a single flat `~/Music/opus`.

Recommended output root:

```text
~/Music/LMS Offline Exports/
```

Recommended layout:

```text
~/Music/LMS Offline Exports/
  playlists/
    <playlist-name>/
      <artist>/<album>/<track>.opus
      playlist.m3u8
  logs/
  manifests/
```

Why this is better:

- keeps playlist exports separate
- avoids one huge undifferentiated Opus dump
- makes Finder-to-iPhone copying simpler
- allows later re-export without guessing what came from where

## Scope For V1

Implement only playlist export first.

Included:

- pick one playlist file as input
- parse its referenced tracks
- resolve file paths
- transcode to `Opus`
- preserve tags where practical
- optionally create a playlist file for the export set

Not included in V1:

- albums as first-class export input
- automatic iPhone sync
- UI
- incremental smart re-sync
- AAC/ALAC dual export
- remote downloads through LMS clients

## Expected Inputs

Primary input folder:

```text
/Volumes/xnas/playlists
```

Expected playlist formats to inspect first:

- `.m3u`
- `.m3u8`
- maybe `.pls`

Questions implementation must answer during discovery:

1. Are playlist entries absolute or relative?
2. Do playlist entries point directly to NAS paths?
3. Are path separators/macOS mount paths consistent?
4. Are playlists using the same library root as LMS?

## Source Library Assumption

Working assumption for first implementation:

- playlists ultimately reference files on the NAS music library
- source files are mostly `FLAC`
- the Mac can read them through the mounted NAS volume

If playlist paths are Windows-style or LMS-style, the exporter will need a normalization layer before transcoding.

## Output Format Decision

Recommended default:

- `Opus`
- start at `128 kbps`
- keep this configurable

Why:

- better size/quality tradeoff than `AAC` for this use
- ideal for car listening
- `foobar2000` on iPhone supports `Opus`

Possible later presets:

- `96 kbps` for smallest portable exports
- `128 kbps` as default
- `160 kbps` if you want extra headroom

## Tooling Direction

Use a scriptable local pipeline on the Mac.

Likely stack:

- `Python` orchestration
- `ffmpeg` for transcoding
- optional `ffprobe` for metadata checks

Why:

- easier to inspect playlist path issues
- simpler to iterate than shell-only logic
- enough control for manifests, logs, and retries

## Proposed Workflow

### Phase 1: Discovery

Inspect real playlist files under:

```text
/Volumes/xnas/playlists
```

Determine:

- actual format
- path style
- whether duplicate tracks occur
- whether playlists reference missing files

### Phase 2: Path Resolution

Build a resolver that converts playlist entries into valid local file paths on macOS.

Possible cases:

- already valid `/Volumes/xnas/...`
- Windows-style `\\server\share\...`
- mixed slash/backslash paths
- paths relative to playlist location

### Phase 3: Export Engine

For one selected playlist:

- create export folder
- transcode each track to `Opus`
- preserve metadata if possible
- keep artist/album subfolders for readability
- skip or log missing files

### Phase 4: Export Manifest

Write sidecar files such as:

- `playlist.m3u8`
- `export-manifest.json`
- `export.log`

Manifest should record:

- source playlist
- source path
- output path
- codec settings
- export date

### Phase 5: iPhone Transfer

Manual first:

- connect iPhone to Mac
- open Finder
- select iPhone
- `Files` tab
- drag export folder into `foobar2000`

No sync automation in V1.

## Key Design Choices

### 1. Export by playlist snapshot, not global cache

First version should export a self-contained folder per playlist.

Reason:

- simpler mental model
- easy to copy/delete
- easier to test on iPhone

### 2. Preserve folder structure

Do not flatten all tracks into one directory.

Reason:

- avoids name collisions
- keeps albums readable
- helps if you later export album-based sets too

### 3. Manual iPhone transfer first

Do not automate Finder or foobar sync initially.

Reason:

- lower risk
- easier to debug
- enough for your actual use

## Risks

1. Playlist paths may not match current mounted macOS paths.
2. Some playlists may include non-FLAC or missing files.
3. Artwork/tag preservation may vary by source file quality.
4. Duplicate tracks across playlists may waste space until dedupe is added.

## Success Criteria

V1 is successful if:

1. one real playlist can be exported end-to-end
2. output files are valid `Opus`
3. tags are good enough to browse on iPhone
4. exported folder can be copied into `foobar2000`
5. playback works offline in the car

## Likely Next Step After V1

After playlist export works, extend input types to:

- single album
- multiple playlists
- explicit track list

Then optionally add:

- deduplicated shared export cache
- `AAC` export preset
- a small macOS UI
