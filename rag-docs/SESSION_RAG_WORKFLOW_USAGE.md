# 세션 기억을 연결한 RAG 사용법

작성일: 2026-10-25 (Asia/Seoul)

문서의 다섯 묶음 State를 코드에 반영하고 SessionStore·최근 대화 해석·조건부 요약 조회·증분 요약을 연결했다. 현재 FastAPI·음성 프록시·콘솔·Vue 세션 흐름에 연결했다. [HTTP API 계약](HR_RAG_API_USAGE.md)을 참고한다.

## 호출

`rag-code-template_ext/rag-service`를 작업 디렉터리 또는 PYTHONPATH로 설정한다. 아래 코드는 이미 준비된 `vectorstore`, `llm`을 사용한다. API 연결부는 인증된 사용자가 해당 세션에 접근할 수 있는지 확인해야 한다.

```python
from rag_router import RagService
from rag_state import RagSettings
from session_memory import InMemorySessionStore

sessions = InMemorySessionStore(ttl_seconds=1800, recent_turn_limit=5)
service = RagService(vectorstore, llm, session_store=sessions,
                     settings=RagSettings(summary_max_chars=4000))

session = await sessions.create_session()
result = await service.ainvoke({
    "session_id": session.session_id,
    "request_id": "client-request-001",
    "question": "육아휴직 신청 방법은?",
})
print(result["output"])

# 후속 질문은 같은 session_id, 새로운 request_id로 호출한다.
# 같은 요청을 재전송할 때는 원래 request_id와 질문을 그대로 사용한다.
await sessions.end_session(session.session_id)
```

세션 모드에서는 `session_id`와 `request_id`가 필수다. 알 수 없거나 만료된 세션을 자동 생성하지 않는다. 외부에서 전달한 비어 있지 않은 `history`는 거부하고 서버 저장 이력만 사용한다. 세션 저장소를 주입하지 않으면 기존 question/history 호출과 라우팅이 유지된다.

## State와 실행 흐름

| 묶음 | 내용 |
|---|---|
| request | 요청 ID와 변경하지 않는 원질문 |
| memory | 세션 버전, 최근 완료 턴, 필요할 때 읽은 요약과 조회 상태 |
| interpretation | 기억 판단, 독립 질문, 미해결 참조, 확인 질문 |
| retrieval | 현재 검색 결과·메시지·출처, 검색 횟수·이전 질의·근거 판정 |
| result | status, output, 코드가 정한 reason_code |

각 노드는 중첩 묶음의 기존 필드를 보존해 새 값으로 교체한다. `retry_count`는 State에 중복 저장하지 않고 실제 검색 횟수로부터 응답 시 계산한다. 모델·저장소·런타임은 State에 넣지 않는다. `session_facts`는 도메인 계약이 정해지지 않아 빈 예약 필드이며 자동 추출·저장은 구현하지 않았다.

```text
세션 잠금 → 세션 이력 스냅샷 → 완료 요청 재전송 확인
 → 입력 분류: 인사/범위 밖은 최종 응답, 모호한 입력도 문서 그래프로 전달
 → resolve_recent
     ├─ ready → 기존 검색·근거 판단·재검색·답변 그래프
     ├─ clarify → 확인 질문
     └─ load_summary → load_summary (최대 1회)
                         → 최신 요약 있음: resolve_with_summary → ready 또는 clarify
                         → 요약 없음/갱신 지연: 확인 질문
 → 완료 턴 저장 → 최근 범위 밖의 미요약 구간으로 누적 요약 갱신 → 응답
```

요약 생성은 응답을 반환하기 전에 같은 요청 안에서 동기적으로 기다린다. 별도 백그라운드 작업은 없다. 완료된 5턴까지는 요약 모델을 호출하지 않으며, 6턴 저장 후 첫 턴부터 요약한다. 기존 요약과 새 미요약 구간 전체를 전달하고 성공할 때만 요약·cursor를 원자적으로 저장한다. 요약 실패 후 다음 새 요청에서 누락 구간 전체를 다시 시도한다.

