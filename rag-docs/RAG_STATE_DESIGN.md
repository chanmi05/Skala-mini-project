# RAG 노드·State 정의 전략

작성일: 2026-10-23 (Asia/Seoul)  
상태: 2026-10-25 다섯 묶음 State와 기억 그래프를 코드에 반영했다. 아래 타입 예시는 최초 설계 초안이며 현재 계약은 [세션 RAG 사용법](SESSION_RAG_WORKFLOW_USAGE.md)을 참고한다.

## 1. 기본 원칙

State는 **이번 질문을 처리하는 데 필요한 작업 상태**다. 세션 전체 대화를 보관하는 DB와 구분한다.

| 구분 | 내용 | 유지 범위 |
|---|---|---|
| 세션 기억 | 전체 대화 원문·누적 요약·확정 조건 | 하나의 대화 세션 |
| 그래프 State | 이번 요청의 기억 스냅샷·질문·검색·판정·응답 | 질문 한 건 |
| 실행 의존성·설정 | 모델·문서 저장소·세션 저장소·횟수/시간/토큰 제한 | 서비스 구성 |
| 요청 Runtime | 호출 수·토큰·지연·단계 기록 | 질문 한 건 |

현재 합의한 기억 전략은 최근 완료 5턴 우선 참조, 필요 시 요약 최대 1회 조회다.
1턴은 사용자 질문과 최종 응답 한 쌍이다. 오래된 대화는 세션 저장소에 남기고,
최근 범위 밖의 대화는 누적 요약으로 유지한다. 기억은 사실 근거가 아니라 문맥 해석에 사용한다.

## 2. 전체 노드 흐름

```text
API 입력 검증
 → 세션 스냅샷 조회
 → LangChain 입력 분류
     ├─ 인사/명확한 범위 밖 → 공통 결과
     └─ 문서 질문 또는 문맥 확인이 필요한 입력 → LangGraph
          resolve_recent
             ├─ ready → prepare_query
             ├─ load_summary → load_summary → resolve_with_summary
             │                                  ├─ ready → prepare_query
             │                                  └─ clarify → 확인 질문
             └─ clarify → 확인 질문

          prepare_query → retrieve → prepare_context → assess_evidence
                                                       ├─ sufficient → generate_answer
                                                       ├─ clarify → 확인 질문
                                                       ├─ insufficient → rewrite_query → retrieve
                                                       └─ 한도/무진전 → abstain
 → 공통 결과 구성
 → 완료 턴 저장
 → 필요 시 누적 요약 갱신 (같은 요청 예산 안에서 완료 대기)
 → output 및 요약 갱신 상태 반환
```

요약 조회는 문서 검색 전 한 번만 수행한다. 문서 검색 실패를 요약 조회 사유로 사용하지 않는다.
모호한 문서 입력을 라우터에서 즉시 종료하지 않아야 요약 조회 경로가 동작한다.
원문 저장과 요약 갱신은 세션 계층의 책임이며 문서 재검색 루프에 넣지 않는다.

## 3. 다섯 묶음의 State

```python
class RagState(TypedDict, total=False):
    request: RequestState
    memory: MemoryState
    interpretation: InterpretationState
    retrieval: RetrievalState
    result: ResultState
```

아래 코드는 필드 계약의 초안이다. 실행 코드가 아니며 import·전체 유효성 검사를 생략했다.
total=False는 단계에 따라 아직 없는 필드를 표현하며 잘못된 값을 자동으로 검증하지 않는다.
외부 입력과 모델 판정에는 별도 Pydantic 검증을 적용한다.

### 3.1 request: 요청 원문과 식별

```python
class RequestState(TypedDict):
    request_id: str
    original_question: str
```

- original_question은 변경하지 않는다.
- request_id는 재전송 시 완료 턴 중복 저장을 방지하는 데 사용한다.
- 사용자 인증 객체·API 키·모델 객체를 넣지 않는다.

