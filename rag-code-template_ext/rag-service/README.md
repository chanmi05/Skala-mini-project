# 독립 RAG 서비스 모듈

기존 `soobin_rag` 폴더의 현재 이름은 `rag-service`다. State·세션 기억·증분 요약 연결은 구현했으며, 기존 FastAPI 서버와의 연결은 아직 구현하지 않았다. [세션 RAG 사용법](../../rag-docs/SESSION_RAG_WORKFLOW_USAGE.md)을 참고한다.

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
