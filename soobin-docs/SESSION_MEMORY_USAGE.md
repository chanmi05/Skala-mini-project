# 메모리 기반 SessionStore 사용법

작성일: 2026-10-23 (Asia/Seoul)

## 1. 구현 범위

`rag-code-template_ext/session_memory.py`에 세션 보관 기반을 구현했다.
LangChain·LangGraph·FastAPI·외부 모델 호출에 의존하지 않으며 추가 패키지가 필요 없다.

- 세션 생성·조회·종료, 미사용 만료와 만료 항목 정리.
- 세션의 전체 완료 턴 원문 보관과 기본 최근 5턴 조회.
- 원문·상태·출처 ID 보관. output이 최종 응답 문자열이다.
- 요약 읽기, 미요약 구간 산출, 완성된 요약과 cursor의 원자적 저장.
- request_id별 중복 완료 저장 방지, 버전 충돌 감지.
- 변경 불가능한 스냅샷 반환, 같은 프로세스의 스레드 간 연산 보호.

**아직 구현하지 않은 부분:** LLM 요약 생성·자동 갱신, session_facts의 추출·보관 정책,
기억 관련 그래프 노드, API·UI 연결, 영속 DB·인증·실패 이벤트 저장.
현재 기존 RAG 서비스는 SessionStore를 자동 사용하지 않는다.

## 2. 초기 설정

```python
from session_memory import InMemorySessionStore

# 서버/서비스 수명 동안 같은 인스턴스를 주입해 사용한다.
# 매 요청마다 새로 만들면 이전 대화에 접근할 수 없다.
store = InMemorySessionStore(
    ttl_seconds=1800,       # 초기 기본값: 미사용 30분, 정책에 따라 변경
    recent_turn_limit=5,   # 완료된 질문·응답 한 쌍이 1턴
    max_sessions=1000,     # 활성 세션 제한, 기존 활성 세션을 강제로 버리지 않음
)
```

30분은 초기 설정값이며 최종 운영 정책을 확정한 것은 아니다.
종료·만료된 세션을 자동으로 되살리지 않는다. 새 대화는 create_session으로 별도 생성한다.

## 3. 세션 생성과 완료 턴 저장

```python
session = await store.create_session()

result = await store.append_turn(
    session.session_id,
    expected_version=session.version,
    request_id="request-001",
    question="사용자 질문 원문",
    output="사용자에게 전달할 최종 응답",
    status="answered",
    source_ids=["document-chunk-id"],
)

context = await store.get_context(session.session_id)
recent_turns = context.recent_turns
```

성공한 완료 응답으로 answered, clarification_needed, no_evidence, greeting, out_of_scope를
지원한다. 오류·취소를 정상 완료 턴으로 저장하지 않는다. 질문과 output은 공백 여부만
검사하고 원문 문자열을 그대로 보관한다.

현재 `RagService`의 결과 필드는 answer이므로 연결할 때 `output=rag_result["answer"]`로
매핑할 수 있다. 최종 외부 API의 output 계약은 아직 적용하지 않았다.
전체 source 객체 대신 source_ids만 저장하므로 출처 원문 보관이 필요하면 별도 계약을 추가한다.

## 4. 최근 5턴과 전체 원문

```python
context = await store.get_context(session_id)  # 실제 사용자 요청 시작용, TTL 연장
history = [
    message
    for turn in context.recent_turns
    for message in [
        {"role": "user", "content": turn.question},
        {"role": "assistant", "content": turn.output},
    ]
]

full = await store.get_session(session_id, touch=False)
all_turns = full.turns
```

8턴이 저장되면 recent_turns는 4~8턴이고 all_turns는 1~8턴이다.
최근 조회를 한다고 오래된 대화가 삭제되지 않는다.
불변 dataclass와 tuple로 반환하므로 호출자가 조회 결과를 바꿔 내부 저장소를 오염시키지 않는다.

get_context는 요약 본문을 포함하지 않고 summary_available·요약 범위·최신성만 알려준다.
summary_is_current가 False이면 최근 범위 밖의 미요약 대화가 있다는 뜻이다.
기억 연결 계층은 이를 무시하고 오래된 대화를 다 기억한다고 간주하면 안 된다.

## 5. 요약 대상과 저장

```python
context = await store.get_context(session_id)

# 그래프가 필요하다고 판단한 경우: 시작할 때 읽은 버전과 같은 요약만 조회
summary = await store.get_summary(session_id, expected_version=context.version)

# 요약 갱신 작업: 기존 요약 + 아직 요약하지 않은 오래된 턴 조회
work = await store.get_summary_work(session_id, expected_version=context.version)

if work.turns:
    # 외부 요약기 구현은 다음 단계다. 실패하면 저장하지 않는다.
    summary_text = await summarizer(work.previous_summary.text, work.turns)
    updated = await store.update_summary(
        session_id,
        expected_version=work.version,
        text=summary_text,
        summarized_until_turn_id=work.target_until_turn_id,
    )
```

위 summarizer는 인터페이스 설명용이며 아직 제공하지 않는다.
요약의 정확성은 저장소에서 판정하지 않는다. 반환된 work.turns 전체와 기존 요약을
반영한 누적 요약을 전달해야 한다.

처리 범위 예:

| 완료 턴 | 기존 요약 범위 | 최근 5턴 | 새 요약 대상 |
|---|---|---|---|
| 5 | 없음 | 1~5 | 없음 |
| 6 | 없음 | 2~6 | 1 |
| 8 | 1 | 4~8 | 2~3 |

