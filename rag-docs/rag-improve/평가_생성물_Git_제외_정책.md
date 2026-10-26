# 평가 생성물 Git 제외 정책

- 적용일: 2026-10-26 (Asia/Seoul)
- 대상 브랜치: `rag-improve`
- 기존 추적 파일 중 생성물 161개, 총 3,384,644바이트(약 3.38MB)를 Git 추적에서 제외한다.
- 로컬 파일은 유지한다. 기존 커밋 이력을 다시 쓰지 않고 새 커밋으로 반영한다.

## 제외 대상

| 경로 | 기존 추적 파일 수 | 내용 |
|---|---:|---|
| `rag-code-template_ext/rag-service/evaluation/runs/`의 Markdown 이외 파일 | 156 | JSON 132개, JSONL 22개, 테스트 출력 TXT 2개 |
| `rag-code-template_ext/rag-service/evaluation/comparisons/`의 Markdown 이외 파일 | 1 | 비교 집계 JSON |
| `rag-code-template_ext/rag-service/evaluation/inspections/`의 Markdown 이외 파일 | 2 | 점검 JSON·스크린샷 PNG |
| `rag-code-template_ext/rag-service/evaluation/corpus.jsonl` | 1 | 인덱스에서 내보낸 코퍼스 스냅샷 |
| `data/eval/result.csv` | 1 | 검색 평가 실행 결과 |

`runs/`에는 `Q01.json`~`Q32.json`, `results.json`, `results.jsonl`, `manifest.json`, `summary.json`, `comparison.json`, `comparison_context.json`, `agent_review.json`, 리뷰 사본·템플릿, 질문 스냅샷, 테스트 표준 출력 등이 포함된다. 앞으로 같은 출력 디렉터리에 생성되는 파일도 같은 규칙으로 제외한다.

## 유지 대상

- 평가 입력·기대값: `data/eval/eval_set.csv`, `evaluation/questions.jsonl`.
- RAG 서비스 코드와 자동 테스트, 평가·비교 Python 스크립트.
- `evaluation/runs/`, `comparisons/`, `inspections/` 아래 Markdown 보고서.
- `rag-docs/rag-improve/`의 개선 전달·전후 비교 문서와 작업기록.
- 프로젝트 설정 JSON, 프런트엔드 이미지, 공유 FAISS 인덱스. 전역 `*.json` 제외 규칙은 추가하지 않는다.

## 새 체크아웃에서의 사용

원자료는 저장소에서 받지 않는다. 실행이 필요하면 평가 README의 명령으로 새 출력 폴더를 생성한다. 기존 실행을 다시 집계하려면 해당 실행의 로컬 원자료가 필요하다. `corpus.jsonl`도 신뢰하는 인덱스에서 export 명령으로 다시 생성할 수 있다.

Markdown 보고서의 과거 수치는 보존하지만 원자료가 함께 배포된다는 의미는 아니다. 실제 API 재실행은 별도 비용과 외부 전송이 발생한다.

## 적용 시점의 정확한 추적 제외 목록

아래는 이번 커밋에서 추적을 제외한 161개의 경로다. 이후 생성물은 `.gitignore` 규칙으로 처리한다.

<details>
<summary>전체 경로 161개</summary>

```text
data/eval/result.csv
rag-code-template_ext/rag-service/evaluation/comparisons/topk_20261023/comparison.json
rag-code-template_ext/rag-service/evaluation/corpus.jsonl
rag-code-template_ext/rag-service/evaluation/inspections/hr_20261025/console.png
rag-code-template_ext/rag-service/evaluation/inspections/hr_20261025/inspection.json
rag-code-template_ext/rag-service/evaluation/runs/baseline_20261023/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/baseline_20261023/questions.snapshot.jsonl
rag-code-template_ext/rag-service/evaluation/runs/baseline_20261023/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/baseline_20261023/reviews.agent.jsonl
rag-code-template_ext/rag-service/evaluation/runs/baseline_20261023/reviews.template.jsonl
rag-code-template_ext/rag-service/evaluation/runs/baseline_20261023/summary.json
rag-code-template_ext/rag-service/evaluation/runs/hr_api_20261025T103549689810Z/results.json
rag-code-template_ext/rag-service/evaluation/runs/hr_api_20261025T104231003137Z/results.json
rag-code-template_ext/rag-service/evaluation/runs/hr_api_20261025T105257588628Z/results.json
rag-code-template_ext/rag-service/evaluation/runs/hr_api_20261025T120016925120Z/results.json
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T102526546206Z/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T102526546206Z/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T102635771515Z/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T102635771515Z/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T102809241670Z/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T102809241670Z/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T103003089794Z/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T103003089794Z/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T103346192426Z/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T103346192426Z/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T103448686359Z/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T103448686359Z/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T105257260569Z/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/hr_session_20261025T105257260569Z/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_fixture/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_fixture/results.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q01.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q02.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q03.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q04.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q05.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q06.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q07.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q08.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q09.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q10.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q11.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q12.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q13.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q14.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q15.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q16.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q17.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q18.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q19.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q20.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q21.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q22.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q23.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q24.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q25.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q26.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q27.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q28.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q29.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q30.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q31.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/Q32.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/after_live/results.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/agent_review.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_fixture/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_fixture/results.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q01.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q02.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q03.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q04.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q05.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q06.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q07.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q08.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q09.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q10.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q11.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q12.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q13.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q14.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q15.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q16.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q17.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q18.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q19.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q20.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q21.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q22.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q23.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q24.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q25.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q26.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q27.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q28.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q29.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q30.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q31.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/Q32.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_live/results.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/before_tests.txt
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/comparison.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/comparison_context.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_fixture/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_fixture/results.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q01.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q02.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q03.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q04.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q05.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q06.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q07.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q08.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q09.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q10.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q11.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q12.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q13.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q14.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q15.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q16.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q17.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q18.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q19.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q20.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q21.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q22.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q23.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q24.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q25.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q26.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q27.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q28.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q29.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q30.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q31.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/Q32.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_live/results.json
rag-code-template_ext/rag-service/evaluation/runs/improvement_20261026/final_tests.txt
rag-code-template_ext/rag-service/evaluation/runs/topk_10_20261023/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/topk_10_20261023/questions.snapshot.jsonl
rag-code-template_ext/rag-service/evaluation/runs/topk_10_20261023/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/topk_10_20261023/reviews.template.jsonl
rag-code-template_ext/rag-service/evaluation/runs/topk_10_20261023/summary.json
rag-code-template_ext/rag-service/evaluation/runs/topk_3_20261023/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/topk_3_20261023/questions.snapshot.jsonl
rag-code-template_ext/rag-service/evaluation/runs/topk_3_20261023/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/topk_3_20261023/reviews.template.jsonl
rag-code-template_ext/rag-service/evaluation/runs/topk_3_20261023/summary.json
rag-code-template_ext/rag-service/evaluation/runs/topk_7_20261023/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/topk_7_20261023/questions.snapshot.jsonl
rag-code-template_ext/rag-service/evaluation/runs/topk_7_20261023/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/topk_7_20261023/reviews.template.jsonl
rag-code-template_ext/rag-service/evaluation/runs/topk_7_20261023/summary.json
rag-code-template_ext/rag-service/evaluation/runs/workflow_smoke_20261023/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/workflow_smoke_20261023/results.jsonl
rag-code-template_ext/rag-service/evaluation/runs/workflow_smoke_20261023_v2/manifest.json
rag-code-template_ext/rag-service/evaluation/runs/workflow_smoke_20261023_v2/results.jsonl
```

</details>
