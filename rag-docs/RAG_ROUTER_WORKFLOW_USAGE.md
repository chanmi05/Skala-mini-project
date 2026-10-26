# LangChain 라우터·LangGraph 문서 질의 구현과 State 초안

작성일: 2026-10-23 (Asia/Seoul)

2026-10-25 State를 중첩 구조로 전환하고 선택적 세션 모드를 추가했다. 세션 모드의 기억 해석·요약·저장과 최신 응답 필드는 [세션 RAG 사용법](SESSION_RAG_WORKFLOW_USAGE.md)을 참고한다. 아래 최초 평가 수치는 세션 연결 전 결과다.

## 1. 구현한 호출 구조

아래는 세션 저장소를 주입하지 않는 호환 호출 흐름이다. 세션 모드는 문맥 복원을 기억 그래프에서 수행한다.

```text
RagService.ainvoke({question, history})
    ↓
입력 검증
    ↓
LangChain: ChatPromptTemplate → 구조화 분류 → RunnableBranch
    ├─ 인사 → 안내
    ├─ 모호함 → 확인 질문
    ├─ 명시된 지원 범위 밖 → 범위 안내
    └─ 문서 질문 → 별도 rag_workflow.py의 컴파일된 LangGraph
                      prepare_query → retrieve → prepare_context → assess_evidence
                                                                    ├─ generate_answer → END
                                                                    ├─ clarify → END
                                                                    ├─ rewrite_query → retrieve
                                                                    └─ abstain → END
```

파일별 역할:

| 파일 | 역할 |
|---|---|
| `rag_router.py` | 공개 진입점 `RagService`, 입력·이력 검증, LangChain 분기, 공통 응답 |
| `rag_workflow.py` | 그래프 구성·노드·조건 전이와 요청별 호출/입력 예산 계측 |
| `rag_state.py` | State, 구조화 출력 스키마, 이력 스키마, 실행 설정 |
| `rag_agent.py` | 기존 기본 RAG와 공통 검색·컨텍스트·생성 함수 |

기존 `answer_question()`은 유지했다. 생성 부분만 `generate_answer()`로 분리하여
기존 함수와 그래프가 함께 사용한다. 생성 노드가 기존 전체 함수를 호출해 재검색하는
중복은 없다. 기존 서버·HTML·업로드 API와의 연결은 아직 변경하지 않았다.

## 2. 사용 예시

`rag-code-template_ext/rag-service`에서 다음 객체를 만들어 재사용한다. 저장소 적재는 이 코드의 책임이 아니다.

```python
from langchain_openai import ChatOpenAI
from rag_router import RagService
from rag_state import RagSettings

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=600,
    timeout=30,
    max_retries=0,
)

service = RagService(
    vectorstore=prepared_vectorstore,
    llm=llm,
    settings=RagSettings(top_k=5, max_retries=1, timeout_seconds=45),
    # 지원 범위가 확정된 경우에만 설정한다. 기본은 범위 밖 자동 차단 비활성화.
    supported_scope="",
)

result = await service.ainvoke({
    "question": "그럼 신청 방법은요?",
    "history": [
        {"role": "user", "content": "휴가 제도를 알고 싶어요."},
        {"role": "assistant", "content": "휴가 제도의 어떤 내용이 궁금하신가요?"},
    ],
})
```

이는 사용 예시이며 운영 데이터가 휴가 규정으로 확정되었다는 뜻은 아니다.
`prepared_vectorstore`는 호출자가 준비한 LangChain 호환 저장소다.
기본 검색 수는 여전히 5이며 평가 결과만으로 10으로 변경하지 않았다.

실행 환경 준비:

```bash
cd rag-code-template_ext
.venv/bin/python -m pip install -r rag-service/requirements-rag-workflow.txt
.venv/bin/python -B -m unittest discover -s rag-service/tests -v
```

새 requirements는 기존 파일을 포함하고 직접 사용하는 LangGraph 1.0.10을 명시한다.
이번 구현 시에는 이미 해당 패키지가 설치되어 있어 설치 명령을 다시 실행하지 않았다.

## 3. State는 세 가지로 분리했다

### A. 그래프 State: 이번 문서 질문의 작업 데이터

`RagState`는 `TypedDict`다. 모든 노드가 전체 상태를 다시 만들지 않고 변경한 키만
반환한다. 목록도 기본적으로 덮어쓰며, 이전 회차 자료가 자동 누적되지 않는다.

