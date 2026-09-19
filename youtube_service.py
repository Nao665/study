import os
import re
import tempfile
from typing import Optional, Dict, Any, List, cast
import requests

# Try importing youtube_transcript_api safely
try:
    import youtube_transcript_api
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    youtube_transcript_api = None
    YouTubeTranscriptApi = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# Regex patterns for extracting YouTube video IDs
YOUTUBE_URL_PATTERNS = [
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/live\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?youtu\.be\/([a-zA-Z0-9_-]{11})',
    r'^([a-zA-Z0-9_-]{11})$'  # direct video ID
]

def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extract 11-character YouTube video ID from various URL formats."""
    if not url_or_id:
        return None
    clean_input = url_or_id.strip()
    for pattern in YOUTUBE_URL_PATTERNS:
        match = re.search(pattern, clean_input)
        if match:
            return match.group(1)
    return None

def _get_cookie_file_path() -> Optional[str]:
    """
    Check for cookie file existence or environment variable YOUTUBE_COOKIES.
    Returns path to cookie file if available.
    """
    # 1. Check local file
    for p in ("cookies.txt", "youtube_cookies.txt"):
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return os.path.abspath(p)

    # 2. Check environment variable containing cookie content
    cookies_env = os.getenv("YOUTUBE_COOKIES")
    if cookies_env and len(cookies_env.strip()) > 10:
        try:
            temp_file = os.path.join(tempfile.gettempdir(), "yt_cookies_env.txt")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(cookies_env.strip())
            return temp_file
        except Exception as e:
            print(f"[Cookie Warning] Could not write env cookie to temp file: {e}")

    return None

def _safe_thumbnail(thumbnails: Dict[str, Any], default_url: str) -> str:
    """Safely extract thumbnail URL from various quality levels."""
    if not isinstance(thumbnails, dict):
        return default_url
    for quality in ("maxres", "standard", "high", "medium", "default"):
        thumb = thumbnails.get(quality)
        if isinstance(thumb, dict) and thumb.get("url"):
            return str(thumb["url"])
    return default_url

def get_video_metadata(video_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch video metadata (title, author, thumbnail, description).
    1. YouTube Data API v3 if key provided
    2. oEmbed endpoint (reliable and no API key required)
    3. yt-dlp fallback
    """
    default_meta = {
        "video_id": video_id,
        "title": f"YouTube Video ({video_id})",
        "channel": "YouTube Creator",
        "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "description": ""
    }

    # 1. YouTube Data API v3
    if api_key:
        try:
            from googleapiclient.discovery import build
            youtube = cast(Any, build('youtube', 'v3', developerKey=api_key))
            request = youtube.videos().list(part="snippet", id=video_id)
            response = request.execute()
            items = response.get('items', [])
            if items:
                snippet = items[0].get('snippet', {})
                thumbnails = snippet.get('thumbnails', {})
                thumb = _safe_thumbnail(thumbnails, default_meta["thumbnail_url"])
                return {
                    "video_id": video_id,
                    "title": snippet.get('title', default_meta["title"]),
                    "channel": snippet.get('channelTitle', default_meta["channel"]),
                    "thumbnail_url": thumb,
                    "url": default_meta["url"],
                    "description": snippet.get('description', '')
                }
        except Exception as e:
            print(f"[YouTube API v3 Warning] Failed: {e}. Falling back.")

    # 2. oEmbed
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        resp = requests.get(oembed_url, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "video_id": video_id,
                "title": data.get('title', default_meta["title"]),
                "channel": data.get('author_name', default_meta["channel"]),
                "thumbnail_url": data.get('thumbnail_url', default_meta["thumbnail_url"]),
                "url": default_meta["url"],
                "description": ""
            }
    except Exception as e:
        print(f"[oEmbed Warning] Failed: {e}")

    return default_meta

def _parse_json3_subtitles(json3_content: str) -> List[str]:
    """Parse YouTube json3 subtitle format into clean text segments."""
    import json
    segments: List[str] = []
    try:
        data = json.loads(json3_content)
        for event in data.get('events', []):
            event_text: List[str] = []
            for seg in event.get('segs', []):
                utf8_text = seg.get('utf8', '')
                if utf8_text and utf8_text != '\n':
                    event_text.append(utf8_text)
            line = "".join(event_text).strip()
            # Remove [Music], [Applause] tags
            cleaned = re.sub(r'\[.*?\]', '', line).strip()
            if cleaned:
                segments.append(cleaned)
    except Exception as e:
        print(f"[json3 parse error] {e}")
    return segments

