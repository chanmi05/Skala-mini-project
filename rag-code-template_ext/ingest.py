"""data/regulations 의 규정 PDF 를 한 번에 벡터DB(faiss_db/pdf)에 적재한다.

사용법 (rag-code-template_ext 폴더에서):
    python ingest.py --dry-run            # 임베딩 없이 청크만 확인 (API 비용 없음)
    python ingest.py                      # 기존 PDF 저장소를 지우고 5개 규정으로 새로 적재
    CHUNK_MODE=article python ingest.py   # 조문 단위로 적재
"""
import argparse
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

import pdf_pipeline

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR.parent / "data" / "regulations"


def main() -> None:
    parser = argparse.ArgumentParser(description="사내 규정 PDF 일괄 적재")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--mode", choices=["fixed", "article"], default=os.getenv("CHUNK_MODE", "fixed"))
    parser.add_argument("--dry-run", action="store_true", help="임베딩·저장 없이 청크만 출력")
    parser.add_argument("--keep", action="store_true", help="기존 저장소를 지우지 않고 파일별로 교체")
    args = parser.parse_args()

    pdfs = sorted(args.data_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"PDF가 없습니다: {args.data_dir}")

    all_docs = []
    for pdf in pdfs:
        parsed = pdf_pipeline.parse_pdf(pdf)
        docs = pdf_pipeline.chunk(parsed, args.mode)
        articles = sum(1 for s in parsed.sections if s.article)
        print(f"📄 {parsed.doc} ({parsed.doc_no} v{parsed.version}) 조문 {articles}개 → 청크 {len(docs)}개")
        all_docs.append(docs)

    if args.dry_run:
        for docs in all_docs:
            lengths = [len(d.page_content) for d in docs]
            print(f"\n=== {docs[0].metadata['doc']} | 청크 길이 최소 {min(lengths)} / 최대 {max(lengths)}")
            for d in docs[:3]:
                m = d.metadata
                print(f"--- p.{m['page']} {m['chapter']} | {m['article']} {m['title']}")
                print(d.page_content[:200])
        return

    load_dotenv(BASE_DIR / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 없습니다. rag-code-template_ext/.env 를 확인하세요.")

    if not args.keep and pdf_pipeline.PDF_STORE_PATH.exists():
        shutil.rmtree(pdf_pipeline.PDF_STORE_PATH)
        print("🗑  기존 faiss_db/pdf 삭제")

    store = pdf_pipeline.load_store()
    for docs in all_docs:
        store = pdf_pipeline.upsert(store, docs)
    pdf_pipeline.save_store(store)

    print("\n✅ 적재 완료:", pdf_pipeline.count_by_source(store))


if __name__ == "__main__":
    main()
