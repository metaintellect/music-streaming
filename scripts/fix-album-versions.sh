#!/bin/bash
# Fix album tags for remastered/remixed versions to distinguish from originals

process_album() {
    local source_dir="$1"
    local new_album="$2"
    
    if [ ! -d "$source_dir" ]; then
        echo "  SKIP: Directory not found: $source_dir"
        return
    fi
    
    echo "  Processing: $(basename "$source_dir")"
    echo "  New album tag: $new_album"
    
    for file in "$source_dir"/*.wav "$source_dir"/*.flac; do
        [ -f "$file" ] || continue
        filename=$(basename "$file")
        temp_file="$source_dir/.tmp_$filename"
        
        ffmpeg -i "$file" \
            -metadata album="$new_album" \
            -c copy \
            "$temp_file" -y 2>/dev/null && \
        mv "$temp_file" "$file"
    done
    
    echo "  Done!"
    echo ""
}

echo "=== Fixing REMIX albums ==="
echo ""

# Marillion - Afraid Of Sunlight
process_album "/Volumes/xnas/music/metal/Marillion/Afraid Of Sunlight (2019)" "Afraid of Sunlight (Steven Wilson Remix)"

# Blind Guardian
process_album "/Volumes/xnas/music/metal/Blind Guardian/Somewhere Far Beyond (2018)" "Somewhere Far Beyond (Remix)"
process_album "/Volumes/xnas/music/metal/Blind Guardian/Tales From The Twilight World (2018)" "Tales From The Twilight World (Remix)"

# Whitesnake
process_album "/Volumes/xnas/music/metal/Whitesnake/Into The Light (2024)" "Into The Light (Remix)"
process_album "/Volumes/xnas/music/metal/Whitesnake/Restless Heart (2021)" "Restless Heart (Remix)"
process_album "/Volumes/xnas/music/metal/Whitesnake/Slide It In (2019)" "Slide It In (Remix)"

echo "=== Fixing REMASTER albums ==="
echo ""

# Dio
process_album "/Volumes/xnas/music/metal/Dio/Holy Diver (2023)" "Holy Diver (Remaster)"
process_album "/Volumes/xnas/music/metal/Dio/The Last in Line (2023)" "The Last in Line (Remaster)"

# Judas Priest
process_album "/Volumes/xnas/music/metal/Judas Priest/British Steel (2001)" "British Steel (Remaster)"
process_album "/Volumes/xnas/music/metal/Judas Priest/Defenders of the Faith (2001)" "Defenders of the Faith (Remaster)"
process_album "/Volumes/xnas/music/metal/Judas Priest/Painkiller (2001)" "Painkiller (Remaster)"
process_album "/Volumes/xnas/music/metal/Judas Priest/Priest...Live! (2001)" "Priest...Live! (Remaster)"
process_album "/Volumes/xnas/music/metal/Judas Priest/Ram It Down (2001)" "Ram It Down (Remaster)"
process_album "/Volumes/xnas/music/metal/Judas Priest/Screaming for Vengeance (2012)" "Screaming for Vengeance (Remaster)"
process_album "/Volumes/xnas/music/metal/Judas Priest/Sin After Sin (2001)" "Sin After Sin (Remaster)"
process_album "/Volumes/xnas/music/metal/Judas Priest/Stained Class (2001)" "Stained Class (Remaster)"
process_album "/Volumes/xnas/music/metal/Judas Priest/Turbo (2001)" "Turbo (Remaster)"

# King Diamond
process_album "/Volumes/xnas/music/metal/King Diamond/Fatal Portrait (1997)" "Fatal Portrait (Remaster)"

# Metallica
process_album "/Volumes/xnas/music/metal/Metallica/Master of Puppets (2003)" "Master of Puppets (Remaster)"

# Queensrÿche
process_album "/Volumes/xnas/music/metal/Queensrÿche/Empire (2003)" "Empire (Remaster)"

echo "=== ALL DONE ==="
echo ""
echo "Now in Roon:"
echo "  1. Settings → Library → Clean Up Library"
echo "  2. Settings → Library → Force Rescan"
