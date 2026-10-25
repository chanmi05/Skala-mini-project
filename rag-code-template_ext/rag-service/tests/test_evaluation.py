"""Offline checks for evaluation metrics and read-only search instrumentation."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.documents import Document
from evaluation.run_evaluation import RecordingStore, evidence_metrics, validate_cases
from evaluation.compare_runs import MATCH_FIELDS, check_compatibility, stats


class MetricsTests(unittest.TestCase):
    def test_comparison_rejects_changed_model_or_duplicate_k(self):
        base = {field: "same" for field in MATCH_FIELDS}
        first = {**base, "top_k": 5, "index_unchanged": True}
        second = {**base, "top_k": 10, "index_unchanged": True}
        check_compatibility([first, second])
        with self.assertRaises(ValueError):
            check_compatibility([first, {**second, "model": "different"}])
        with self.assertRaises(ValueError):
            check_compatibility([first, first])

    def test_comparison_statistics_use_reported_values_only(self):
        result = stats([{"ms": 1}, {"ms": None}, {"ms": 3}], "ms")
        self.assertEqual(result, {"mean": 2, "median": 2, "p95_nearest_rank": 3})

    def test_alternatives_and_multiple_required_groups(self):
        case = {"answerable": True, "expected_evidence_groups": [["a", "b"], ["c"]]}
        hits = [{"chunk_id": "x"}, {"chunk_id": "b"}, {"chunk_id": "c"}]
        metrics = evidence_metrics(case, hits, [{"chunk_id": "b"}])
        self.assertEqual(metrics["hit_at_k"], 1)
        self.assertEqual(metrics["evidence_group_recall"], 1)
        self.assertEqual(metrics["context_group_recall"], 0.5)
        self.assertEqual(metrics["reciprocal_rank"], 0.5)

    def test_no_hit_is_zero_not_missing(self):
        metrics = evidence_metrics({"answerable": True, "expected_evidence_groups": [["a"]]}, [], [])
        self.assertEqual(set(metrics.values()), {0})

    def test_unanswerable_not_used_as_retrieval_ground_truth(self):
        metrics = evidence_metrics({"answerable": False}, [{"chunk_id": "a"}], [])
        self.assertTrue(all(v is None for v in metrics.values()))

    def test_invalid_gold_and_duplicate_case_ids_rejected(self):
        case = {"id": "q", "question": "question", "answerable": True,
                "expected_evidence_groups": [["a"]]}
        with self.assertRaises(ValueError):
            validate_cases([case], {"b"})
        with self.assertRaises(ValueError):
            validate_cases([case, case], {"a"})


class InstrumentationTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_search_and_original_document_unchanged(self):
        original = Document(page_content="evidence", metadata={"source": "fixture"})

        class FakeStore:
            index_to_docstore_id = {0: "stored-id"}
            calls = 0

            def __init__(self):
                self.docstore = self

            def search(self, key):
                return original

            async def asimilarity_search_with_score(self, question, k):
                self.calls += 1
                return [(original, 0.2)]

        store = FakeStore()
        recorder = RecordingStore(store)
        pairs = await recorder.asimilarity_search_with_score("q", 5)
        self.assertEqual(store.calls, 1)
        self.assertNotIn("chunk_id", original.metadata)
        self.assertIsNone(original.id)
        self.assertEqual(pairs[0][0].metadata["chunk_id"], "stored-id")
        self.assertEqual(recorder.hits[0]["chunk_id"], "stored-id")


if __name__ == "__main__":
    unittest.main()
