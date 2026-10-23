"""라우터·그래프의 공통 계약. State는 요청별 작업 메모리이며 DB가 아니다."""

from dataclasses import dataclass
import math
from typing import Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StructuredDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RouteDecision(StructuredDecision):
    """분류 결과. 자유 문장을 파싱하지 않고 허용된 경로만 실행한다."""
    intent: Literal["greeting", "clarify", "document_question", "out_of_scope"]
    standalone_question: str | None = Field(default=None, min_length=1, max_length=4000)
    clarification_question: str | None = Field(default=None, min_length=1, max_length=1000)
    reason_code: str = Field(min_length=1, max_length=100)

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
    reason_code: str = Field(min_length=1, max_length=100)

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
    max_model_calls: int = 8
    timeout_seconds: float = 45
    max_history_messages: int = 10

    def __post_init__(self):
        for name, low, high in [
            ("top_k", 1, 50), ("max_retries", 0, 2),
            ("max_input_tokens", 1, 1000000), ("max_total_input_tokens", 1, 1000000),
            ("max_model_calls", 1, 20), ("max_history_messages", 0, 50),
        ]:
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"Invalid {name}")
        if (isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (float, int))
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError("Invalid timeout_seconds")


class RagState(TypedDict, total=False):
    """LangGraph의 노드가 변경분을 반환하는 요청 전용 상태. 기본 갱신 방식은 덮어쓰기다."""
    original_question: str
    standalone_question: str
    search_query: str
    previous_queries: list[str]
    search_count: int
    retry_count: int
    current_documents: list[tuple[Document, float]]
    messages: list[BaseMessage]
    sources: list[dict]
    previous_evidence_ids: list[str]
    missing_information: list[str]
    evidence_decision: Literal["sufficient", "insufficient", "clarify"]
    clarification_question: str | None
    answer: str
    status: Literal["answered", "clarification_needed", "no_evidence"]
    reason_code: str