def _parse_vtt_subtitles(vtt_content: str) -> List[str]:
    """Parse WebVTT subtitle format into clean text segments."""
    segments: List[str] = []
    lines = vtt_content.splitlines()
    seen_lines = set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if "-->" in line:
            continue
        # Remove timestamps like <00:00:00.000> or HTML tags like <c.color>
        cleaned = re.sub(r'<[^>]+>', '', line)
        cleaned = re.sub(r'\[.*?\]', '', cleaned).strip()
        if cleaned and cleaned not in seen_lines:
            seen_lines.add(cleaned)
            segments.append(cleaned)
    return segments

def _fetch_via_ytdlp(video_id: str) -> List[str]:
    """
    Fetch subtitles using yt-dlp.
    yt-dlp has active bot-detection bypass and supports various clients (Android, VisionOS, Web).
    """
    if yt_dlp is None:
        raise RuntimeError("yt-dlp is not installed.")

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    cookie_file = _get_cookie_file_path()
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")

    ydl_opts: Dict[str, Any] = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file
    if proxy:
        ydl_opts['proxy'] = proxy

    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
        try:
            info = ydl.extract_info(video_url, download=False)
        except Exception as e:
            err = str(e)
            if "Sign in to confirm you're not a bot" in err or "429" in err:
                raise ValueError(f"YouTube IP/Bot判定エラー: {err}")
            if "Video unavailable" in err:
                raise ValueError(f"指定された動画は非公開または削除されています: {video_id}")
            raise ValueError(f"yt-dlpでの動画情報取得に失敗しました: {err}")

    if not info:
        raise ValueError("動画情報の取得に失敗しました。")

    # Inspect subtitles
    subtitles = info.get('subtitles', {}) or {}
    auto_captions = info.get('automatic_captions', {}) or {}

    # Target language search order:
    # 1. Manual Korean subtitles ('ko', 'ko-KR', 'ko-orig')
    # 2. Automatic Korean subtitles ('ko', 'ko-KR')
    # 3. Any available Korean translated captions
    target_formats = None

    for k in subtitles.keys():
        if k.lower().startswith('ko'):
            target_formats = subtitles[k]
            break

    if not target_formats:
        for k in auto_captions.keys():
            if k.lower().startswith('ko'):
                target_formats = auto_captions[k]
                break

    # If no Korean, check if any subtitle is available
    if not target_formats:
        if subtitles:
            first_key = next(iter(subtitles.keys()))
            target_formats = subtitles[first_key]
        elif auto_captions:
            first_key = next(iter(auto_captions.keys()))
            target_formats = auto_captions[first_key]

    if not target_formats:
        raise ValueError("利用可能な字幕が見つかりませんでした。")

    # Choose best format: json3 > vtt > srv1 > others
    format_choice = None
    for ext in ('json3', 'vtt', 'srv1', 'ttml'):
        for f in target_formats:
            if f.get('ext') == ext or ext in f.get('url', ''):
                format_choice = f
                break
        if format_choice:
            break

    if not format_choice:
        format_choice = target_formats[0]

    sub_url = format_choice.get('url')
    if not sub_url:
        raise ValueError("字幕URLが見つかりませんでした。")

    # Fetch subtitle stream using ydl's internal opener (preserves session, cookies, tokens)
    try:
        sub_resp = ydl.urlopen(sub_url)
        content_bytes = sub_resp.read()
        content = content_bytes.decode('utf-8', errors='replace')
    except Exception as e:
        # Fallback to requests if ydl opener failed
        try:
            req_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            resp = requests.get(sub_url, headers=req_headers, timeout=12)
            if resp.status_code != 200:
                raise ValueError(f"Status: {resp.status_code}")
            content = resp.text
        except Exception:
            raise ValueError(f"字幕のダウンロードに失敗しました: {str(e)}")

    ext = format_choice.get('ext', '')
    if ext == 'json3' or 'srv3' in sub_url or content.strip().startswith('{'):
        segments = _parse_json3_subtitles(content)
    elif ext == 'vtt' or 'WEBVTT' in content:
        segments = _parse_vtt_subtitles(content)
    else:
        # Fallback regex extraction for XML/TTML or plaintext
        text_tags = re.findall(r'>([^<]+)<', content)
        segments = [re.sub(r'\[.*?\]', '', t).strip() for t in text_tags if t.strip() and not t.strip().startswith('&')]

    if not segments:
        raise ValueError("字幕データからテキストを抽出できませんでした。")

    return segments