### 3.2 memory: 이번 요청에서 읽는 세션 기억

```python
class MemoryState(TypedDict, total=False):
    session_id: str
    session_version: int
    recent_history: list[Turn]       # 최근 완료 5턴
    session_facts: dict             # 사용자가 명시·확정한 조건과 출처 턴
    summary_checked: bool
    summary_status: Literal["unchecked", "loaded", "empty"]
    summary: str | None
    summary_until_turn_id: int | None
```

최근 이력과 확정 조건은 요청 시작 시 스냅샷으로 읽는다. 요약 내용은 필요할 때만 가져온다.
세션 버전은 조회와 저장 사이의 충돌을 감지하는 데 사용한다. 전체 원문은 State에 복사하지 않는다.

session_facts에는 사용자 발언으로 확인한 적용 대상·선택·명시적 정정 등을 저장한다.
값마다 출처 턴을 남기고 도메인별 필드는 실제 데이터 계약 뒤 확정한다.
이전 assistant 답변을 검증된 사실로 저장하거나 모델이 추측한 조건을 확정하지 않는다.

### 3.3 interpretation: 무엇을 묻는지 해석

```python
class InterpretationState(TypedDict, total=False):
    memory_action: Literal["ready", "load_summary", "clarify"]
    missing_reference: str | None
    standalone_question: str
    clarification_question: str | None
```

| action | 조건 |
|---|---|
| ready | 질문 대상과 의도를 최근 문맥에서 독립 질문으로 표현 가능 |
| load_summary | 과거 대화의 대상이 필요하나 최근 문맥에는 없음 |
| clarify | 사용자에게 새 정보를 받아야 하거나 요약 조회 후에도 대상이 불명확 |

ready이면 standalone_question이 필수다. load_summary에는 missing_reference,
clarify에는 clarification_question이 필수다. 요약 확인 후 load_summary는 다시 허용하지 않는다.

세 질문 필드의 차이:

- 원질문: ‘그럼 신청은?’
- 독립 질문: ‘육아휴직 신청 방법은?’
- 검색 질의: ‘육아휴직 신청 절차 제출 서류’

독립 질문은 문맥 해석 뒤 유지하고, 검색 질의만 재검색에 맞게 바꾼다.
원질문과 해석한 질문을 함께 보존해 모델의 조건 변경·추가를 점검한다.

### 3.4 retrieval: 검색·컨텍스트·근거 판단

```python
class RetrievalState(TypedDict, total=False):
    search_query: str
    previous_queries: list[str]
    search_count: int
    current_documents: list[tuple[Document, float]]
    messages: list[BaseMessage]
    sources: list[dict]
    previous_evidence_ids: list[str]
    evidence_decision: Literal["sufficient", "insufficient", "clarify"]
    missing_information: list[str]
```

**missing_reference와 missing_information을 구분한다.**

- missing_reference: ‘아까 말한 두 번째 제도’가 무엇인지 모름 → 기억 조회/확인 질문.
- missing_information: 제도는 알지만 신청 기간을 문서에서 찾지 못함 → 문서 재검색/유보.

search_count는 실제 시작한 검색 시도를 센다. 검색이 시작된 경우 재검색 횟수는
search_count - 1로 파생시켜 중복 상태를 줄인다. retry_count를 따로 저장한다면
두 값의 불변식을 검사해야 한다.

현재 문서·메시지·출처는 회차마다 교체한다. 이전 질의와 근거 식별값은 중복·무진전 판정용이다.
근거 충분성은 실제 생성에 사용할 메시지·출처를 대상으로 판정하며 생성 시 다시 검색하지 않는다.
자료를 여러 회차에 걸쳐 병합하는 정책은 기본 구현에 포함하지 않는다.

### 3.5 result: 최종 결과

