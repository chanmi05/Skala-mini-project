# 독립 RAG 서비스 모듈

기존 `soobin_rag` 폴더의 현재 이름은 `rag-service`다. State·세션 기억·증분 요약과 기존 FastAPI 진입점의 연결을 구현했다.
- [RAG 설계·전략 및 LangChain/LangGraph·Python 모듈 상세 설명 (`ARCHITECTURE.md`)](ARCHITECTURE.md)
- [현재 API 실행·화면 연결](../../rag-docs/HR_RAG_API_USAGE.md) 및 [세션 RAG 사용법](../../rag-docs/SESSION_RAG_WORKFLOW_USAGE.md)을 참고한다.

[환경 설정을 포함한 서비스 디렉터리 구조](../프로젝트%20구조.md)

## 경로 기준

- `rag-service/`: RAG 모듈, 테스트, 평가 스크립트·결과.
- 상위 `rag-code-template_ext/`: 공용 `requirements-e.txt`, `.env`, `faiss_db/`.
- 평가 스크립트는 파일 위치를 기준으로 공용 설정·인덱스를 찾으므로 실행 디렉터리에 영향을 받지 않는다. 명시한 CLI 상대 경로는 실행 디렉터리를 기준으로 한다.
- 과거 평가 manifest·report의 절대 경로와 코드 해시는 당시 실행 기록이므로 보존한다.

## Windows PowerShell

Python 3.11 이상을 사용한다. 저장소 루트에서 시작하며, 이미 준비된 가상환경은 그대로 사용할 수 있다.

```powershell
cd rag-code-template_ext
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r rag-service/requirements-rag-workflow.txt
.\.venv\Scripts\python.exe -B -m unittest discover -s rag-service/tests -v

# 외부 API 호출 없이 평가 CLI 로딩 확인
.\.venv\Scripts\python.exe -B rag-service/evaluation/run_evaluation.py --help
.\.venv\Scripts\python.exe -B rag-service/evaluation/run_workflow_smoke.py --help
```

macOS/Linux에서는 `.venv/bin/python`을 사용한다. 상세 평가 명령은 [평가 안내](evaluation/README.md)를 참고한다.

## Python import

`rag-service`는 폴더 이름이며 Python 패키지 이름으로 사용하지 않는다. 모듈을 직접 사용하는 프로그램은 이 폴더에서 실행하거나 해당 폴더를 `PYTHONPATH`에 추가한다. 테스트와 평가 스크립트는 자신의 위치를 기준으로 이 경로를 추가한다.

```powershell
# rag-code-template_ext에서 실행
$env:PYTHONPATH = (Resolve-Path ./rag-service).Path
.\.venv\Scripts\python.exe -c "from rag_router import RagService; from session_memory import InMemorySessionStore"
```

## 근거 검증 및 조문 지정 검색

`RagService`는 근거 평가에서 선택한 출처만 생성에 전달하고, 생성 결과의 `answered`/`no_evidence`를 구분한다. 사실 답변에는 유효한 출처 ID 인용을 요구하며, 생성 후 별도의 구조화 모델 호출로 대상·조건·수치와 인용 자료의 일치를 검토한다. 검토에서 근거 부족 또는 확인 불가로 판정하면 `no_evidence`를 반환한다. 모델 기반 검토가 사실성을 보장하는 것은 아니며 정상 답변의 과도한 유보도 평가해야 한다.

선택 출처는 생성 전에 `S1..Sn`으로 다시 번호를 매겨 완료 턴의 `source_ids` 순서와 맞춘다. 같은 요청의 재전송은 기존 저장 결과와 출처를 재사용한다. 검증 호출이 추가되어 기본 전체 모델 호출 한도는 9이며 입력·시간 예산은 기존 제한을 공유한다.

`rag_retrieval.MetadataLookup`은 취업·복리후생·근태·휴가·출장 규정의 명시적 조문 번호를 인식한다. 이 경우 FAISS의 유사도 후보 필터 대신 docstore의 메타데이터 매핑으로 조문 청크를 직접 조회한다. 매핑은 해당 `RagService`의 코퍼스 스냅샷당 한 번 만들며, 런타임에서 코퍼스 교체 시 서비스를 재생성해야 한다. 규정명 없는 조항이 여러 규정에 있으면 확인 질문을 반환한다. 없는 조항은 다른 조항으로 재검색하지 않고 유보한다. 일반 의미 검색의 기본 `top_k=5`는 유지한다. 명시적 조문 조회는 지정 조문의 모든 청크를 대상으로 하며 50개를 초과하면 검색 오류로 처리한다.

정확 조회는 `index_to_docstore_id`/`docstore.search`를 제공하는 저장소가 필요하다. 이를 지원하지 않는 저장소에 조문 지정 질문을 하면 `retrieval_error`로 처리한다. 일반 의미 검색의 기존 비동기/동기 저장소 인터페이스는 유지한다. 레거시 `rag_agent.answer_question()`에는 인용 검증이 적용되지만, 구조화 유보·생성 후 검토·조문 직접 조회는 `RagService` 경로의 기능이다.

개선 전후 실제 API·모의 테스트 비교는 [개선 비교 문서](../../rag-docs/rag-improve/RAG_서비스_개선_전후_비교_2026-10-26.md)를 참고한다.
