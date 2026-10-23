"""No API billing, real credentials, or Whisper model needed for these tests."""
import io
import os
import sys
import tempfile
import time
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

os.environ["JWT_SECRET"] = "voice-test-only-secret-0123456789abcdef"
os.environ["VOICE_RAG_MODE"] = "mock"
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from app.jwt_config import SECRET_KEY, ALGORITHM, ISSUER
from app.routers.voice_query_router import router
from app.services import voice_pipeline as p

app = FastAPI()
app.include_router(router)

def auth(user="test-user", expired=False):
    token = jwt.encode({"sub": user, "iss": ISSUER,
                        "exp": int(time.time()) + (-10 if expired else 3600)},
                       SECRET_KEY, algorithm=ALGORITHM)
    return {"Authorization": "Bearer " + token}

def wav_data(seconds=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * seconds)
    return output.getvalue()

class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.directory = tempfile.TemporaryDirectory()
        self.output = patch.object(p, "OUTPUT_DIR", Path(self.directory.name))
        self.output.start()

    def tearDown(self):
        self.output.stop()
        self.directory.cleanup()

    def post(self, body=b"audio", filename="input.webm", headers=None):
        return self.client.post("/voice-query", files={"audio": (filename, body)},
                                headers=auth() if headers is None else headers)

    def test_auth_required(self):
        self.assertEqual(self.post(headers={}).status_code, 401)

    def test_expired_token(self):
        self.assertEqual(self.post(headers=auth(expired=True)).status_code, 401)

    def test_cookie_auth(self):
        token = auth()["Authorization"].split(" ", 1)[1]
        self.client.cookies.set("ACCESS_TOKEN", token)
        fake = types.SimpleNamespace(recognition_settings=lambda: {
            "model":"small", "language":"ko", "vocabulary_hint":True})
        with patch.dict(sys.modules, {"app.services.stt_service":fake}):
            response = self.client.get("/voice-config")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stt"]["model"], "small")

    def test_bad_extension(self):
        self.assertEqual(self.post(filename="../../input.txt").status_code, 400)

    def test_empty(self):
        self.assertEqual(self.post(body=b"").status_code, 422)

    def test_size_limit(self):
        self.assertEqual(self.post(body=b"a" * (10*1024*1024+1)).status_code, 413)

    def test_pipeline_and_private_playback(self):
        with patch.object(p, "transcribe_private", return_value="음성 테스트"):
            def synthesize(text, user):
                filename = p.owner_prefix(user) + "_" + "a"*32 + ".mp3"
                (p.OUTPUT_DIR / filename).write_bytes(b"test-mp3")
                return "/voice-audio/" + filename
            with patch.object(p, "synthesize", side_effect=synthesize):
                response = self.post()
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["mode"], "mock")
        self.assertEqual(result["sources"], [])
        self.assertIn("개발용", result["answer"])
        url = result["audio_url"]
        self.assertEqual(self.client.get(url, headers=auth()).status_code, 200)
        self.assertEqual(self.client.get(url, headers=auth("other")).status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 401)
        path = p.OUTPUT_DIR / url.rsplit("/", 1)[1]
        os.utime(path, (0, 0))
        self.assertEqual(self.client.get(url, headers=auth()).status_code, 404)

    def test_tts_failure_preserves_answer(self):
        with patch.object(p, "transcribe_private", return_value="테스트"), patch.object(
                p, "synthesize", side_effect=RuntimeError("provider failure")):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["audio_url"])
        self.assertTrue(response.json()["warning"])
        self.assertNotIn("provider failure", response.text)

    def test_stt_empty_error(self):
        with patch.object(p, "transcribe_private", side_effect=HTTPException(422, "무음")):
            self.assertEqual(self.post().status_code, 422)

    def test_rag_unavailable(self):
        with patch.object(p, "transcribe_private", return_value="테스트"), patch.object(
                p, "ask_rag", side_effect=HTTPException(503, "RAG unavailable")):
            self.assertEqual(self.post().status_code, 503)

    def test_masking(self):
        self.assertEqual(p.mask_private("010-1234-5678 900101-1234567"),
                         "[전화번호] [주민번호]")

    def test_live_contract_and_forwarded_jwt(self):
        import httpx
        seen = []
        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"answer":"실제 API 계약 테스트",
                "sources":[{"doc":"가상규정","article":"테스트조항","page":1}],
                "needs_review":False,"handoff":False})
        original = httpx.Client
        with patch.dict(os.environ, {"VOICE_RAG_MODE":"live"}), patch.object(
                p.httpx, "Client", side_effect=lambda **kw: original(
                    transport=httpx.MockTransport(handler), **kw)):
            result = p.ask_rag("질문", "sample-token")
        self.assertEqual(result.sources[0].doc, "가상규정")
        self.assertEqual(seen[0].headers["Authorization"], "Bearer sample-token")
        self.assertIn(b'"prompt"', seen[0].content)

    def test_old_rag_schema_rejected(self):
        import httpx
        original = httpx.Client
        with patch.dict(os.environ, {"VOICE_RAG_MODE":"live"}), patch.object(
                p.httpx, "Client", side_effect=lambda **kw: original(
                    transport=httpx.MockTransport(lambda req: httpx.Response(
                        200, json={"response":"old response"})), **kw)):
            with self.assertRaises(HTTPException) as cm:
                p.ask_rag("질문", "sample")
        self.assertEqual(cm.exception.status_code, 503)

    def test_real_ffmpeg_cleanup_before_rag(self):
        seen = []
        def transcribe(path):
            seen.append(Path(path))
            self.assertTrue(Path(path).is_file())
            return "010-1234-5678 음성 테스트"
        fake = types.SimpleNamespace(transcribe_audio_file_local=transcribe)
        with patch.dict(sys.modules, {"app.services.stt_service":fake}):
            result = p.transcribe_private(wav_data(), ".wav")
        self.assertIn("[전화번호]", result)
        self.assertFalse(seen[0].exists())
        self.assertFalse(seen[0].parent.exists())

    def test_corrupt_audio_cleanup(self):
        fake = types.SimpleNamespace(transcribe_audio_file_local=lambda path: "unused")
        with patch.dict(sys.modules, {"app.services.stt_service":fake}):
            with self.assertRaises(HTTPException) as cm:
                p.transcribe_private(b"not audio", ".webm")
        self.assertEqual(cm.exception.status_code, 422)

    def test_recording_over_60_seconds_rejected(self):
        fake = types.SimpleNamespace(transcribe_audio_file_local=lambda path: "unused")
        with patch.dict(sys.modules, {"app.services.stt_service":fake}):
            with self.assertRaises(HTTPException) as cm:
                p.transcribe_private(wav_data(61), ".wav")
        self.assertEqual(cm.exception.status_code, 422)

if __name__ == "__main__":
    unittest.main()
