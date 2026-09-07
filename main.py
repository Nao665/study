import os
import io
import csv
import re
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from youtube_service import extract_video_id, get_video_metadata, fetch_korean_transcript
from gemini_service import extract_and_enrich_words, WordItem

# Load environment variables from .env if present
load_dotenv()

app = FastAPI(
    title="Korean Vocab Extractor for YouTube",
    description="YouTubeの韓国語動画字幕から学習レベルに応じた単語を抽出し、日本語の意味と韓国語例文を生成するWebアプリ",
    version="1.0.0"
)

# Enable CORS for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExtractRequest(BaseModel):
    youtube_url: Optional[str] = Field(None, description="YouTube動画のURLまたはID")
    raw_text: Optional[str] = Field(None, description="直接入力された韓国語テキスト（字幕なし動画などのフォールバック用）")
    level: str = Field(default="intermediate", description="目標学習レベル (beginner, intermediate, advanced, all)")
    gemini_api_key: Optional[str] = Field(None, description="クライアントから渡されたGemini APIキー")
    youtube_api_key: Optional[str] = Field(None, description="クライアントから渡されたYouTube Data APIキー")

class VideoInfo(BaseModel):
    video_id: str
    title: str
    channel: str
    thumbnail_url: str
    url: str

class ExtractResponse(BaseModel):
    video_info: Optional[VideoInfo] = None
    level: str
    total_count: int
    words: List[WordItem]
    transcript_preview: Optional[str] = None

class ExportCsvRequest(BaseModel):
    words: List[WordItem]
    filename: Optional[str] = "korean_vocabulary.csv"

@app.get("/api/config")
def get_config_status():
    """Check if environment variables are configured on the server."""
    env_gemini = bool(os.getenv("GEMINI_API_KEY"))
    env_youtube = bool(os.getenv("YOUTUBE_API_KEY"))
    return {
        "has_server_gemini_key": env_gemini,
        "has_server_youtube_key": env_youtube
    }

@app.post("/api/extract", response_model=ExtractResponse)
def extract_words_endpoint(req: ExtractRequest):
    """
    1. Extract YouTube transcript (or use raw text)
    2. Call Gemini API to extract vocabulary by level
    3. Return deduplicated word list with meanings and examples
    """
    # 1. Resolve Gemini API Key
    gemini_key = req.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(
            status_code=400,
            detail="Gemini APIキーが設定されていません。右上の「APIキー設定」または環境変数に設定してください。"
        )

    youtube_key = req.youtube_api_key or os.getenv("YOUTUBE_API_KEY")

    full_text = ""
    video_info = None

    # Case A: YouTube URL provided
    if req.youtube_url and req.youtube_url.strip():
        video_id = extract_video_id(req.youtube_url)
        if not video_id:
            raise HTTPException(
                status_code=400,
                detail="有効なYouTube URLまたは動画IDを入力してください。"
            )

        # Default metadata fallback
        meta: dict = {
            "video_id": video_id,
            "title": f"YouTube Video ({video_id})",
            "channel": "YouTube",
            "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "description": ""
        }
        try:
            fetched_meta = get_video_metadata(video_id, youtube_key)
            if fetched_meta:
                meta.update(fetched_meta)
            video_info = VideoInfo(**meta)
        except Exception as e:
            print(f"[Warning] Failed to fetch metadata: {e}")
            video_info = VideoInfo(**meta)

        # Fetch Korean transcript with fallback to title and description
        try:
            transcript_data = fetch_korean_transcript(video_id)
            full_text = transcript_data["full_text"]
        except ValueError as e:
            # Check if video title or description contains Korean characters
            title_text = str(meta.get("title") or "")
            desc_text_content = str(meta.get("description") or "")
            has_korean = bool(re.search(r'[\uac00-\ud7a3]', f"{title_text} {desc_text_content}"))
            desc_text = f"{title_text}\n{desc_text_content}".strip()
            if has_korean and len(desc_text) >= 15:
                # Use description and title as fallback text so extraction succeeds
                full_text = desc_text
                print(f"[Info] Subtitle restricted. Used video description as fallback for {video_id}")
            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"{str(e)}（動画の概要欄や韓国語の文章を「テキスト直接入力」タブに貼り付けるとすぐに抽出できます）"
                )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"字幕の取得中に予期せぬエラーが発生しました: {str(e)}"
            )

    # Case B: Direct Korean text provided
    elif req.raw_text and req.raw_text.strip():
        full_text = req.raw_text.strip()
    else:
        raise HTTPException(
            status_code=400,
            detail="YouTubeのURLまたは韓国語テキストのいずれかを入力してください。"
        )

    # Validate extracted text length
    if len(full_text.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="解析対象の韓国語テキストが短すぎます。"
        )

    # Extract words with Gemini API
    try:
        enriched_words = extract_and_enrich_words(
            text=full_text,
            level=req.level,
            api_key=gemini_key
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"単語抽出中にエラーが発生しました: {str(e)}"
        )

    # Format into Pydantic models
    word_items = [WordItem(**w) for w in enriched_words]

    return ExtractResponse(
        video_info=video_info,
        level=req.level,
        total_count=len(word_items),
        words=word_items,
        transcript_preview=full_text[:300] + ("..." if len(full_text) > 300 else "")
    )

@app.post("/api/export-csv")
def export_csv_endpoint(req: ExportCsvRequest):
    """
    Generate CSV file formatted with UTF-8 BOM for Japanese Excel compatibility.
    Columns: 単語, 漢字, 品詞, 発音, 日本語意味, 韓国語例文, 例文訳, レベル
    """
    output = io.StringIO()
    # Write UTF-8 BOM
    output.write('\ufeff')
    writer = csv.writer(output)

    # Header
    writer.writerow(["韓国語単語", "漢字表記", "品詞", "発音(カタカナ)", "日本語意味", "韓国語例文", "例文の日本語訳", "学習レベル"])

    for item in req.words:
        writer.writerow([
            item.word,
            item.hanja or "",
            item.part_of_speech,
            item.pronunciation,
            item.meaning,
            item.example_ko,
            item.example_ja,
            item.level
        ])

    output.seek(0)
    response = StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8"
    )
    raw_filename = req.filename or "korean_vocabulary.csv"
    filename = raw_filename if raw_filename.endswith(".csv") else f"{raw_filename}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

# Serve static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Korean Vocab Extractor Backend is running. Please access static files."}
