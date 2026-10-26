"""실제 그래프·SessionStore를 사용하고 모델 판정만 모의하는 세션 통합 테스트."""

import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError
from rag_router import RagService
from rag_state import MemoryDecision, RagSettings
from rag_workflow import compile_document_graph, RequestRuntime
from session_memory import InMemorySessionStore
from test_rag_workflow import FakeModel, FakeStore, insufficient


def ready(question="휴가 신청 방법"):
    return {"action": "ready", "standalone_question": question, "reason_code": "resolved"}


def lookup():
    return {"action": "load_summary", "missing_reference": "앞서 고른 제도", "reason_code": "old_reference"}


class MemoryModel(FakeModel):
    def with_structured_output(self, schema, include_raw, **kwargs):
        if schema.__name__ not in {"InputDecision", "MemoryDecisionOutput", "SummaryDecision"}:
            return super().with_structured_output(schema, include_raw)

        async def call(messages):
            name = "MemoryDecision" if schema.__name__ == "MemoryDecisionOutput" else schema.__name__
            self.calls.append(name)
            self.inputs.append(messages)
            queued = self.decisions.get(name)
            if queued:
                result = queued.pop(0)
            else:
                result = {"InputDecision": {"intent": "document_question", "reason_code": "document"},
                          "MemoryDecision": ready(),
                          "SummaryDecision": {"summary": "사용자 선택은 육아휴직 (turn_id=1)."}}[name]
            if isinstance(result, Exception):
                raise result
            if name == "MemoryDecision":
                result = {"decision": {key: value for key, value in result.items() if key != "reason_code"}}
            elif name == "InputDecision":
                result = {key: value for key, value in result.items() if key != "reason_code"}
            return {"parsed": result, "parsing_error": None, "raw": SimpleNamespace(usage_metadata={})}
        return RunnableLambda(call)


class CountingStore(InMemorySessionStore):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.summary_reads = 0

    async def get_summary(self, *args, **kwargs):
        self.summary_reads += 1
        return await super().get_summary(*args, **kwargs)


async def seed(store, count):
    session = await store.create_session()
    for n in range(count):
        await store.append_turn(session.session_id, expected_version=n, request_id=f"seed-{n}",
                                question=f"질문 {n}", output=f"이전 응답 {n}")
    return session.session_id


class MemoryWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, service, sid, question="그럼 신청은?", request_id="request"):
        return await service.ainvoke({"question": question, "session_id": sid, "request_id": request_id})

    async def test_nested_state_preserves_request_and_memory_across_retries(self):
        settings = RagSettings()
        model = FakeModel({"EvidenceDecision": [insufficient()],
                           "RewrittenQuery": [{"search_query": "새 검색"}]})
        graph = compile_document_graph(FakeStore(), model, settings)
        initial = {"request": {"request_id": "r", "original_question": "그럼?"},
                   "memory": {"summary_checked": False, "session_facts": {}},
                   "interpretation": {"memory_action": "ready", "standalone_question": "휴가"}}
        state = await graph.ainvoke(initial, config={"configurable": {"runtime": RequestRuntime(model, settings)}})
        self.assertEqual(set(state), {"request", "memory", "interpretation", "retrieval", "result"})
        self.assertEqual(state["request"], initial["request"])
        self.assertEqual(state["memory"], initial["memory"])
        self.assertEqual(state["interpretation"]["standalone_question"], "휴가")
        self.assertEqual(state["retrieval"]["previous_queries"], ["휴가", "새 검색"])
        self.assertEqual(state["result"]["status"], "answered")
        self.assertNotIn("retrieval", initial)

    async def test_memory_schema_rejects_inconsistent_fields(self):
        for value in [dict(action="ready", reason_code="x"),
                      {**ready(), "missing_reference": "x"},
                      dict(action="load_summary", reason_code="x"),
                      dict(action="clarify", reason_code="x")]:
            with self.assertRaises(ValidationError):
                MemoryDecision.model_validate(value)

    async def test_recent_history_resolves_without_summary_and_saves_exact_output(self):
        store, model, vectors = CountingStore(), MemoryModel(), FakeStore()
        sid = await seed(store, 3)
        result = await self.invoke(RagService(vectors, model, session_store=store), sid)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(vectors.calls[0][0], "휴가 신청 방법")
        self.assertEqual(store.summary_reads, 0)
        self.assertFalse(result["summary_checked"])
        saved = (await store.get_session(sid)).turns[-1]
        self.assertEqual(saved.output, result["output"])
        self.assertEqual(result["answer"], result["output"])
        self.assertEqual(saved.source_ids, tuple(result["source_ids"]))
        self.assertIn("질문 2", model.inputs[1][-1].content)
        self.assertNotIn("질문 2", model.inputs[0][-1].content)

    async def test_old_reference_loads_current_summary_once_and_keeps_memory_out_of_sources(self):
        store = CountingStore()
        sid = await seed(store, 8)
        await store.update_summary(sid, expected_version=8, text="오래된 선택: 육아휴직", summarized_until_turn_id=3)
        model = MemoryModel({"MemoryDecision": [lookup(), ready("육아휴직 신청 방법")]})
        vectors = FakeStore()
        result = await self.invoke(RagService(vectors, model, session_store=store), sid)
        self.assertEqual(result["status"], "answered")
        self.assertTrue(result["summary_checked"])
        self.assertEqual(store.summary_reads, 1)
        self.assertEqual(vectors.calls[0][0], "육아휴직 신청 방법")
        recent = next(messages for name, messages in zip(model.calls, model.inputs) if name == "MemoryDecision")
        self.assertNotIn("질문 0", recent[-1].content)
        self.assertIn("질문 3", recent[-1].content)
        self.assertNotIn("오래된 선택", recent[-1].content)
        self.assertNotIn("오래된 선택", str(result["sources"]))
        self.assertNotIn("recent_history", result)
        self.assertEqual(result["summary_update_status"], "updated")
        self.assertEqual((await store.get_session(sid)).summary.summarized_until_turn_id, 4)

    async def test_empty_summary_asks_and_stores_clarification_without_search(self):
        store = CountingStore()
        sid = await seed(store, 1)
        model, vectors = MemoryModel({"MemoryDecision": [lookup()]}), FakeStore()
        result = await self.invoke(RagService(vectors, model, session_store=store), sid)
        self.assertEqual(result["status"], "clarification_needed")
        self.assertEqual(result["reason_code"], "summary_empty")
        self.assertEqual(store.summary_reads, 1)
        self.assertEqual(model.calls.count("MemoryDecision"), 1)
        self.assertEqual(vectors.calls, [])
        self.assertEqual((await store.get_session(sid)).turns[-1].output, result["output"])

    async def test_stale_summary_is_not_used_to_guess_past_corrections(self):
        store = CountingStore()
        sid = await seed(store, 8)
        model = MemoryModel({"MemoryDecision": [lookup(), ready("추측한 대상")]})
        result = await self.invoke(RagService(FakeStore(), model, session_store=store), sid)
        self.assertEqual(result["reason_code"], "summary_incomplete")
        self.assertEqual(result["status"], "clarification_needed")
        self.assertEqual(result["search_count"], 0)
        self.assertEqual(model.calls.count("MemoryDecision"), 1)
        self.assertEqual(result["summary_update_status"], "updated")

    async def test_repeated_summary_action_is_error_and_does_not_append(self):
        store = CountingStore()
        sid = await seed(store, 6)
        await store.update_summary(sid, expected_version=6, text="이전 대상", summarized_until_turn_id=1)
        model = MemoryModel({"MemoryDecision": [lookup(), lookup()]})
        result = await self.invoke(RagService(FakeStore(), model, session_store=store), sid)
        self.assertEqual(result["reason_code"], "invalid_model_decision")
        self.assertEqual(store.summary_reads, 1)
        self.assertEqual(len((await store.get_session(sid)).turns), 6)

    async def test_document_missing_facts_retries_without_summary(self):
        store = CountingStore()
        sid = await seed(store, 0)
        model = MemoryModel({"EvidenceDecision": [insufficient()], "RewrittenQuery": [{"search_query": "다른 검색"}]})
        result = await self.invoke(RagService(FakeStore(), model, session_store=store), sid)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["search_count"], 2)
        self.assertEqual(store.summary_reads, 0)

    async def test_summary_failures_preserve_completed_turn_raw_and_cursor(self):
        for decision in [OSError("fixture private detail"), {"summary": "x" * 4001}]:
            store = CountingStore()
            sid = await seed(store, 5)
            model = MemoryModel({"SummaryDecision": [decision]})
            result = await self.invoke(RagService(FakeStore(), model, session_store=store), sid)
            self.assertEqual(result["status"], "answered")
            self.assertEqual(result["summary_update_status"], "failed")
            self.assertFalse(result["summary_is_current"])
            snapshot = await store.get_session(sid)
            self.assertEqual(len(snapshot.turns), 6)
            self.assertEqual(snapshot.summary.summarized_until_turn_id, 0)
            self.assertNotIn("private detail", str(result))

    async def test_summary_budget_and_correction_instruction(self):
        store = CountingStore()
        sid = await seed(store, 5)
        model = MemoryModel()
        result = await self.invoke(RagService(FakeStore(), model, session_store=store,
                                             settings=RagSettings(max_model_calls=5)), sid)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["summary_update_status"], "failed")
        self.assertNotIn("SummaryDecision", model.calls)
        result = await self.invoke(RagService(FakeStore(), model, session_store=store), sid, request_id="new")
        self.assertEqual(result["summary_update_status"], "updated")
        summary_input = model.inputs[-1]
        self.assertIn("최근 정정", summary_input[0].content)
        self.assertIn("turn_id", summary_input[-1].content)
        self.assertEqual((await store.get_session(sid)).summary.summarized_until_turn_id, 2)

    async def test_no_evidence_is_saved_but_errors_are_not(self):
        store = CountingStore()
        sid = await seed(store, 0)
        model = MemoryModel({"EvidenceDecision": [insufficient()]})
        result = await self.invoke(RagService(FakeStore(), model, session_store=store,
                                             settings=RagSettings(max_retries=0)), sid)
        self.assertEqual(result["status"], "no_evidence")
        model = MemoryModel({"MemoryDecision": [OSError("secret")]})
        result = await self.invoke(RagService(FakeStore(), model, session_store=store), sid, request_id="error")
        self.assertEqual(result["status"], "error")
        self.assertEqual(len((await store.get_session(sid)).turns), 1)
        self.assertNotIn("secret", str(result))

    async def test_same_request_concurrent_replay_makes_one_model_execution(self):
        store, model = CountingStore(), MemoryModel()
        sid = await seed(store, 0)
        service = RagService(FakeStore(), model, session_store=store)
        first, replay = await asyncio.gather(self.invoke(service, sid), self.invoke(service, sid))
        self.assertEqual(first["output"], replay["output"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["model_calls"], 0)
        self.assertEqual(first["source_ids"], replay["source_ids"])
        self.assertEqual(len((await store.get_session(sid)).turns), 1)
        self.assertEqual(model.calls.count("generate"), 1)
        self.assertEqual(service.sessions._locks, {})
        conflict = await self.invoke(service, sid, question="다른 질문")
        self.assertEqual(conflict["reason_code"], "session_conflict")
        self.assertEqual(conflict["model_calls"], 0)

    async def test_distinct_requests_same_session_see_previous_committed_turn(self):
        store, model = CountingStore(), MemoryModel()
        sid = await seed(store, 0)
        service = RagService(FakeStore(), model, session_store=store)
        await asyncio.gather(self.invoke(service, sid, "첫 질문", "a"), self.invoke(service, sid, "두 번째", "b"))
        turns = (await store.get_session(sid)).turns
        self.assertEqual([t.request_id for t in turns], ["a", "b"])
        memory_inputs = [messages for name, messages in zip(model.calls, model.inputs) if name == "MemoryDecision"]
        self.assertEqual(len(memory_inputs), 2)
        self.assertIn("첫 질문", memory_inputs[1][-1].content)
        self.assertEqual(service.sessions._locks, {})

    async def test_sessions_remain_isolated(self):
        store = CountingStore()
        a, b = await seed(store, 0), await seed(store, 0)
        model = MemoryModel({"MemoryDecision": [ready("A"), ready("B")]})
        service = RagService(FakeStore(), model, session_store=store)
        first, second = await asyncio.gather(self.invoke(service, a), self.invoke(service, b))
        self.assertEqual({first["sources"][0]["metadata"]["source"], second["sources"][0]["metadata"]["source"]}, {"A", "B"})
        self.assertEqual(len((await store.get_session(a)).turns), 1)
        self.assertEqual(len((await store.get_session(b)).turns), 1)

    async def test_missing_session_and_invalid_input_do_not_call_model(self):
        store, model = CountingStore(), MemoryModel()
        service = RagService(FakeStore(), model, session_store=store)
        result = await self.invoke(service, "unavailable")
        self.assertEqual(result["reason_code"], "session_unavailable")
        for data in [{"question": "q"}, {"question": "q", "session_id": "s"},
                     {"question": "q", "session_id": "s", "request_id": "r", "history": [{"role": "user", "content": "x"}]}]:
            with self.assertRaises(ValueError):
                await service.ainvoke(data)
        self.assertEqual(model.calls, [])

    async def test_summary_read_failure_and_append_failure_are_distinct(self):
        class BrokenSummary(CountingStore):
            async def get_summary(self, *args, **kwargs):
                raise OSError("private storage detail")
        store = BrokenSummary()
        sid = await seed(store, 0)
        result = await self.invoke(RagService(FakeStore(), MemoryModel({"MemoryDecision": [lookup()]}), session_store=store), sid)
        self.assertEqual(result["reason_code"], "memory_read_error")
        self.assertEqual(len((await store.get_session(sid)).turns), 0)
        class BrokenAppend(CountingStore):
            async def append_turn(self, *args, **kwargs):
                raise OSError("private storage detail")
        store = BrokenAppend()
        sid = await seed(store, 0)
        result = await self.invoke(RagService(FakeStore(), MemoryModel(), session_store=store), sid)
        self.assertEqual(result["reason_code"], "session_storage_error")
        self.assertEqual(result["status"], "error")
        self.assertNotIn("private storage detail", str(result))

    async def test_external_write_causes_conflict_instead_of_overwriting(self):
        store = CountingStore()
        sid = await seed(store, 0)
        class ConcurrentModel(MemoryModel):
            async def ainvoke(self, messages):
                await store.append_turn(sid, expected_version=0, request_id="external", question="other", output="other")
                return await super().ainvoke(messages)
        result = await self.invoke(RagService(FakeStore(), ConcurrentModel(), session_store=store), sid)
        self.assertEqual(result["reason_code"], "session_conflict")
        self.assertEqual([t.request_id for t in (await store.get_session(sid)).turns], ["external"])

    async def test_cancelled_generation_releases_lock_without_completed_turn(self):
        entered = asyncio.Event()
        class SlowModel(MemoryModel):
            async def ainvoke(self, messages):
                entered.set()
                await asyncio.Event().wait()
        store = CountingStore()
        sid = await seed(store, 0)
        service = RagService(FakeStore(), SlowModel(), session_store=store)
        task = asyncio.create_task(self.invoke(service, sid))
        await entered.wait()
        waiting = asyncio.create_task(self.invoke(service, sid, request_id="waiting"))
        await asyncio.sleep(0)
        waiting.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiting
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual((await store.get_session(sid)).turns, ())
        self.assertEqual(service.sessions._locks, {})
        retry = await self.invoke(RagService(FakeStore(), MemoryModel(), session_store=store), sid)
        self.assertEqual(retry["status"], "answered")

    async def test_failed_incremental_summary_preserves_previous_summary_and_retries_gap(self):
        store = CountingStore()
        sid = await seed(store, 8)
        await store.update_summary(sid, expected_version=8, text="기존 사용자 선택 (turn_id=1)", summarized_until_turn_id=3)
        service = RagService(FakeStore(), MemoryModel({"SummaryDecision": [OSError("failed")]}), session_store=store)
        result = await self.invoke(service, sid)
        snapshot = await store.get_session(sid)
        self.assertEqual(result["summary_update_status"], "failed")
        self.assertEqual(snapshot.summary.text, "기존 사용자 선택 (turn_id=1)")
        self.assertEqual(snapshot.summary.summarized_until_turn_id, 3)
        self.assertEqual(len(snapshot.turns), 9)
        model = MemoryModel()
        result = await self.invoke(RagService(FakeStore(), model, session_store=store), sid, request_id="next")
        summary_input = model.inputs[-1][-1].content
        self.assertIn("기존 사용자 선택", summary_input)
        self.assertIn("질문 3", summary_input)
        self.assertIn("질문 4", summary_input)
        self.assertNotIn("질문 5", summary_input)
        self.assertEqual((await store.get_session(sid)).summary.summarized_until_turn_id, 5)

    async def test_session_greeting_and_scope_result_are_saved(self):
        for question, decisions, status in [("안녕하세요!", {}, "greeting"),
                ("범위 밖", {"InputDecision": [{"intent": "out_of_scope", "reason_code": "outside"}]}, "out_of_scope")]:
            store, model = CountingStore(), MemoryModel(decisions)
            sid = await seed(store, 0)
            result = await self.invoke(RagService(FakeStore(), model, session_store=store,
                                                 supported_scope="휴가"), sid, question)
            self.assertEqual(result["status"], status)
            self.assertEqual((await store.get_session(sid)).turns[0].output, result["output"])
            self.assertNotIn("MemoryDecision", model.calls)

    async def test_queue_wait_counts_towards_timeout_and_releases_waiter(self):
        store, model = CountingStore(), MemoryModel()
        sid = await seed(store, 0)
        service = RagService(FakeStore(), model, session_store=store,
                             settings=RagSettings(timeout_seconds=0.05))
        async with service.sessions.hold(sid):
            result = await self.invoke(service, sid)
            self.assertEqual(result["reason_code"], "workflow_timeout")
            self.assertEqual(result["model_calls"], 0)
        self.assertEqual(service.sessions._locks, {})
        self.assertEqual((await store.get_session(sid)).turns, ())

    async def test_expired_session_is_not_recreated(self):
        from datetime import datetime, timedelta, timezone
        now = [datetime(2026, 10, 25, tzinfo=timezone.utc)]
        store = CountingStore(ttl_seconds=1, clock=lambda: now[0])
        sid = await seed(store, 0)
        now[0] += timedelta(seconds=2)
        result = await self.invoke(RagService(FakeStore(), MemoryModel(), session_store=store), sid)
        self.assertEqual(result["reason_code"], "session_unavailable")
        self.assertEqual(result["model_calls"], 0)

    async def test_summary_timeout_preserves_already_committed_output(self):
        class SlowSummaryModel(MemoryModel):
            def with_structured_output(self, schema, include_raw, **kwargs):
                if schema.__name__ == "SummaryDecision":
                    async def wait(messages):
                        await asyncio.Event().wait()
                    return RunnableLambda(wait)
                return super().with_structured_output(schema, include_raw, **kwargs)
        store = CountingStore()
        sid = await seed(store, 5)
        service = RagService(FakeStore(), SlowSummaryModel(), session_store=store,
                             settings=RagSettings(timeout_seconds=1.0))
        result = await self.invoke(service, sid)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["summary_update_status"], "failed")
        self.assertEqual((await store.get_session(sid)).turns[-1].output, result["output"])
        self.assertEqual(service.sessions._locks, {})


if __name__ == "__main__":
    unittest.main()