| 묶음 | 필드 | 갱신 방식 |
|---|---|---|
| request | request_id, original_question | 요청 시작 후 고정 |
| memory | 세션 버전, 최근 완료 턴, 요약 조회 상태·본문 | 최근 스냅샷 고정, 요약은 조건부 1회 조회 |
| interpretation | 독립 질문, 미해결 참조, 확인 질문 | 문맥 복원 후 독립 질문 유지 |
| retrieval | 검색 질의·횟수·이전 질의·현재 문서·메시지·출처·근거 판정 | 이전 질의만 누적, 현재 문서·메시지·출처는 회차별 교체 |
| result | status, output, reason_code | 종료 노드에서 작성 |

각 노드는 변경 묶음의 기존 필드를 보존한다. retry_count는 State에 중복 보관하지 않고 search_count로부터 응답 시 계산한다.

원질문과 복원 질문이 다르면 근거 판단과 생성에 둘 다 전달한다. 모델이 이력에서
대상을 복원할 때 조건을 만들지 않도록 지시하지만, 의미 보존을 자동 보장하지는 않는다.

`TypedDict(total=False)`는 중간 단계에서 일부 키만 존재할 수 있음을 표현한다.
실행 중 값 검증을 모두 수행하는 도구는 아니다. 외부 입력과 LLM 판정은 Pydantic으로
검증하고, 서비스에서 초기 상태를 만든다. 사용자가 완성된 내부 State를 직접 입력하지 않는다.

### B. 실행 설정: 정책값

`RagSettings`는 frozen dataclass이며 State에 섞지 않는다.

- `top_k=5`
- `max_retries=1`: 0~2 허용. 최초 검색 포함 총 1~3회.
- `max_input_tokens=6000`: 모델 호출별 메시지 입력 예산.
- `max_total_input_tokens=24000`: 요청 전체 입력 예산.
- `max_model_calls=8`: 분류·판정·재구성·생성 합산.
- `timeout_seconds=45`: 바깥 라우팅부터 전체 종료까지.
- `max_history_messages=10`: 레거시 요청에 제공하는 이력 길이 제한.
- `summary_max_chars=4000`: 증분 요약 문자 한도. 요약 호출도 전체 시간·모델·입력 예산에 포함한다.

### C. 실행 의존성·계측: 요청 Runtime

- 모델·저장소·컴파일된 체인/그래프는 서비스가 주입받는다.
- `RequestRuntime`은 각 `ainvoke()`에서 새로 만들고 LangGraph `RunnableConfig`로 전달한다.
- 호출 수, 입력 예산, 실제 시작한 검색 횟수, 단계별 이벤트·시간을 기록한다.
- 모델 객체·API 키·네트워크 클라이언트를 State에 넣지 않는다.

따라서 그래프를 재사용해도 요청 상태와 예산은 공유하지 않는다.
checkpointer나 대화 DB는 붙이지 않았으며 프로세스 재시작 시 실행 상태를 복구하지 않는다.

## 4. 재검색과 종료

- 충분한 근거가 있으면 현재 메시지로 바로 생성한다.
- 사용자가 정해야 할 조건이 빠졌으면 확인 질문을 반환한다.
- 부족한 사실은 동의어·표현 변경 등으로 질의를 재구성해 찾는다.
- 실행한 것과 같은 질의면 추가 검색 없이 종료한다.
- 이전 회차와 근거 및 누락 항목이 같으면 무진전으로 종료한다.
- 한도 도달 시 유보한다. 기본 최대 2회 검색, 설정 최대 3회 검색이다.
- 검색 후보가 모두 컨텍스트에서 제외되면 `context_empty`로 유보하여 불필요한 반복을 막는다.
- 첫 검색에 결과가 없으면 생성·근거 판정 모델 호출을 생략하고 재구성을 시도할 수 있다.

모델의 자유로운 reason_code가 반복 횟수나 종료 경로를 제어하지 않도록 했다.
루프 제어 사유는 코드가 계산한다. LangGraph recursion_limit은 별도 단계 제한이다.

재검색 시 이전 문서는 trace 판단에만 사용하고 현재 문서를 덮어쓴다.
여러 회차 자료를 합치는 정책이나 메타데이터 필터는 아직 구현하지 않았다.
필터가 필요하면 데이터 담당자의 필드·저장소 계약을 먼저 확정해야 한다.

## 5. 공통 응답과 오류

```json
{
  "status": "answered",
  "output": "문서에 따른 답변 [S1]",
  "answer": "문서에 따른 답변 [S1]",
  "sources": [],
  "retrieved_count": 5,
  "search_count": 1,
  "retry_count": 0,
  "reason_code": "evidence_sufficient",
  "model_calls": 3,
  "input_tokens_estimate": 3000,
  "budget_input_tokens": 3500,
  "elapsed_ms": 5000,
  "trace": []
}
```

