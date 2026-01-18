#!/bin/bash
# Fix multi-disc folder naming and cleanup AppleDouble files
# Usage: ./fix-multidisc.sh [--dry-run] [--clean-apple-files]

set -euo pipefail

# Configuration
BASE_PATH="/mnt/nas/CD_RIP"
DRY_RUN=false
CLEAN_APPLE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --clean-apple-files)
            CLEAN_APPLE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--clean-apple-files]"
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

# Function to rename CD folders with zero-padding
rename_cd_folders() {
    echo -e "${GREEN}Searching for CD folders to rename...${NC}"

    # Find all CD[1-9] folders (single digit only)
    local count=0
    while IFS= read -r -d '' folder; do
        local dirname=$(basename "$folder")
        local parent=$(dirname "$folder")

        # Extract the digit
        if [[ "$dirname" =~ ^CD([1-9])$ ]]; then
            local disc_num="${BASH_REMATCH[1]}"
            local new_name="CD0${disc_num}"
            local new_path="${parent}/${new_name}"

            if [[ "$DRY_RUN" == "true" ]]; then
                echo "Would rename: $folder -> $new_path"
            else
                echo "Renaming: $folder -> $new_path"
                mv "$folder" "$new_path"
            fi
            ((count++))
        fi
    done < <(find "$BASE_PATH" -type d -name "CD[1-9]" -print0)

    echo -e "${GREEN}Found and ${DRY_RUN:+would }renamed $count folder(s)${NC}"
    echo ""
}

# Function to clean AppleDouble files
clean_apple_files() {
    if [[ "$CLEAN_APPLE" == "true" ]]; then
        echo -e "${GREEN}Cleaning AppleDouble ._ files...${NC}"

        local count=$(find "$BASE_PATH" -type f -name "._*" | wc -l | tr -d ' ')

        if [[ "$DRY_RUN" == "true" ]]; then
            echo "Would delete $count ._ files"
        else
            find "$BASE_PATH" -type f -name "._*" -delete
            echo "Deleted $count ._ files"
        fi
        echo ""
    fi
}

# Main execution
echo -e "${GREEN}=== Multi-disc Folder Fix Script ===${NC}"
echo "Base path: $BASE_PATH"
echo ""

# Check if base path exists
if [[ ! -d "$BASE_PATH" ]]; then
    echo -e "${RED}Error: Base path does not exist: $BASE_PATH${NC}"
    exit 1
fi

# Execute operations
rename_cd_folders
clean_apple_files

echo -e "${GREEN}=== Done ===${NC}"

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}This was a dry run. Run without --dry-run to apply changes.${NC}"
fi