```python
class ResultState(TypedDict, total=False):
    status: Literal[
        "answered", "clarification_needed", "no_evidence",
        "greeting", "out_of_scope", "error",
    ]
    output: str
    reason_code: str
```

외부 응답은 result의 output과 status, 최종 사용 출처, session_id 등 필요한 필드만 구성한다.
내부 State·요약·Runtime 전체를 응답하지 않는다. 서비스는 output과 같은 문자열의 호환 answer를
함께 반환한다. 기존 API·화면과의 연결 계약은 후속 작업이다.

확인 질문과 유보도 최종 응답이므로 다음 대화 이해를 위해 세션에 기록한다.
시스템 오류는 실패 이벤트로 구분하고 정상 상담 답변처럼 요약하지 않는다.
취소된 요청은 완료 턴으로 세지 않는다.

## 4. 노드별 읽기·쓰기 계약

| 노드 | 읽기 | 쓰기 |
|---|---|---|
| resolve_recent | request, memory의 최근 이력·확정 조건 | interpretation |
| load_summary | memory의 세션 ID·버전·조회 여부 | memory의 요약·범위·조회 상태 |
| resolve_with_summary | request, memory의 최근 이력·조건·요약 | interpretation: ready 또는 clarify |
| prepare_query | 독립 질문, 확정된 검색 조건 | retrieval의 최초 질의·카운터 |
| retrieve | 검색 질의·검색 설정 | 현재 문서·횟수·이전 질의 |
| prepare_context | 현재 문서·입력 예산 | 메시지·출처 |
| assess_evidence | 독립 질문·현재 메시지·출처 | 충분성·부족한 사실·이전 근거 식별값, 필요 시 확인 질문 |
| rewrite_query | 독립 질문·부족한 사실·이전 질의 | 새 검색 질의 |
| generate_answer | 검토된 메시지·출처 | result |
| clarify | 필요한 사용자 확인 내용 | result |
| abstain | 한도·근거 부족·무진전 사유 | result |

각 노드는 자신에게 할당된 필드만 바꾼다. 모델 출력으로 State 전체를 덮어쓰지 않는다.
분류·근거 모델은 허용된 판정만 반환하고 반복 카운터·세션 키·실행 경로 검증은 코드가 관리한다.

## 5. 중첩 상태 갱신 규칙

중첩 묶음은 내부 키까지 자동 병합된다고 가정하지 않는다. 기본 덮어쓰기 채널에서
부분 필드만 반환하면 같은 묶음의 다른 필드가 사라질 수 있다.

```python
# 잘못된 예: memory의 session_id·recent_history 등이 사라질 수 있음
return {"memory": {"summary_checked": True}}

# 권장: 기존 묶음을 보존한 전체 새 값 반환
return {
    "memory": {
        **state["memory"],
        "summary_checked": True,
        "summary_status": "loaded",
        "summary": loaded_summary,
    }
}
```

현재 설계는 직렬 노드 흐름을 전제로 한다. 같은 묶음을 병렬 노드가 동시에 쓰는 경우
충돌·유실을 고려해 소유 필드 분리나 명시적 reducer가 필요하다. 모든 목록에
무조건 append reducer를 붙이지 않는다.

| 필드 | 갱신 방식 |
|---|---|
| 원질문·요청 ID | 고정 |
| 세션 버전·최근 이력·확정 조건 | 요청 시작 시 고정 스냅샷 |
| 요약·조회 상태 | 최대 1회 조회 결과 반영 |
| 독립 질문 | 문맥 해석 후 고정 |
| 검색 질의 | 재검색 시 변경 |
| 현재 문서·메시지·출처·판정 | 회차별 교체 |
| 이전 질의 | 실제 검색 시작 시 새 리스트로 누적 |
| 최종 응답 | 종료 노드에서 작성 |

## 6. State 밖에 둘 항목

