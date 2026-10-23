# 독립 RAG 모듈 사용법

작성일: 2026-10-23

## 구현 범위

`rag-code-template_ext/rag_agent.py`에 검색·컨텍스트·답변 로직을 구현했다.
기존 서버·화면·저장소·업로드 API는 수정하지 않았다. 현재 실행 중인 `/rag-query`는
여전히 기존 함수를 사용한다.

- 문서 저장소와 LLM을 인자로 받는다. 파일 로딩·청킹·색인은 수행하지 않는다.
- 웹/PDF 분기가 없다. PDF에서 만들어진 청크 저장소를 연결하면 된다.
- import 시 서버 실행이나 외부 API 호출이 발생하지 않는다.
- 완성된 답변을 반환하는 기존 전략이다. 음성용 스트리밍·대화 이력은 이번 구현에 포함하지 않았다.

## 함수

```python
result = await answer_question(
    question="Transformer의 핵심 구조는 무엇인가요?",
    vectorstore=vectorstore,
    llm=llm,
    top_k=5,
    max_input_tokens=6000,
    timeout_seconds=45,
)
```

`rag_agent.py`를 import할 수 있는 경로에서 `from rag_agent import answer_question`으로 사용한다.
저장소와 LLM은 호출자가 준비한다. 모듈에서 API 키나 FAISS 파일 경로를 관리하지 않는다.

| 인자 | 계약 |
|---|---|
| `question` | 공백 제거 후 1~4,000자 |
| `vectorstore` | `asimilarity_search_with_score(question, k=...)` 또는 동기 동등 메서드 제공 |
| 검색 결과 | `(Document, raw_score)` 목록. Document에 `page_content`, `metadata`가 있어야 함 |
| `llm` | `ainvoke(messages)` 또는 `invoke(messages)` 제공, 결과에 `.content` 존재 |
| `top_k` | 정수 1~50, 기본 5. 요청값을 그대로 검색에 전달 |
| `max_input_tokens` | 지시문·질문·메타데이터·본문을 포함한 전체 입력 토큰 예산, 기본 6,000 |
| `timeout_seconds` | 검색·컨텍스트·생성 전체 제한 시간, 기본 45초 |
| `count_tokens` | 선택적 동기 함수. 메시지 목록의 토큰 수 반환. 생략 시 `llm.get_num_tokens_from_messages` 사용 |

입력 예산에 모델의 출력 토큰 수는 포함되지 않는다. 호출자가 실제 모델의 컨텍스트
한도와 출력 여유를 고려해 설정해야 한다. LLM 클라이언트의 출력 한도·네트워크 시간 제한도
별도로 설정한다. 토큰 계산은 모델의 카운터에 의존하며 서버가 계산한 실제 사용량과
차이가 있을 수 있다. 다른 모델을 연결할 때는 해당 모델에 맞는 카운터를 제공한다.

비동기 메서드가 있으면 우선 사용하고, 동기 메서드는 스레드에서 실행한다.
주입한 비동기 메서드 자체가 이벤트 루프를 막지 않는지는 해당 구현의 책임이다.

## 반환값

```python
{
    "answer": "어텐션을 기반으로 합니다. [S1]",
    "retrieved_count": 5,
    "sources": [
        {
            "id": "S1",
            "chunk_id": "c1",  # 제공되지 않으면 None
            "metadata": {"source": "manual.pdf", "chunk_id": "c1"},
            "text": "LLM에 제공한 해당 청크의 전체 원문",
            "score": 0.25,
        }
    ],
}
```

위 값은 예시다. `retrieved_count`는 저장소 반환 건수이며 `sources`는 실제 컨텍스트에
포함한 근거다. 빈 본문·중복·예산 초과 청크는 제외될 수 있다. 출처 목록이 전부 답변에서
인용되었다는 의미는 아니다. 점수는 저장소의 원시 점수이며 확률·정확도·신뢰도가 아니다.

청크 ID는 `metadata.chunk_id`를 우선 사용하고 없으면 `Document.id`를 사용한다.
중복 판단에는 청크 ID·전체 메타데이터·본문을 함께 사용한다. 같은 본문이라도 출처나
적용 대상이 다르면 유지한다. 페이지·조항 등을 새로 추정하지 않는다.

