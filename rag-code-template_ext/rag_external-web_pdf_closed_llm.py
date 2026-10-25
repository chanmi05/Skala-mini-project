#### 다음 실습 코드는 학습 목적으로만 사용 바랍니다. 문의 : audit@korea.ac.kr 임성열 Ph.D.

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request, Response, Body
from sqlalchemy.ext.asyncio import create_async_engine
from fastapi.responses import JSONResponse, FileResponse
from starlette.concurrency import run_in_threadpool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, ConfigDict, Field
from langchain_core.documents import Document
from pypdf import PdfReader
from langchain_core.messages import HumanMessage

from typing import List, Dict, Any, Optional, Literal
import os
import re
import sys
import json
import uuid
import asyncio
import logging
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from dotenv import load_dotenv

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# 현재 Python 파일과 같은 위치에 있는 .env 파일 및 rag-service 모듈 경로 로드
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "rag-service") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "rag-service"))

import pdf_pipeline
from rag_api import (
    RagRuntime,
    InvalidDocument,
    SessionRequest,
    client_owner,
    public_sources,
)

# 패키지는 저자 업데이트에 맞춰 해당 버전으로 맞추는 것을 권장
# 직접 저자의 site-packages/패키지명/을 직접 수정하는 것은 추천하지 않음
# 추후 pip install -U 시 원상 복구되며 버전 충돌 가능성 있음
# 참고로 다음은 Deprecated 패키지 또는 미사용 패키지 목록
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain.vectorstores import FAISS
# from langchain.chat_models import ChatOpenAI
# from langchain.embeddings import OpenAIEmbeddings
# from langchain_openai import OpenAIEmbeddings, ChatOpenAI
# from langchain_community.embeddings import OpenAIEmbeddings
# from langchain.chat_models import ChatOpenAI
# from langchain.schema import HumanMessage
# from langchain.embeddings import HuggingFaceEmbeddings
# from pydantic import BaseModel

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ✅ DB 연결 정보
ASYNC_DB_URL = os.getenv("ASYNC_DB_URL", "mysql+aiomysql://root:password@127.0.0.1:53301/sql_db?charset=utf8mb4")
engine = create_async_engine(ASYNC_DB_URL)

# ✅ FastAPI 인스턴스
app = FastAPI(
    title="RAG 기반 Closed Source LLM API Server",
    description="외부 정보 기반 벡터화 + LLM 질의 응답 (rag-service 연결)",
    version="2.0.0",
)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://[::1]:5174",  # IPv6도 허용
        "http://localhost:8008",
        "http://localhost:8001",
    ],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ✅ 전역 벡터 저장소
VECTORSTORE_WEB = None
VECTORSTORE_PDF = None

# ✅ 외부 (웹검색, OpenAI 전용)
web_path = BASE_DIR / "faiss_db" / "web"
if OPENAI_API_KEY and (web_path / "index.faiss").exists() and (web_path / "index.pkl").exists():
    VECTORSTORE_WEB = FAISS.load_local(
        str(web_path),
        embeddings=pdf_pipeline.embeddings(),
        allow_dangerous_deserialization=True,
    )
    print("✅ VECTORSTORE_WEB 로드 완료")
else:
    print("❌ VECTORSTORE_WEB 벡터화된 파일이 없습니다.")

# ✅ PDF (업로드용, OpenAI 전용)
VECTORSTORE_PDF = pdf_pipeline.load_store() if OPENAI_API_KEY else None
if VECTORSTORE_PDF is not None:
    print("✅ VECTORSTORE_PDF 로드 완료")
else:
    print("❌ VECTORSTORE_PDF 벡터화된 파일이 없습니다.")

# ✅ rag-service 런타임 연결 (세션 기억, LangChain 라우터, LangGraph 워크플로우 관리)
runtime = RagRuntime(vectorstore=VECTORSTORE_PDF)
if VECTORSTORE_WEB is not None:
    runtime.stores["web"] = VECTORSTORE_WEB
app.state.rag = runtime


# ✅ PDF 텍스트 추출
def load_paper(file_path: str) -> str:
    reader = PdfReader(file_path)
    return "\n".join(text for page in reader.pages if (text := page.extract_text()))


# ✅ 상태 확인 및 콘솔/세션 엔드포인트
@app.get("/health", tags=["시스템"])
async def health(request: Request):
    rt: RagRuntime = request.app.state.rag
    return {"status": "ok", "corpus_revision": rt.revision}


@app.get("/console", include_in_schema=False)
async def console():
    return FileResponse(pdf_pipeline.BASE_DIR / "external_index.html")


