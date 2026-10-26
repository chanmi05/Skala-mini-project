# 실제 저장소 기반 RAG 기준 평가

기존 서버를 실행하거나 변경하지 않고 `rag_agent.answer_question()`을 직접 평가한다.
원본 PDF 추출·청킹·재색인은 수행하지 않는다.

## 파일

| 파일 | 내용 |
|---|---|
| `run_evaluation.py` | 실제 FAISS·OpenAI 연결, 후보 기록, 지표 계산, 리포트 생성 |
| `corpus.jsonl` | 기존 저장소에서 API 없이 내보낸 44개 청크와 원래 문서 ID |
| `questions.jsonl` | 원문 청크를 확인해 작성한 질문 24개와 기대 근거·답변 요점 |
| `runs/baseline_20261023/` | 실제 실행 결과와 에이전트의 1차 답변 검토 |

질문은 생성 답변을 보기 전에 작성했다. 정답 기준과 리뷰는 Codex가 작성했으며
독립적인 사람의 검증을 받지 않았다. 한 논문·한국어 질문 중심의 소규모 기준 평가다.
운영 정확도나 일반적인 성능 수치로 해석하지 않는다.

## 실행

저장소 루트에서 아래처럼 `rag-code-template_ext`로 이동해 실행한다. `.venv`와 기존 requirements를 사용한다.
API 키는 환경변수 또는 `rag-code-template_ext/.env`에서 읽고 결과에 저장하지 않는다.

Windows PowerShell 설치·실행 예시는 [RAG 모듈 안내](../README.md)를 참고한다. 아래 예시는 macOS/Linux용이다.

```bash
cd rag-code-template_ext

# 로컬 원문 목록 확인: 외부 API 호출 없음
.venv/bin/python -B rag-service/evaluation/run_evaluation.py \
  --trust-local-index --export-corpus rag-service/evaluation/corpus.jsonl

# 실제 평가: 질문 임베딩과 답변 생성에 OpenAI API 사용
# --output을 생략하면 새 시각 이름의 디렉터리를 자동 생성
.venv/bin/python -B rag-service/evaluation/run_evaluation.py --trust-local-index

# 기존 결과와 리뷰로 리포트만 재생성: 외부 API 호출 없음
.venv/bin/python -B rag-service/evaluation/run_evaluation.py \
  --summarize rag-service/evaluation/runs/baseline_20261023 \
  --reviews rag-service/evaluation/runs/baseline_20261023/reviews.agent.jsonl

# 외부 API 없이 평가 계산·기록과 RAG 로직 테스트
.venv/bin/python -B -m unittest discover -s rag-service/tests -v
```

`--trust-local-index`는 신뢰하는 기존 pickle 저장소를 읽겠다는 옵션이다. 실행 시
이 프로젝트의 기존 FAISS 파일에 사용했으며, 외부에서 받은 임의의 pickle에는 사용하지 않는다.
이미 존재하는 평가 출력 폴더는 덮어쓰지 않는다.

기본 설정은 `gpt-4o`, temperature=0, 출력 최대 600토큰, `top_k=5`, 입력 예산
6,000토큰, 질문별 전체 제한 60초, 순차 실행이다. SDK 재시도는 0으로 설정한다.
임베딩은 기존 서버 기본값과 동일한 `text-embedding-ada-002`를 명시했다.
원래 인덱스에는 임베딩 모델 정보가 없어 과거 적재 모델을 메타데이터로 증명할 수는 없다.

## 평가 질문 및 근거 정의

- 답변 가능 20개: 구조, 수치, 이유, 비교, 여러 근거, 표현 변경 질문.
- 답변 불가 4개: 환불, 정확한 전력량, 영어-한국어 BLEU, 고객지원 번호.
- `expected_evidence_groups`: 내부 목록은 대체 가능한 근거 ID, 그룹 간에는 함께 필요한 정보.
- `expected_points`: 사람이 검토할 때 비교할 핵심 요점. 문자열 일치로 자동 채점하지 않는다.
- 원문 ID는 FAISS docstore의 기존 UUID를 사용한다. 인덱스를 다시 만들면 ID가 달라질 수 있으므로
  해당 인덱스에 맞게 정답 기준을 새로 검증해야 한다.

기준을 수정할 때 과거 실행의 `questions.snapshot.jsonl`은 유지한다. 결과를 본 뒤 정답 기준을
바꾸어 과거 지표를 조용히 개선하지 않는다. 새 버전으로 기록하고 변경 이유를 남긴다.

## 기록 및 검증

