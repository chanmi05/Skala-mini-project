"""Compare completed top-k runs locally; no API calls or correctness guessing."""

import argparse
import json
import math
from pathlib import Path
import statistics

if __package__:
    from .run_evaluation import read_jsonl, sha256, write_json
else:
    from run_evaluation import read_jsonl, sha256, write_json


MATCH_FIELDS = ["index_sha256", "cases_sha256", "module_sha256", "model", "embedding_model",
                "embedding_dimensions", "temperature", "max_output_tokens", "max_input_tokens",
                "timeout_seconds", "concurrency", "packages", "case_count"]


def check_compatibility(manifests):
    first = manifests[0]
    for manifest in manifests[1:]:
        for field in MATCH_FIELDS:
            if manifest[field] != first[field]:
                raise ValueError(f"Runs differ in {field}; not a top-k-only comparison")
    if len({m["top_k"] for m in manifests}) != len(manifests):
        raise ValueError("Duplicate top_k runs")
    if not all(m.get("index_unchanged") for m in manifests):
        raise ValueError("Run lacks confirmation that index was unchanged")


def stats(rows, field):
    values = [r[field] for r in rows if r.get(field) is not None]
    if not values:
        return None
    return {"mean": statistics.mean(values), "median": statistics.median(values),
            "p95_nearest_rank": sorted(values)[math.ceil(len(values) * 0.95) - 1]}


def compare(paths, output):
    manifests = [json.loads((p / "manifest.json").read_text()) for p in paths]
    check_compatibility(manifests)
    datasets = [read_jsonl(p / "results.jsonl") for p in paths]
    question_map = {r["id"]: r["question"] for r in datasets[0]}
    for manifest, rows in zip(manifests, datasets):
        if len(rows) != manifest["case_count"] or len({r["id"] for r in rows}) != len(rows):
            raise ValueError("Incomplete or duplicated results")
        if {r["id"]: r["question"] for r in rows} != question_map:
            raise ValueError("Question IDs/text differ")
    results = []
    by_k = {}
    for path, manifest, rows in sorted(zip(paths, manifests, datasets), key=lambda entry: entry[1]["top_k"]):
        ok = [r for r in rows if r["status"] == "ok"]
        answerable = [r for r in ok if r["answerable"]]
        metrics = {name: statistics.mean(r["metrics"][name] for r in answerable) if answerable else None
                   for name in ["hit_at_k", "evidence_group_recall", "context_group_recall", "reciprocal_rank"]}
        # Token counts come from provider usage, not estimates from string lengths.
        usage_rows = [{field: (r.get("usage") or {}).get(field) for field in
                       ["input_tokens", "output_tokens", "total_tokens"]} for r in ok]
        results.append({
            "top_k": manifest["top_k"], "run_path": str(path),
            "started_at_utc": manifest["started_at_utc"],
            "results_sha256": sha256(path / "results.jsonl"),
            "total": len(rows), "success": len(ok), "errors": len(rows) - len(ok),
            "answerable_success": len(answerable), **metrics,
            "search_ms": stats(ok, "search_ms"), "generation_ms": stats(ok, "generation_ms"),
            "total_ms": stats(ok, "total_ms"),
            "usage_reported_count": sum(r["input_tokens"] is not None for r in usage_rows),
            "usage": {field: stats(usage_rows, field) for field in
                      ["input_tokens", "output_tokens", "total_tokens"]},
            "mean_context_count": statistics.mean(len(r["sources"]) for r in ok) if ok else None,
            "retrieval_miss_ids": [r["id"] for r in answerable if not r["metrics"]["hit_at_k"]],
        })
        by_k[manifest["top_k"]] = {r["id"]: r for r in rows}
    comparison = {"runs": results, "limitations": [
        "One run per k; baseline k=5 reused from an earlier execution.",
        "Latency includes provider/network/caching variability; not a causal benchmark.",
        "Gold evidence authored by agent and not independently reviewed.",
        "No aggregate answer accuracy assigned without a comparable review set.",
        "Historical embedding model is inferred from server defaults, not index metadata.",
    ]}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "comparison.json", comparison)
    lines = ["# top_k 비교 평가", "", "같은 24개 질문·모델·RAG 모듈·인덱스·입력 예산으로 비교했다.",
             "k=5는 기존 실행을 재사용했고 나머지는 순차 실행했다. 기존 기준 결과는 변경하지 않았다.", "",
             "## 집계", "", "| k | 성공/전체 | Hit@k | 근거 그룹 재현율 | 컨텍스트 재현율 | MRR | 중앙 응답 초 | 평균 입력 토큰 | 평균 사용 청크 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for row in results:
        fmt = lambda v: f"{v:.3f}" if v is not None else "N/A"
        mean_input = (row["usage"]["input_tokens"] or {}).get("mean")
        latency = row["total_ms"]["median"] / 1000 if row["total_ms"] else None
        lines.append(f'| {row["top_k"]} | {row["success"]}/{row["total"]} | '
                     f'{fmt(row["hit_at_k"])} | {fmt(row["evidence_group_recall"])} | '
                     f'{fmt(row["context_group_recall"])} | {fmt(row["reciprocal_rank"])} | '
                     f'{fmt(latency)} | {fmt(mean_input)} | {fmt(row["mean_context_count"])} |')
    lines.extend(["", "검색 지표는 성공한 답변 가능 질문만 대상으로 하며 답변 정확도와 구분한다.", "",
                  "## 질문별 검색 성공", "", "| 질문 | " + " | ".join(f"k={k}" for k in by_k) + " |",
                  "|---|" + "---|" * len(by_k)])
    for key in question_map:
        if not by_k[next(iter(by_k))][key]["answerable"]:
            continue
        values = [str(by_k[k][key].get("metrics", {}).get("hit_at_k", "error")) for k in by_k]
        lines.append(f'| {key} | ' + " | ".join(values) + " |")
    lines.extend(["", "## 해석 시 주의", "",
                  "- 검색률의 분모는 성공한 답변 가능 질문이다. 오류와 성공 수를 함께 확인한다.",
                  "- 입력 토큰·지연이 증가해도 답변 품질이 개선되었다고 자동 판정하지 않는다.",
                  "- 각 k는 1회 실행이며 시간·캐시·네트워크·출력 길이 영향이 섞인다.",
                  "- 답변 정확도와 인용 충실성은 별도 검토해야 한다.",
                  "- 상세 후보·답변·점수·사용 출처는 각 실행의 results.jsonl/report.md에 보존했다."])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return comparison


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.runs, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
