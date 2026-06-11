"""
Robust YouTube media download service adapted from Downloader-Bot.
Integrates with New-download-bot- (Pyrogram-based) to fix format errors.
"""

import asyncio
import glob
import os
import re
import time
from typing import Any, Optional

import yt_dlp
from yt_dlp import YoutubeDL

from HELPERS.logger import logger
from CONFIG.config import Config

# ═══════════════════════════════════════════════════════════════
#  Format fallback chains (robust — copied from reference bot)
# ═══════════════════════════════════════════════════════════════

YTDLP_FORMAT_720 = (
    "best[height<=720][ext=mp4][acodec!=none][vcodec!=none]/"
    "best[height<=720][acodec!=none][vcodec!=none]/"
    "bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo[height<=720]+bestaudio/"
    "best[height<=720]/best"
)

YTDLP_FORMAT_1080 = (
    "best[height<=1080][ext=mp4][acodec!=none][vcodec!=none]/"
    "best[height<=1080][acodec!=none][vcodec!=none]/"
    "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo[height<=1080]+bestaudio/"
    "best[height<=1080]/best"
)

YTDLP_FORMAT_BEST = (
    "best[ext=mp4][acodec!=none][vcodec!=none]/"
    "best[acodec!=none][vcodec!=none]/"
    "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo+bestaudio/"
    "best"
)

# yt-dlp speed options
YTDLP_SPEED_OPTS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "continuedl": True,
    "overwrites": True,
    "noplaylist": True,
    "cachedir": False,
    "socket_timeout": 15,
    "retries": 2,
    "fragment_retries": 2,
    "concurrent_fragment_downloads": 4,
}

DEFAULT_YOUTUBE_COOKIES_FILE = os.path.join("cookies", "youtube.txt")

YOUTUBE_INFO_TIMEOUT_SECONDS = 45.0


def _read_float_env(name: str) -> Optional[float]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        logger.warning("Ignoring invalid float env var: %s=%s", name, value)
        return None


def _split_env_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]


def _parse_cookies_from_browser(value: str) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    match = re.fullmatch(
        r"(?x)(?P<name>[^+:]+)(?:\s*\+\s*(?P<keyring>[^:]+))?"
        r"(?:\s*:\s*(?!:)(?P<profile>.+?))?(?:\s*::\s*(?P<container>.+))?",
        value.strip(),
    )
    if not match:
        raise ValueError(f"invalid cookies-from-browser value: {value}")
    browser_name, keyring, profile, container = match.group("name", "keyring", "profile", "container")
    return browser_name.lower(), profile, keyring.upper() if keyring else None, container