target은 전체 턴 수에서 recent_turn_limit를 뺀 경계다.
이번 구현은 미요약 전체 구간을 한 번에 처리한다. 일부만 요약한 뒤 임의 cursor로
저장하거나 최근 5턴까지 침범하는 것을 거부한다. 대규모 요약 배치 분할은 후속 확장이다.

요약과 summarized_until_turn_id는 같은 쓰기에서 저장한다. 빈 요약·잘못된 경계·역행·
중복 cursor 저장은 거부한다. 요약 생성 실패로 저장을 하지 않으면 기존 원문·요약·cursor는
그대로 남으며 get_summary_work로 다시 대상 구간을 읽을 수 있다.
요약 자동 재시도나 갱신 지연 해결은 저장소가 아니라 다음 요약 서비스에서 구현한다.

## 6. 버전과 중복 요청

version은 **대화 내용 또는 요약의 변경 버전**이다. turn_id와 다르다.
턴 저장과 요약 저장 모두 version을 증가시킨다. 단순 조회·활동 시각 갱신은 증가시키지 않는다.

- 쓰기는 expected_version이 현재와 다르면 SessionVersionConflict로 실패한다.
- 요약 생성 중 새 턴이 추가되면 이전 스냅샷으로 요약을 덮어쓰지 못한다.
- 같은 request_id·같은 완료 결과를 재전송하면 duplicate=True로 기존 턴을 반환한다.
  이 경우 오래된 expected_version이어도 중복임을 먼저 확인해 새로 쓰지 않는다.
- 같은 request_id에 다른 질문·응답·상태·출처가 오면 RequestConflict로 실패한다.
- request_id는 세션 안에서만 유일하면 된다.

API는 생성 전에 get_turn_by_request로 완료 여부를 확인해 이미 저장된 output을 재사용할 수 있다.
이 기능은 **완료 저장의 중복 방지**이며 동시에 들어온 미완료 요청의 LLM 호출까지 막지는 않는다.
현재 CAS는 저장 충돌을 감지한다. 요청 시작부터 순서를 보장하는 큐·실행 잠금은 별도다.
버전 충돌 시 예전 문맥으로 만든 답변을 새 버전 번호만 붙여 무조건 저장해서는 안 된다.

## 7. 수명·종료·정리

- create_session, append_turn 및 기본 get_session/get_context가 사용자 활동 시각과 TTL을 갱신한다.
- get_session/get_context에 touch=False를 주면 조회가 TTL을 연장하지 않는다.
- 최근 턴 단독 조회·request_id 조회·요약 읽기/작업/저장은 TTL을 연장하지 않는다.
  백그라운드 요약 작업만으로 미사용 세션이 계속 살아 있는 것을 막는다.
- end_session은 원문·요약·요청 인덱스를 함께 제거한다. 이미 없는 세션에는 False를 반환한다.
- 만료 후 접근하면 SessionNotFoundError다. 종료·알 수 없는 ID도 같은 예외로 처리한다.
- 만료는 접근 시 검사하고, create_session과 purge_expired에서 만료 항목을 정리한다.
  자동 정리 타이머는 없다. 접근하지 않는 만료 객체의 물리적 제거는 purge 호출 등이 필요하다.

```python
await store.end_session(session_id)
removed_count = await store.purge_expired()
```

## 8. 저장 인터페이스와 오류

SessionStore는 비동기 Protocol이며 InMemorySessionStore가 구현한다.
향후 Redis/DB 구현은 같은 계약의 읽기·원자적 버전 쓰기·중복 처리·수명을 구현해야 한다.

| 예외 | 의미 |
|---|---|
| ValueError | 입력·설정·요약 범위가 잘못됨 |
| SessionNotFoundError | 알 수 없음·종료·만료 |
| SessionVersionConflict | 기대 버전과 현재 버전 불일치 |
| RequestConflict | 같은 요청 ID의 완료 내용 불일치 |
| SessionCapacityError | 활성 세션 한도 도달 |

저장소는 HTTP 상태나 사용자 문구를 결정하지 않는다.
세션 ID가 대화 접근 권한을 자동 보장하지 않으므로 API 연결 시 접근 범위를 확인해야 한다.

## 9. 검증과 한계

실행:

```bash
cd rag-code-template_ext
.venv/bin/python -B -m unittest discover -s tests -v
```

신규 저장소 테스트 22개와 기존 38개, 전체 60개 통과.

- 세션 분리·원문 보존·최근 범위·5/6/8턴 요약 경계.
- 스냅샷 불변성과 입력 목록 복제.
- 요약 실패 보존·cursor 검증·지연된 요약 저장 충돌.
- 같은 요청 재전송·다른 내용 충돌·실제 스레드 간 CAS 경쟁.
- TTL 연장·정확한 만료 경계·요약 작업의 비연장·종료·용량 정리.

이 모듈은 단일 프로세스 데모용이다. 프로세스 재시작 시 사라지고 여러 워커 사이에서 공유되지 않는다.
저장소 연산만 짧은 RLock으로 보호하고 LLM 호출은 잠금 안에서 수행하지 않는다.
모든 대화 원문을 보관하므로 활성 세션의 대화량이 커지면 메모리 사용량도 증가한다.
외부 모델·API·그래프 통합은 이번 테스트에 포함하지 않는다.

다음 단계는 이 인터페이스를 이용한 **증분 요약기 구현**이며, 그 뒤 기억 노드를 그래프에 연결한다.
이력·확정 조건·요약 State 구조는 [State 정의 전략](RAG_STATE_DESIGN.md)을 참고한다.
