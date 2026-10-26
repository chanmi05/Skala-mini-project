"""평가셋으로 검색 품질(Hit@K, MRR)을 잰다.

정답은 청크 ID가 아니라 (규정명, 조문)으로 판정하므로, 청킹 방식이 달라도 같은 평가셋을 쓴다.
저장된 faiss_db/pdf 는 건드리지 않고, 모드마다 메모리에 저장소를 새로 만들어 비교한다.

사용법 (rag-code-template_ext 폴더에서):
    .venv/bin/python eval_retrieval.py                     # fixed, article 둘 다
    .venv/bin/python eval_retrieval.py --modes article     # 하나만
    .venv/bin/python eval_retrieval.py --k 5 --out ../data/eval/result.csv
"""
import argparse
import csv
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

import pdf_pipeline

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
DEFAULT_EVAL = DATA_DIR / "eval" / "eval_set.csv"


def load_eval(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_store(mode: str, embeddings: OpenAIEmbeddings) -> FAISS:
    docs = []
    for pdf in sorted((DATA_DIR / "regulations").glob("*.pdf")):
        docs += pdf_pipeline.chunk(pdf_pipeline.parse_pdf(pdf), mode)
    return FAISS.from_documents(docs, embeddings)


def gold_rank(results: list, row: dict) -> int | None:
    """정답 조문이 처음 나온 순위(1부터). 없으면 None."""
    for rank, (doc, _) in enumerate(results, start=1):
        meta = doc.metadata
        if meta.get("doc") == row["근거_규정"] and meta.get("article") == row["근거_조문"]:
            return rank
    return None


def evaluate(store: FAISS, rows: list[dict], k: int) -> tuple[dict, list[dict]]:
    answerable = [r for r in rows if r["근거_조문"]]
    detail, ranks = [], []
    for row in rows:
        results = store.similarity_search_with_score(row["질문"], k=k)
        rank = gold_rank(results, row) if row["근거_조문"] else None
        top = results[0][0].metadata if results else {}
        if row["근거_조문"]:
            ranks.append(rank)
        detail.append({
            "id": row["id"],
            "유형": row["유형"],
            "질문": row["질문"],
            "정답": f"{row['근거_규정']} {row['근거_조문']}".strip(),
            "정답_순위": rank or "",
            "1위_검색결과": f"{top.get('doc', '')} {top.get('article', '')} {top.get('title', '')}".strip(),
            "1위_거리": round(results[0][1], 4) if results else "",
        })

    n = len(answerable)
    summary = {f"Hit@{x}": sum(1 for r in ranks if r and r <= x) / n for x in (1, 3, k)}
    summary["MRR"] = sum(1 / r for r in ranks if r) / n
    summary["정답 문항"] = n
    return summary, detail


def main() -> None:
    parser = argparse.ArgumentParser(description="평가셋 기반 검색 평가 (Hit@K, MRR)")
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--modes", nargs="+", default=["fixed", "article"], choices=["fixed", "article"])
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", type=Path, help="문항별 결과를 저장할 CSV")
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다. rag-code-template_ext/.env 를 확인하세요.")

    rows = load_eval(args.eval)
    embeddings = OpenAIEmbeddings()
    all_detail = []
    print(f"평가셋 {len(rows)}문항 (정답 있는 문항 {sum(1 for r in rows if r['근거_조문'])}개), top-k={args.k}\n")

    for mode in args.modes:
        summary, detail = evaluate(build_store(mode, embeddings), rows, args.k)
        print(f"[{mode}] " + "  ".join(f"{name} {value:.3f}" if isinstance(value, float) else f"{name} {value}"
                                       for name, value in summary.items()))
        misses = [d for d in detail if d["정답"] and not d["정답_순위"]]
        for d in misses:
            print(f"   ✗ {d['id']} {d['질문']}  (정답 {d['정답']} / 1위 {d['1위_검색결과']})")
        all_detail += [{"mode": mode, **d} for d in detail]

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_detail[0].keys()))
            writer.writeheader()
            writer.writerows(all_detail)
        print(f"\n문항별 결과 저장: {args.out}")


if __name__ == "__main__":
    main()
