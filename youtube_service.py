import re
from typing import Optional, Dict, Any, List
import requests
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    IpBlocked,
    RequestBlocked
)

# Regex patterns for extracting YouTube video IDs
YOUTUBE_URL_PATTERNS = [
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
    r'(?:https?:\/\/)?youtu\.be\/([a-zA-Z0-9_-]{11})',
    r'^([a-zA-Z0-9_-]{11})$'  # direct video ID
]

def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extract 11-character YouTube video ID from various URL formats."""
    clean_input = url_or_id.strip()
    for pattern in YOUTUBE_URL_PATTERNS:
        match = re.search(pattern, clean_input)
        if match:
            return match.group(1)
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
    Uses YouTube Data API v3 if API key is provided,
    otherwise falls back to YouTube oEmbed API.
    """
    default_meta = {
        "video_id": video_id,
        "title": f"YouTube Video ({video_id})",
        "channel": "YouTube Creator",
        "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "description": ""
    }

    # 1. Try YouTube Data API v3 if key is provided
    if api_key:
        try:
            from googleapiclient.discovery import build
            youtube = build('youtube', 'v3', developerKey=api_key)
            request = youtube.videos().list(
                part="snippet",
                id=video_id
            )
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
            print(f"[YouTube Data API v3 Warning] Failed to fetch via API key: {e}. Falling back to oEmbed.")

    # 2. Fallback: YouTube oEmbed endpoint (reliable and no API key required)
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        resp = requests.get(oembed_url, timeout=5)
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
        print(f"[oEmbed Warning] Could not fetch oembed info: {e}")

    return default_meta

def _fetch_transcript_list_or_direct(video_id: str):
    """
    Safely retrieve raw transcript segments using modern instance API or legacy get_transcript.
    """
    # 1. Compatibility check for older versions (v0.6.x) via getattr to avoid static type errors
    get_transcript_fn = getattr(YouTubeTranscriptApi, 'get_transcript', None)
    if callable(get_transcript_fn):
        try:
            return get_transcript_fn(video_id, languages=['ko', 'ko-KR'])
        except (NoTranscriptFound, TranscriptsDisabled):
            return get_transcript_fn(video_id)

    # 2. Modern instance API (v1.x+)
    api = YouTubeTranscriptApi()

    # Try direct fetch with Korean preference
    try:
        fetched = api.fetch(video_id, languages=['ko', 'ko-KR'])
        if hasattr(fetched, 'to_raw_data'):
            return fetched.to_raw_data()
        return fetched
    except (TranscriptsDisabled, VideoUnavailable, IpBlocked, RequestBlocked):
        raise
    except Exception:
        pass

    # Try listing available transcripts and translating to Korean if possible
    try:
        t_list = api.list(video_id)
        # 1. Prioritize Korean transcript
        for t in t_list:
            if getattr(t, 'language_code', '').startswith('ko'):
                fetched = t.fetch()
                return fetched.to_raw_data() if hasattr(fetched, 'to_raw_data') else fetched
        # 2. Translate to Korean if translatable
        for t in t_list:
            if getattr(t, 'is_translatable', False):
                fetched = t.translate('ko').fetch()
                return fetched.to_raw_data() if hasattr(fetched, 'to_raw_data') else fetched
        # 3. Fallback to any available transcript
        for t in t_list:
            fetched = t.fetch()
            return fetched.to_raw_data() if hasattr(fetched, 'to_raw_data') else fetched
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable, IpBlocked, RequestBlocked):
        raise
    except Exception as e:
        raise ValueError(f"字幕の取得に失敗しました: {str(e)}")

    raise ValueError("この動画には利用可能な字幕が見つかりませんでした。")

def fetch_korean_transcript(video_id: str) -> Dict[str, Any]:
    """
    Fetch transcript for the given YouTube video ID.
    Converts raw items into combined Korean text.
    Handles known errors gracefully with helpful messages.
    """
    try:
        raw_transcript = _fetch_transcript_list_or_direct(video_id)
    except TranscriptsDisabled:
        raise ValueError("この動画では字幕が無効化されています。「テキスト直接入力」タブから韓国語テキストを入力して単語を抽出できます。")
    except NoTranscriptFound:
        raise ValueError("この動画には利用可能な字幕が見つかりませんでした。「テキスト直接入力」タブからテキストを入力してください。")
    except VideoUnavailable:
        raise ValueError("指定された動画は非公開、削除されたか、再生できません。URLをご確認ください。")
    except (IpBlocked, RequestBlocked):
        raise ValueError("YouTube側による一時的なアクセス制限（IP/Bot制限）が発生しました。少し時間をおいて再試行するか、「テキスト直接入力」タブをご利用ください。")
    except Exception as e:
        err_msg = str(e)
        if "no attribute 'list_transcripts'" in err_msg:
            err_msg = "字幕APIの互換性エラーを回避しました。再度お試しください。"
        raise ValueError(f"字幕の取得に失敗しました: {err_msg}")

    # Combine text snippets
    text_segments = []
    for item in raw_transcript:
        snippet = getattr(item, 'text', None)
        if snippet is None and isinstance(item, dict):
            snippet = item.get('text', '')
        if snippet:
            cleaned = re.sub(r'\[.*?\]', '', str(snippet)).strip()
            if cleaned:
                text_segments.append(cleaned)

    full_text = " ".join(text_segments)
    if not full_text.strip():
        raise ValueError("字幕テキストが空でした。「テキスト直接入力」タブから韓国語テキストを入力してください。")

    return {
        "language": "Korean",
        "language_code": "ko",
        "full_text": full_text,
        "segment_count": len(text_segments)
    }
