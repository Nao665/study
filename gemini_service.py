import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class WordItem(BaseModel):
    word: str = Field(description="韓国語の単語（動詞・形容詞は必ず辞書形「-다」で記載）")
    hanja: Optional[str] = Field(default="", description="漢字語の場合の漢字表記。純粋な固有語や外来語の場合は空文字")
    pronunciation: str = Field(description="カタカナでの標準的な発音表記")
    part_of_speech: str = Field(description="品詞（名詞、動詞、形容詞、副詞、感嘆詞、助詞など）")
    meaning: str = Field(description="日本語での意味・訳語")
    example_ko: str = Field(description="その単語を使った自然で実用的な韓国語例文")
    example_ja: str = Field(description="韓国語例文の日本語訳")
    level: str = Field(description="該当レベル（初級、中級、上級）")

class WordExtractionResult(BaseModel):
    words: List[WordItem] = Field(description="抽出・重複排除された単語リスト")

# Priority modern Gemini models in order of trial
CANDIDATE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.0-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite"
]

LEVEL_DESCRIPTIONS = {
    "beginner": "初級（TOPIK 1〜2級レベル）: 日常会話の基本語彙、挨拶、家族、買い物、基本的な動詞・形容詞など",
    "intermediate": "中級（TOPIK 3〜4級レベル）: 日常生活で困らない程度の会話、感情・意見表現、仕事・社会生活に関する単語、慣用句など",
    "advanced": "上級（TOPIK 5〜6級レベル）: ニュース、時事問題、専門用語、抽象的な概念、四字熟語、高度な慣用表現など",
    "all": "全レベル: 初級から上級まで、テキストに出てくる重要かつ有用な語彙をバランスよく抽出"
}

def get_candidate_models(client: genai.Client, preferred_model: Optional[str] = None) -> List[str]:
    """
    Get a prioritized list of Gemini models, attempting to dynamically query
    available models for the API key to avoid deprecated/unavailable models.
    """
    candidates: List[str] = []
    if preferred_model:
        candidates.append(preferred_model)

    # First add our known modern models
    for m in CANDIDATE_MODELS:
        if m not in candidates:
            candidates.append(m)

    # Try dynamically listing models to discover active models for this account
    try:
        discovered: List[str] = []
        for model_info in client.models.list():
            m_name = getattr(model_info, 'name', '') or ''
            clean_name = m_name.replace("models/", "")
            if not clean_name:
                continue
            if "gemini" in clean_name.lower():
                discovered.append(clean_name)

        # Sort discovered: put flash-lite or flash first, newer versions first
        def model_sort_key(name: str):
            is_flash_lite = "flash-lite" in name.lower()
            is_flash = "flash" in name.lower() and not is_flash_lite
            is_pro = "pro" in name.lower()
            tier = 0 if is_flash_lite else (1 if is_flash else (2 if is_pro else 3))
            v_match = re.search(r'gemini-(\d+(?:\.\d+)?)', name.lower())
            version = float(v_match.group(1)) if v_match else 0.0
            return (tier, -version)

        discovered_sorted = sorted(discovered, key=model_sort_key)
        # Put discovered models at the front of candidates
        for m in reversed(discovered_sorted):
            if m in candidates:
                candidates.remove(m)
            candidates.insert(0, m)
    except Exception as e:
        print(f"[Info] Could not list models dynamically ({e}), using default candidate list.")

    return candidates