def build_ytdlp_youtube_options(**overrides: Any) -> dict[str, Any]:
    """Build yt-dlp options optimized for YouTube with cookie/PO-token support."""
    options = {**YTDLP_SPEED_OPTS}

    sleep_requests = _read_float_env("YTDLP_YOUTUBE_SLEEP_REQUESTS_SECONDS")
    if sleep_requests is not None:
        options["sleep_interval_requests"] = sleep_requests
    sleep_interval = _read_float_env("YTDLP_YOUTUBE_SLEEP_INTERVAL_SECONDS")
    if sleep_interval is not None:
        options["sleep_interval"] = sleep_interval
    max_sleep_interval = _read_float_env("YTDLP_YOUTUBE_MAX_SLEEP_INTERVAL_SECONDS")
    if max_sleep_interval is not None:
        options["max_sleep_interval"] = max_sleep_interval

    # Cookies file
    cookies_file = os.getenv("YTDLP_YOUTUBE_COOKIES_FILE")
    if cookies_file and cookies_file.strip():
        options["cookiefile"] = cookies_file.strip()
    elif os.path.isfile(DEFAULT_YOUTUBE_COOKIES_FILE):
        options["cookiefile"] = DEFAULT_YOUTUBE_COOKIES_FILE

    # Cookies from browser
    cookies_from_browser = os.getenv("YTDLP_YOUTUBE_COOKIES_FROM_BROWSER")
    if cookies_from_browser and cookies_from_browser.strip():
        try:
            options["cookiesfrombrowser"] = _parse_cookies_from_browser(cookies_from_browser)
        except ValueError as exc:
            logger.warning("Ignoring %s", exc)

    # Extractor args (player client, PO token)
    extractor_args: dict[str, dict[str, list[str]]] = {}
    player_client = os.getenv("YTDLP_YOUTUBE_PLAYER_CLIENT")
    if player_client and player_client.strip():
        extractor_args.setdefault("youtube", {})["player_client"] = _split_env_list(player_client)
    po_token = os.getenv("YTDLP_YOUTUBE_PO_TOKEN")
    if po_token and po_token.strip():
        extractor_args.setdefault("youtube", {})["po_token"] = _split_env_list(po_token)
    if extractor_args:
        options["extractor_args"] = extractor_args

    # Remote components
    remote_components = os.getenv("YTDLP_YOUTUBE_REMOTE_COMPONENTS")
    if remote_components and remote_components.strip():
        options["remote_components"] = set(_split_env_list(remote_components))

    # Add PO token provider if enabled
    try:
        from HELPERS.pot_helper import add_pot_to_ytdl_opts
        options = add_pot_to_ytdl_opts(options, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    except Exception:
        pass

    options.update({key: value for key, value in overrides.items() if value is not None})
    return options


# ═══════════════════════════════════════════════════════════════
#  Stream selection helpers
# ═══════════════════════════════════════════════════════════════

def get_youtube_thumbnail_url(yt: Optional[dict[str, Any]]) -> Optional[str]:
    """Extract the best thumbnail URL from yt-dlp info dict."""
    if not yt:
        return None
    thumbnail = yt.get("thumbnail")
    if isinstance(thumbnail, str) and thumbnail:
        return thumbnail
    thumbnails = yt.get("thumbnails")
    if isinstance(thumbnails, list):
        for item in reversed(thumbnails):
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url:
                    return url
    video_id = yt.get("id")
    if isinstance(video_id, str) and video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return None


def get_video_stream(yt: dict, max_height: int = 720) -> dict | None:
    """Pick the best progressive MP4 stream with both video and audio."""
    formats = yt.get("formats", [])
    progressive = [
        item for item in formats
        if item.get("vcodec") != "none"
        and item.get("acodec") != "none"
        and item.get("ext") == "mp4"
        and int(item.get("height") or 0) <= max_height
    ]
    progressive.sort(key=lambda item: int(item.get("height", 0)), reverse=True)
    if progressive:
        best = progressive[0]
        best["webpage_url"] = yt.get("webpage_url", "")
        return best
    return None


def get_audio_stream(yt: dict) -> dict | None:
    """Pick the best audio-only stream (m4a/mp4)."""
    formats = yt.get("formats", [])
    audio_streams = [
        item for item in formats
        if item.get("vcodec") == "none" and item.get("ext") in ("m4a", "mp4")
    ]
    audio_streams.sort(key=lambda item: float(item.get("abr") or 0), reverse=True)
    best = audio_streams[0] if audio_streams else None
    if best:
        best["webpage_url"] = yt.get("webpage_url", "")
    return best


def is_manifest_stream(stream: dict) -> bool:
    """Check if a stream uses HLS/DASH manifest (needs merging)."""
    protocol = (stream.get("protocol") or "").lower()
    manifest_url = stream.get("manifest_url") or stream.get("url") or ""
    return "m3u8" in protocol or "dash" in protocol or manifest_url.endswith(".m3u8")


# ═══════════════════════════════════════════════════════════════
#  Video info extraction
# ═══════════════════════════════════════════════════════════════

def get_youtube_video(url: str, cookie_file: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Extract YouTube video info using yt-dlp with optimized options."""
    try:
        ydl_opts = build_ytdlp_youtube_options(
            skip_download=True,
            ignore_no_formats_error=True,
        )
        if cookie_file and os.path.exists(cookie_file):
            ydl_opts["cookiefile"] = cookie_file
        with YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        logger.error("Error fetching YouTube info: %s", exc)
        return None


async def get_youtube_video_async(url: str, cookie_file: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Async wrapper for get_youtube_video."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(get_youtube_video, url, cookie_file),
            timeout=YOUTUBE_INFO_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("Timeout getting YouTube info for %s", url)
        return None
    except Exception as exc:
        logger.error("Error getting YouTube info: %s", exc)
        return None


# ═══════════════════════════════════════════════════════════════
#  Format helpers for down_and_up integration
# ═══════════════════════════════════════════════════════════════

def get_youtube_format_for_quality(quality_key: Optional[str]) -> str:
    """Return a robust format string for a given quality key."""
    if not quality_key:
        return YTDLP_FORMAT_720
    quality_key = str(quality_key).lower().strip()
    if quality_key == "best":
        return YTDLP_FORMAT_BEST
    if quality_key in ("720p", "720"):
        return YTDLP_FORMAT_720
    if quality_key in ("1080p", "1080"):
        return YTDLP_FORMAT_1080
    if quality_key in ("144p", "240p", "360p", "480p"):
        height = quality_key.replace("p", "")
        return (
            f"best[height<={height}][ext=mp4][acodec!=none][vcodec!=none]/"
            f"best[height<={height}][acodec!=none][vcodec!=none]/"
            f"bestvideo[height<={height}][vcodec^=avc1]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={height}]+bestaudio/"
            f"best[height<={height}]/best"
        )
    if quality_key in ("1440p", "2160p", "4320p"):
        height = quality_key.replace("p", "")
        return (
            f"best[height<={height}][ext=mp4][acodec!=none][vcodec!=none]/"
            f"best[height<={height}][acodec!=none][vcodec!=none]/"
            f"bestvideo[height<={height}][vcodec^=avc1]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={height}]+bestaudio/"
            f"best[height<={height}]/best"
        )
    if "bestvideo" in quality_key or "bv" in quality_key:
        return YTDLP_FORMAT_BEST
    # Default fallback
    return YTDLP_FORMAT_720


def build_youtube_attempts(quality_key: Optional[str], merge_format: str = "mp4") -> list[dict]:
    """Build download attempts list optimized for YouTube."""
    fmt = get_youtube_format_for_quality(quality_key)
    return [
        {
            "format": fmt,
            "prefer_ffmpeg": True,
            "merge_output_format": merge_format,
            "extract_flat": False,
        },
        {
            "format": "bestvideo+bestaudio/best",
            "prefer_ffmpeg": True,
            "merge_output_format": merge_format,
            "extract_flat": False,
        },
        {
            "format": "best",
            "prefer_ffmpeg": False,
            "extract_flat": False,
        },
    ]


# ═══════════════════════════════════════════════════════════════
#  yt-dlp download wrappers
# ═══════════════════════════════════════════════════════════════

def _resolve_downloaded_path(expected_path: str) -> str:
    """Resolve the actual downloaded file path (handles yt-dlp extensions)."""
    if os.path.exists(expected_path):
        return expected_path
    stem, ext = os.path.splitext(expected_path)
    matches = sorted(glob.glob(f"{stem}*{ext}") + glob.glob(f"{stem}.*"))
    for match in matches:
        if os.path.isfile(match):
            return match
    raise FileNotFoundError(f"yt-dlp output file missing: {expected_path}")


def run_ytdlp_download(url: str, out_path: str, format_selector: str,
                       cookie_file: Optional[str] = None,
                       merge_format: str = "mp4",
                       max_filesize: Optional[int] = None) -> Optional[str]:
    """
    Download a YouTube video using yt-dlp with robust format selection.
    Returns the path to the downloaded file, or None on failure.
    """
    base_path = out_path
    if out_path.endswith(".mp4") or out_path.endswith(".mkv"):
        base_path = out.path.rsplit(".", 1)[0] if hasattr(out, "path") else out_path.rsplit(".", 1)[0]

    out_template = f"{base_path}.%(ext)s"
    ydl_opts = build_ytdlp_youtube_options(
        format=format_selector,
        outtmpl=out_template,
        merge_output_format=merge_format,
    )
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file
    if max_filesize is not None:
        ydl_opts["max_filesize"] = int(max_filesize)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        resolved = _resolve_downloaded_path(f"{base_path}.{merge_format}")
        if os.path.exists(resolved):
            return resolved
        # Try any extension
        return _resolve_downloaded_path(out_template.replace(".%(ext)s", ".*"))
    except Exception as exc:
        logger.error("yt-dlp download failed: url=%s error=%s", url, exc)
        return None


async def download_with_ytdlp_async(url: str, out_path: str, format_selector: str,
                                     cookie_file: Optional[str] = None,
                                     merge_format: str = "mp4",
                                     max_filesize: Optional[int] = None,
                                     timeout: float = 900.0) -> Optional[str]:
    """Async wrapper for run_ytdlp_download."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                run_ytdlp_download, url, out_path, format_selector,
                cookie_file, merge_format, max_filesize
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.error("yt-dlp download timeout for %s", url)
        return None
    except Exception as exc:
        logger.error("yt-dlp download error: %s", exc)
        return None


def download_mp3_with_ytdlp(url: str, base_path: str,
                             cookie_file: Optional[str] = None,
                             max_filesize: Optional[int] = None) -> Optional[str]:
    """Download and convert YouTube audio to MP3."""
    out_template = f"{base_path}.%(ext)s"
    final_path = f"{base_path}.mp3"
    ydl_opts = build_ytdlp_youtube_options(
        format="bestaudio/best",
        outtmpl=out_template,
        postprocessors=[{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    )
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file
    if max_filesize is not None:
        ydl_opts["max_filesize"] = int(max_filesize)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if os.path.exists(final_path):
            return final_path
        matches = glob.glob(f"{base_path}.*")
        if matches:
            return matches[0]
        return None
    except Exception as exc:
        logger.error("yt-dlp MP3 download failed: url=%s error=%s", url, exc)
        return None


async def download_mp3_with_ytdlp_async(url: str, base_path: str,
                                         cookie_file: Optional[str] = None,
                                         max_filesize: Optional[int] = None,
                                         timeout: float = 900.0) -> Optional[str]:
    """Async wrapper for download_mp3_with_ytdlp."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(download_mp3_with_ytdlp, url, base_path, cookie_file, max_filesize),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.error("yt-dlp MP3 download timeout for %s", url)
        return None
    except Exception as exc:
        logger.error("yt-dlp MP3 download error: %s", exc)
        return None
