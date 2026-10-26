"""실제 LangChain RunnableBranch/LCEL와 LangGraph를 모의 모델로 검증한다."""

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from rag_router import RagService
from rag_state import RagSettings


def evidence(text="규정 본문", key="a"):
    return [(Document(page_content=text, metadata={"source": key}, id=key), 0.2)]


class FakeStore:
    def __init__(self, mapping=None):
        self.mapping = mapping
        self.calls = []

    async def asimilarity_search_with_score(self, query, k):
        self.calls.append((query, k))
        if self.mapping is None:
            return evidence(key=query)
        return self.mapping.get(query, [])


def insufficient(missing="기간"):
    return {"decision": "insufficient", "missing_information": [missing], "reason_code": "missing_fact"}


class FakeModel:
    def __init__(self, decisions=None):
        self.decisions = {key: list(values) for key, values in (decisions or {}).items()}
        self.calls = []
        self.inputs = []

    def get_num_tokens_from_messages(self, messages):
        return sum(len(m.content) for m in messages)

    def with_structured_output(self, schema, include_raw, **kwargs):
        if schema.__name__ == "AnswerReview":
            async def review(messages):
                self.calls.append("AnswerReview")
                self.inputs.append(messages)
                queued = self.decisions.get("AnswerReview")
                return {"parsed": queued.pop(0) if queued else {"decision": "grounded", "reason_code": "fixture"},
                        "parsing_error": None}
            return RunnableLambda(review)
        if schema.__name__ == "GenerationDecision":
            async def generate(messages):
                response = await self.ainvoke(messages)
                return {"parsed": {"status": "answered", "answer": response.content},
                        "raw": response, "parsing_error": None}
            return RunnableLambda(generate)
        async def call(messages):
            name = schema.__name__
            self.calls.append(name)
            self.inputs.append(messages)
            queued = self.decisions.get(name)
            if queued:
                result = queued.pop(0)
            elif name == "RouteDecision":
                result = {"intent": "document_question", "reason_code": "document",
                          "standalone_question": messages[-1].content.split("현재 질문: ")[-1]}
            elif name == "EvidenceDecision":
                result = {"decision": "sufficient", "supported_source_ids": ["S1"],
                          "reason_code": "supported"}
            else:
                result = {"search_query": "다른 표현"}
            if isinstance(result, Exception):
                raise result
            return {"parsed": result, "parsing_error": None,
                    "raw": SimpleNamespace(usage_metadata={"input_tokens": 10, "output_tokens": 5})}

        return RunnableLambda(call)

    async def ainvoke(self, messages):
        self.calls.append("generate")
        self.inputs.append(messages)
        return SimpleNamespace(content="문서에 따른 답변 [S1]", usage_metadata={"output_tokens": 8})


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_input_and_invalid_history_never_call_model(self):
        model, store = FakeModel(), FakeStore()
        service = RagService(store, model)
        for data in [{"question": " "}, {"question": "q", "history": [{"role": "system", "content": "x"}]}]:
            with self.assertRaises(ValueError):
                await service.ainvoke(data)
        self.assertEqual(model.calls, [])
        self.assertEqual(store.calls, [])

    async def test_empty_model_explanation_does_not_reject_valid_business_decision(self):
        model = FakeModel({"RouteDecision": [{"intent": "document_question", "standalone_question": "q", "reason_code": ""}],
                           "EvidenceDecision": [{"decision": "sufficient", "supported_source_ids": ["S1"], "reason_code": ""}]})
        result = await RagService(FakeStore(), model).ainvoke({"question": "q"})
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["reason_code"], "evidence_sufficient")

    async def test_greeting_does_not_search_or_call_model(self):
        model, store = FakeModel(), FakeStore()
        result = await RagService(store, model).ainvoke({"question": "안녕하세요!"})
        self.assertEqual(result["status"], "greeting")
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(store.calls, [])

    async def test_greeting_plus_question_is_not_discarded(self):
        store = FakeStore()
        result = await RagService(store, FakeModel()).ainvoke({"question": "안녕하세요, 휴가 조건은?"})
        self.assertEqual(result["status"], "answered")
        self.assertEqual(len(store.calls), 1)

    async def test_short_topic_reaches_document_graph(self):
        result = await RagService(FakeStore(), FakeModel()).ainvoke({"question": "연차?"})
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["search_count"], 1)
        self.assertEqual(result["model_calls"], 4)

    async def test_router_clarification_without_search(self):
        model = FakeModel({"RouteDecision": [{"intent": "clarify", "reason_code": "missing_subject",
                                               "clarification_question": "어떤 신청인가요?"}]})
        store = FakeStore()
        result = await RagService(store, model).ainvoke({"question": "어떻게 해?"})
        self.assertEqual(result["status"], "clarification_needed")
        self.assertEqual(result["answer"], "어떤 신청인가요?")
        self.assertEqual(store.calls, [])

    async def test_history_resolves_followup(self):
        model = FakeModel({"RouteDecision": [{"intent": "document_question", "reason_code": "followup",
                                               "standalone_question": "휴가 신청 방법"}]})
        store = FakeStore()
        result = await RagService(store, model).ainvoke({"question": "그럼 신청은?",
                           "history": [{"role": "user", "content": "휴가를 알고 싶어요"}]})
        self.assertEqual(result["status"], "answered")
        self.assertEqual(store.calls[0][0], "휴가 신청 방법")
        self.assertIn("휴가를 알고 싶어요", model.inputs[0][-1].content)

    async def test_success_after_one_rewrite_no_duplicate_generation_search(self):
        model = FakeModel({"EvidenceDecision": [insufficient(),
                           {"decision": "sufficient", "supported_source_ids": ["S1"], "reason_code": "ok"}],
                           "RewrittenQuery": [{"search_query": "신청 기간"}]})
        store = FakeStore({"신청?": evidence("대상", "a"), "신청 기간": evidence("기간", "b")})
        result = await RagService(store, model).ainvoke({"question": "신청?"})
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["search_count"], 2)
        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(result["sources"][0]["metadata"]["source"], "b")
        self.assertEqual(model.calls.count("generate"), 1)
        self.assertEqual(len(store.calls), 2)

    async def test_empty_first_search_can_recover(self):
        model = FakeModel({"RewrittenQuery": [{"search_query": "q2"}]})
        store = FakeStore({"q": [], "q2": evidence()})
        result = await RagService(store, model).ainvoke({"question": "q"})
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["search_count"], 2)
        self.assertEqual(model.calls.count("EvidenceDecision"), 1)

    async def test_reported_schema_tokens_count_toward_budget(self):
        # 사전 카운터에는 스키마가 빠질 수 있다. 실제 입력 사용량으로 사후 보정한다.
        result = await RagService(FakeStore(), FakeModel(), count_tokens=lambda messages: 1,
                                 settings=RagSettings(max_total_input_tokens=5)).ainvoke({"question": "q"})
        self.assertEqual(result["reason_code"], "budget_exhausted")
        self.assertEqual(result["input_tokens_estimate"], 1)
        self.assertEqual(result["budget_input_tokens"], 10)
        self.assertEqual(result["search_count"], 0)

    async def test_zero_retry_budget(self):
        model = FakeModel({"EvidenceDecision": [insufficient()]})
        result = await RagService(FakeStore(), model, settings=RagSettings(max_retries=0)).ainvoke({"question": "q"})
        self.assertEqual(result["status"], "no_evidence")
        self.assertEqual(result["reason_code"], "retry_limit")
        self.assertEqual(result["search_count"], 1)
        self.assertNotIn("RewrittenQuery", model.calls)

    async def test_two_retries_means_at_most_three_searches(self):
        model = FakeModel({"EvidenceDecision": [insufficient("a"), insufficient("b"), insufficient("c")],
                           "RewrittenQuery": [{"search_query": "q2"}, {"search_query": "q3"}]})
        result = await RagService(FakeStore(), model, settings=RagSettings(max_retries=2)).ainvoke({"question": "q1"})
        self.assertEqual(result["status"], "no_evidence")
        self.assertEqual(result["search_count"], 3)
        self.assertEqual(result["retry_count"], 2)
        self.assertNotIn("generate", model.calls)

    async def test_duplicate_query_stops_before_second_search(self):
        model = FakeModel({"EvidenceDecision": [insufficient()],
                           "RewrittenQuery": [{"search_query": "Q !"}]})
        result = await RagService(FakeStore(), model).ainvoke({"question": "q"})
        self.assertEqual(result["reason_code"], "duplicate_query")
        self.assertEqual(result["search_count"], 1)

    async def test_same_evidence_and_missing_facts_stop_early(self):
        model = FakeModel({"EvidenceDecision": [insufficient(), insufficient()],
                           "RewrittenQuery": [{"search_query": "q2"}]})
        store = FakeStore({"q": evidence(), "q2": evidence()})
        result = await RagService(store, model, settings=RagSettings(max_retries=2)).ainvoke({"question": "q"})
        self.assertEqual(result["reason_code"], "no_progress")
        self.assertEqual(len(store.calls), 2)

    async def test_graph_can_request_user_condition(self):
        model = FakeModel({"EvidenceDecision": [{"decision": "clarify", "reason_code": "subject",
                                                  "clarification_question": "어떤 직군인가요?"}]})
        result = await RagService(FakeStore(), model).ainvoke({"question": "조건?"})
        self.assertEqual(result["status"], "clarification_needed")
        self.assertEqual(result["sources"], [])

    async def test_unknown_evidence_id_is_error_not_no_evidence(self):
        model = FakeModel({"EvidenceDecision": [{"decision": "sufficient", "reason_code": "ok",
                                                  "supported_source_ids": ["S99"]}]})
        result = await RagService(FakeStore(), model).ainvoke({"question": "q"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["reason_code"], "invalid_model_decision")
        self.assertNotIn("generate", model.calls)

    async def test_invalid_route_schema_does_not_search(self):
        model = FakeModel({"RouteDecision": [{"intent": "other", "reason_code": "bad"}]})
        store = FakeStore()
        result = await RagService(store, model).ainvoke({"question": "q"})
        self.assertEqual(result["reason_code"], "invalid_model_decision")
        self.assertEqual(store.calls, [])

    async def test_scope_rejection_requires_scope(self):
        for scope, expected in [("", "error"), ("휴가 규정", "out_of_scope")]:
            model = FakeModel({"RouteDecision": [{"intent": "out_of_scope", "reason_code": "outside"}]})
            result = await RagService(FakeStore(), model, supported_scope=scope).ainvoke({"question": "q"})
            self.assertEqual(result["status"], expected)

    async def test_model_call_and_total_input_budgets(self):
        for settings in [RagSettings(max_model_calls=1), RagSettings(max_total_input_tokens=1)]:
            model = FakeModel()
            result = await RagService(FakeStore(), model, settings=settings).ainvoke({"question": "q"})
            self.assertEqual(result["reason_code"], "budget_exhausted")
            self.assertNotIn("generate", model.calls)

    async def test_search_failure_is_not_a_document_absence(self):
        class BrokenStore(FakeStore):
            async def asimilarity_search_with_score(self, *args, **kwargs):
                raise OSError("fixture secret details")

        result = await RagService(BrokenStore(), FakeModel()).ainvoke({"question": "q"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["reason_code"], "retrieval_error")
        self.assertNotIn("secret", str(result))

    async def test_concurrent_requests_do_not_share_state(self):
        service = RagService(FakeStore(), FakeModel())
        a, b = await asyncio.gather(service.ainvoke({"question": "A"}), service.ainvoke({"question": "B"}))
        self.assertEqual(a["sources"][0]["metadata"]["source"], "A")
        self.assertEqual(b["sources"][0]["metadata"]["source"], "B")
        self.assertEqual(a["search_count"], 1)
        self.assertEqual(b["model_calls"], 4)

    async def test_timeout_and_cancellation(self):
        entered = asyncio.Event()

        class SlowModel(FakeModel):
            async def ainvoke(self, messages):
                entered.set()
                await asyncio.Event().wait()

        service = RagService(FakeStore(), SlowModel(), settings=RagSettings(timeout_seconds=0.1))
        result = await service.ainvoke({"question": "q"})
        self.assertEqual(result["reason_code"], "workflow_timeout")
        entered.clear()
        service = RagService(FakeStore(), SlowModel())
        task = asyncio.create_task(service.ainvoke({"question": "q"}))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_model_reason_code_does_not_control_retry(self):
        bad = insufficient()
        bad["reason_code"] = "retry_limit"
        model = FakeModel({"EvidenceDecision": [bad], "RewrittenQuery": [{"search_query": "q2"}]})
        result = await RagService(FakeStore(), model).ainvoke({"question": "q"})
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["search_count"], 2)


if __name__ == "__main__":
    unittest.main()
