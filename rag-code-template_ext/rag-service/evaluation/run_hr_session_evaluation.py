"""인사규정 실제 LLM 다중 턴 평가. 인덱스는 읽기 전용, 출력 폴더는 새로 생성한다."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from rag_router import RagService
from rag_state import RagSettings
from session_memory import InMemorySessionStore

# 기대값은 제공된 규정의 해당 조항을 먼저 확인해 작성했다. 현행 법률의 정답을 뜻하지 않는다.
CASES = [
    {"id": "travel_deadline", "question": "출장규정 제12조에 따르면 출장비 정산은 복귀 후 몇 영업일 이내 제출하는 것이 원칙인가요?", "status": "answered", "source": "05_출장규정.pdf", "article": "제12조", "groups": [["10영업일", "10 영업일"]]},
    {"id": "followup", "question": "그럼 같은 조항에서 완비된 정산서를 제출하면 회사는 몇 영업일 안에 지급하나요?", "status": "answered", "source": "05_출장규정.pdf", "article": "제12조", "groups": [["10영업일", "10 영업일"]]},
    {"id": "leave", "question": "휴가규정 제2조에서 일반 연차는 언제까지 신청하는 것을 권장하나요?", "status": "answered", "source": "04_휴가규정.pdf", "article": "제2조", "groups": [["3영업일", "3 영업일"]]},
    {"id": "attendance", "question": "근태규정 제2조의 기본 시업 시각과 종업 시각은 무엇인가요?", "status": "answered", "source": "03_근태규정.pdf", "article": "제2조", "groups": [["09:00", "9시"], ["18:00", "6시"]]},
    {"id": "benefit", "question": "복리후생규정 제9조에서 본인 혼인 경조금의 회사 제안액은 얼마인가요?", "status": "answered", "source": "02_복리후생규정.pdf", "article": "제9조", "groups": [["500,000", "500000", "50만"]]},
    {"id": "greet1", "question": "안녕하세요!", "status": "greeting", "groups": []},
    {"id": "greet2", "question": "안녕하세요!", "status": "greeting", "groups": []},
    {"id": "old_reference", "question": "맨 처음 질문했던 그 제출 기한을 다시 알려주세요.", "status": "answered", "summary_expected": True, "source": "05_출장규정.pdf", "article": "제12조", "groups": [["10영업일", "10 영업일"]]},
    {"id": "absent", "question": "등록된 규정에 직원의 화성 출장 우주선 좌석 등급이 정해져 있나요?", "status": "no_evidence", "groups": []},
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    index = args.index.resolve()
    before = {name: sha(index / name) for name in ["index.faiss", "index.pkl"]}
    embedding = OpenAIEmbeddings(model=args.embedding_model, request_timeout=30, max_retries=0)
    store = FAISS.load_local(str(index), embedding, allow_dangerous_deserialization=True)
    model = ChatOpenAI(model=args.model, temperature=0, max_tokens=1200, timeout=30, max_retries=0)
    sessions = InMemorySessionStore()
    session = await sessions.create_session()
    settings = RagSettings(timeout_seconds=60, summary_max_chars=2000)
    service = RagService(store, model, session_store=sessions, settings=settings)
    manifest = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "model": args.model,
                "embedding_model": args.embedding_model, "index_sha256": before,
                "settings": settings.__dict__, "module_sha256": {name: sha(ROOT / name) for name in
                    ["rag_agent.py", "rag_state.py", "rag_router.py", "rag_workflow.py", "rag_session.py", "session_memory.py"]},
                "limitations": ["Small provided-draft HR sample, not a legal determination.",
                    "Lexical expected-value/source checks are not independent factual-accuracy grading.",
                    "Model memory and summary quality require review against the supplied documents."]}
    records = []
    for case in CASES:
        result = await service.ainvoke({"question": case["question"], "session_id": session.session_id,
                                        "request_id": case["id"]})
        groups = all(any(word in result["output"] for word in group) for group in case["groups"])
        source_hit = any(s["metadata"].get("source") == case.get("source") and
                         s["metadata"].get("article") == case.get("article") for s in result["sources"]) if case.get("source") else None
        row = {"case": case, "result": result, "status_match": result["status"] == case["status"],
               "expected_values_present": groups, "expected_source_present": source_hit,
               "summary_check_match": not case.get("summary_expected") or result["summary_checked"]}
        memory = await sessions.get_session(session.session_id, touch=False)
        row["summary_snapshot"] = {"text": memory.summary.text,
                                   "until_turn_id": memory.summary.summarized_until_turn_id}
        records.append(row)
        (args.output / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        print(case["id"], result["status"], result["reason_code"], "summary", result["summary_update_status"], flush=True)
        if result["status"] == "error":
            # 인증·한도·모델 오류를 반복 호출하지 않는다.
            break
    snapshot = await sessions.get_session(session.session_id, touch=False)
    manifest.update({"finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "index_unchanged": before == {name: sha(index / name) for name in before},
        "completed_cases": len(records), "summary_until_turn_id": snapshot.summary.summarized_until_turn_id,
        "status_matches": sum(r["status_match"] for r in records),
        "model_calls": sum(r["result"]["model_calls"] for r in records),
        "input_tokens_reported": sum(e.get("usage", {}).get("input_tokens", 0) for r in records for e in r["result"]["trace"])})
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    lines = ["# 인사규정 실제 LLM 세션 평가", "", "API 실호출 결과. 기대값은 제공된 규정 초안에서 작성했으며 법률 검증이나 독립적인 정확도 채점은 아니다.", "",
             "| 사례 | 상태 | 기대 상태 일치 | 기대 표현 포함 | 지정 출처 검색 | 요약 조회 | 지연 ms |",
             "|---|---|---|---|---|---|---|"]
    for r in records:
        result = r["result"]
        lines.append(f"| {r['case']['id']} | {result['status']} | {r['status_match']} | {r['expected_values_present']} | {r['expected_source_present']} | {result['summary_checked']} | {result['elapsed_ms']} |")
    lines.extend(["", f"실행 사례 {len(records)}/{len(CASES)}, 상태 일치 {manifest['status_matches']}, 모델 호출 {manifest['model_calls']}, 입력 실사용 토큰 {manifest['input_tokens_reported']}.",
                  f"인덱스 변경 없음: {manifest['index_unchanged']}. 요약 cursor: {manifest['summary_until_turn_id']}.", ""])
    for r in records:
        lines.extend(["## " + r["case"]["id"], "", r["case"]["question"], "", r["result"]["output"], ""])
    (args.output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    if not manifest["index_unchanged"]:
        raise RuntimeError("Index changed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trust-local-index", action="store_true")
    parser.add_argument("--index", type=Path, default=PROJECT / "faiss_db/pdf")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "runs" / ("hr_session_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")))
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--embedding-model", default="text-embedding-ada-002")
    args = parser.parse_args()
    if not args.trust_local_index:
        parser.error("Known trusted local FAISS index requires --trust-local-index")
    load_dotenv(PROJECT / ".env")
    asyncio.run(run(args))
