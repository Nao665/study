# 韓国語学習用 YouTube単語抽出ウェブアプリ (K-Word Studio)

YouTubeの韓国語動画字幕から、学習者の目標レベル（初級・中級・上級）に合わせた重要単語をGemini APIで自動抽出し、重複を排除した上で「日本語の意味」「発音(カタカナ)」「韓国語の実践例文」「例文の日本語訳」を生成・表示するWebアプリケーションです。

---

## 🌟 主な機能

1. **YouTubeリンクからの字幕自動取得**:
   - 通常URL、短縮URL（`youtu.be`）、埋め込みURLに対応
   - YouTube Data API v3 による動画タイトル・サムネイル・メタデータ取得
   - `youtube-transcript-api` による公式字幕および自動生成字幕の抽出
   - 字幕のない動画や外部テキストに対応した「直接テキスト入力モード」も搭載

2. **Gemini APIによる目標レベル別単語抽出**:
   - **初級** (TOPIK 1〜2級相当): 日常生活の基本語彙、挨拶、基礎動詞・形容詞
   - **中級** (TOPIK 3〜4級相当): 日常会話を発展させた表現、感情・意見、仕事や慣用句
   - **上級** (TOPIK 5〜6級相当): ニュース、時事問題、専門用語、四字熟語、高級語彙
   - **全レベル**: 動画内の重要語彙を網羅的にバランスよく抽出

3. **自動重複排除 & 辞書形への正規化**:
   - 活用された動詞・形容詞（例: 「먹었어요」「좋네요」）を原形（「먹다」「좋다」）に統一
   - 重複する単語を自動で完全排除

4. **学習に役立つ情報の付与**:
   - 単語（ハングル）＋ 漢字語の場合は漢字表記
   - 発音（連音化などを考慮したカタカナ表記）
   - 品詞（動詞、形容詞、名詞、副詞など）
   - 簡潔で自然な日本語の意味
   - 実践的な韓国語の例文 ＋ 例文の日本語訳

5. **リッチでモダンな学習UI**:
   - **ネイティブ音声読み上げ (Web Speech API)**: 単語と例文の韓国語発音をワンクリックで再生可能
   - **カード表示 / テーブル表示切り替え**
   - **品詞別フィルター & キーワード検索**
   - **CSVエクスポート** (Excelで文字化けしないUTF-8 BOM付き)
   - **Ankiインポート用TSVコピー**

---

## 🚀 起動方法

### 1. APIキーの準備
- **Gemini APIキー** (必須): [Google AI Studio](https://aistudio.google.com/app/apikey) より無料で取得できます。
- **YouTube Data API v3 キー** (任意): [Google Cloud Console](https://console.cloud.google.com/apis/credentials) から取得可能（未設定でも自動フォールバックが動作します）。

`.env.example` をコピーして `.env` を作成し、キーを入力してください:
```bash
copy .env.example .env
```
※ APIキーはWebブラウザ右上の「APIキー設定」モーダルから直接入力・保存することも可能です（LocalStorageに保持されます）。

### 2. アプリの起動
Windows環境の場合、`start.bat` をダブルクリックするか、ターミナルで以下を実行します:

```powershell
.venv\Scripts\python.exe run.py
```

ブラウザで以下のURLを開きます:
👉 **http://localhost:8000**

## ☁️ Web（Render等）への無料デプロイ手順

このアプリは、Render などのクラウドサービスに無料でデプロイして全世界に公開できます。

### Renderでのデプロイ手順
1. **GitHubにコードをプッシュ**:
   ```bash
   git add .
   git commit -m "Update YouTube subtitle engine and cloud deployment config"
   git push origin main
   ```
2. **Render (render.com) にログイン**:
   - 「New +」 -> **「Web Service」** を選択
   - GitHubリポジトリを選択
3. **設定を入力**:
   - **Name**: `korean-vocab-extractor` (任意)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
4. **Environment Variables（環境変数）の設定**:
   - `GEMINI_API_KEY`: Google AI Studioで取得したAPIキー（※クライアント側で個別入力させる場合は省略可能）
   - `PYTHON_VERSION`: `3.10.0`
   - `YOUTUBE_COOKIES` (任意・推奨): YouTubeのIPブロックを完全に回避したい場合、ブラウザ拡張機能（例: "Get cookies.txt LOCALLY"）で取得したYouTubeのNetscape形式クッキーテキストをここに貼り付けると、クラウドIPでもBot判定を回避できます。
5. **「Deploy Web Service」** をクリック！
   - 数分でデプロイが完了し、`https://xxxx.onrender.com` でアクセス可能になります。

---

## 🛡️ YouTubeのIPブロック（Bot判定）対策について

クラウドサーバー（RenderやAWS等）のIPアドレスは、YouTube側からBotアクセスとして制限される場合があります。本アプリでは以下の多層防御により、**100%確実に単語抽出を行える仕組み**を整えています：

1. **`yt-dlp` クライアントエミュレーション**: 最新のクライアントIDをシミュレートし、直接取得率を大幅向上。
2. **Cookie & Proxy自動注入**: `YOUTUBE_COOKIES` または `cookies.txt` を設定することで完全回避。
3. **動画概要欄・タイトル自動解析**: 字幕が制限された場合でも、動画の韓国語概要欄から自動抽出。
4. **YouTube文字起こしアシスト機能**:
   - 万が一YouTubeから直接取得が拒絶された場合、画面に案内モーダルが自動表示されます。
   - YouTube動画ページで「文字起こしを表示」→「コピー」し、ワンクリックで本アプリの「テキスト直接入力」タブに貼り付けて解析できます（ユーザーのブラウザIPはブロックされないため100%成功します）。
