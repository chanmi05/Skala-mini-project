"""Project API: authenticated STT -> RAG -> TTS."""
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from app.services.transcript_review import review_transcript, TranscriptReview

from app.voice_auth import voice_identity
from app.services import voice_pipeline as pipeline

router = APIRouter(tags=["프로젝트 음성"])
MAX_BYTES = 10 * 1024 * 1024

@router.get("/voice-config")
def voice_config(identity=Depends(voice_identity)):
    from app.services.stt_service import recognition_settings
    return {"mode": pipeline.rag_mode(), "max_seconds": 60, "max_bytes": MAX_BYTES,
            "stt": recognition_settings()}

@router.post("/voice-query", response_model=pipeline.VoiceAnswer)
async def voice_query(audio: UploadFile = File(...), identity=Depends(voice_identity)):
    data, suffix = await read_audio(audio)
    return await run_in_threadpool(pipeline.run_pipeline, data, suffix, identity)

@router.post("/voice-transcribe", response_model=TranscriptReview)
async def voice_transcribe(audio: UploadFile = File(...), identity=Depends(voice_identity)):
    data, suffix = await read_audio(audio)
    text = await run_in_threadpool(pipeline.transcribe_private, data, suffix)
    if len(text) > 2000:
        raise HTTPException(422, "질문은 2000자 이내로 녹음해 주세요.")
    return await run_in_threadpool(review_transcript, text)

class ConfirmedQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

@router.post("/voice-query-text", response_model=pipeline.VoiceAnswer)
def voice_query_text(body: ConfirmedQuestion, identity=Depends(voice_identity)):
    return pipeline.answer_question(body.question, identity)

async def read_audio(audio: UploadFile):
    suffix = Path(audio.filename or "").suffix.lower()
    try:
        if suffix not in {".webm", ".wav", ".m4a", ".mp4", ".ogg"}:
            raise HTTPException(400, "WebM, WAV, M4A, MP4, OGG 오디오를 사용해 주세요.")
        chunks, size = [], 0
        while chunk := await audio.read(65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise HTTPException(413, "음성 파일은 10MB 이하여야 합니다.")
            chunks.append(chunk)
        if not size:
            raise HTTPException(422, "빈 음성 파일입니다.")
        return b"".join(chunks), suffix
    finally:
        await audio.close()

@router.get("/voice-audio/{filename}", include_in_schema=False)
def voice_audio(filename: str, identity=Depends(voice_identity)):
    prefix = pipeline.owner_prefix(identity["id"])
    if not re.fullmatch(re.escape(prefix) + r"_[0-9a-f]{32}\.mp3", filename):
        raise HTTPException(404, "음성을 찾을 수 없습니다.")
    path = pipeline.OUTPUT_DIR / filename
    if not path.is_file():
        raise HTTPException(404, "음성을 찾을 수 없습니다.")
    if time.time() - path.stat().st_mtime > pipeline.AUDIO_TTL_SECONDS:
        path.unlink(missing_ok=True)
        raise HTTPException(404, "음성 재생 기간이 만료되었습니다. 다시 질문해 주세요.")
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
