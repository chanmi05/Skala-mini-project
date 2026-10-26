"""음성 서버의 텍스트 경로 → 실제 RAG API 팩토리·FAISS 연결을 모의 모델로 검증."""
from pathlib import Path
import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "voice-integration-test-secret-not-production")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "rag-code-template_ext"), str(ROOT / "rag-code-template_ext/rag-service"),
               str(ROOT / "rag-code-template_ext/rag-service/tests")]
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.voice_query_router import router
from app.voice_auth import voice_identity
from app.services import voice_pipeline as pipeline
from rag_api import create_app
from test_rag_api import LocalEmbeddings, document
from test_memory_workflow import MemoryModel
from langchain_community.vectorstores import FAISS
import httpx


class IntegratedTests(unittest.TestCase):
    def test_text_followup_and_session_end_through_both_apis(self):
        embedding = LocalEmbeddings()
        vectors = FAISS.from_documents([document("테스트 규정")], embedding, ids=["a.pdf::0"])
        with tempfile.TemporaryDirectory(prefix="voice-rag-test-") as directory:
            rag = TestClient(create_app(vectorstore=vectors, embedding=embedding,
                                       llm=MemoryModel(), index_path=Path(directory) / "index"))
            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[voice_identity] = lambda: {"id": "fixture-user", "token": "fixture-token"}
            client = TestClient(app)
            seen = []
            original = httpx.Client
            def upstream(request):
                seen.append(request)
                response = rag.request(request.method, request.url.path, content=request.content,
                                       headers={"Authorization": request.headers["Authorization"], "Content-Type": "application/json"})
                return httpx.Response(response.status_code, json=response.json())
            with patch.dict(os.environ, {"VOICE_RAG_MODE": "live"}), patch.object(
                    pipeline.httpx, "Client", side_effect=lambda **kwargs: original(transport=httpx.MockTransport(upstream), **kwargs)), patch.object(pipeline, "synthesize", return_value=None):
                first = client.post("/voice-query-text", json={"question": "신청 기준?", "request_id": "one"})
                self.assertEqual(first.status_code, 200)
                sid = first.json()["session_id"]
                second = client.post("/voice-query-text", json={"question": "그럼 신청은?", "session_id": sid, "request_id": "two"})
                self.assertEqual(second.status_code, 200)
                self.assertEqual(second.json()["session_id"], sid)
                self.assertEqual(second.json()["sources"][0]["doc"], "a.pdf")
                self.assertEqual(json.loads(seen[1].content)["session_id"], sid)
                self.assertEqual(client.post("/voice-session-end", json={"session_id": sid}).status_code, 200)
                self.assertEqual(client.post("/voice-query-text", json={"question": "q", "session_id": sid}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
