# TG-YTDLP Bot - Render Deployment Guide

## Features
- Download videos from YouTube, Instagram, TikTok, Twitter/X, Facebook, VK, and 1000+ sites
- Support for private videos using cookies
- Playlist download support
- Audio extraction
- Subtitle download and embedding
- Format selection (quality)
- Video splitting by size
- Multi-language support (25+ languages)
- Works without Firebase (local JSON mode)

## Required Environment Variables

Set these in your Render dashboard (Environment section):

| Variable | Description | Example |
|----------|-------------|---------|
| `API_ID` | Telegram API ID (from my.telegram.org) | `12345678` |
| `API_HASH` | Telegram API Hash (from my.telegram.org) | `abc123...` |
| `BOT_TOKEN` | Bot token from @BotFather | `123456:ABC-DEF...` |
| `BOT_NAME` | Your bot's username without @ | `mydownloadbot` |
| `ADMIN_IDS` | Comma-separated admin user IDs | `123456789,987654321` |

## Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_NAME_FOR_USERS` | Name used in database | Same as BOT_NAME |
| `ADMIN_USERNAME` | Admin contact username | @admin |
| `ADMIN_GROUP_IDS` | Comma-separated admin group IDs | (empty) |
| `ALLOWED_GROUP_IDS` | Allowed group IDs for bot usage | (empty) |
| `LOGS_ID` | Channel ID for logs | 0 |
| `SUBSCRIBE_CHANNEL` | Required subscription channel ID | 0 |
| `SUBSCRIBE_CHANNEL_URL` | Subscription channel invite URL | (empty) |
| `USE_FIREBASE` | Use Firebase (true/false) | false |
| `YOUTUBE_COOKIE_URL` | URL to YouTube cookies file | (empty) |

## Render Deployment Steps

### 1. Create Render Account
- Go to https://render.com and sign up

### 2. Create New Service
- Click "New +" → "Background Worker"
- Connect your GitHub repo or use "Upload Code"

### 3. Configure Service
- **Name**: `tg-ytdlp-bot`
- **Runtime**: `Python 3`
- **Plan**: Standard (recommended for video processing)
- **Build Command**:
```bash
apt-get update && apt-get install -y --no-install-recommends ffmpeg mediainfo fonts-noto-core fonts-noto-color-emoji fontconfig libass9 && rm -rf /var/lib/apt/lists/* && pip install -r requirements.txt
```
- **Start Command**: `bash start.sh`

### 4. Set Environment Variables
Add all required variables in the "Environment" tab.

### 5. Deploy
Click "Create Background Worker" or "Manual Deploy".

## Getting API Credentials

### Telegram API ID & Hash
1. Visit https://my.telegram.org
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application
5. Copy `api_id` and `api_hash`

### Bot Token
1. Open Telegram and search for @BotFather
2. Send `/newbot` and follow instructions
3. Copy the bot token

### Admin ID
1. Open Telegram and search for @userinfobot
2. Start the bot to get your user ID

## How to Get Session String (Optional)

For channel guard features, you need a user session:

```bash
python generate_session_string.py
```

This will output a session string to set as `CHANNEL_GUARD_SESSION_STRING`.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help |
| `/settings` | Bot settings |
| `/format` | Set video quality |
| `/audio` | Extract audio only |
| `/subs` | Download subtitles |
| `/split` | Split video by size |
| `/proxy` | Configure proxy |
| `/vid` | Download video with range |
| `/playlist` | Download playlist |

**Or simply send any video URL!**

## Cookie Setup for Private Videos

Upload cookies via the bot:
1. Send `/settings`
2. Select Cookie option
3. Upload your cookie file

Or set `YOUTUBE_COOKIE_URL` to a direct URL of your cookies file.

## Troubleshooting

### Bot not starting
- Check that `API_ID`, `API_HASH`, and `BOT_TOKEN` are set correctly
- Check Render logs for specific errors

### Downloads failing
- Make sure `ffmpeg` is installed (included in build command)
- Check disk space on Render
- For YouTube, try updating cookies

### Memory issues
- Upgrade to a higher Render plan
- Reduce `MAX_FILE_SIZE_GB` in config if needed

## License
GPL-3.0
