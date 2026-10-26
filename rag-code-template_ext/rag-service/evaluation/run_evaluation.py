"""Read-only FAISS baseline evaluation for rag_agent; no server required.

Questions/gold evidence are authored separately from generated answers. Retrieval
metrics are automatic; factual correctness/abstention require explicit review.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import statistics
import sys
import time

# Python modules live in rag-service; shared data and .env stay in its parent.
ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from rag_agent import answer_question


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, values):
    path.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values), encoding="utf-8")


class NoNetworkEmbeddings(Embeddings):
    """Corpus inspection must not embed or contact an external service."""
    def embed_documents(self, texts):
        raise RuntimeError("Corpus export does not perform embedding")

    def embed_query(self, text):
        raise RuntimeError("Corpus export does not perform embedding")


def fingerprint(document):
    return json.dumps([document.page_content, document.metadata], sort_keys=True, ensure_ascii=False)


class RecordingStore:
    """Record the exact search used by answer_question; never search twice."""
    def __init__(self, store):
        self.store = store
        self.ids = {}
        for key in store.index_to_docstore_id.values():
            document = store.docstore.search(key)
            signature = fingerprint(document)
            if signature in self.ids:
                raise ValueError("Ambiguous identical stored documents: explicit chunk IDs required")
            self.ids[signature] = key
        self.hits = []
        self.elapsed_ms = None

    async def asimilarity_search_with_score(self, question, k):
        started = time.perf_counter()
        try:
            entries = await self.store.asimilarity_search_with_score(question, k=k)
            self.hits = []
            result = []
            for rank, (document, score) in enumerate(entries, 1):
                key = self.ids[fingerprint(document)]
                # Clone: keep on-disk and in-memory source documents unchanged.
                metadata = {**document.metadata, "chunk_id": key}
                clone = Document(page_content=document.page_content, metadata=metadata, id=key)
                self.hits.append({"rank": rank, "chunk_id": key, "score": float(score),
                                  "metadata": metadata, "text": document.page_content})
                result.append((clone, score))
            return result
        finally:
            self.elapsed_ms = round((time.perf_counter() - started) * 1000, 2)


class RecordingModel:
    def __init__(self, model):
        self.model = model
        self.elapsed_ms = None
        self.usage = None

    def get_num_tokens_from_messages(self, messages):
        return self.model.get_num_tokens_from_messages(messages)

    async def ainvoke(self, messages):
        started = time.perf_counter()
        try:
            response = await self.model.ainvoke(messages)
            self.usage = response.usage_metadata
            return response
        finally:
            self.elapsed_ms = round((time.perf_counter() - started) * 1000, 2)


def evidence_metrics(case, hits, sources):
    if not case["answerable"]:
        return {"hit_at_k": None, "evidence_group_recall": None,
                "context_group_recall": None, "reciprocal_rank": None}
    groups = [set(group) for group in case["expected_evidence_groups"]]
    hit_ids = [hit["chunk_id"] for hit in hits]
    context_ids = {source["chunk_id"] for source in sources}
    expected = set().union(*groups)
    first = next((rank for rank, key in enumerate(hit_ids, 1) if key in expected), None)
    return {
        "hit_at_k": int(first is not None),
        "evidence_group_recall": sum(bool(g.intersection(hit_ids)) for g in groups) / len(groups),
        "context_group_recall": sum(bool(g.intersection(context_ids)) for g in groups) / len(groups),
        "reciprocal_rank": 1 / first if first else 0,
    }


def validate_cases(cases, corpus_ids):
    seen = set()
    for case in cases:
        if case["id"] in seen or not case["question"].strip():
            raise ValueError("Duplicate ID or empty question")
        seen.add(case["id"])
        groups = case["expected_evidence_groups"]
        if case["answerable"] and (not groups or any(not g for g in groups)):
            raise ValueError("Answerable cases require evidence groups")
        if not case["answerable"] and groups:
            raise ValueError("Unanswerable cases must not have gold evidence")
        for group in groups:
            if not set(group) <= corpus_ids:
                raise ValueError("Gold IDs do not match this index snapshot")


def summarize(run_dir, reviews_path=None):
    records = read_jsonl(run_dir / "results.jsonl")
    reviews = read_jsonl(reviews_path) if reviews_path else []
    by_id = {}
    for review in reviews:
        if review.get("results_sha256") and review["results_sha256"] != sha256(run_dir / "results.jsonl"):
            raise ValueError("Review belongs to a different results snapshot")
        if review["id"] in by_id:
            raise ValueError("Duplicate review ID")
        by_id[review["id"]] = review
    if not set(by_id) <= {row["id"] for row in records}:
        raise ValueError("Review contains unknown case ID")
    successful = [r for r in records if r["status"] == "ok"]
    answerable = [r for r in successful if r["answerable"]]
    def mean_metric(key):
        return statistics.mean(r["metrics"][key] for r in answerable) if answerable else None
    summary = {
        "total": len(records), "success": len(successful), "errors": len(records) - len(successful),
        "answerable_success_count": len(answerable),
        "hit_at_k": mean_metric("hit_at_k"),
        "evidence_group_recall": mean_metric("evidence_group_recall"),
        "context_group_recall": mean_metric("context_group_recall"),
        "mrr": mean_metric("reciprocal_rank"),
        "median_total_ms": statistics.median(r["total_ms"] for r in successful) if successful else None,
        "reviewed_count": len(by_id),
        "reviewer_types": sorted({r.get("reviewer", "unspecified") for r in reviews}),
    }
    for field, target in [("answer_correct", True), ("grounded", True), ("abstained", False)]:
        values = [by_id[r["id"]].get(field) for r in successful
                  if r["answerable"] == target and r["id"] in by_id]
        values = [v for v in values if type(v) is bool]
        summary[field + "_reviewed_count"] = len(values)
        summary[field + "_rate"] = sum(values) / len(values) if values else None
    write_json(run_dir / "summary.json", summary)
    lines = ["# 독립 RAG 모듈 평가 결과", "", "## 실행 설정", "",
             "```json", (run_dir / "manifest.json").read_text().strip(), "```", "",
             "## 집계", "", "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```", "",
             "검색 지표는 성공한 답변 가능 질문만 대상으로 한다. 오류 건수는 별도로 확인한다.",
             "근거 그룹 내부 ID는 대체 가능한 근거이며 그룹 간에는 모두 필요한 정보로 정의했다.",
             "Hit@k는 하나 이상 적중, 그룹 재현율은 필요한 정보 그룹의 충족 비율이다.",
             "정답·근거 일치·답변 유보는 자동 판정하지 않고 명시적인 리뷰만 집계한다.", "",
             "리뷰 작성자가 codex_agent이면 에이전트의 1차 검토이며 독립된 사람의 평가가 아니다.", "",
             "## 질문별 결과", "",
             "| ID | 유형 | 상태 | Hit@k | 근거 그룹 재현율 | 전체 ms |",
             "|---|---|---|---|---|---|"]
    for row in records:
        metrics = row.get("metrics", {})
        lines.append(f'| {row["id"]} | {row["category"]} | {row["status"]} | '
                     f'{metrics.get("hit_at_k")} | {metrics.get("evidence_group_recall")} | {row["total_ms"]} |')
    for row in records:
        lines.extend(["", f'### {row["id"]}: {row["question"]}', "",
                      "기대 요점: " + "; ".join(row["expected_points"]), "",
                      "답변:", "", row.get("answer") or f'오류: {row.get("error_type")}', "",
                      "검색 청크: " + ", ".join(h["chunk_id"] for h in row["hits"]), "",
                      "컨텍스트 청크: " + ", ".join(s["chunk_id"] for s in row.get("sources", []))])
        if row["id"] in by_id:
            lines.extend(["", "리뷰:", "", "```json",
                          json.dumps(by_id[row["id"]], ensure_ascii=False, indent=2), "```"])
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


async def evaluate(args, store, cases):
    run_dir = args.output.resolve()
    # Never silently overwrite an earlier baseline.
    run_dir.mkdir(parents=True, exist_ok=False)
    snapshot = {name: sha256(args.index / name) for name in ["index.faiss", "index.pkl"]}
    model = ChatOpenAI(model=args.model, temperature=0, max_tokens=600, timeout=45, max_retries=0)
    manifest = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "index_path": str(args.index), "index_sha256": snapshot,
        "cases_sha256": sha256(args.cases), "module_sha256": sha256(ROOT / "rag_agent.py"),
        "model": args.model, "embedding_model": args.embedding_model,
        "embedding_model_provenance": "Matches existing server default; original index lacks model metadata",
        "embedding_dimensions": store.index.d, "temperature": 0, "max_output_tokens": 600,
        "top_k": args.top_k, "max_input_tokens": 6000, "timeout_seconds": 60,
        "concurrency": 1, "case_count": len(cases),
        "packages": {p: importlib.metadata.version(p) for p in
                     ["langchain-core", "langchain-openai", "langchain-community", "openai", "faiss-cpu"]},
        "limitations": ["Small single-document baseline; not production accuracy.",
                        "No independent human gold validation yet; evidence authored from corpus.",
                        "LLM time is complete-response latency, not first-token latency.",
                        "No model-based automatic correctness judge."]
    }
    write_json(run_dir / "manifest.json", manifest)
    write_jsonl(run_dir / "questions.snapshot.jsonl", cases)
    records = []
    for case in cases:
        recording_store, recording_model = RecordingStore(store), RecordingModel(model)
        row = {**case, "hits": [], "sources": []}
        started = time.perf_counter()
        try:
            result = await answer_question(case["question"], recording_store, recording_model,
                                           top_k=args.top_k, timeout_seconds=60)
            row.update(result)
            row["status"] = "ok"
            row["metrics"] = evidence_metrics(case, recording_store.hits, result["sources"])
        except Exception as exc:
            # Provider exception strings can contain sensitive request details.
            row.update(status="error", error_type=type(exc).__name__,
                       cause_type=type(exc.__cause__).__name__ if exc.__cause__ else None)
        row.update(hits=recording_store.hits,
                   search_ms=recording_store.elapsed_ms, generation_ms=recording_model.elapsed_ms,
                   usage=recording_model.usage,
                   total_ms=round((time.perf_counter() - started) * 1000, 2))
        records.append(row)
        write_jsonl(run_dir / "results.jsonl", records)
        print(f'{case["id"]}: {row["status"]}, {row["total_ms"]} ms', flush=True)
    after = {name: sha256(args.index / name) for name in snapshot}
    manifest["index_unchanged"] = after == snapshot
    write_json(run_dir / "manifest.json", manifest)
    # Initialize review fields as null: the runner must not claim factual accuracy.
    write_jsonl(run_dir / "reviews.template.jsonl", [
        {"id": r["id"], "answer_correct": None, "grounded": None,
         "abstained": None, "notes": ""} for r in records
    ])
    print(json.dumps(summarize(run_dir), ensure_ascii=False, indent=2))
    if not manifest["index_unchanged"]:
        raise RuntimeError("Index changed during evaluation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=PROJECT_ROOT / "faiss_db/pdf")
    parser.add_argument("--cases", type=Path, default=Path(__file__).parent / "questions.jsonl")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "runs" /
                        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    parser.add_argument("--trust-local-index", action="store_true", help="Load the known repository pickle index")
    parser.add_argument("--export-corpus", type=Path, help="Export stored chunks without external API calls")
    parser.add_argument("--summarize", type=Path, help="Rebuild report for an existing run; no API calls")
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--embedding-model", default="text-embedding-3-large")
    parser.add_argument("--top-k", type=int, choices=range(1, 51), default=5)
    args = parser.parse_args()
    if args.summarize:
        print(json.dumps(summarize(args.summarize, args.reviews), ensure_ascii=False, indent=2))
        return
    if not args.trust_local_index:
        parser.error("Pass --trust-local-index only for a known trusted FAISS pickle")
    load_dotenv(PROJECT_ROOT / ".env")
    args.index = args.index.resolve()
    embeddings = NoNetworkEmbeddings() if args.export_corpus else OpenAIEmbeddings(model=args.embedding_model)
    store = FAISS.load_local(str(args.index), embeddings, allow_dangerous_deserialization=True)
    if args.export_corpus:
        corpus = [{"index_position": i, "chunk_id": key,
                   "metadata": store.docstore.search(key).metadata,
                   "text": store.docstore.search(key).page_content}
                  for i, key in sorted(store.index_to_docstore_id.items())]
        args.export_corpus.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(args.export_corpus, corpus)
        print(f"Exported {len(corpus)} chunks without API calls")
        return
    cases = read_jsonl(args.cases)
    validate_cases(cases, set(store.index_to_docstore_id.values()))
    asyncio.run(evaluate(args, store, cases))


if __name__ == "__main__":
    main()
