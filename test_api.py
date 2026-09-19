import unittest
from fastapi.testclient import TestClient
from main import app
from youtube_service import extract_video_id

class TestKoreanVocabApp(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_youtube_url_parsing(self):
        cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120s", "dQw4w9WgXcQ"),
        ]
        for url, expected in cases:
            self.assertEqual(extract_video_id(url), expected, f"Failed on URL: {url}")

    def test_api_config(self):
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("has_server_gemini_key", data)
        self.assertIn("has_server_youtube_key", data)
        self.assertIn("has_youtube_cookies", data)

    def test_export_csv(self):
        payload = {
            "words": [
                {
                    "word": "공부하다",
                    "hanja": "工夫하다",
                    "pronunciation": "コンブハダ",
                    "part_of_speech": "動詞",
                    "meaning": "勉強する",
                    "example_ko": "매일 한국어를 공부해요.",
                    "example_ja": "毎日韓国語を勉強します。",
                    "level": "初級"
                }
            ],
            "filename": "unit_test.csv"
        }
        resp = self.client.post("/api/export-csv", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.headers["Content-Type"])
        # Check UTF-8 BOM
        self.assertTrue(resp.content.startswith(b'\xef\xbb\xbf'))
        content_text = resp.content.decode('utf-8')
        self.assertIn("공부하다", content_text)
        self.assertIn("勉強する", content_text)

    def test_extract_missing_key_validation(self):
        # When no API key is provided and server has none, should return 400 with helpful message
        payload = {
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "level": "beginner"
        }
        resp = self.client.post("/api/extract", json=payload)
        # If server has no key in env, it responds 400
        if resp.status_code == 400:
            self.assertIn("Gemini APIキー", resp.json().get("detail", ""))

if __name__ == "__main__":
    unittest.main()
