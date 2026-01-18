#!/bin/bash
# Restructure exyu collection to Artist/Album (Year) format
# Usage: ./restructure-exyu.sh [--dry-run]

set -euo pipefail

# Configuration
BASE_PATH="/mnt/nas/music/exyu-cdrip"
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run]"
            exit 1
            ;;
    esac
done

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}DRY RUN MODE - No changes will be made${NC}"
    echo ""
fi

# Check if base path exists
if [[ ! -d "$BASE_PATH" ]]; then
    echo -e "${RED}Error: Base path does not exist: $BASE_PATH${NC}"
    exit 1
fi

echo -e "${GREEN}=== Exyu Collection Restructure Script ===${NC}"
echo "Base path: $BASE_PATH"
echo ""

# Function to parse folder name
parse_folder_name() {
    local folder_name="$1"

    # Match pattern: "Artist - YYYY Album Title (XCD/Single)"
    # Extract year (4 digits)
    if [[ "$folder_name" =~ (.+)[[:space:]]-[[:space:]]([0-9]{4})[[:space:]](.+)$ ]]; then
        local artist="${BASH_REMATCH[1]}"
        local year="${BASH_REMATCH[2]}"
        local album="${BASH_REMATCH[3]}"

        # Strip disc count suffixes: (2CD), (Single), (3CD), etc.
        album=$(echo "$album" | sed -E 's/[[:space:]]*\([0-9]*CD\)[[:space:]]*$//')
        album=$(echo "$album" | sed -E 's/[[:space:]]*\(Single\)[[:space:]]*$//')

        echo "ARTIST:${artist}|YEAR:${year}|ALBUM:${album}"
        return 0
    else
        return 1
    fi
}

# Function to restructure album folders
restructure_albums() {
    local search_depth="$1"
    local count=0
    local errors=0

    echo -e "${GREEN}Searching at depth $search_depth for albums to restructure...${NC}"

    # Find all folders matching the pattern at specified depth
    while IFS= read -r -d '' folder; do
        local folder_path="$folder"
        local folder_name=$(basename "$folder_path")
        local parent_dir=$(dirname "$folder_path")

        # Parse the folder name
        local parse_result
        if parse_result=$(parse_folder_name "$folder_name"); then
            local artist=$(echo "$parse_result" | grep -o 'ARTIST:[^|]*' | cut -d: -f2)
            local year=$(echo "$parse_result" | grep -o 'YEAR:[^|]*' | cut -d: -f2)
            local album=$(echo "$parse_result" | grep -o 'ALBUM:[^|]*' | cut -d: -f2)

            # Determine target paths
            local artist_folder="$BASE_PATH/$artist"
            local new_album_name="$album ($year)"
            local target_path="$artist_folder/$new_album_name"

            # Skip if source and target are the same
            if [[ "$folder_path" == "$target_path" ]]; then
                continue
            fi

            # Check if target already exists
            if [[ -e "$target_path" ]]; then
                echo -e "${RED}SKIP (target exists): $folder_path${NC}"
                echo -e "${RED}  -> $target_path${NC}"
                ((errors++))
                continue
            fi

            if [[ "$DRY_RUN" == "true" ]]; then
                echo "Would move:"
                echo "  FROM: $folder_path"
                echo "  TO:   $target_path"
            else
                echo "Moving:"
                echo "  FROM: $folder_path"
                echo "  TO:   $target_path"

                # Create artist folder if doesn't exist
                mkdir -p "$artist_folder"

                # Move the album folder
                mv "$folder_path" "$target_path"
            fi
            ((count++))
        fi
    done < <(find "$BASE_PATH" -mindepth "$search_depth" -maxdepth "$search_depth" -type d -print0 | sort -z) || true

    echo -e "${GREEN}Processed $count folder(s) at depth $search_depth${NC}"
    if [[ $errors -gt 0 ]]; then
        echo -e "${RED}Skipped $errors folder(s) due to conflicts${NC}"
    fi
    echo ""

    return 0
}

# Main execution
echo -e "${GREEN}Processing top-level folders (depth 1)...${NC}"
restructure_albums 1

echo -e "${GREEN}Processing nested folders (depth 2)...${NC}"
restructure_albums 2

echo -e "${GREEN}=== Done ===${NC}"

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}This was a dry run. Run without --dry-run to apply changes.${NC}"
fi
