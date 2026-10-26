"""실제 임베딩·LLM으로 업로드→질의→후속 질문→종료를 임시 인덱스에서 확인한다."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path[:0] = [str(ROOT), str(PROJECT)]
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from rag_api import create_app
import pdf_pipeline


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    index = PROJECT / "faiss_db/pdf"
    digest = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in index.iterdir() if p.is_file()}
    before = digest()
    embedding = OpenAIEmbeddings(model="text-embedding-ada-002", request_timeout=30, max_retries=0)
    model = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=1200, timeout=30, max_retries=0)
    store = pdf_pipeline.load_store(index, embedding)
    results = []
    with tempfile.TemporaryDirectory(prefix="skala-hr-api-") as directory:
        temporary = Path(directory).resolve()
        assert temporary.name.startswith("skala-hr-api-") and temporary != index.resolve()
        target = temporary / "index"
        pdf_pipeline.save_store(store, target)
        app = create_app(index_path=target, vectorstore=store, llm=model, embedding=embedding)
        with TestClient(app) as client:
            first = client.post("/rag-query", json={"prompt": "출장규정 제12조의 비용 정산 제출기한은?", "request_id": "before"})
            results.append({"stage": "query_before", "http_status": first.status_code, "body": first.json()})
            if first.status_code == 200:
                sid = first.json()["session_id"]
                pdf = PROJECT.parent / "data/regulations/02_복리후생규정.pdf"
                uploaded = client.post("/upload-paper", files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")})
                results.append({"stage": "upload", "http_status": uploaded.status_code, "body": uploaded.json()})
                stale = client.post("/rag-query", json={"prompt": "그럼 지급은?", "session_id": sid, "request_id": "stale"})
                results.append({"stage": "stale_session", "http_status": stale.status_code, "body": stale.json()})
                fresh = client.post("/rag-query", json={"prompt": "복리후생규정 제9조에서 본인 혼인 경조금의 제안액은 얼마인가요?", "request_id": "after"})
                results.append({"stage": "query_after", "http_status": fresh.status_code, "body": fresh.json()})
                if fresh.status_code == 200:
                    sid = fresh.json()["session_id"]
                    follow = client.post("/rag-query", json={"prompt": "그 경조금은 어떤 규정에 따른 금액인가요?", "session_id": sid, "request_id": "follow"})
                    results.append({"stage": "followup", "http_status": follow.status_code, "body": follow.json()})
                    ended = client.delete("/sessions/" + sid)
                    results.append({"stage": "end", "http_status": ended.status_code, "body": ended.json()})
                    closed = client.post("/rag-query", json={"prompt": "다시 알려줘", "session_id": sid})
                    results.append({"stage": "closed_session", "http_status": closed.status_code, "body": closed.json()})
    report = {"results": results, "original_index_unchanged": before == digest(),
              "limitations": ["API TestClient flow, not a production multi-worker or authenticated browser test.",
                               "Original index preserved; actual embedding upload uses a disposable index."]}
    (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    lines = ["# 실제 RAG API 업로드·대화 점검", "", "기존 원본 인덱스와 분리한 임시 인덱스에서 실제 OpenAI 임베딩·LLM을 호출했다.", "",
             "| 단계 | HTTP | 상태 |", "|---|---|---|"]
    for row in results:
        lines.append(f"| {row['stage']} | {row['http_status']} | {row['body'].get('status', row['body'].get('detail', 'ok'))} |")
    lines.extend(["", f"원본 인덱스 유지: {report['original_index_unchanged']}", "",
                  "전체 응답은 results.json에 보관했다. 생성한 임시 인덱스는 검증 종료 시 정리했다. 사용자 로그인·음성 인식·TTS는 이 평가에 포함하지 않았다."])
    (output / "report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps({"stages": [(r["stage"], r["http_status"]) for r in results], "index_unchanged": report["original_index_unchanged"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trust-local-index", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "runs" / ("hr_api_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")))
    args = parser.parse_args()
    if not args.trust_local_index:
        parser.error("Known trusted local FAISS index requires --trust-local-index")
    load_dotenv(PROJECT / ".env")
    run(args.output)
