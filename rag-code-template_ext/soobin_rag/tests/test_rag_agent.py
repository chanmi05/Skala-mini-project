"""Offline behavior checks; never load production indexes or call providers."""

import asyncio
from pathlib import Path
import sys
import threading
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.documents import Document
from rag_agent import (
    ContextError, GenerationError, RetrievalError, answer_question, build_context,
)


def count_chars(messages):
    # Deterministic stand-in for the model's token counter.
    return sum(len(m.content) for m in messages)


def doc(text="근거", source="manual", chunk_id="c1"):
    return Document(page_content=text, metadata={"source": source, "chunk_id": chunk_id})


class Store:
    def __init__(self, documents=None):
        self.documents = [(doc(), 0.25)] if documents is None else documents
        self.calls = []

    async def asimilarity_search_with_score(self, question, k):
        self.calls.append((question, k))
        return self.documents[:k]


class Model:
    def __init__(self, content="문서에 따른 답변입니다. [S1]"):
        self.content = content
        self.calls = []

    def get_num_tokens_from_messages(self, messages):
        return count_chars(messages)

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.content)


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_question_top_k_and_provenance(self):
        store, model = Store(), Model()
        result = await answer_question(" 질문 ", store, model, top_k=1)
        self.assertEqual(store.calls, [("질문", 1)])
        self.assertEqual(result["retrieved_count"], 1)
        self.assertEqual(result["sources"][0]["metadata"]["source"], "manual")
        self.assertEqual(result["sources"][0]["text"], "근거")
        self.assertIn("[S1]", model.calls[0][1].content)

    async def test_invalid_inputs_never_search(self):
        store, model = Store(), Model()
        for question, k in [(" ", 5), ("x" * 4001, 5), ("q", 0), ("q", 51), ("q", True)]:
            with self.subTest(question=question[:10], top_k=k), self.assertRaises(ValueError):
                await answer_question(question, store, model, k)
        self.assertEqual(store.calls, [])

    async def test_empty_and_blank_results_do_not_generate(self):
        for documents in [[], [(doc(" "), 0.2)]]:
            model = Model()
            result = await answer_question("q", Store(documents), model)
            self.assertEqual(result["sources"], [])
            self.assertEqual(model.calls, [])

    async def test_whole_chunks_dedup_and_source_identity(self):
        entries = [(doc("a" * 1000), 0.1), (doc("short"), 0.2),
                   (doc("short"), 0.3), (doc("short", source="other"), 0.4)]
        baseline = count_chars(build_context("q", [], count_tokens=count_chars)[0])
        messages, sources = build_context("q", entries, count_tokens=count_chars,
                                          max_input_tokens=baseline + 250)
        self.assertEqual([s["text"] for s in sources], ["short", "short"])
        self.assertEqual([s["id"] for s in sources], ["S1", "S2"])
        self.assertLessEqual(count_chars(messages), baseline + 250)
        self.assertNotIn("a" * 1000, messages[1].content)

    async def test_no_chunk_fits_does_not_generate(self):
        model = Model()
        baseline = count_chars(build_context("q", [], count_tokens=count_chars)[0])
        result = await answer_question("q", Store(), model, max_input_tokens=baseline)
        self.assertEqual(result["retrieved_count"], 1)
        self.assertEqual(result["sources"], [])
        self.assertEqual(model.calls, [])

    async def test_errors_are_distinguished(self):
        class BrokenStore(Store):
            async def asimilarity_search_with_score(self, *args, **kwargs):
                raise OSError("fixture")

        with self.assertRaises(RetrievalError):
            await answer_question("q", BrokenStore(), Model())
        with self.assertRaises(ContextError):
            await answer_question("q", Store(), Model(), max_input_tokens=1)
        with self.assertRaises(GenerationError):
            await answer_question("q", Store(), Model(""))
        with self.assertRaises(GenerationError):
            await answer_question("q", Store(), Model("잘못된 출처 [S99]"))

    async def test_structured_text_content(self):
        result = await answer_question("q", Store(), Model([
            {"type": "text", "text": "답변 [S1]"}, {"type": "reasoning", "text": "internal"}
        ]))
        self.assertEqual(result["answer"], "답변 [S1]")

    async def test_sync_fallback_does_not_block_event_loop(self):
        entered, release = threading.Event(), threading.Event()

        class SyncStore:
            def similarity_search_with_score(self, question, k):
                entered.set()
                if not release.wait(2):
                    raise TimeoutError("event loop did not release worker")
                return [(doc(), 0.1)]

        class SyncModel:
            def get_num_tokens_from_messages(self, messages):
                return count_chars(messages)

            def invoke(self, messages):
                return SimpleNamespace(content="답변 [S1]")

        task = asyncio.create_task(answer_question("q", SyncStore(), SyncModel()))
        try:
            while not entered.is_set():
                await asyncio.sleep(0.001)
            release.set()  # Must run while the synchronous search is waiting.
            self.assertTrue((await task)["answer"])
        finally:
            release.set()

    async def test_timeout_and_cancellation_propagate(self):
        started = asyncio.Event()

        class SlowModel(Model):
            async def ainvoke(self, messages):
                started.set()
                await asyncio.Event().wait()

        with self.assertRaises(TimeoutError):
            await answer_question("q", Store(), SlowModel(), timeout_seconds=0.1)
        started.clear()
        task = asyncio.create_task(answer_question("q", Store(), SlowModel()))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    unittest.main()