`RecordingStore`는 새 함수가 실제 수행한 검색을 한 번만 가로채 후보를 기록한다.
추가 검색으로 평가 결과와 실제 답변 근거가 달라지지 않도록 했다. 반환 문서만 복제해
기존 UUID를 `chunk_id`에 넣으며 원본 메타데이터·저장소에는 쓰지 않는다.

| 산출물 | 의미 |
|---|---|
| `manifest.json` | 인덱스·질문·모듈 해시, 모델 설정, 패키지 버전, 저장소 불변 확인 |
| `questions.snapshot.jsonl` | 해당 실행 시점의 평가 기준 복사본 |
| `results.jsonl` | 질문·답변, 후보 전체·점수, 사용 출처, 검색·생성·전체 시간, 사용 토큰·오류 |
| `reviews.template.jsonl` | 판정이 비어 있는 리뷰 양식 |
| `reviews.agent.jsonl` | Codex의 1차 검토. 결과 파일 해시와 판정 이유 포함 |
| `summary.json` | 자동 검색 지표와 명시적으로 제공된 리뷰 집계 |
| `report.md` | 실행 설정·질문별 결과·검토를 읽을 수 있는 문서 |

`search_ms`에는 질문 임베딩과 FAISS 검색이 포함된다. `generation_ms`는 LLM 호출부터
완성 응답까지이며 첫 토큰 시간이 아니다. `total_ms`는 컨텍스트 구성도 포함한다.
시간 초과 시 실제로 이미 소비한 호출 비용은 취소로 환불되는 것이 아니다.

## 지표 해석

- **Hit@k**: 사전에 지정한 기대 근거가 검색 후보 상위 k개에 하나 이상 있는 질문 비율.
- **근거 그룹 재현율**: 각 질문의 필요한 근거 그룹 중 하나 이상 충족한 그룹 비율을 평균.
- **컨텍스트 그룹 재현율**: 검색 후보가 아닌 실제 LLM 전달 근거에 같은 계산 적용.
- **MRR**: 첫 기대 근거의 검색 순위 역수 평균.

검색 지표는 성공한 답변 가능 질문만 집계하며 호출 오류는 별도 보고한다. 답변 불가 질문에는
기대 근거가 없으므로 검색 지표를 계산하지 않는다. 필요하면 실패를 0점으로 포함하는 운영
지표를 별도 정의해야 한다.

답변의 정답 여부(`answer_correct`), 전달 근거 충실성(`grounded`), 답변 불가 질문의
유보 여부(`abstained`)는 별도 리뷰다. 기본 실행은 이 값들을 null로 두며, 리뷰 파일을
제공해야 집계한다. 사람이 검토할 때는 양식 복사본에 reviewer와 판정 이유를 작성한다.
기존 `reviews.agent.jsonl`은 사람의 판정으로 표시하지 않는다.

## 최초 결과

- 실제 실행 성공: 24/24, 오류 0.
- 답변 가능 질문 Hit@5: 13/20, **65%**.
- 근거 그룹 및 컨텍스트 그룹 재현율: 각각 **65%**.
- 전체 처리 시간 중앙값: **약 1.78초**. STT/TTS·네트워크 화면 전달을 포함하지 않는다.
- 에이전트 1차 검토에서 답변 불가 질문 4개 모두 유보.
- q09는 원문 내용과 대체로 맞는 답을 했으나 검색된 근거에는 위치 인코딩 설명이 없고,
  인용한 청크도 그 주장을 뒷받침하지 않았다. 정답 여부와 근거 충실성을 분리해야 하는 사례다.
- 인덱스 파일의 실행 전후 해시 동일 확인.

상세 결과는 [최초 리포트](runs/baseline_20261023/report.md)를 참고한다.

## 검색 개수 비교

기존 k=5를 보존하고 k=3, 7, 10 각각 24개 질문을 추가 실행했다.
RAG 모듈·질문·모델·인덱스·컨텍스트 예산은 동일하게 유지했다.

```bash
# 각 값 실행: 출력 폴더는 기존에 없는 이름으로 지정한다.
.venv/bin/python -B rag-service/evaluation/run_evaluation.py --trust-local-index \
  --top-k 7 --output rag-service/evaluation/runs/topk_7_new

# 완료된 실행을 로컬에서 집계한다. API 호출 없음.
.venv/bin/python -B rag-service/evaluation/compare_runs.py \
  --runs rag-service/evaluation/runs/topk_3_20261023 \
         rag-service/evaluation/runs/baseline_20261023 \
         rag-service/evaluation/runs/topk_7_20261023 \
         rag-service/evaluation/runs/topk_10_20261023 \
  --output rag-service/evaluation/comparisons/topk_new
```

