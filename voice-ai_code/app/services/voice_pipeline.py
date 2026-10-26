"""Voice pipeline. Input audio is private and removed before the RAG call."""
import hashlib
import os
import re
import subprocess
import tempfile
import time
import uuid
import wave
from pathlib import Path

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

OUTPUT_DIR = Path(__file__).resolve().parents[2] / ".voice_output"
AUDIO_TTL_SECONDS = 900

class Source(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    doc: str
    article: str | None = None
    page: int | str | None = None

class RagAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    answer: str = Field(min_length=1, max_length=12000)
    sources: list[Source]
    needs_review: bool
    handoff: bool
    warning: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    corpus_revision: int | None = None
    summary_update_status: str | None = None

class VoiceAnswer(RagAnswer):
    transcript: str
    audio_url: str | None = None
    warning: str | None = None
    mode: str
    latency_ms: int

def mask_private(text: str) -> str:
    text = re.sub(r"(?<!\d)\d{6}\s*[-–]?\s*[1-8]\d{6}(?!\d)", "[주민번호]", text)
    text = re.sub(r"(?<!\d)(?:\+82[- .]?)?0?1[016789][- .]?\d{3,4}[- .]?\d{4}(?!\d)", "[전화번호]", text)
    return text

def rag_mode() -> str:
    mode = os.getenv("VOICE_RAG_MODE", "live").lower()
    if mode not in {"mock", "demo", "live"}:
        raise HTTPException(503, "VOICE_RAG_MODE는 mock, demo 또는 live여야 합니다.")
    return mode

def ask_rag(question: str, token: str, session_id: str | None = None, request_id: str | None = None) -> RagAnswer:
    mode = rag_mode()
    if mode == "demo":
        from app.services.demo_rag import demo_answer
        return RagAnswer.model_validate(demo_answer(question))
    if mode == "mock":
        # A wiring fixture, never presented as a real regulation or citation.
        return RagAnswer(
            answer="개발용 음성 연결 테스트가 성공했습니다. 실제 규정 답변은 RAG 연동 후 제공됩니다.",
            sources=[], needs_review=True, handoff=True,
        )
    base = os.getenv("RAG_BASE_URL", "http://localhost:8001").rstrip("/")
    try:
        payload = {"prompt": question, "source": "pdf", "top_k": 4}
        if session_id:
            payload["session_id"] = session_id
        if request_id:
            payload["request_id"] = request_id
        with httpx.Client(timeout=90, follow_redirects=False, trust_env=False) as client:
            response = client.post(base + "/rag-query",
                headers={"Authorization": "Bearer " + token},
                json=payload)
        if response.status_code == 401:
            raise HTTPException(401, "RAG 인증에 실패했습니다. 다시 로그인해 주세요.")
        if response.status_code in {404, 409, 410}:
            raise HTTPException(response.status_code, "대화 또는 검색 문서가 변경되었습니다. 새 대화를 시작해 주세요.")
        response.raise_for_status()
        result = RagAnswer.model_validate(response.json())
        if not result.answer.strip():
            raise ValueError("Empty answer")
        return result
    except HTTPException:
        raise
    except (httpx.HTTPError, ValidationError, ValueError):
        raise HTTPException(503, "RAG 연결 또는 응답 형식 오류입니다. RAG 담당자와 API 계약을 확인해 주세요.")

def transcribe_private(data: bytes, suffix: str) -> str:
    # Lazy import keeps API contract tests independent of the Whisper model.
    from app.services.stt_service import transcribe_audio_file_local
    with tempfile.TemporaryDirectory(prefix="skala-voice-") as directory:
        source = Path(directory) / ("input" + suffix)
        wav = Path(directory) / "decoded.wav"
        source.write_bytes(data)
        try:
            # MediaRecorder WebM may have no duration metadata. Measure decoded WAV.
            # Decode at most 61 seconds to bound work for oversized recordings.
            subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(source),
                 "-t", "61", "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000", "-vn", str(wav)],
                capture_output=True, timeout=30, check=True)
            with wave.open(str(wav)) as decoded:
                duration = decoded.getnframes() / decoded.getframerate()
            if not 0 < duration <= 60:
                raise HTTPException(422, "녹음은 60초 이내여야 합니다.")
        except HTTPException:
            raise
        except (subprocess.SubprocessError, ValueError, wave.Error, EOFError):
            raise HTTPException(422, "오디오를 읽을 수 없습니다. 다시 녹음해 주세요.")
        except FileNotFoundError:
            raise HTTPException(503, "ffmpeg 설치가 필요합니다.")
        try:
            text = transcribe_audio_file_local(str(wav)).strip()
        except Exception:
            raise HTTPException(503, "음성 인식에 실패했습니다. 모델 준비 상태를 확인해 주세요.")
    if not text:
        raise HTTPException(422, "음성을 인식하지 못했습니다. 다시 녹음해 주세요.")
    return mask_private(text)

def owner_prefix(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:32]

def cleanup_audio() -> None:
    OUTPUT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    for path in OUTPUT_DIR.glob("*.mp3"):
        try:
            if time.time() - path.stat().st_mtime > AUDIO_TTL_SECONDS:
                path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass

def synthesize(answer: str, user_id: str) -> str:
    from app.services.tts_service import text_to_speech
    cleanup_audio()
    filename = owner_prefix(user_id) + "_" + uuid.uuid4().hex + ".mp3"
    path = OUTPUT_DIR / filename
    try:
        text_to_speech(answer, str(path))
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Empty speech")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return "/voice-audio/" + filename

def run_pipeline(data: bytes, suffix: str, identity: dict, session_id=None, request_id=None) -> VoiceAnswer:
    started = time.perf_counter()
    transcript = transcribe_private(data, suffix)
    return answer_question(transcript, identity, started, session_id=session_id, request_id=request_id)

def answer_question(question: str, identity: dict, started: float | None = None, *, session_id=None, request_id=None) -> VoiceAnswer:
    if started is None:
        started = time.perf_counter()
    transcript = mask_private(question.strip())
    if not transcript:
        raise HTTPException(422, "질문을 입력해 주세요.")
    # No raw question is logged or sent to the external LLM by this service.
    result = ask_rag(transcript, identity["token"], session_id=session_id, request_id=request_id)
    result.answer = mask_private(result.answer)
    audio_url, warning = None, result.warning
    try:
        audio_url = synthesize(result.answer, identity["id"])
    except Exception:
        warning = "음성을 생성하지 못했습니다. 텍스트 답변을 확인해 주세요."
    return VoiceAnswer(**result.model_dump(exclude={"warning"}), transcript=transcript,
        audio_url=audio_url, warning=warning, mode=rag_mode(),
        latency_ms=round((time.perf_counter() - started) * 1000))


def end_rag_session(session_id: str, token: str):
    if rag_mode() != "live":
        return {"ended": True}
    base = os.getenv("RAG_BASE_URL", "http://localhost:8001").rstrip("/")
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            result = client.delete(base + "/sessions/" + session_id,
                                   headers={"Authorization": "Bearer " + token})
        if result.status_code not in {200, 404, 410}:
            raise HTTPException(503, "대화 종료에 실패했습니다.")
    except httpx.HTTPError:
        raise HTTPException(503, "대화 종료에 실패했습니다.")
    return {"ended": True}