위 숫자와 빈 목록은 형식 설명용이다. 실제 answered 결과에는 사용한 출처가 들어간다.
`retrieved_count`는 마지막 검색 후보 수다. sources는 answered일 때만 최종 생성에
전달한 자료를 포함한다. 인용과 사실이 일치하는지까지 검증한 목록은 아니다.

status는 answered / greeting / clarification_needed / out_of_scope / no_evidence / error다.
빈 입력·잘못된 이력은 `ValueError`로 호출 전에 거부한다. 취소는 전파한다.
실행 중 검색·모델·형식·예산·시간 오류는 `error`로 반환하고 `no_evidence`와 구분한다.
검색이 실패해도 이미 시작한 시도는 search_count에 포함한다.
오류 종료 시 부분 그래프 상태는 반환하지 않으므로 retrieved_count는 0일 수 있다.

`trace`는 개발·평가용이다. 기존 API 연결 시 내부 trace 전체를 기본 공개할지는 별도 결정한다.
모델의 구조화 판정 원문·자유로운 추론 내용은 trace에 저장하지 않고 단계·상태·수치만 기록한다.

## 6. 토큰과 지연의 한계

메시지 토큰을 사전 계산해 호출 수·입력 예산을 제한한다. 구조화 출력의 스키마는
메시지 카운터에 빠질 수 있으므로 실제 usage가 있으면 보수적으로 보정하고 다음 호출을 막는다.
실제 사용량이 한도를 넘었다는 사실은 해당 호출 후에만 알 수 있으므로 완전한 비용 상한이 아니다.
`input_tokens_estimate`와 보정된 `budget_input_tokens`를 구분한다.

출력 토큰 한도는 전달한 모델에 설정해야 한다. 이번 코드에서 임의 모델의 출력 설정을
강제로 덮어쓰지 않는다. 동기 스레드나 외부 제공자 작업은 취소 후에도 실행 중일 수 있다.

기본 문서 경로는 분류 1회 + 근거 판정 1회 + 생성 1회로, 이전의 생성 1회보다
지연과 비용이 늘어난다. 재검색에는 재구성·판정 호출도 추가된다.
음성용 스트리밍·전체 1~2초 목표는 아직 구현·검증하지 않았다.

## 7. 검증 범위

- 기존 회귀와 새 경로 테스트를 포함한 오프라인 테스트 38개 통과.
- 모의 모델을 사용하지만 실제 LangChain LCEL/RunnableBranch와 컴파일된 LangGraph를 실행한다.
- 입력·인사·모호함·후속 질문·재검색 한도·중복·무진전·빈 검색 복구·형식/출처 오류,
  호출·입력 예산·실제 usage 보정·장애·시간 초과·취소·동시 요청 상태 분리를 검증했다.
- 실제 공개 논문 검증은 `evaluation/run_workflow_smoke.py`로 수행한다.
  최종 코드의 기대 상태 6/6 일치를 확인했다. 정보 부재 사례는 재검색 1회 후 유보했다.
  [최종 실제 연동 결과](../rag-code-template_ext/rag-service/evaluation/runs/workflow_smoke_20261023_v2/report.md)에
  상태·호출 수·지연·답변을 기록했다. 문서 질문은 약 3.94~5.64초였다.

실제 분류와 충분성 판단은 모델이 수행하므로 별도 데이터별 품질 평가가 필요하다.
이번 단계는 흐름 검증이며 기존 24개 평가보다 좋아졌다는 결론을 내리지 않는다.

## 8. 다음 State 논의에서 결정할 항목

1. **이력의 책임:** 지금처럼 호출자가 요청마다 이력을 보낼지, 서버가 세션별로 저장할지.
2. **도메인 조건:** 실제 데이터에 적용 대상·문서 버전·제품 등이 있는지와 필수 필터 필드.
3. **근거 보존:** 현재 회차만 사용할지, 재검색 전후 자료를 모아 다시 선별할지.
4. **응답과 계측:** 외부 API에 공개할 필드와 내부 저장할 trace 범위.

현재 추천은 **요청 단위 State + 외부 주입 이력 + 현재 회차 근거만 유지**다.
도메인 필드는 데이터 계약이 정해진 뒤 추가하고, session_id·사용자 객체를 지금 넣지는 않았다.
기본적으로 대화 전체를 그래프에 저장하지 않고 바깥에서 필요한 질문 문맥만 복원한다.
