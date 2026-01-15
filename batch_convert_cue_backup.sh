#!/bin/bash

# Batch CUE+Audio to individual FLAC converter
# Processes APE, FLAC, WV files with CUE sheets
# Skips: DSD files, SACD ISOs

SOURCE_DIR="/Volumes/Untitled"
LOG_FILE="/tmp/cue_conversion_$(date +%Y%m%d_%H%M%S).log"
TEMP_DIR="/tmp/cue_batch_temp"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Counters
TOTAL=0
SUCCESS=0
SKIPPED=0
FAILED=0

echo "==================================================" | tee "$LOG_FILE"
echo "CUE to Individual FLAC Batch Converter" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE"
echo ""

mkdir -p "$TEMP_DIR"

# Process each CUE file
find "$SOURCE_DIR" -name "*.cue" -type f 2>/dev/null | while read -r cue_file; do
    ((TOTAL++))
    cue_dir=$(dirname "$cue_file")
    cue_name=$(basename "$cue_file" .cue)

    echo -e "${YELLOW}[$TOTAL] Processing:${NC} $(basename "$cue_file")" | tee -a "$LOG_FILE"
    echo "  Directory: $cue_dir" | tee -a "$LOG_FILE"

    # Skip if ISO file in directory (SACD)
    if ls "$cue_dir"/*.iso >/dev/null 2>&1; then
        echo -e "${YELLOW}  SKIPPED: SACD ISO found${NC}" | tee -a "$LOG_FILE"
        ((SKIPPED++))
        echo "" | tee -a "$LOG_FILE"
        continue
    fi

    # Find audio file referenced in CUE
    audio_line=$(grep -i "^FILE " "$cue_file" | head -1)

    if [ -z "$audio_line" ]; then
        echo -e "${RED}  ERROR: No FILE line in CUE${NC}" | tee -a "$LOG_FILE"
        ((FAILED++))
        echo "" | tee -a "$LOG_FILE"
        continue
    fi

    # Extract filename (handle quotes)
    audio_file=$(echo "$audio_line" | sed -n 's/^FILE "\(.*\)" WAVE$/\1/p')
    if [ -z "$audio_file" ]; then
        audio_file=$(echo "$audio_line" | sed -n "s/^FILE '\(.*\)' WAVE$/\1/p")
    fi
    if [ -z "$audio_file" ]; then
        audio_file=$(echo "$audio_line" | awk '{print $2}' | tr -d '"')
    fi

    audio_path="$cue_dir/$audio_file"
    ext="${audio_file##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    echo "  Audio: $audio_file" | tee -a "$LOG_FILE"

    # Skip DSD files
    if [ "$ext" = "dff" ] || [ "$ext" = "dsf" ]; then
        echo -e "${YELLOW}  SKIPPED: DSD format${NC}" | tee -a "$LOG_FILE"
        ((SKIPPED++))
        echo "" | tee -a "$LOG_FILE"
        continue
    fi

    # Check if audio file exists
    if [ ! -f "$audio_path" ]; then
        echo -e "${YELLOW}  SKIPPED: Audio file not found${NC}" | tee -a "$LOG_FILE"
        ((SKIPPED++))
        echo "" | tee -a "$LOG_FILE"
        continue
    fi

    # Check if already split (look for numbered FLAC files)
    if ls "$cue_dir"/[0-9][0-9]*.flac >/dev/null 2>&1; then
        echo -e "${YELLOW}  SKIPPED: Already split (numbered FLACs found)${NC}" | tee -a "$LOG_FILE"
        ((SKIPPED++))
        echo "" | tee -a "$LOG_FILE"
        continue
    fi

    # Clean temp directory
    rm -rf "$TEMP_DIR"/*

    # Split audio based on CUE
    echo "  Splitting..." | tee -a "$LOG_FILE"

    if cuebreakpoints "$cue_file" | shnsplit -d "$TEMP_DIR" -o flac -t "%n - %t" "$audio_path" >>"$LOG_FILE" 2>&1; then
        # Apply metadata from CUE
        echo "  Applying metadata..." | tee -a "$LOG_FILE"
        cuetag.sh "$cue_file" "$TEMP_DIR"/*.flac >>"$LOG_FILE" 2>&1

        # Count files created
        file_count=$(ls -1 "$TEMP_DIR"/*.flac 2>/dev/null | wc -l | tr -d ' ')

        if [ "$file_count" -gt 0 ]; then
            echo "  Moving $file_count files to output..." | tee -a "$LOG_FILE"
            mv "$TEMP_DIR"/*.flac "$cue_dir/" 2>/dev/null

            echo "  Removing CUE file..." | tee -a "$LOG_FILE"
            rm -f "$cue_file"

            # Optionally remove source audio file (UNCOMMENT if you want to delete originals)
            # echo "  Removing original audio file..." | tee -a "$LOG_FILE"
            # rm -f "$audio_path"

            echo -e "${GREEN}  SUCCESS! Created $file_count tracks${NC}" | tee -a "$LOG_FILE"
            ((SUCCESS++))
        else
            echo -e "${RED}  ERROR: No files created${NC}" | tee -a "$LOG_FILE"
            ((FAILED++))
        fi
    else
        echo -e "${RED}  ERROR: Splitting failed${NC}" | tee -a "$LOG_FILE"
        ((FAILED++))
    fi

    echo "" | tee -a "$LOG_FILE"
done

# Cleanup
rm -rf "$TEMP_DIR"

# Summary
echo "==================================================" | tee -a "$LOG_FILE"
echo "Conversion Summary" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE"
echo "Total CUE files: $TOTAL" | tee -a "$LOG_FILE"
echo -e "${GREEN}Successfully converted: $SUCCESS${NC}" | tee -a "$LOG_FILE"
echo -e "${YELLOW}Skipped: $SKIPPED${NC}" | tee -a "$LOG_FILE"
echo -e "${RED}Failed: $FAILED${NC}" | tee -a "$LOG_FILE"
echo ""
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Completed: $(date)" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE"
