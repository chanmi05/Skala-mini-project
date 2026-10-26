"""전처리 FAISS와 세션 RagService를 연결하는 FastAPI 런타임·헬퍼 모듈. import 시 외부 호출 없음."""
import asyncio
from dataclasses import replace
import hashlib
import importlib
import logging
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from pypdf.errors import PdfReadError

import pdf_pipeline
from rag_router import RagService
from rag_session import SessionCoordinator
from rag_state import RagSettings
from session_memory import InMemorySessionStore, SessionNotFoundError

logger = logging.getLogger(__name__)


class SessionRequest(BaseModel):
    source: Literal["pdf", "web"] = "pdf"


class InvalidDocument(ValueError):
    """추출할 수 없는 PDF. 저장소·모델 설정 오류와 구분한다."""


class QueryRequest(SessionRequest):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    prompt: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50, strict=True)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    request_id: str | None = Field(default=None, min_length=1, max_length=128)


def client_owner(request: Request, response: Response):
    # 기존 공개 로컬 API를 유지한다. 이 값은 세션 소유권 구분이며 사용자 인증을 대체하지 않는다.
    # 음성 서버는 검증한 Bearer를 전달하고 브라우저 콘솔은 HttpOnly 소유권 쿠키를 쓴다.
    authorization = request.headers.get("Authorization")
    if authorization:
        return hashlib.sha256(("bearer:" + authorization).encode()).hexdigest()
    cookie = request.cookies.get("RAG_CLIENT")
    if not cookie or len(cookie) != 64 or any(c not in "0123456789abcdef" for c in cookie):
        cookie = secrets.token_hex(32)
        response.set_cookie("RAG_CLIENT", cookie, httponly=True, samesite="lax", max_age=1800)
    return hashlib.sha256(("cookie:" + cookie).encode()).hexdigest()


class RagRuntime:
    def __init__(self, *, index_path=None, vectorstore=None, llm=None, embedding=None, sessions=None):
        configured = Path(index_path or os.getenv("RAG_INDEX_PATH", str(pdf_pipeline.PDF_STORE_PATH)))
        self.path = (configured if configured.is_absolute() else pdf_pipeline.BASE_DIR / configured).resolve()
        self.state_lock = threading.RLock()
        self.stores = {"pdf": vectorstore, "web": None}
        self.llm, self.embedding = llm, embedding
        self.sessions = sessions if sessions is not None else InMemorySessionStore()
        self.settings = RagSettings(summary_max_chars=2000, timeout_seconds=60)
        self.coordinator = None
        self.owners = {}
        self.initial_requests = {}
        self.session_start_lock = asyncio.Lock()
        self.services = {}
        self.revision = 1
        self.update_lock = asyncio.Lock()

    def ensure(self):
        with self.state_lock:
            self._ensure()

    def _ensure(self):
        if self.embedding is None:
            self.embedding = pdf_pipeline.embeddings()
        if self.llm is None:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model=os.getenv("RAG_MODEL", "gpt-4o"), temperature=0,
                                 max_tokens=1200, timeout=30, max_retries=0)
        if self.stores["pdf"] is None:
            self.stores["pdf"] = pdf_pipeline.load_store(self.path, self.embedding)
        if self.coordinator is None:
            self.coordinator = SessionCoordinator(self.sessions, self.llm, self.settings)

    def store(self, source):
        self.ensure()
        if source == "web" and self.stores["web"] is None:
            self.stores["web"] = pdf_pipeline.load_store(pdf_pipeline.BASE_DIR / "faiss_db/web", self.embedding)
        store = self.stores[source]
        if store is None:
            raise HTTPException(409, "검색 자료를 먼저 등록해 주세요.")
        return store

    def service(self, source, top_k):
        with self.state_lock:
            return self._service(source, top_k)

    def _service(self, source, top_k):
        store = self.store(source)
        key = (source, top_k, self.revision)
        if key not in self.services:
            self.services[key] = RagService(store, self.llm, settings=replace(self.settings, top_k=top_k),
                session_store=self.sessions, session_coordinator=self.coordinator)
        return self.services[key]

    def snapshot_service(self, source, top_k):
        with self.state_lock:
            service = self.service(source, top_k)
            return service, self.stores[source], self.revision

    async def create_session(self, owner, source):
        self.store(source)
        # 만료된 소유권 레코드도 세션 생성 시 정리한다.
        for sid in list(self.owners):
            try:
                await self.sessions.get_context(sid, touch=False)
            except SessionNotFoundError:
                self.owners.pop(sid, None)
        self.initial_requests = {key: sid for key, sid in self.initial_requests.items() if sid in self.owners}
        session = await self.sessions.create_session()
        self.owners[session.session_id] = (owner, source, self.revision)
        return session.session_id

    async def require_session(self, sid, owner, source=None):
        record = self.owners.get(sid)
        if record is None or record[0] != owner:
            raise HTTPException(404, "대화를 찾을 수 없습니다.")
        try:
            await self.sessions.get_context(sid, touch=False)
        except SessionNotFoundError:
            self.owners.pop(sid, None)
            raise HTTPException(410, "대화가 만료되었습니다. 새 대화를 시작해 주세요.")
        if source is not None and record[1] != source:
            raise HTTPException(409, "자료 유형이 바뀌었습니다. 새 대화를 시작해 주세요.")
        if source is not None and record[2] != self.revision:
            raise HTTPException(409, "검색 문서가 갱신되었습니다. 새 대화를 시작해 주세요.")

    def upload(self, data, source):
        self.ensure()
        with tempfile.TemporaryDirectory(prefix="skala-rag-upload-") as directory:
            path = Path(directory) / "input.pdf"
            path.write_bytes(data)
            try:
                parsed = pdf_pipeline.parse_pdf(path, source=source)
            except PdfReadError as exc:
                raise InvalidDocument("Unreadable PDF") from exc
        docs = pdf_pipeline.chunk(parsed)
        if not docs:
            raise InvalidDocument("PDF에서 검색 가능한 텍스트를 추출하지 못했습니다.")
        existing = self.stores["pdf"]
        candidate = pdf_pipeline.clone_store(existing) if existing is not None else None
        candidate = pdf_pipeline.upsert(candidate, docs, self.embedding)
        pdf_pipeline.save_store(candidate, self.path)
        # 저장에 성공한 뒤에만 새 요청이 보는 인덱스를 교체한다.
        with self.state_lock:
            self.stores["pdf"] = candidate
            self.revision += 1
            self.services.clear()
        return {
            "message": f"{len(docs)}개 청크 등록 완료",
            "doc": parsed.doc,
            "doc_no": parsed.doc_no,
            "chunk_mode": docs[0].metadata["chunk_mode"],
            "articles": sum(1 for sec in parsed.sections if sec.article),
            "extracted_characters": sum(len(sec.text) for sec in parsed.sections),
            "store_counts": pdf_pipeline.count_by_source(candidate),
            "preview": docs[0].page_content[:300],
            "corpus_revision": self.revision,
        }


