#!/bin/bash
#
# Promote one album from CD_RIP staging into the permanent music library.
# Supports:
# - single-image CUE rips that need splitting
# - already-split track files that only need renaming/tag-based normalization
#
# Destination layout:
#   /Volumes/xnas/music/<dest-root>/<Artist>/<Album (Year)>/
#
# Example:
#   ./scripts/promote-cd-rip-album.sh \
#     --source 'Agent Steel - Skeptics Apocalypse (1985)' \
#     --dest-root metal
#
#   ./scripts/promote-cd-rip-album.sh \
#     --source 'Agent Steel/1986 - Mad Locust Rising (Vinyl Rip 16-44)' \
#     --dest-root metal \
#     --artist 'Agent Steel' \
#     --album 'Mad Locust Rising' \
#     --year 1986

set -euo pipefail

NAS_ROOT="${NAS_ROOT:-/Volumes/xnas}"
CD_RIP_ROOT="$NAS_ROOT/CD_RIP"
MUSIC_ROOT="$NAS_ROOT/music"

DRY_RUN=0
SOURCE_ARG=""
DEST_ROOT=""
ARTIST=""
ALBUM=""
YEAR=""
KEEP_SOURCE=0

usage() {
    cat <<'EOF'
Usage:
  promote-cd-rip-album.sh --source <path> --dest-root <music-subdir> [options]

Required:
  --source <path>      Source album folder. Relative paths resolve under CD_RIP.
  --dest-root <path>   Destination root under music/, e.g. metal, exyu, classical/cd-rip

Optional:
  --artist <name>      Override inferred artist
  --album <title>      Override inferred album title
  --year <yyyy>        Override inferred album year
  --dry-run            Show planned actions only
  --keep-source        Do not delete the source CD_RIP folder after success
  --help               Show this message

Notes:
  - Final destination is always: music/<dest-root>/<Artist>/<Album (Year)>/
  - Track files are renamed to: NN Artist - Title.ext
  - CD_RIP is treated as staging only and is cleaned after a successful move
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)
            SOURCE_ARG="${2:-}"
            shift 2
            ;;
        --dest-root)
            DEST_ROOT="${2:-}"
            shift 2
            ;;
        --artist)
            ARTIST="${2:-}"
            shift 2
            ;;
        --album)
            ALBUM="${2:-}"
            shift 2
            ;;
        --year)
            YEAR="${2:-}"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --keep-source)
            KEEP_SOURCE=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "$SOURCE_ARG" || -z "$DEST_ROOT" ]]; then
    usage >&2
    exit 1
fi

run_cmd() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '[dry-run] '
        printf '%q ' "$@"
        printf '\n'
    else
        "$@"
    fi
}

strip_prefix() {
    local value="$1"
    value="${value#${value%%[![:space:]]*}}"
    value="${value%${value##*[![:space:]]}}"
    printf '%s' "$value"
}

sanitize_filename_part() {
    local value="$1"
    value="${value//\//_}"
    value="${value//:/ -}"
    value="${value//$'\r'/}"
    printf '%s' "$value"
}

first_existing() {
    local candidate
    for candidate in "$@"; do
        if [[ -e "$candidate" ]]; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    return 1
}

tag_value() {
    local file="$1"
    local tag="$2"
    local line
    line="$(metaflac --show-tag="$tag" "$file" 2>/dev/null | head -n 1 || true)"
    printf '%s' "${line#*=}"
}

cue_value() {
    local cue_file="$1"
    local key="$2"
    awk -F'"' -v key="$key" '$1 ~ ("^" key " ") { print $2; exit }' "$cue_file" | tr -d '\r'
}

