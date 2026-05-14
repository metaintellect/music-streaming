#!/bin/bash
# Deploy and run move-cd-rip-classical.py on NAS
# Usage: ./run-classical-move.sh [--dry-run] [--execute]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAS="root@192.168.100.83"
REMOTE_DIR="/root"

DRY_RUN="--dry-run"
[[ "$1" == "--execute" ]] && DRY_RUN=""

echo "Copying script + mapping to NAS..."
scp "$SCRIPT_DIR/move-cd-rip-classical.py" \
    "$SCRIPT_DIR/cd-rip-classical-mapping.json" \
    "$NAS:$REMOTE_DIR/"

echo ""
echo "Running on NAS..."
ssh "$NAS" "cd $REMOTE_DIR && python3 move-cd-rip-classical.py $DRY_RUN"
