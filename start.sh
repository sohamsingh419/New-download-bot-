#!/bin/bash
set -e

echo "========================================"
echo "  TG-YTDLP Bot - Starting on Render"
echo "========================================"

# Create necessary directories
mkdir -p TXT
mkdir -p users
mkdir -p cookies
mkdir -p downloads
mkdir -p temp

# Set Python to unbuffered mode for Render logs
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Check required environment variables
if [ -z "$API_ID" ] || [ "$API_ID" = "0" ]; then
    echo "ERROR: API_ID environment variable is not set!"
    echo "Please set API_ID in your Render environment variables."
    exit 1
fi

if [ -z "$API_HASH" ]; then
    echo "ERROR: API_HASH environment variable is not set!"
    echo "Please set API_HASH in your Render environment variables."
    exit 1
fi

if [ -z "$BOT_TOKEN" ]; then
    echo "ERROR: BOT_TOKEN environment variable is not set!"
    echo "Please set BOT_TOKEN in your Render environment variables."
    exit 1
fi

echo "Bot Name: $BOT_NAME"
echo "Bot Name for Users: $BOT_NAME_FOR_USERS"
echo "Admin IDs: $ADMIN_IDS"
echo "USE_FIREBASE: ${USE_FIREBASE:-false}"
echo "Working Directory: $(pwd)"

# Start the bot
echo "========================================"
echo "  Starting Telegram Bot..."
echo "========================================"
python3 magic.py