@app.post("/sessions", summary="대화 세션 생성", tags=["세션 관리"])
async def create_session(body: SessionRequest, request: Request, response: Response):
    rt: RagRuntime = request.app.state.rag
    owner = client_owner(request, response)
    try:
        sid = await rt.create_session(owner, body.source)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="RAG 설정 또는 저장소 준비 상태를 확인해 주세요.")
    return {"session_id": sid, "source": body.source, "corpus_revision": rt.revision}


@app.delete("/sessions/{sid}", summary="대화 세션 종료", tags=["세션 관리"])
async def end_session(sid: str, request: Request, response: Response):
    rt: RagRuntime = request.app.state.rag
    owner = client_owner(request, response)
    await rt.require_session(sid, owner)
    await rt.sessions.end_session(sid)
    rt.owners.pop(sid, None)
    rt.initial_requests = {key: value for key, value in rt.initial_requests.items() if value != sid}
    return {"ended": True}


# ✅ PDF 업로드 및 벡터화
@app.post("/upload-paper", summary="PDF 업로드 및 벡터화", tags=["PDF 처리"])
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    rt: RagRuntime = request.app.state.rag
    try:
        source = (file.filename or "").replace("\\", "/").split("/")[-1]
        if not source.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="PDF 파일만 등록할 수 있습니다.")

        data = await file.read(20 * 1024 * 1024 + 1)
        if not data or len(data) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="PDF는 0바이트 초과 20MB 이하로 등록해 주세요.")

        # 페이지별 추출 → 정제 → 청킹(CHUNK_MODE: fixed 500/50 | article 조문 단위) → 스냅샷 교체
        async with rt.update_lock:
            result = await run_in_threadpool(rt.upload, data, source)
            if rt is app.state.rag:
                global VECTORSTORE_PDF
                VECTORSTORE_PDF = rt.stores["pdf"]
            return JSONResponse(content=result)
    except HTTPException:
        raise
    except InvalidDocument:
        raise HTTPException(status_code=422, detail="PDF에서 검색 가능한 텍스트를 추출하지 못했습니다.")
    except Exception:
        raise HTTPException(status_code=502, detail="문서 등록에 실패했습니다. 기존 검색 자료는 유지됩니다.")
    finally:
        await file.close()


# 질의 요청/응답 모델 정의
# ✅ 질의 요청 모델
class RAGRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_by_name=True)

    prompt: str = Field(default=..., min_length=1, max_length=4000, description="질문 프롬프트")
    source: Literal["pdf", "web"] = Field(default="pdf", description="web | pdf")
    top_k: int = Field(default=5, ge=1, le=50, strict=True, description="검색할 결과 수 (기본값 5)")
    session_id: Optional[str] = Field(default=None, min_length=1, max_length=128, description="대화 세션 ID")
    request_id: Optional[str] = Field(default=None, min_length=1, max_length=128, description="요청 멱등성 ID")


# ✅ 응답 모델 (기존 prompt/response와 rag-service 확장 필드 모두 포함)
class AnswerResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: str
    response: str
    answer: Optional[str] = None
    output: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    status: Optional[str] = None
    needs_review: Optional[bool] = None
    handoff: Optional[bool] = None
    warning: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    replayed: Optional[bool] = None
    summary_checked: Optional[bool] = None
    summary_update_status: Optional[str] = None
    summary_is_current: Optional[bool] = None
    retrieved_count: Optional[int] = None
    search_count: Optional[int] = None
    retry_count: Optional[int] = None
    model_calls: Optional[int] = None
    elapsed_ms: Optional[float] = None
    reason_code: Optional[str] = None
    corpus_revision: Optional[int] = None


# 유틸
def extract_by_marker(
    text: str,
    start: str = "### ANSWER_START",
    end: str = "### ANSWER_END",
) -> str | None:
    i = text.find(start)
    if i == -1:
        return None
    j = text.find(end, i + len(start))
    if j == -1:
        return None
    return text[i + len(start) : j].strip()


# 컨텍스트가 "id:\n title:\n content:" 형태일 때의 간단 백업 파서(옵션)
def fallback_extract_from_context(context: str, question: str) -> str | None:
    q = re.sub(r"[^\w가-힣A-Za-z0-9 ]", "", question).strip()
    blocks = re.split(r"\n\s*\n", context.strip())
    for b in blocks:
        m_title = re.search(r"^title:\s*(.+)$", b, flags=re.MULTILINE | re.IGNORECASE)
        m_content = re.search(r"^content:\s*(.+)$", b, flags=re.MULTILINE | re.IGNORECASE)
        if m_title and m_content:
            t = re.sub(r"[^\w가-힣A-Za-z0-9 ]", "", m_title.group(1)).strip()
            if q.lower() in t.lower():
                return m_content.group(1).strip()
    m_any = re.search(r"^content:\s*(.+)$", context, flags=re.MULTILINE | re.IGNORECASE)
    return m_any.group(1).strip() if m_any else None


