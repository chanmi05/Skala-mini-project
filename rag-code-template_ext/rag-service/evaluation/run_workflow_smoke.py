"""새 LangChain 라우터/LangGraph를 기존 공개 논문으로 소규모 실제 검증한다."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

# Python modules live in rag-service; shared data and .env stay in its parent.
ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from rag_router import RagService
from rag_state import RagSettings
from run_evaluation import RecordingStore, sha256, write_json, write_jsonl


CASES = [
    {"id": "greeting", "question": "안녕하세요!", "expected_status": "greeting"},
    {"id": "ambiguous", "question": "어떻게 해?", "expected_status": "clarification_needed"},
    {"id": "document", "question": "논문에서 기본 Transformer 인코더는 몇 개 층이며 하위 계층은 무엇인가요?",
     "expected_status": "answered"},
    {"id": "followup", "question": "그럼 디코더는 몇 층인가요?", "expected_status": "answered",
     "history": [{"role": "user", "content": "논문의 기본 Transformer 인코더는 몇 층인가요?"},
                 {"role": "assistant", "content": "논문의 기본 인코더는 6개 층입니다."}]},
    {"id": "missing_fact", "question": "이 논문에서 Transformer 구매 고객의 환불 기간은 며칠인가요?",
     "expected_status": "no_evidence"},
    {"id": "retrieval_gap", "question": "디코더가 아직 생성하지 않은 미래 토큰을 보지 못하게 하는 방법은 무엇인가요?",
     "expected_status": "answered"},
]


async def run(args):
    started_at = datetime.now(timezone.utc).isoformat()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    index = PROJECT_ROOT / "faiss_db/pdf"
    before = {name: sha256(index / name) for name in ["index.faiss", "index.pkl"]}
    store = FAISS.load_local(str(index), OpenAIEmbeddings(model="text-embedding-ada-002"),
                             allow_dangerous_deserialization=True)
    recorder = RecordingStore(store)
    llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=600, timeout=30, max_retries=0)
    settings = RagSettings(timeout_seconds=60)
    service = RagService(recorder, llm, settings=settings)
    records = []
    for case in CASES:
        result = await service.ainvoke({"question": case["question"], "history": case.get("history", [])})
        records.append({**case, "result": result,
                        "expected_status_matches": result["status"] == case["expected_status"]})
        write_jsonl(output / "results.jsonl", records)
        print(case["id"], result["status"], "searches", result["search_count"],
              "calls", result["model_calls"], flush=True)
    manifest = {"started_at_utc": started_at,
                "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                "model": "gpt-4o", "embedding_model": "text-embedding-ada-002",
                "settings": settings.__dict__, "index_before": before,
                "index_unchanged": before == {name: sha256(index / name) for name in before},
                "module_sha256": {name: sha256(ROOT / name) for name in
                                  ["rag_agent.py", "rag_router.py", "rag_state.py", "rag_workflow.py"]},
                "limitations": "Six smoke cases; status matches are not factual-accuracy scores."}
    write_json(output / "manifest.json", manifest)
    if not manifest["index_unchanged"]:
        raise RuntimeError("Index changed during smoke run")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trust-local-index", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "runs" /
                        ("workflow_smoke_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")))
    args = parser.parse_args()
    if not args.trust_local_index:
        parser.error("Known trusted repository FAISS index requires --trust-local-index")
    load_dotenv(PROJECT_ROOT / ".env")
    asyncio.run(run(args))
