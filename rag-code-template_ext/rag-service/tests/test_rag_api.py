"""모의 모델·실제 FAISS로 API/업로드/세션 경계를 검증. 외부 호출 없음."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "rag-service")]
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS
import pdf_pipeline as pipeline
from rag_api import create_app
from test_memory_workflow import MemoryModel


class LocalEmbeddings(Embeddings):
    def embed_query(self, text):
        if text == "embedding failure":
            raise OSError("fixture private error")
        return [float(len(text) % 7 + 1), 1.0, 0.0]

    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]


def document(text, source="a.pdf"):
    return Document(page_content=text, metadata={"source": source, "doc": source,
                    "article": "제1조", "page": 1, "chunk_mode": "fixed"})


def parsed(source="a.pdf", text="새 규정"):
    return pipeline.ParsedDoc(source, source, "test", "1.0",
        [pipeline.Section("", "제1조", "시험", 1, [text])])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="rag-api-test-")
        self.path = Path(self.directory.name) / "index"
        self.embedding = LocalEmbeddings()
        self.store = FAISS.from_documents([document("기존 규정"), document("다른 규정", "b.pdf")],
                                         self.embedding, ids=["a.pdf::0", "b.pdf::0"])
        pipeline.save_store(self.store, self.path)
        self.model = MemoryModel()
        self.app = create_app(index_path=self.path, vectorstore=self.store, embedding=self.embedding, llm=self.model)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def query(self, **kwargs):
        return self.client.post("/rag-query", json={"prompt": "신청 방법", "source": "pdf", **kwargs})

    def test_legacy_response_and_voice_contract_and_sources(self):
        response = self.query(top_k=1)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["response"], result["answer"])
        self.assertEqual(result["answer"], result["output"])
        self.assertEqual(result["retrieved_count"], 1)
        self.assertIn("doc", result["sources"][0])
        self.assertIn("page", result["sources"][0])
        self.assertNotIn("text", result["sources"][0])
        self.assertNotIn("trace", result)
        self.assertIsInstance(result["needs_review"], bool)
        self.assertIsInstance(result["handoff"], bool)

    def test_session_owner_end_and_replay_across_top_k(self):
        sid = self.client.post("/sessions", json={"source": "pdf"}).json()["session_id"]
        first = self.query(session_id=sid, request_id="one", top_k=1).json()
        replay = self.query(session_id=sid, request_id="one", top_k=2).json()
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["model_calls"], 0)
        self.assertEqual(first["sources"], replay["sources"])
        self.assertEqual(self.model.calls.count("generate"), 1)
        outsider = TestClient(self.app)
        self.assertEqual(outsider.post("/rag-query", json={"prompt": "x", "session_id": sid}).status_code, 404)
        self.assertEqual(self.client.delete("/sessions/" + sid).status_code, 200)
        self.assertEqual(self.query(session_id=sid).status_code, 404)
        services = list(self.app.state.rag.services.values())
        self.assertIs(services[0].sessions, services[1].sessions)

    def test_initial_request_retries_reuse_session_without_explicit_session_id(self):
        first = self.query(request_id="initial").json()
        second = self.query(request_id="initial").json()
        self.assertEqual(first["session_id"], second["session_id"])
        self.assertTrue(second["replayed"])
        self.assertEqual(self.model.calls.count("generate"), 1)

    def test_input_validation(self):
        for bad in [{"prompt": " "}, {"top_k": True}, {"top_k": 0}, {"top_k": 51}, {"source": "other"}]:
            self.assertEqual(self.query(**bad).status_code, 422)
        self.assertEqual(self.model.calls, [])

    def test_summary_failure_is_visible_without_losing_completed_reply(self):
        self.model.decisions["SummaryDecision"] = [OSError("fixture failure")]
        sid = None
        for n in range(6):
            data = {"prompt": "안녕하세요!", "request_id": f"greet-{n}"}
            if sid:
                data["session_id"] = sid
            response = self.client.post("/rag-query", json=data)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            sid = result["session_id"]
        self.assertEqual(result["status"], "greeting")
        self.assertEqual(result["summary_update_status"], "failed")
        self.assertIn("요약 갱신에 실패", result["warning"])

    def test_upload_replaces_only_source_and_invalidates_old_session(self):
        sid = self.query().json()["session_id"]
        with patch.object(pipeline, "parse_pdf", return_value=parsed()):
            result = self.client.post("/upload-paper", files={"file": ("a.pdf", b"%PDF-test")})
        self.assertEqual(result.status_code, 200)
        current = self.app.state.rag.stores["pdf"]
        self.assertEqual(pipeline.count_by_source(current), {"a.pdf": 1, "b.pdf": 1})
        self.assertEqual(current.docstore.search("a.pdf::0").page_content, "제1조 시험\n새 규정")
        self.assertEqual(self.store.docstore.search("a.pdf::0").page_content, "기존 규정")
        self.assertEqual(self.query(session_id=sid).status_code, 409)
        fresh = self.query().json()
        self.assertEqual(fresh["corpus_revision"], 2)
        self.assertEqual(fresh["status"], "answered")
        reloaded = pipeline.load_store(self.path, self.embedding)
        self.assertEqual(reloaded.docstore.search("a.pdf::0").page_content, current.docstore.search("a.pdf::0").page_content)

    def test_failed_upload_keeps_memory_and_disk_snapshot(self):
        before = {p.name: p.read_bytes() for p in self.path.iterdir()}
        for method in ("embed_documents", "save_store"):
            target = self.embedding if method == "embed_documents" else pipeline
            with patch.object(pipeline, "parse_pdf", return_value=parsed()), patch.object(target, method, side_effect=OSError("fixture private error")):
                response = self.client.post("/upload-paper", files={"file": ("a.pdf", b"%PDF-test")})
            self.assertEqual(response.status_code, 502)
            self.assertNotIn("private error", response.text)
            self.assertIs(self.app.state.rag.stores["pdf"], self.store)
            self.assertEqual(self.app.state.rag.revision, 1)
            self.assertEqual(before, {p.name: p.read_bytes() for p in self.path.iterdir()})

    def test_empty_text_and_bad_file_are_rejected(self):
        with patch.object(pipeline, "parse_pdf", return_value=pipeline.ParsedDoc("x", "x", "", "", [])):
            response = self.client.post("/upload-paper", files={"file": ("x.pdf", b"%PDF-test")})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.post("/upload-paper", files={"file": ("x.exe", b"x")}).status_code, 400)
        self.assertEqual(self.client.post("/upload-paper", files={"file": ("x.pdf", b"")}).status_code, 413)

    def test_atomic_save_rolls_back_when_publish_fails(self):
        before = {p.name: p.read_bytes() for p in self.path.iterdir()}
        original = Path.rename
        def rename(path, destination):
            if "-stage-" in path.name:
                raise OSError("fixture publish failure")
            return original(path, destination)
        with patch.object(Path, "rename", rename), self.assertRaises(OSError):
            pipeline.save_store(self.store, self.path)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.path.iterdir()})
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_unrelated_files_are_not_overwritten(self):
        (self.path / "keep.txt").write_text("keep")
        with self.assertRaises(ValueError):
            pipeline.save_store(self.store, self.path)
        self.assertEqual((self.path / "keep.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