infer_year_from_name() {
    local name="$1"
    if [[ "$name" =~ \(([0-9]{4})\) ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
        return 0
    fi
    if [[ "$name" =~ ^([0-9]{4})[[:space:]]*-[[:space:]]* ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

infer_album_from_name() {
    local name="$1"
    local artist_name="$2"
    local result="$name"

    if [[ -n "$artist_name" && "$result" == "$artist_name - "* ]]; then
        result="${result#"$artist_name - "}"
    fi
    if [[ "$result" =~ ^[0-9]{4}[[:space:]]*-[[:space:]]*(.*)$ ]]; then
        result="${BASH_REMATCH[1]}"
    fi
    if [[ "$result" =~ ^(.*)[[:space:]]+\([0-9]{4}\)$ ]]; then
        result="${BASH_REMATCH[1]}"
    fi
    result="$(printf '%s' "$result" | sed -E 's/[[:space:]]+\((Vinyl Rip|CD Rip|Rip)[^)]*\)$//I')"
    printf '%s' "$(strip_prefix "$result")"
}

infer_artist_from_name() {
    local name="$1"
    if [[ "$name" =~ ^(.+)[[:space:]]-[[:space:]].+\([0-9]{4}\)$ ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

resolve_source() {
    if [[ "$SOURCE_ARG" = /* ]]; then
        printf '%s' "$SOURCE_ARG"
    else
        printf '%s/%s' "$CD_RIP_ROOT" "$SOURCE_ARG"
    fi
}

SOURCE_DIR="$(resolve_source)"

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Source folder not found: $SOURCE_DIR" >&2
    exit 1
fi

if [[ ! -d "$MUSIC_ROOT" ]]; then
    echo "Music root not found: $MUSIC_ROOT" >&2
    exit 1
fi

SOURCE_BASENAME="$(basename "$SOURCE_DIR")"
SOURCE_PARENT_BASENAME="$(basename "$(dirname "$SOURCE_DIR")")"

mapfile -t CUE_FILES < <(find "$SOURCE_DIR" -maxdepth 1 -type f -iname '*.cue' | sort)
mapfile -t AUDIO_FILES < <(find "$SOURCE_DIR" -maxdepth 1 -type f \( -iname '*.flac' -o -iname '*.wav' -o -iname '*.ape' -o -iname '*.wv' \) | sort)
mapfile -t SPLIT_TRACKS < <(find "$SOURCE_DIR" -maxdepth 1 -type f \( -iname '*.flac' -o -iname '*.wav' \) | sort | grep -E '/[0-9][0-9][ _-]')

WORK_DIR="$SOURCE_DIR"
TEMP_DIR=""
SPLIT_FROM_CUE=0

if [[ -z "$ARTIST" ]]; then
    if [[ "$SOURCE_DIR" == "$CD_RIP_ROOT"/*/* ]]; then
        ARTIST="$SOURCE_PARENT_BASENAME"
    fi
    if [[ -z "$ARTIST" ]] && [[ ${#CUE_FILES[@]} -gt 0 ]]; then
        ARTIST="$(cue_value "${CUE_FILES[0]}" 'PERFORMER')"
    fi
    if [[ -z "$ARTIST" ]] && [[ ${#AUDIO_FILES[@]} -gt 0 ]]; then
        ARTIST="$(tag_value "${AUDIO_FILES[0]}" 'ARTIST')"
    fi
    if [[ -z "$ARTIST" ]]; then
        ARTIST="$(infer_artist_from_name "$SOURCE_BASENAME" || true)"
    fi
fi

if [[ -z "$ALBUM" ]] && [[ ${#CUE_FILES[@]} -gt 0 ]]; then
    ALBUM="$(cue_value "${CUE_FILES[0]}" 'TITLE')"
fi
if [[ -z "$ALBUM" ]] && [[ ${#AUDIO_FILES[@]} -gt 0 ]]; then
    ALBUM="$(tag_value "${AUDIO_FILES[0]}" 'ALBUM')"
fi
if [[ -z "$ALBUM" ]]; then
    ALBUM="$(infer_album_from_name "$SOURCE_BASENAME" "$ARTIST")"
fi

if [[ -z "$YEAR" ]] && [[ ${#CUE_FILES[@]} -gt 0 ]]; then
    YEAR="$(awk '/^REM DATE / { print $3; exit }' "${CUE_FILES[0]}" | tr -d '\r')"
fi
if [[ -z "$YEAR" ]] && [[ ${#AUDIO_FILES[@]} -gt 0 ]]; then
    YEAR="$(tag_value "${AUDIO_FILES[0]}" 'DATE')"
fi
if [[ -z "$YEAR" ]]; then
    YEAR="$(infer_year_from_name "$SOURCE_BASENAME" || true)"
fi

if [[ -z "$ARTIST" || -z "$ALBUM" || -z "$YEAR" ]]; then
    echo "Could not infer enough metadata." >&2
    echo "artist=$ARTIST" >&2
    echo "album=$ALBUM" >&2
    echo "year=$YEAR" >&2
    echo "Pass explicit --artist/--album/--year." >&2
    exit 1
fi

DEST_DIR="$MUSIC_ROOT/$DEST_ROOT/$ARTIST/$ALBUM ($YEAR)"

echo "Source:      $SOURCE_DIR"
echo "Destination: $DEST_DIR"
echo "Artist:      $ARTIST"
echo "Album:       $ALBUM"
echo "Year:        $YEAR"

if [[ -e "$DEST_DIR" ]]; then
    echo "Destination already exists: $DEST_DIR" >&2
    exit 1
fi

cleanup() {
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

if [[ ${#CUE_FILES[@]} -gt 0 && ${#SPLIT_TRACKS[@]} -eq 0 ]]; then
    if [[ ${#CUE_FILES[@]} -ne 1 ]]; then
        echo "Expected exactly one CUE file, found ${#CUE_FILES[@]}" >&2
        exit 1
    fi

    CUE_FILE="${CUE_FILES[0]}"
    AUDIO_LINE="$(grep -i '^FILE ' "$CUE_FILE" | head -n 1 || true)"
    if [[ -z "$AUDIO_LINE" ]]; then
        echo "Could not find FILE line in $CUE_FILE" >&2
        exit 1
    fi

    IMAGE_NAME="$(printf '%s\n' "$AUDIO_LINE" | awk -F'"' '/^FILE / { print $2; exit }')"
    if [[ -z "$IMAGE_NAME" ]]; then
        IMAGE_NAME="$(printf '%s\n' "$AUDIO_LINE" | awk -F"'" '/^FILE / { print $2; exit }')"
    fi
    if [[ -z "$IMAGE_NAME" ]]; then
        IMAGE_NAME="$(printf '%s\n' "$AUDIO_LINE" | awk '{print $2}' | tr -d '"'\''\r')"
    fi
    IMAGE_NAME="$(printf '%s' "$IMAGE_NAME" | tr -d '\r')"

    IMAGE_PATH="$SOURCE_DIR/$IMAGE_NAME"
    if [[ ! -f "$IMAGE_PATH" ]]; then
        echo "Referenced image file not found: $IMAGE_PATH" >&2
        exit 1
    fi

    TEMP_DIR="$(mktemp -d /tmp/cd-rip-promote.XXXXXX)"
    echo "Splitting image via CUE into $TEMP_DIR"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] cuebreakpoints '$CUE_FILE' | shnsplit -d '$TEMP_DIR' -o flac '$IMAGE_PATH'"
        echo "[dry-run] cuetag.sh '$CUE_FILE' '$TEMP_DIR/*.flac'"
    else
        cuebreakpoints "$CUE_FILE" | shnsplit -d "$TEMP_DIR" -o flac "$IMAGE_PATH"
        cuetag.sh "$CUE_FILE" "$TEMP_DIR"/*.flac
    fi
    WORK_DIR="$TEMP_DIR"
    SPLIT_FROM_CUE=1
fi

run_cmd mkdir -p "$DEST_DIR"

mapfile -t TRACK_FILES < <(find "$WORK_DIR" -maxdepth 1 -type f \( -iname '*.flac' -o -iname '*.wav' \) | sort)

if [[ ${#TRACK_FILES[@]} -eq 0 ]]; then
    if [[ "$DRY_RUN" -eq 1 && -n "$TEMP_DIR" ]]; then
        echo "[dry-run] track files will be created from the CUE split step"
        echo "[dry-run] extras and source cleanup would be processed after split"
        exit 0
    fi
    echo "No track files found in $WORK_DIR" >&2
    exit 1
fi

for track_file in "${TRACK_FILES[@]}"; do
    ext="${track_file##*.}"
    if [[ "$WORK_DIR" == "$TEMP_DIR" ]]; then
        track_number="$(tag_value "$track_file" 'TRACKNUMBER')"
        title="$(tag_value "$track_file" 'TITLE')"
    else
        track_number="$(tag_value "$track_file" 'TRACKNUMBER')"
        title="$(tag_value "$track_file" 'TITLE')"
        if [[ -z "$track_number" ]]; then
            base="$(basename "$track_file")"
            if [[ "$base" =~ ^([0-9]{2})([[:space:]_-]) ]]; then
                track_number="${BASH_REMATCH[1]}"
            fi
        fi
        if [[ -z "$title" ]]; then
            title="$(basename "$track_file")"
            title="${title%.*}"
            title="$(printf '%s' "$title" | sed -E 's/^[0-9]{2}[ _-]*//')"
            title="$(printf '%s' "$title" | sed -E "s/^${ARTIST}[ _-]+//I")"
        fi
    fi

    if [[ -z "$track_number" || -z "$title" ]]; then
        echo "Could not infer track number/title for $track_file" >&2
        exit 1
    fi

    safe_title="$(sanitize_filename_part "$title")"
    dest_track="$DEST_DIR/$track_number $ARTIST - $safe_title.$ext"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] promote track: $track_file -> $dest_track"
    else
        cp "$track_file" "$dest_track"
        if [[ "$ext" == "flac" ]]; then
            metaflac \
                --remove-tag=ALBUM \
                --remove-tag=ALBUMARTIST \
                --remove-tag=ARTIST \
                --remove-tag=TITLE \
                --remove-tag=TRACKNUMBER \
                --remove-tag=DATE \
                --set-tag="TRACKNUMBER=$track_number" \
                --set-tag="TITLE=$title" \
                --set-tag="ARTIST=$ARTIST" \
                --set-tag="ALBUM=$ALBUM" \
                --set-tag="ALBUMARTIST=$ARTIST" \
                --set-tag="DATE=$YEAR" \
                "$dest_track"
        fi
    fi
done

COVER_SOURCE="$(first_existing \
    "$SOURCE_DIR/Folder.jpg" \
    "$SOURCE_DIR/folder.jpg" \
    "$SOURCE_DIR/front.jpg" \
    "$SOURCE_DIR/Front.jpg" \
    "$SOURCE_DIR/cover.jpg" \
    "$SOURCE_DIR/Cover.jpg" || true)"

if [[ -n "$COVER_SOURCE" ]]; then
    run_cmd cp "$COVER_SOURCE" "$DEST_DIR/Folder.jpg"
fi

while IFS= read -r extra_path; do
    extra_name="$(basename "$extra_path")"
    if [[ "$extra_name" == "Folder.jpg" ]]; then
        continue
    fi
    if [[ "$SPLIT_FROM_CUE" -eq 1 && "$extra_name" == *.cue ]]; then
        continue
    fi
    if [[ -d "$extra_path" ]]; then
        run_cmd cp -R "$extra_path" "$DEST_DIR/"
    else
        run_cmd cp "$extra_path" "$DEST_DIR/"
    fi
done < <(find "$SOURCE_DIR" -maxdepth 1 \( -type f \( -iname '*.cue' -o -iname '*.log' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.pdf' \) -o -type d \( -iname 'scans*' -o -iname 'artwork*' -o -iname 'booklet*' \) \) | sort)

if [[ "$KEEP_SOURCE" -eq 0 ]]; then
    run_cmd rm -rf "$SOURCE_DIR"
else
    echo "Keeping source folder: $SOURCE_DIR"
fi

echo "Promotion complete."
