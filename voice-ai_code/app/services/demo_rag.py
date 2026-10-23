"""Local retrieval-only demo. No FAISS, embeddings, or answer-generation API."""
import json
import re
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "demo_hr_rules.json"
NOTICE = "테스트용 가상 규정 기준입니다. 실제 법령이나 회사 규정이 아닙니다. "

class DemoRule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    doc: str
    article: str
    page: int = Field(ge=1)
    match_all: list[list[str]]
    content: str

def normalized(text: str) -> str:
    return re.sub(r"[^가-힣a-z0-9]", "", text.lower())

def load_rules() -> list[DemoRule]:
    return [DemoRule.model_validate(item) for item in json.loads(RULES_PATH.read_text(encoding="utf-8"))]

def handoff_answer(message: str) -> dict:
    return {"answer": NOTICE + message, "sources": [],
            "needs_review": True, "handoff": True}

def retrieve(question: str, rules: list[DemoRule]) -> list[DemoRule]:
    """Match every topic/intent keyword group; rank by matched keyword length."""
    query = normalized(question)
    matches = []
    for rule in rules:
        groups = [[normalized(term) for term in group] for group in rule.match_all]
        hits = [[term for term in group if term and term in query] for group in groups]
        if not groups or any(not group for group in hits):
            continue
        score = sum(max(map(len, group)) for group in hits)
        matches.append((score, rule))
    return [rule for _, rule in sorted(matches, key=lambda item: item[0], reverse=True)]

def demo_answer(question: str) -> dict:
    query = normalized(question)
    # Explicit demo boundaries. This is not an automated legal determination.
    if any(term in query for term in ["징계", "정당", "부당", "위법", "소송", "해고"]):
        return handoff_answer("개별 사안의 판단은 제공하지 않습니다. 인사담당자의 검토가 필요합니다.")
    # No salary/calendar/cost clauses are present in this small corpus.
    if any(term in query for term in ["연봉", "인상률", "회식", "수수료", "비용", "급여", "잔여", "몇개남", "남았", "취소"]):
        return handoff_answer("테스트 규정에서 답을 찾을 수 없습니다. 인사담당자에게 문의해 주세요.")
    # The leave clause covers one's own marriage, not a relative's.
    if any(term in query for term in ["형제", "자매", "부모", "자녀", "친구", "동생", "언니", "오빠"]):
        return handoff_answer("테스트 규정에서 해당 대상의 근거를 찾을 수 없습니다. 인사담당자에게 문의해 주세요.")
    try:
        matches = retrieve(question, load_rules())
    except (OSError, ValueError, TypeError):
        from fastapi import HTTPException
        raise HTTPException(503, "테스트 규정 데이터를 읽을 수 없습니다.")
    if not matches:
        return handoff_answer("테스트 규정에서 답을 찾을 수 없습니다. 인사담당자에게 문의해 주세요.")
    if len(matches) > 2:
        return handoff_answer("질문 범위가 넓습니다. 한 번에 한두 가지 규정으로 나눠 질문해 주세요.")
    return {"answer": NOTICE + " ".join(rule.content for rule in matches),
            "sources": [{"doc":r.doc, "article":r.article, "page":r.page} for r in matches],
            "needs_review":False, "handoff":False}