def _fetch_via_transcript_api(video_id: str) -> List[str]:
    """
    Fallback subtitle fetching using youtube-transcript-api.
    Uses generic call to avoid type-stub and version incompatibilities.
    """
    if YouTubeTranscriptApi is None:
        raise RuntimeError("youtube-transcript-api is not installed.")

    api_cls: Any = YouTubeTranscriptApi

    cookie_file = _get_cookie_file_path()
    proxies = None
    proxy_env = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if proxy_env:
        proxies = {"http": proxy_env, "https": proxy_env}

    kwargs: Dict[str, Any] = {}
    if cookie_file:
        kwargs['cookies'] = cookie_file
    if proxies:
        kwargs['proxies'] = proxies

    # 1. Try direct fetch for Korean
    try:
        if hasattr(api_cls, 'get_transcript'):
            raw = api_cls.get_transcript(video_id, languages=['ko', 'ko-KR'], **kwargs)
            return [item['text'] for item in raw if 'text' in item]
    except Exception as e:
        err_type = type(e).__name__
        if err_type in ("IpBlocked", "RequestBlocked"):
            raise ValueError(f"YouTube IP/Bot判定エラー: {str(e)}")

    # 2. Try listing transcripts
    try:
        if hasattr(api_cls, 'list_transcripts'):
            transcript_list = api_cls.list_transcripts(video_id)
            # Korean manual/auto
            try:
                t = transcript_list.find_transcript(['ko', 'ko-KR'])
                raw = t.fetch()
                return [item['text'] for item in raw if 'text' in item]
            except Exception:
                pass

            # Translate to Korean if translatable
            for t in transcript_list:
                if getattr(t, 'is_translatable', False):
                    raw = t.translate('ko').fetch()
                    return [item['text'] for item in raw if 'text' in item]

            # First available transcript
            for t in transcript_list:
                raw = t.fetch()
                return [item['text'] for item in raw if 'text' in item]
    except Exception as e:
        err_type = type(e).__name__
        if err_type in ("IpBlocked", "RequestBlocked"):
            raise ValueError(f"YouTube IP/Bot判定エラー: {str(e)}")
        raise e

    raise ValueError("利用可能な字幕が見つかりませんでした。")

def fetch_korean_transcript(video_id: str) -> Dict[str, Any]:
    """
    Fetch transcript for the given YouTube video ID.
    Multi-tier architecture:
    Tier 1: yt-dlp (Strongest against Bot/IP blocks)
    Tier 2: youtube-transcript-api (Direct fallback)
    """
    text_segments: List[str] = []
    fetch_errors: List[str] = []

    # 1. Attempt with yt-dlp first
    try:
        text_segments = _fetch_via_ytdlp(video_id)
    except Exception as e:
        fetch_errors.append(f"yt-dlp: {str(e)}")
        # 2. Fallback to youtube-transcript-api
        try:
            text_segments = _fetch_via_transcript_api(video_id)
        except Exception as e2:
            fetch_errors.append(f"youtube-transcript-api: {str(e2)}")

    if not text_segments:
        # Check if error indicates IP block or bot detection
        combined_err = " | ".join(fetch_errors)
        if any(keyword in combined_err for keyword in ("IpBlocked", "RequestBlocked", "Sign in to confirm", "429", "IP/Bot")):
            raise ValueError(
                "YouTube側による一時的なアクセス制限（IP/Bot判定）が発生しました。"
                "「テキスト直接入力」タブで韓国語テキストまたは文字起こしを貼り付けるとすぐに抽出できます。"
            )
        if any(keyword in combined_err for keyword in ("VideoUnavailable", "not available", "削除")):
            raise ValueError("指定された動画は非公開、削除されたか、再生できません。URLをご確認ください。")

        raise ValueError(
            "この動画から利用可能な字幕が取得できませんでした。"
            "字幕が無効化されているか、自動生成字幕が未生成の可能性があります。"
            "「テキスト直接入力」タブをご利用ください。"
        )

    # Clean and concatenate segments
    clean_segments: List[str] = []
    for s in text_segments:
        cleaned = re.sub(r'\[.*?\]', '', str(s)).strip()
        if cleaned:
            clean_segments.append(cleaned)

    full_text = " ".join(clean_segments)
    if not full_text.strip():
        raise ValueError("字幕テキストが空でした。「テキスト直接入力」タブからテキストを入力してください。")

    return {
        "language": "Korean",
        "language_code": "ko",
        "full_text": full_text,
        "segment_count": len(clean_segments)
    }
