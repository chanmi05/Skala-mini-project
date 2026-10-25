# 실제 RAG API 업로드·대화 점검

기존 원본 인덱스와 분리한 임시 인덱스에서 실제 OpenAI 임베딩·LLM을 호출했다.

| 단계 | HTTP | 상태 |
|---|---|---|
| query_before | 200 | answered |
| upload | 200 | ok |
| stale_session | 409 | 검색 문서가 갱신되었습니다. 새 대화를 시작해 주세요. |
| query_after | 200 | answered |
| followup | 200 | answered |
| end | 200 | ok |
| closed_session | 404 | 대화를 찾을 수 없습니다. |

원본 인덱스 유지: True

전체 응답은 results.json에 보관했다. 생성한 임시 인덱스는 검증 종료 시 정리했다. 사용자 로그인·음성 인식·TTS는 이 평가에 포함하지 않았다.