`compare_runs.py`는 같은 조건의 완결된 실행인지 확인한 후 검색 지표·지연·실제
사용 토큰·컨텍스트 개수와 질문별 검색 성공을 비교한다. 기존 출력 폴더는 덮어쓰지 않는다.
답변 정확도는 검색률에서 추정하거나 서로 다른 리뷰 집계로 비교하지 않는다.
k=5는 과거 실행 결과여서 지연·캐시·공급자 변동을 통제한 성능 실험은 아니다.


## 인사규정 세션·업로드 실제 평가 (2026-10-25)

기존 논문 질문·결과는 보존한다. 현재 기본 PDF 인덱스는 인사규정 115개이므로 논문용 questions.jsonl을 그대로 실행하지 않는다. 소규모 규정 평가는 다음 명령을 사용한다. 실제 OpenAI 호출과 사용량이 발생한다.

```powershell
# rag-code-template_ext에서, Python 3.11 이상 환경
python -B rag-service/evaluation/run_hr_session_evaluation.py --trust-local-index
python -B rag-service/evaluation/run_hr_api_smoke.py --trust-local-index
```

각 명령은 새 결과 폴더를 만들며 원본 인덱스를 보존한다. API 업로드는 별도 임시 인덱스에서만 수행한다. 실패한 개발 실행도 결과 폴더에 남아 있으며 최종 실행은 [연결 결과 문서](../../../rag-docs/HR_RAG_INTEGRATION_RESULT.md)에 지정했다.

## 2026-10-26 개선 전후 평가

- `evaluate_improvement.py`: 기본은 외부 API가 없는 고정 모의 사례 8개. `--live`는 32문항 CSV로 실제 OpenAI 임베딩·모델 API를 호출하므로 규정 자료 전송과 비용이 발생한다.
- 실행 예: 부모 `rag-code-template_ext`에서 `.venv/bin/python rag-service/evaluation/evaluate_improvement.py --output /tmp/new-fixture-run`.
- 실제 평가 예: 같은 명령에 `--live --cases ../data/eval/eval_set.csv --top-k 5`를 추가한다. 출력 폴더는 새 경로여야 한다. 신뢰하는 로컬 FAISS pickle만 사용한다.
- 각 실행은 질문별 원문 답변·출처·trace, 코드/인덱스/질문 해시와 실행 설정을 보존한다. 단일 질문마다 새 세션을 쓰고 동시성은 2다.
- `RAG_REVIEW_CODE_ROOT`를 별도 코드 스냅샷 경로로 지정하면 해당 소스를 불러와 비교할 수 있다. 평가 스크립트·환경·인덱스는 현재 작업 경로를 사용한다.
- `compare_improvement.py runs/improvement_20261026`: 인덱스·질문·모델·k가 같은지 확인한 뒤 `comparison.json`, `case_comparison.md`를 생성한다. 에이전트 검토는 결과 해시와 연결해 다른 실행에 재사용하지 않는다.
- `run_evaluation.py`는 레거시 `rag_agent` 기준선 도구다. 이번 개선의 구조화 생성·검증·기억 경로는 `evaluate_improvement.py`의 `RagService` 경로로 평가한다.
- 실제 API 전송은 이번 작업에서 사용자에게 명시적으로 승인받았다. 기존 실행 원자료는 `runs/improvement_20261026/`에 있다. 현재 32문항은 개발 중 확인한 자료이며 미사용 holdout은 아니다.


## Git에 저장하는 범위

질문·기대값과 평가 코드, Markdown 보고서는 유지한다. `runs/`, `comparisons/`, `inspections/` 아래 Markdown 이외의 생성물과 내보낸 `corpus.jsonl`은 로컬에만 보관한다. 검색 평가의 `data/eval/result.csv`도 제외한다. 위의 원자료 경로는 로컬 실행 위치를 설명하며 새 체크아웃에서 제공되는 파일을 뜻하지 않는다. `--summarize` 및 `compare_improvement.py` 실행에는 해당 실행의 로컬 결과·검토 파일이 필요하다. 원자료가 없으면 새 출력 폴더로 평가를 실행하거나 코퍼스를 export해야 한다.

정확한 제외 목록은 [평가 생성물 Git 제외 정책](../../../rag-docs/rag-improve/평가_생성물_Git_제외_정책.md)에 기록했다.
