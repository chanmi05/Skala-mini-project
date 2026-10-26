# 인사규정 RAG API 연결 및 실행

갱신일: 2026-10-25 (Asia/Seoul)

기존 uvicorn 모듈명은 유지하고 구현을 `rag-service/rag_api.py`의 앱 팩토리로 옮겼다. PDF 전처리·FAISS 저장소를 세션 RagService에 연결했다. 기존 prompt/response와 음성·프론트의 answer/sources/needs_review/handoff 형식을 함께 반환한다.

## 실행과 설정

Python 3.11 이상 환경에서 `rag-code-template_ext`를 작업 디렉터리로 사용한다.

```powershell
python -m pip install -r rag-service/requirements-rag-workflow.txt
python -m uvicorn rag_external-web_pdf_closed_llm:app --host 127.0.0.1 --port 8001
```

- 콘솔: http://127.0.0.1:8001/console
- API 문서: http://127.0.0.1:8001/docs
- 상태 확인: http://127.0.0.1:8001/health

공용 `.env`는 `rag-code-template_ext/.env`다. `.env.example`에는 비밀값 없이 변수 이름과 기본 모델만 있다. 필수 OPENAI_API_KEY 외에 RAG_MODEL, OPENAI_EMBEDDING_MODEL, RAG_INDEX_PATH, CHUNK_MODE를 선택 설정한다. 기본 모델은 GPT-4o, 임베딩은 text-embedding-ada-002다. 색인과 질의의 임베딩 모델은 같아야 한다.

RAG_INDEX_PATH의 상대 경로는 API에서 `rag-code-template_ext` 기준이며 기본값은 faiss_db/pdf다. 현재 저장된 규정 인덱스 115개를 그대로 사용한다. 프로젝트용 `.venv`와 검증에 사용한 저장소 밖 Python 3.12 가상환경은 구분한다.

## HTTP 계약

| 경로 | 용도 |
|---|---|
| POST /sessions | source(pdf/web)의 새 대화 생성 |
| DELETE /sessions/{session_id} | 해당 대화 종료 |
| POST /rag-query | 세션 기억·검색·근거 판정·답변·요약 실행 |
| POST /upload-paper | multipart file로 PDF 추가 또는 같은 파일명 교체 |

```json
{
  "prompt": "출장규정 제12조의 정산 기한은?",
  "source": "pdf",
  "top_k": 5,
  "session_id": "sessions 응답의 ID",
  "request_id": "클라이언트가 질문마다 생성하는 ID"
}
```

session_id를 생략하면 대화를 생성해 응답에 반환한다. 같은 대화의 후속 질문은 그 ID를 사용한다. request_id도 생략할 수 있으나 재전송 중복 방지를 위해 클라이언트가 생성·재사용하는 것을 권장한다. 같은 소유자·source·request_id의 최초 질문 재전송도 같은 세션으로 연결한다. 같은 요청 ID에 다른 질문은 충돌이다.

응답에는 prompt, response, answer, output, status, sources, needs_review, handoff, warning, session_id, request_id, replayed, corpus_revision, summary_checked, summary_update_status, summary_is_current와 검색·호출·지연 수치가 있다. answer/response/output은 같은 문자열이다. sources는 id, chunk_id, doc, article, page, source, version을 포함하며 원문 청크·프롬프트·내부 trace는 공개 응답에 넣지 않는다.

- 422: 빈 질문, 잘못된 top_k/source, 텍스트 추출 불가 PDF 등.
- 404/410: 다른 소유자의 대화, 종료·만료된 대화.
- 409: 같은 요청의 다른 질문, source 또는 문서 인덱스 변경으로 새 대화가 필요한 경우.
- 502/503: 실제 모델·임베딩·저장소·설정 오류. 제공자 오류 원문·키는 노출하지 않는다.
- 요약만 실패하면 완료 답변을 보존하고 summary_update_status=failed 및 warning을 표시한다.

## 문서 추가·교체

PDF는 20MB 이하를 등록한다. source는 업로드 파일의 기본 이름이다. 같은 이름의 청크를 교체하고 다른 문서는 유지한다. 전처리 모드·본문 보존 규칙은 기존 pdf_pipeline을 재사용한다.

