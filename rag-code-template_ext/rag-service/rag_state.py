"""라우터·그래프의 공통 계약. State는 요청별 작업 메모리이며 DB가 아니다."""

from dataclasses import dataclass
import math
from typing import Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

from pydantic import BaseModel, ConfigDict, Field, model_validator
from session_memory import Turn


class StructuredDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InputDecision(StructuredDecision):
    """세션 모드 분류. 문맥 복원은 기억 노드에서만 수행한다."""
    intent: Literal["greeting", "document_question", "out_of_scope"]


class MemoryDecision(StructuredDecision):
    action: Literal["ready", "load_summary", "clarify"]
    standalone_question: str | None = Field(default=None, min_length=1, max_length=4000)
    missing_reference: str | None = Field(default=None, min_length=1, max_length=1000,
        description="과거 대화에서만 알 수 있는 미해결 참조. 현재 질문에 명시한 문서명·조항 자체는 누락 참조가 아니다. ready/clarify에서는 null.")
    clarification_question: str | None = Field(default=None, min_length=1, max_length=1000)
    reason_code: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_fields(self):
        required = {"ready": "standalone_question", "load_summary": "missing_reference",
                    "clarify": "clarification_question"}[self.action]
        for name in ("standalone_question", "missing_reference", "clarification_question"):
            if bool(getattr(self, name)) != (name == required):
                raise ValueError("Memory decision fields do not match action")
        return self


class ReadyMemory(StructuredDecision):
    action: Literal["ready"]
    standalone_question: str = Field(min_length=1, max_length=4000)


class LoadMemory(StructuredDecision):
    action: Literal["load_summary"]
    missing_reference: str = Field(min_length=1, max_length=1000)


class ClarifyMemory(StructuredDecision):
    action: Literal["clarify"]
    clarification_question: str = Field(min_length=1, max_length=1000)


class MemoryDecisionOutput(StructuredDecision):
    """모델의 wire schema: 중첩 union으로 분기별 필드 조합을 강제한다."""
    decision: ReadyMemory | LoadMemory | ClarifyMemory


class SummaryDecision(StructuredDecision):
    summary: str = Field(min_length=1, max_length=4000)


class RouteDecision(StructuredDecision):
    """분류 결과. 자유 문장을 파싱하지 않고 허용된 경로만 실행한다."""
    intent: Literal["greeting", "clarify", "document_question", "out_of_scope"]
    standalone_question: str | None = Field(default=None, min_length=1, max_length=4000)
    clarification_question: str | None = Field(default=None, min_length=1, max_length=1000)
    reason_code: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def check_required_fields(self):
        if self.intent == "document_question" and not self.standalone_question:
            raise ValueError("Document route requires a standalone question")
        if self.intent == "clarify" and not self.clarification_question:
            raise ValueError("Clarify route requires a question")
        if self.intent != "clarify" and self.clarification_question is not None:
            raise ValueError("Unexpected clarification question")
        if self.intent != "document_question" and self.standalone_question is not None:
            raise ValueError("Unexpected standalone question")
        return self


class EvidenceDecision(StructuredDecision):
    decision: Literal["sufficient", "insufficient", "clarify"]
    supported_source_ids: list[str] = Field(default_factory=list, max_length=50)
    missing_information: list[str] = Field(default_factory=list, max_length=20)
    clarification_question: str | None = Field(default=None, min_length=1, max_length=1000)
    reason_code: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def check_decision(self):
        if self.decision == "sufficient" and (not self.supported_source_ids or self.missing_information):
            raise ValueError("Sufficient evidence requires sources and no missing facts")
        if self.decision == "insufficient" and not self.missing_information:
            raise ValueError("Insufficient decision must identify missing facts")
        if self.decision == "clarify" and not self.clarification_question:
            raise ValueError("Clarify decision requires a question")
        if self.decision != "clarify" and self.clarification_question is not None:
            raise ValueError("Unexpected clarification question")
        return self


class AnswerReview(StructuredDecision):
    decision: Literal["grounded", "unsupported", "not_found"]
    reason_code: str = Field(min_length=1, max_length=100)


class GenerationDecision(StructuredDecision):
    """문서 사실 답변과 생성 단계의 유보를 명시적으로 구분한다."""
    status: Literal["answered", "no_evidence"]
    answer: str = Field(min_length=1, max_length=12000)


class RewrittenQuery(StructuredDecision):
    search_query: str = Field(min_length=1, max_length=4000)


class HistoryTurn(StructuredDecision):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


@dataclass(frozen=True)
class RagSettings:
    """서비스 공통 설정. 모델/저장소와 달리 순수한 값만 갖는다."""
    top_k: int = 5
    max_retries: int = 1
    max_input_tokens: int = 6000
    max_total_input_tokens: int = 24000
    max_model_calls: int = 9
    timeout_seconds: float = 45
    max_history_messages: int = 10
    summary_max_chars: int = 4000

    def __post_init__(self):
        for name, low, high in [
            ("top_k", 1, 50), ("max_retries", 0, 2),
            ("max_input_tokens", 1, 1000000), ("max_total_input_tokens", 1, 1000000),
            ("max_model_calls", 1, 20), ("max_history_messages", 0, 50),
            ("summary_max_chars", 1, 4000),
        ]:
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"Invalid {name}")
        if (isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (float, int))
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError("Invalid timeout_seconds")


class RequestState(TypedDict):
    request_id: str
    original_question: str


class MemoryState(TypedDict, total=False):
    session_id: str
    session_version: int
    recent_history: list[Turn]
    session_facts: dict
    summary_checked: bool
    summary_status: Literal["unchecked", "loaded", "empty"]
    summary: str | None
    summary_until_turn_id: int | None
    summary_is_current: bool
    summary_available: bool


class InterpretationState(TypedDict, total=False):
    memory_action: Literal["ready", "load_summary", "clarify"]
    missing_reference: str | None
    standalone_question: str
    clarification_question: str | None
    reason_code: str


class RetrievalState(TypedDict, total=False):
    search_query: str
    previous_queries: list[str]
    search_count: int
    current_documents: list[tuple[Document, float]]
    messages: list[BaseMessage]
    sources: list[dict]
    previous_evidence_ids: list[str]
    missing_information: list[str]
    supported_source_ids: list[str]
    exact_target: object
    lookup_clarification: str | None
    evidence_decision: Literal["sufficient", "insufficient", "clarify"]
    reason_code: str


class ResultState(TypedDict, total=False):
    output: str
    status: Literal["answered", "clarification_needed", "no_evidence", "greeting", "out_of_scope", "error"]
    reason_code: str


class RagState(TypedDict, total=False):
    """중첩 묶음은 노드에서 기존 키를 보존해 교체한다. 전체 대화 DB는 별도다."""
    request: RequestState
    memory: MemoryState
    interpretation: InterpretationState
    retrieval: RetrievalState
    result: ResultState