예산을 넘는 청크는 자르지 않고 건너뛰며 후속 후보를 확인한다. 자료가 전혀 없거나
어떤 청크도 담을 수 없으면 LLM을 호출하지 않고 근거 없음 안내와 빈 `sources`를 반환한다.
`retrieved_count > 0`인데 출처가 비어 있으면 본문·예산·입력 계약을 점검한다.

## 오류와 취소

| 결과 | 의미 |
|---|---|
| `ValueError` | 잘못된 질문·검색 개수·예산·시간 제한 |
| `RetrievalError` | 검색 실패 |
| `ContextError` | 토큰 계산·문서 구조 오류 또는 지시문·질문만으로 예산 초과 |
| `GenerationError` | 생성 실패·빈 텍스트·존재하지 않는 `[S숫자]` 출처 인용 |
| `TimeoutError` | 전체 처리 시간 초과 |
| `asyncio.CancelledError` | 호출자 취소, 그대로 전파 |

HTTP 상태 코드는 독립 모듈에서 결정하지 않는다. 기존 서버 연결 시 API 계층에서
검증 실패·제공자 실패·시간 초과 등을 적절한 상태로 매핑한다. 예외 원인은 체인으로
보존하며 외부 응답에 제공자 오류 원문을 무조건 노출하지 않는다.

동기 작업 스레드는 시간 초과나 취소 이후에도 실행 중일 수 있다. 실행 중인
동기 작업을 강제 종료하지 않으므로 제공자 클라이언트에도 시간 제한을 설정해야 한다.
모듈 자체의 자동 재시도는 없다. 제공자 SDK의 재시도 정책은 별도다.

출처 ID 유효성 검사는 `[S1]` 형식을 대상으로 하며, 인용이 실제 주장과 일치하는지까지
검증하지 않는다. 관련성이 낮은 검색 결과도 반환될 수 있다. 프롬프트의 근거 부족·자료 내
명령 무시 지시는 정확성이나 공격 방어를 보장하지 않는다. 실제 평가가 필요하다.

## 기존 API 연결 예시 — 아직 적용하지 않음

```python
from rag_agent import answer_question

# 기존 rag_query 내부에서 준비한 PDF 저장소·LLM을 전달
result = await answer_question(
    question=rag_request.prompt,
    vectorstore=vectorstore,
    llm=llm,
    top_k=rag_request.top_k,
)
return AnswerResponse(
    prompt=rag_request.prompt,
    response=result["answer"],
)
```

이는 기존 응답 필드만 유지하는 최소 연결 예시다. 출처·검색 건수를 화면에 제공하려면
`AnswerResponse`에 해당 필드를 추가하고 HTML도 같은 계약으로 맞춰야 한다.
웹 요청을 이 문서 전용 함수에 자동 연결하지 않는다.

## 검증

프로젝트 루트에서 실행:

```bash
cd rag-code-template_ext
.venv/bin/python -B -m unittest discover -s tests -v
```

가짜 저장소·모델로 테스트 9개 통과:

- 질문 정리·`top_k`·출처 전달
- 잘못된 입력에서 검색 생략
- 빈 결과·공백 본문에서 생성 생략
- 전체 청크 유지·중복 제거·출처 구분·입력 예산
- 예산에 청크가 들어가지 않을 때 생성 생략
- 검색·컨텍스트·생성 오류 구분과 잘못된 인용 차단
- 구조화된 텍스트 응답 처리
- 동기 저장소·LLM 대체 경로와 이벤트 루프 차단 방지
- 시간 초과·취소 전파

이 테스트는 외부 API나 기존 저장소를 사용하지 않는다.
이후 실제 OpenAI·FAISS 연결 평가 24개와 평가 로직 테스트 5개를 추가해 검증했다.
전체 오프라인 테스트는 14개이며 실제 결과는 [최초 평가 기록](RAG_BASELINE_EVALUATION.md)을 참고한다.
기존 API·화면에 새 모듈을 연결하는 작업은 아직 수행하지 않았다.