원본 FAISS를 복제해 새 자료를 임베딩하고, 별도 디렉터리에 저장을 완성한 뒤 디스크·메모리 검색 대상을 교체한다. 실패 시 기존 검색 자료를 보존한다. 진행 중인 질의는 시작 시점의 인덱스 스냅샷을 사용한다. 교체 후 이전 corpus_revision의 대화로 새 질의를 보내면 409이며 새 대화를 시작해야 한다. 콘솔은 업로드 성공 후 대화를 초기화한다.

CLI도 새 인덱스 완성 전에 기존 인덱스를 삭제하지 않도록 바꿨다. 다음 dry-run은 외부 API를 호출하거나 출력 경로를 생성하지 않는다.

```powershell
python ingest.py --dry-run --mode fixed
python ingest.py --dry-run --mode article
# 실제 임베딩이 발생하며, 기존 운영 경로와 분리해 새 인덱스에 저장한다.
python ingest.py --mode article --output-dir faiss_db/hr-validation
```

CLI는 별도 프로세스이므로 실행 중인 API의 메모리 인덱스를 자동 갱신하지 않는다. CLI 적재 결과를 쓰려면 해당 RAG_INDEX_PATH로 API를 재시작한다. 서비스 실행 중 새 문서 반영에는 /upload-paper를 사용한다.

현재의 fixed 재청킹 113개와 기존 저장 인덱스 115개가 달라 검증 중 원본을 자동 재생성하지 않았다. 스캔 PDF OCR, 모든 표/병합 셀의 완전 복원, 문서명 이외의 개정본 식별·시행일 필터는 이 작업에 포함하지 않았다.

## 화면·음성 연결

- 콘솔은 쿠키를 포함해 세션을 만들고 후속 질문에 session_id를 전달한다. 새 대화는 서버의 이전 세션을 종료한다. 답변과 문서·조항·페이지, 실제 검색 수를 표시한다.
- Vue 화면 → /voice-query-text 또는 /voice-query → /rag-query로 session_id/request_id를 전달한다. 텍스트·음성 질문이 같은 대화를 공유한다. 브라우저 취소는 늦은 응답 표시를 막지만 이미 시작된 외부 모델 호출의 중단까지 보장하지 않는다. 실패한 같은 텍스트 질문은 요청 ID를 재사용하며, 새 대화와 문서 변경 충돌에서는 이전 세션을 해제한다.
- /voice-session-end는 인증된 음성 게이트웨이를 통해 RAG 세션을 종료한다. VOICE_RAG_MODE=live와 RAG_BASE_URL=http://localhost:8001을 사용한다. JWT_SECRET은 기존 Java·음성 서버가 같은 값을 사용하도록 별도 설정한다.
- 콘솔의 웹 주제 수집 UI는 현재 API에 엔드포인트가 없어 노출하지 않는다. source=web은 이미 존재하는 웹 인덱스 질의 호환용이다.

RAG 단독 API는 기존 로컬 공개 API 성격을 유지한다. 브라우저 HttpOnly 쿠키 또는 전달된 Authorization 문자열을 기준으로 세션 소유권을 분리하지만, RAG 자체가 JWT를 검증하는 것은 아니다. 사용자 인증은 기존 Java/음성 게이트웨이의 책임이다. 배포용 직접 접근 제한·업로드 권한은 별도 적용이 필요하다. 세션과 소유권·인덱스 캐시는 한 프로세스 안에서 유지하므로 현재 실행은 단일 워커 기준이다.

## 평가와 확인 범위

- 데이터 점검: [PDF 점검 결과](../rag-code-template_ext/rag-service/evaluation/inspections/hr_20261025/report.md).
- 실제 세션 평가: evaluation/run_hr_session_evaluation.py --trust-local-index.
- 실제 API 업로드 평가: evaluation/run_hr_api_smoke.py --trust-local-index. 원본 대신 임시 인덱스에서 업로드·교체를 검증한다.
- 상세 상태와 최종 결과: [단계별 연결 결과](HR_RAG_INTEGRATION_RESULT.md).

모의 테스트와 API 실호출 결과는 구분한다. 9개 고정 질문은 개발 중 보완에 사용한 사례이며 독립된 대규모 정확도 검증은 아니다. 초안·회사 미확정 항목을 포함한 자료이므로 법률 적합성이나 실제 회사 정책 확정을 검증한 결과로 해석하지 않는다.

구조화 출력은 분기별 중첩 union과 strict schema를 사용한다. [OpenAI Structured Outputs 공식 문서](https://developers.openai.com/api/docs/guides/structured-outputs)를 참고했다.
