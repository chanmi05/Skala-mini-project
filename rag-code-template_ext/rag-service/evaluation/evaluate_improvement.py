"""동일 사례의 개선 전후 비교. 기본은 로컬 모의 모델, --live는 실제 API 호출."""
import argparse
import asyncio
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
CODE_ROOT = Path(os.getenv('RAG_REVIEW_CODE_ROOT', str(ROOT)))
sys.path[:0] = [str(CODE_ROOT), str(CODE_ROOT / 'tests')]
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS
from rag_agent import NO_EVIDENCE
from rag_router import RagService
from rag_state import RagSettings
from session_memory import InMemorySessionStore
from test_memory_workflow import MemoryModel
from test_rag_workflow import FakeStore


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ScriptedModel(MemoryModel):
    def __init__(self, output='정상 답변 [S1]', selected='S1'):
        super().__init__({'EvidenceDecision': [{'decision': 'sufficient', 'supported_source_ids': [selected]}]})
        self.output = output
        self.generation_input = ''

    async def ainvoke(self, messages):
        self.calls.append('generate')
        self.generation_input = '\n'.join(m.content for m in messages)
        return SimpleNamespace(content=self.output)

    def with_structured_output(self, schema, include_raw, **kwargs):
        if schema.__name__ == 'GenerationDecision':
            async def generate(messages):
                response = await self.ainvoke(messages)
                return {'parsed': {'status': 'no_evidence' if self.output == NO_EVIDENCE else 'answered',
                                   'answer': response.content}, 'parsing_error': None}
            return RunnableLambda(generate)
        return super().with_structured_output(schema, include_raw, **kwargs)


class LocalEmbedding(Embeddings):
    def embed_documents(self, texts):
        return [[float(n), 0.] for n, _ in enumerate(texts)]
    def embed_query(self, text):
        return [0., 0.]


def exact_store():
    docs = [Document(page_content='본인 혼인 5일', metadata={'doc': '스칼라테크 취업규정', 'article': '제12조'}) for _ in range(25)]
    docs.append(Document(page_content='배우자 출산휴가 20일', metadata={'doc': '스칼라테크 휴가규정', 'article': '제12조'}))
    return FAISS.from_documents(docs, LocalEmbedding(), ids=[f'chunk-{n}' for n in range(26)])


async def fixtures():
    docs = [(Document(page_content='본인 혼인 5일', metadata={'doc': '휴가규정'}, id='a'), .1),
            (Document(page_content='출장 중 주차비 실비', metadata={'doc': '출장규정'}, id='b'), .2)]
    cases = [
        ('normal', '질문', '정상 답변 [S1]', 'S1', 'answered'),
        ('unselected_source', '질문', '미선택 근거 답변 [S2]', 'S1', 'error'),
        ('uncited', '질문', '형제 혼인도 5일입니다.', 'S1', 'error'),
        ('abstention', '질문', NO_EVIDENCE, 'S1', 'no_evidence'),
        ('selected_second', '질문', '정상 답변 [S1]', 'S2', 'answered'),
        ('exact_article', '휴가규정 제12조 내용은?', '정상 답변 [S1]', 'S1', 'answered'),
        ('missing_article', '휴가규정 제999조 내용은?', '정상 답변 [S1]', 'S1', 'no_evidence'),
        ('ambiguous_article', '제12조 내용은?', '정상 답변 [S1]', 'S1', 'clarification_needed'),
    ]
    rows = []
    for name, question, output, selected, expected in cases:
        model = ScriptedModel(output, selected)
        store = exact_store() if 'article' in name else FakeStore({'질문': docs})
        sessions = InMemorySessionStore()
        sid = (await sessions.create_session()).session_id
        service = RagService(store, model, session_store=sessions, count_tokens=lambda m: 100)
        # Resolve fixture text without relying on model semantics.
        model.decisions['MemoryDecision'] = [{'action': 'ready', 'standalone_question': question}]
        result = await service.ainvoke({'question': question, 'session_id': sid, 'request_id': name})
        passed = result['status'] == expected
        if name == 'selected_second':
            passed = passed and result['source_ids'] == ['b']
        if name == 'exact_article':
            passed = passed and all(s['metadata']['doc'] == '스칼라테크 휴가규정' for s in result['sources'])
        rows.append({'id': name, 'question': question, 'expected_status': expected, 'pass': passed,
                     'result': result, 'generation_contains_unselected': '출장 중 주차비 실비' in model.generation_input})
    return rows


async def live(args):
    from dotenv import load_dotenv
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    load_dotenv(PROJECT / '.env')
    index = PROJECT / 'faiss_db/pdf'
    before = {name: sha(index / name) for name in ['index.faiss', 'index.pkl']}
    embeddings = OpenAIEmbeddings(model=args.embedding_model, request_timeout=30, max_retries=0)
    store = FAISS.load_local(str(index), embeddings, allow_dangerous_deserialization=True)
    cases = list(csv.DictReader(args.cases.open(encoding='utf-8-sig', newline='')))
    model = ChatOpenAI(model='gpt-4o', temperature=0, max_tokens=1200, timeout=30, max_retries=0)
    sessions = InMemorySessionStore()
    service = RagService(store, model, session_store=sessions,
                         settings=RagSettings(top_k=args.top_k, timeout_seconds=60, summary_max_chars=2000))
    gate = asyncio.Semaphore(2)
    async def one(case):
        async with gate:
            sid = (await sessions.create_session()).session_id
            result = await service.ainvoke({'question': case['질문'], 'session_id': sid, 'request_id': case['id']})
            row = {'case': case, 'result': result}
            (args.output / (case['id'] + '.json')).write_text(json.dumps(row, ensure_ascii=False, indent=2)+'\n')
            print(case['id'], result['status'], result['elapsed_ms'], flush=True)
            return row
    rows = await asyncio.gather(*(one(case) for case in cases))
    after = {name: sha(index / name) for name in before}
    return rows, {'index_sha256': before, 'index_unchanged': before == after,
                  'cases_sha256': sha(args.cases), 'embedding_model': args.embedding_model,
                  'model': 'gpt-4o', 'top_k': args.top_k, 'concurrency': 2,
                  'cases_snapshot': cases}


async def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'mode': 'live' if args.live else 'fixture',
                'module_sha256': {p.name: sha(p) for p in CODE_ROOT.glob('*.py')}, 'runner_sha256': sha(Path(__file__))}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    if args.live:
        rows, extra = await live(args)
        manifest.update(extra)
    else:
        rows = await fixtures()
    (args.output / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
    manifest['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print('completed', len(rows), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--cases', type=Path, default=PROJECT.parent/'data/eval/eval_set.csv')
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--embedding-model', default='text-embedding-3-large')
    asyncio.run(main(parser.parse_args()))
