"""근거 제한·인용·유보·조문 조회의 회귀 검증. 외부 모델/인덱스 미사용."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'evaluation')]
from evaluate_improvement import fixtures, ScriptedModel, LocalEmbedding, exact_store
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from rag_api import public_sources
from rag_retrieval import MetadataLookup, search_target
from rag_router import RagService
from rag_agent import GenerationError, validate_answer
from session_memory import InMemorySessionStore
from test_rag_workflow import FakeStore


class ImprovementTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_before_after_scenarios(self):
        rows = await fixtures()
        self.assertEqual(len(rows), 8)
        self.assertEqual([r['id'] for r in rows if not r['pass']], [])

    async def test_generation_context_contains_only_selected_evidence(self):
        docs = [(Document(page_content='승인된 근거', id='a'), .1),
                (Document(page_content='제외해야 하는 문장', id='b'), .2)]
        model = ScriptedModel(selected='S1')
        result = await RagService(FakeStore({'q': docs}), model).ainvoke({'question': 'q'})
        self.assertEqual(result['source_ids'], ['a'])
        self.assertNotIn('제외해야 하는 문장', model.generation_input)

    async def test_selected_second_source_is_canonical_on_replay(self):
        store = FAISS.from_documents([
            Document(page_content='근거 A', metadata={'doc': '스칼라테크 휴가규정', 'article': '제12조'}),
            Document(page_content='근거 B', metadata={'doc': '스칼라테크 휴가규정', 'article': '제12조'})],
            LocalEmbedding(), ids=['a', 'b'])
        model = ScriptedModel(selected='S2')
        sessions = InMemorySessionStore()
        sid = (await sessions.create_session()).session_id
        question = '휴가규정 제12조 내용은?'
        model.decisions['MemoryDecision'] = [{'action': 'ready', 'standalone_question': question}]
        service = RagService(store, model, session_store=sessions)
        data = {'question': question, 'session_id': sid, 'request_id': 'same'}
        first = await service.ainvoke(data)
        replay = await service.ainvoke(data)
        self.assertEqual(first['source_ids'], ['b'])
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['model_calls'], 0)
        self.assertEqual(public_sources(first, store), public_sources(replay, store))
        self.assertEqual(first['output'], replay['output'])
        self.assertIn('[S1]', first['output'])

    async def test_paraphrased_structured_abstention_is_saved_as_no_evidence(self):
        model = ScriptedModel()
        original = model.with_structured_output
        from langchain_core.runnables import RunnableLambda
        def structured(schema, **kwargs):
            if schema.__name__ == 'GenerationDecision':
                return RunnableLambda(lambda messages: {'parsed': {'status': 'no_evidence', 'answer': '이 정보는 문서로 확인하기 어렵습니다.'}, 'parsing_error': None})
            return original(schema, **kwargs)
        model.with_structured_output = structured
        sessions = InMemorySessionStore()
        sid = (await sessions.create_session()).session_id
        result = await RagService(FakeStore(), model, session_store=sessions).ainvoke(
            {'question': '질문', 'session_id': sid, 'request_id': 'abstain'})
        self.assertEqual(result['status'], 'no_evidence')
        self.assertEqual(result['sources'], [])
        saved = (await sessions.get_session(sid)).turns[-1]
        self.assertEqual(saved.status, 'no_evidence')
        self.assertEqual(saved.source_ids, ())

    async def test_post_generation_review_rejects_wrong_claim_or_missing_target(self):
        for decision in ["unsupported", "not_found"]:
            model = ScriptedModel()
            model.decisions["AnswerReview"] = [{"decision": decision, "reason_code": "fixture"}]
            result = await RagService(FakeStore(), model).ainvoke({"question": "q"})
            self.assertEqual(result["status"], "no_evidence")
            self.assertEqual(result["sources"], [])
            self.assertTrue(any(e["stage"] == "verify_answer" for e in result["trace"]))

    async def test_review_budget_failure_is_not_reported_as_a_grounded_answer(self):
        from rag_state import RagSettings
        result = await RagService(FakeStore(), ScriptedModel(),
                                  settings=RagSettings(max_model_calls=3)).ainvoke({"question": "q"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["reason_code"], "budget_exhausted")
        self.assertEqual(result["sources"], [])

    async def test_explicit_target_never_falls_back_to_semantic_search(self):
        store = exact_store()
        with patch.object(store, 'asimilarity_search_with_score', side_effect=AssertionError('semantic search')):
            result = await RagService(store, ScriptedModel()).ainvoke({'question': '휴가규정 제12조 내용은?'})
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(result['search_count'], 1)
        self.assertEqual(result['sources'][0]['metadata']['doc'], '스칼라테크 휴가규정')

    async def test_unknown_article_never_rewrites_to_another_article(self):
        model = ScriptedModel()
        result = await RagService(exact_store(), model).ainvoke({'question': '휴가규정 제999조 내용은?'})
        self.assertEqual(result['status'], 'no_evidence')
        self.assertEqual(result['search_count'], 1)
        self.assertNotIn('RewrittenQuery', model.calls)
        self.assertNotIn('generate', model.calls)

    async def test_metadata_lookup_is_built_once(self):
        store = exact_store()
        lookup = MetadataLookup(store)
        with patch.object(store.docstore, 'search', wraps=store.docstore.search) as search:
            first, _ = lookup.find(search_target('휴가규정 제12조'))
            calls = search.call_count
            second, _ = lookup.find(search_target('휴가규정 제12조'))
            self.assertEqual(search.call_count, calls)
        self.assertEqual(first, second)

    async def test_article_ambiguity_asks_before_generation(self):
        model = ScriptedModel()
        result = await RagService(exact_store(), model).ainvoke({'question': '제12조 내용은?'})
        self.assertEqual(result['status'], 'clarification_needed')
        self.assertNotIn('EvidenceDecision', model.calls)
        self.assertNotIn('generate', model.calls)

    async def test_unsupported_exact_lookup_is_an_error_not_absence(self):
        result = await RagService(FakeStore(), ScriptedModel()).ainvoke({'question': '휴가규정 제12조 내용은?'})
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['reason_code'], 'retrieval_error')


class CitationTests(unittest.TestCase):
    def test_missing_and_unknown_citations_rejected(self):
        for text in ['인용 없는 사실', '없는 근거 [S9]', '']:
            with self.subTest(text=text), self.assertRaises(GenerationError):
                validate_answer(text, [{'id': 'S1'}])
        self.assertEqual(validate_answer('정상 [S1]', [{'id': 'S1'}]), '정상 [S1]')

    def test_target_normalization_and_multiple_articles(self):
        target = search_target('스칼라테크 휴가 규정 제 012 조와 제13조의2')
        self.assertEqual(target.documents, ('휴가규정',))
        self.assertEqual(target.articles, ('제12조', '제13조의2'))
        self.assertIsNone(search_target('연차를 어떻게 신청하나요?'))