- 모델·문서 저장소·세션 저장소 클라이언트: 서비스 의존성 주입.
- 최근 5턴·요약 조회 1회·재검색 기본 1회/최대 2회: 실행 설정.
- 호출 횟수·토큰·지연·단계 이벤트: 요청 Runtime.
- 전체 원문·요약 생성·만료·중복 저장 방지: 세션 관리 계층.

State에 session_id가 있다는 사실만으로 세션 접근을 허용하지 않는다.
요약 조회 노드는 서버가 확정한 세션을 사용하고 모델이 임의의 세션 ID를 만들게 하지 않는다.

## 7. 종료·저장·일관성 원칙

- 요약 조회 최대 1회와 문서 재검색 횟수는 독립적으로 제한한다.
- 같은 질의 또는 같은 근거·같은 부족 정보가 반복되면 조기 종료한다.
- 전체 시간·호출·입력 예산은 바깥 분류부터 합산한다.
- 잘못된 모델 판정·저장소 장애·요약 조회 오류를 근거 부족으로 바꾸지 않는다.
- 완료 턴 저장은 request_id로 중복을 막고, 세션 버전 또는 순서 보장으로 충돌을 처리한다.
- 최근 5턴을 벗어난 미요약 구간만 증분 요약하고 요약과 처리 위치를 함께 갱신한다.
- 요약 갱신 실패 시 원문·기존 요약·처리 위치를 보존하고 기억 불완전 상태를 숨기지 않는다.
- 세션 종료·만료 시 해당 세션 기억을 정리한다. 사용자별 장기 기억으로 자동 전환하지 않는다.

## 8. 구현 전 검증할 불변식

1. 원질문은 어떤 노드에서도 변경하지 않는다.
2. 요약 조회 후에는 다시 load_summary로 전이하지 않는다.
3. search_count는 실제 검색 시작과 일치하며 설정된 총 검색 횟수를 넘지 않는다.
4. 생성에 사용한 messages/sources와 근거 판정의 대상이 일치한다.
5. 중첩 상태 갱신 후 다른 필드가 유실되지 않는다.
6. 서로 다른 요청·세션의 State와 Runtime이 섞이지 않는다.
7. 확인 질문의 output과 저장한 assistant 응답이 일치한다.
8. 과거 assistant 답변을 문서 근거로 사용하거나 sources에 위장하지 않는다.

기억 경계·요약 실패·정정·동시 요청과 검색·출처·시간 제한을 모의 테스트로 검증하고,
실제 다중 턴 대화에서 문맥 복원과 과도한 요약 조회·확인 질문도 평가한다.

## 9. 현재 코드와의 차이 및 다음 결정 사항

현재 `rag_state.py`는 다섯 묶음 State를 사용한다. 노드 갱신·MemoryDecision·세션 저장·증분 요약도 연결했다. `retry_count`는 응답에서 파생하고, `summary_is_current`와 코드 소유 판정 사유를 추가했다. `session_facts`는 빈 예약 필드다. 새 서비스는 output과 호환 answer를 반환하지만 기존 FastAPI·화면 계약은 아직 변경하지 않았다.

다음 논의는 기억과 질문 해석 묶음부터 확정하는 순서를 권장한다.

- session_facts에 유지할 도메인별 조건과 출처·정정 규칙.
- 세션 저장 위치·수명·동시 요청·버전 관리 정책.
- 요약 최대 크기와 최근 대화 입력 예산.
- 중첩 갱신 헬퍼·State 초기화·결과 정규화 방식.
- 기존 answer/response와 output의 전환 범위.

관련 문서:

- [세션 기억·요약 조회 그래프 구체화](LANGGRAPH_MEMORY_WORKFLOW_PLAN.md)
- [현재 라우터·문서 그래프 구현](RAG_ROUTER_WORKFLOW_USAGE.md)

최초 작성은 설계 저장만 수행했다. 2026-10-25 구현 및 모의 통합 검증을 진행했으며 실제 외부 모델 다중 턴 평가와 API 연결은 남아 있다.