def extract_and_enrich_words(
    text: str,
    level: str,
    api_key: str,
    model_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract vocabulary matching the target level from Korean text using Gemini API,
    normalize to dictionary forms, deduplicate, and provide meanings & examples in Japanese.
    """
    if not api_key:
        raise ValueError("Gemini APIキーが設定されていません。右上の「APIキー設定」から入力してください。")

    level_desc = LEVEL_DESCRIPTIONS.get(level, LEVEL_DESCRIPTIONS["intermediate"])

    prompt = f"""
あなたは韓国語教育および語学学習の専門家です。
以下の韓国語テキストを分析し、学習者の目標レベルに最も適した重要単語を抽出してください。

【目標学習レベル】
{level_desc}

【要件・ルール】
1. **レベルの適合性**: 指定された目標レベルに合致する単語のみを厳選して抽出してください。
2. **辞書基本形への正規化**: 
   - 活用された動詞・形容詞は、必ず原形（辞書形「〜다」）に直してください（例: 「먹었어요」→「먹다」、「좋네요」→「좋다」）。
   - 名詞についている助詞（〜은/는, 〜이/가, 〜을/를, 〜에, 〜에서 など）は除去して名詞単体で抽出してください。
3. **完全な重複排除**: 同じ単語（または同じ原形）を絶対に複数回抽出しないでください。
4. **学習に役立つ情報の付与**:
   - `word`: 韓国語の単語（原形）
   - `hanja`: 漢字語の場合は漢字表記（例: 学校→學校、約束→約束）、固有語・外来語は空文字 ""
   - `pronunciation`: 日本人学習者にわかりやすいカタカナ発音表記（連音化や鼻音化を反映した実際の発音に近いもの）
   - `part_of_speech`: 品詞（名詞、動詞、形容詞、副詞など）
   - `meaning`: 簡潔で自然な日本語の意味
   - `example_ko`: テキストの文脈または学習に最適な実用的で自然な韓国語例文
   - `example_ja`: 例文の自然な日本語訳
   - `level`: 初級 / 中級 / 上級 のいずれか
5. **抽出単語数（できる限り多く網羅的に抽出）**:
   - 動画・テキスト全体から、学習価値のある重要単語を **できる限り多く網羅的（目標：80個〜100個程度）** に抽出してください。
   - 動詞、形容詞、名詞、副詞、慣用表現などを余すところなく幅広く拾い上げてください。
   - テキストが非常に短い場合は、文中に含まれる重要な語彙を可能な限りすべて抽出してください。

【対象テキスト】
\"\"\"{text[:35000]}\"\"\"
"""

    client = genai.Client(api_key=api_key)

    models_to_try = get_candidate_models(client, model_name)

    response = None
    last_error = None

    for candidate in models_to_try:
        try:
            # First attempt with structured schema
            try:
                response = client.models.generate_content(
                    model=candidate,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=WordExtractionResult,
                        temperature=0.2,
                        max_output_tokens=8192,
                    ),
                )
            except Exception as schema_err:
                err_text = str(schema_err).lower()
                if "404" in err_text or "not found" in err_text or "no longer available" in err_text:
                    raise schema_err
                # Fallback to json mode without schema
                response = client.models.generate_content(
                    model=candidate,
                    contents=prompt + "\n\n必ず {'words': [...]} の形式のJSONを出力してください。",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                        max_output_tokens=8192,
                    ),
                )

            if response and (getattr(response, 'parsed', None) or getattr(response, 'text', None)):
                # Successfully received response
                break
        except Exception as e:
            err_str = str(e)
            if "404" in err_str or "not found" in err_str.lower() or "no longer available" in err_str.lower():
                last_error = e
                continue
            elif "API_KEY_INVALID" in err_str or ("400" in err_str and "key" in err_str.lower()):
                raise ValueError("無効なGemini APIキーです。Google AI Studioで正しいAPIキーを取得して設定してください。")
            elif "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                raise ValueError("Gemini APIの利用制限（レートリミットまたはクォータ上限）に達しました。少し時間を置いて再試行してください。")
            else:
                last_error = e
                continue

    if not response:
        raise ValueError(f"Gemini API呼び出しエラー: 有効なモデルが見つかりませんでした。詳細: {str(last_error)}")

    # Extract words list from parsed object or JSON text
    raw_words = []
    parsed_obj = getattr(response, 'parsed', None)
    if parsed_obj and hasattr(parsed_obj, 'words'):
        try:
            for item in parsed_obj.words:
                if hasattr(item, 'model_dump'):
                    raw_words.append(item.model_dump())
                elif isinstance(item, dict):
                    raw_words.append(item)
                else:
                    raw_words.append(dict(item))
        except Exception:
            raw_words = []

    if not raw_words:
        resp_text = getattr(response, 'text', '') or ''
        text_to_parse = resp_text.strip()
        # Clean markdown wrappers if any
        if text_to_parse.startswith("```json"):
            text_to_parse = text_to_parse[7:]
        elif text_to_parse.startswith("```"):
            text_to_parse = text_to_parse[3:]
        if text_to_parse.endswith("```"):
            text_to_parse = text_to_parse[:-3]
        text_to_parse = text_to_parse.strip()

        try:
            data = json.loads(text_to_parse)
            if isinstance(data, dict):
                raw_words = data.get("words", [])
            elif isinstance(data, list):
                raw_words = data
        except Exception as e:
            raise ValueError(f"Gemini APIの応答JSONの解析に失敗しました: {str(e)}")

    # Programmatic deduplication (safety layer)
    unique_words: List[Dict[str, Any]] = []
    seen_words = set()

    for item in raw_words:
        if isinstance(item, dict):
            w = item.get("word", "").strip()
            item_dict = item
        elif hasattr(item, "word"):
            w = getattr(item, "word", "").strip()
            item_dict = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        else:
            continue
        if not w:
            continue
        # Normalize whitespace
        w_norm = re.sub(r'\s+', ' ', w).lower()
        if w_norm in seen_words:
            continue
        seen_words.add(w_norm)
        unique_words.append(item_dict)

    return unique_words