최근 사용자 정정 우선, assistant 응답을 확정 사실로 취급하지 않기, 이력 속 명령 무시를 프롬프트로 지시한다. 실제 의미 보존은 모델 품질에 의존하며 모의 테스트로 입증한 것은 아니다. 오래된 요약은 누락 구간에 사용자 정정이 있을 수 있어 검색 질문 복원에 쓰지 않고 확인 질문으로 종료한다. 대화 기억 원문·요약을 문서 sources에 추가하지 않는다.

## 응답과 실패

- `output`: 최종 응답. `answer`는 같은 문자열의 호환 필드다.
- `session_id`, `request_id`, `replayed`: 요청 식별과 재전송 여부.
- `summary_checked`: 이번 문맥 해석에서 요약을 조회했는지 여부.
- `summary_update_status`: `up_to_date / updated / failed / pending / not_applicable`.
- `summary_is_current`: 응답 시 확인한 요약의 최신 여부. 세션 없는 호출은 null이다.
- `sources`: 새 답변 생성에 사용한 문서. 재전송에서는 다시 검색하지 않아 빈 목록이다.
- `source_ids`: 저장된 문서 식별자. 재전송에서도 보존한다. 식별자는 chunk_id를 우선하고 없으면 응답 내 S숫자 ID를 쓴다.
- 검색 횟수·모델 호출 수·추정/보정 입력 토큰·지연·trace도 기존처럼 반환한다.

같은 세션·request_id·질문은 저장된 output/status/source_ids를 반환하며 모델과 검색을 다시 호출하지 않는다. 과거 전체 응답 JSON을 저장하는 것은 아니므로 지연·trace·출처 본문까지 동일하게 재생하지 않는다. 같은 request_id에 다른 질문을 보내면 `session_conflict`다.

오류·취소된 생성은 완료 턴에 추가하지 않는다. 저장 실패·버전 충돌은 성공 답변으로 반환하지 않는다. 완료 턴 저장 후 요약만 실패하거나 시간이 끝나면 저장한 답변을 유지하고 `summary_update_status=failed`, `summary_is_current=false`로 표시한다. 저장 이후 사용자가 취소해도 이미 저장한 턴은 롤백하지 않는다. 요약 실패는 기존 원문·요약·cursor를 변경하지 않는다.

한 서비스 인스턴스·한 이벤트 루프에서 세션별로 생성부터 요약까지 직렬화한다. 대기 중 취소/시간 초과도 잠금을 정리한다. 여러 인스턴스/프로세스 간에는 순서를 보장하지 않으며, 저장소 CAS가 덮어쓰기를 막는다. 요청 시작 시 버전을 고정하므로 외부 쓰기가 발생하면 충돌로 종료한다.

큐 대기·분류·기억 해석·검색·생성·저장·요약은 전체 시간 제한을 공유한다. 요약 호출도 모델 호출 수·입력 토큰 예산에 합산한다. 입력이 예산을 넘으면 요약을 임의로 잘라 cursor를 진행시키지 않고 실패 상태를 남긴다. 요약의 문자 한도는 기본 4000자이며, 모델 출력 토큰 한도는 주입하는 LLM에 설정해야 한다.

## 검증 범위와 다음 단계

기존 회귀 테스트와 실제 LangChain/LangGraph·메모리 저장소에 모의 모델을 연결한 통합 테스트로 검증한다. 실행은 `rag-code-template_ext`에서 `python -B -m unittest discover -s rag-service/tests`다.

실제 외부 모델의 분류·문맥 복원·정정·요약 정확도와 지연은 아직 재평가하지 않았다. 다음 단계는 실제 다중 턴 평가, 도메인 session_facts 계약, 독립된 추가 평가 세트·도메인 session_facts·배포용 직접 접근 인증이다. HTTP 세션 생성/종료·output 호환 연결은 완료했다. 메모리 저장소는 프로세스 재시작 시 사라지며 다중 워커 공유가 필요하면 별도 저장소와 분산 실행 제어가 필요하다.


2026-10-25 실호출 보완: 모델 출력은 MemoryDecisionOutput의 분기별 중첩 union으로 받고 strict schema를 사용한 뒤 기존 MemoryDecision 계약으로 검증한다. State에는 summary_available도 전달한다. 동일 SessionCoordinator를 top_k별 서비스가 공유한다. 상세 결과는 [단계별 연결 결과](HR_RAG_INTEGRATION_RESULT.md)를 참고한다.
