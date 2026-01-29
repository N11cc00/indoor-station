#!/bin/bash

# Deploy script for indoor-station
# Syncs local files with server at nico-behrens.de using rsync

set -e  # Exit on error

# Configuration
SERVER="nico-behrens.de"
SERVER_USER="${DEPLOY_USER:-nico}"
REMOTE_DIR="${REMOTE_DIR:-/home/nico/indoor-station}"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Deploying indoor-station to ${SERVER_USER}@${SERVER}..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Rsync options:
# -a: archive mode (preserves permissions, timestamps, etc.)
# -v: verbose
# -z: compress during transfer
# --delete: delete files on remote that don't exist locally
# --exclude: exclude certain files/directories

echo "🔄 Syncing files with rsync..."
rsync -avz --delete \
    --exclude='.git/' \
    --exclude='node_modules/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.vscode/' \
    --exclude='.idea/' \
    --exclude='bin/' \
    --exclude='*.o' \
    --exclude='*.d' \
    --exclude='instance/' \
    --exclude='.venv/' \
    "${LOCAL_DIR}/" \
    "${SERVER_USER}@${SERVER}:${REMOTE_DIR}/"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment completed successfully!"
echo ""