# ✅ 질의 응답 라우터 (rag-service 연결)
@app.post("/rag-query", response_model=AnswerResponse, summary="Closed Source LLM + 벡터 DB 질의", tags=["질의 응답"])
async def rag_query(request: Request, response: Response, rag_request: RAGRequest = Body(...)):
    rt: RagRuntime = request.app.state.rag
    owner = client_owner(request, response)
    sid = rag_request.session_id
    request_id = rag_request.request_id or uuid.uuid4().hex

    try:
        # 1. 벡터스토어 및 LLM 결정
        if rag_request.source == "web":
            if rt is app.state.rag and rt.stores["web"] is None and VECTORSTORE_WEB is not None:
                rt.stores["web"] = VECTORSTORE_WEB
            source = "web"

        elif rag_request.source == "pdf":
            # [Q03] 요청 출처와 검색 저장소 연결
            # [설계 판단] 사용자가 source="pdf"를 선택하면 웹 저장소가 아니라 PDF 저장소를 검색하도록 연결하세요.
            if rt is app.state.rag and rt.stores["pdf"] is None and VECTORSTORE_PDF is not None:
                rt.stores["pdf"] = VECTORSTORE_PDF
            source = "pdf"

        else:
            raise HTTPException(
                status_code=400,
                detail="❗ 외부 source는 'web', 'pdf' 중 하나여야 합니다.",
            )

        # 세션 생성 또는 기존 세션 유효성·버전 확인
        if sid is None:
            async with rt.session_start_lock:
                key = (owner, source, request_id)
                sid = rt.initial_requests.get(key)
                if sid is None:
                    sid = await rt.create_session(owner, source)
                    rt.initial_requests[key] = sid
        await rt.require_session(sid, owner, source)

        # [Q04] 질문과 유사 문서 검색 연결 & [Q05] 검색 근거를 LLM 답변으로 연결
        # rag-service의 RagService(LangChain 라우터 + LangGraph 워크플로우)를 통해
        # 대화 문맥 해석 → 상위 top_k 문서 검색 → 근거 평가/재검색 → 출처 인용 답변 생성을 수행합니다.
        service, vectorstore, revision = rt.snapshot_service(source, rag_request.top_k)
        if rt.owners.get(sid, (None, None, None))[2] != revision:
            raise HTTPException(status_code=409, detail="검색 문서가 갱신되었습니다. 새 대화를 시작해 주세요.")

        # 2. 검색 및 LLM 응답 생성 (rag-service 실행)
        result = await service.ainvoke({
            "question": rag_request.prompt,
            "session_id": sid,
            "request_id": request_id,
        })
        if result["status"] == "error":
            failures = [event.get("error_type", "unknown") for event in result["trace"] if "error_type" in event]
            logger.warning("rag_query_failed reason=%s error_types=%s", result["reason_code"], failures)
            code = 409 if result["reason_code"] == "session_conflict" else 502
            raise HTTPException(status_code=code, detail="질문 처리에 실패했습니다. 설정을 확인하거나 다시 시도해 주세요.")

        sources = public_sources(result, vectorstore)
        draft = any(
            "초안" in d.page_content or "회사 확정:" in d.page_content
            for d in vectorstore.docstore._dict.values()
        )
        warnings = []
        if draft:
            warnings.append("등록 문서에 초안 또는 회사 미확정 항목이 포함되어 있습니다.")
        if result["summary_update_status"] == "failed":
            warnings.append("대화 요약 갱신에 실패했습니다. 원문은 보관했으며 과거 참조를 다시 확인할 수 있습니다.")

        return {
            "prompt": rag_request.prompt,
            "response": result["output"],
            "answer": result["output"],
            "output": result["output"],
            "sources": sources,
            "status": result["status"],
            "needs_review": draft or result["status"] != "answered" or result["summary_update_status"] == "failed",
            "handoff": result["status"] in {"no_evidence", "out_of_scope"},
            "warning": " ".join(warnings) or None,
            **{
                key: result[key]
                for key in [
                    "session_id",
                    "request_id",
                    "replayed",
                    "summary_checked",
                    "summary_update_status",
                    "summary_is_current",
                    "retrieved_count",
                    "search_count",
                    "retry_count",
                    "model_calls",
                    "elapsed_ms",
                    "reason_code",
                ]
            },
            "corpus_revision": revision,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="RAG 설정 또는 저장소 준비 상태를 확인해 주세요.")


# 실행 명령어 예시:
# python -m uvicorn rag_external-web_pdf_closed_llm:app --host 127.0.0.1 --port 8001 --reload
