# CD_RIP Promotion Workflow

`CD_RIP` is staging only.

Rule:
- clean and normalize albums in `CD_RIP`
- then move them into the correct permanent folder under `music/`
- do not keep finished albums in `CD_RIP`

## Script

Use [scripts/promote-cd-rip-album.sh](/Users/x/src/music-streaming/scripts/promote-cd-rip-album.sh).

It handles:
- splitting a single-image CUE + FLAC/WAV/APE/WV rip into tracks
- renaming tracks to the live library pattern: `NN Artist - Title.ext`
- setting basic FLAC tags: `TRACKNUMBER`, `TITLE`, `ARTIST`, `ALBUM`, `ALBUMARTIST`, `DATE`
- copying common extras like `cue`, `log`, `Folder.jpg`, and `scans*`
- removing the source folder from `CD_RIP` after success

## Usage

Metal album:

```bash
./scripts/promote-cd-rip-album.sh \
  --source 'Agent Steel - Skeptics Apocalypse (1985)' \
  --dest-root metal
```

Album already inside an artist folder in `CD_RIP`:

```bash
./scripts/promote-cd-rip-album.sh \
  --source 'Agent Steel/1986 - Mad Locust Rising (Vinyl Rip 16-44)' \
  --dest-root metal \
  --artist 'Agent Steel' \
  --album 'Mad Locust Rising' \
  --year 1986
```

Different target tree:

```bash
./scripts/promote-cd-rip-album.sh \
  --source 'Some Artist/Some Album (1994)' \
  --dest-root 'classical/cd-rip'
```

Preview only:

```bash
./scripts/promote-cd-rip-album.sh \
  --source 'Some Artist/Some Album (1994)' \
  --dest-root jazz \
  --dry-run
```

## Notes

- `--dest-root` is the path under `music/` before the artist folder.
- If artist, album, or year cannot be inferred cleanly, pass them explicitly.
- If you want to keep the original staging folder temporarily, use `--keep-source`.