def public_sources(result, store):
    sources = result["sources"]
    if result.get("replayed"):
        sources = []
        for number, key in enumerate(result.get("source_ids", []), 1):
            document = store.docstore.search(key)
            if not isinstance(document, str):
                sources.append({"id": f"S{number}", "chunk_id": key, "metadata": document.metadata})
    return [{"id": s["id"], "chunk_id": s.get("chunk_id"),
             "doc": str(s["metadata"].get("doc") or s["metadata"].get("source") or "등록 문서"),
             "article": s["metadata"].get("article") or None, "page": s["metadata"].get("page"),
             "source": s["metadata"].get("source"), "version": s["metadata"].get("version")}
            for s in sources]


def create_app(**kwargs):
    """테스트 및 독립 실행을 위해 진입점(rag_external-web_pdf_closed_llm.py)의 라우트를 바인딩한 FastAPI 앱을 생성한다."""
    if str(pdf_pipeline.BASE_DIR) not in sys.path:
        sys.path.insert(0, str(pdf_pipeline.BASE_DIR))
    entrypoint = importlib.import_module("rag_external-web_pdf_closed_llm")

    runtime = RagRuntime(**kwargs)
    app = FastAPI(title="세션 인사규정 RAG API", version="2.0.0")
    app.state.rag = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://localhost:5174", "http://127.0.0.1:5174",
            "http://localhost:8008", "http://localhost:8001",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    app.add_api_route("/health", entrypoint.health, methods=["GET"])
    app.add_api_route("/console", entrypoint.console, methods=["GET"], include_in_schema=False)
    app.add_api_route("/sessions", entrypoint.create_session, methods=["POST"])
    app.add_api_route("/sessions/{sid}", entrypoint.end_session, methods=["DELETE"])
    app.add_api_route("/upload-paper", entrypoint.upload_pdf, methods=["POST"])
    app.add_api_route(
        "/rag-query",
        entrypoint.rag_query,
        methods=["POST"],
        response_model=entrypoint.AnswerResponse,
    )
    return app
