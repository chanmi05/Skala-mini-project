"""Deterministic local retrieval tests; no model, network, or paid calls."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_voice_query as helpers
from app.services import voice_pipeline as p
from app.services import demo_rag as demo

class DemoTests(unittest.TestCase):
    def test_questions_find_expected_rules(self):
        cases = [
            ("연차 신청은 며칠 전에 해야 하나요?", "DEMO-01", "3영업일"),
            ("연차를 쓰려면 어떻게 해요?", "DEMO-01", "사내 포털"),
            ("남은 연차를 내년으로 넘길 수 있나요?", "DEMO-02", "최대 2일"),
            ("본인이 결혼하면 휴가가 며칠인가요?", "DEMO-03", "3일"),
            ("재택근무는 일주일에 몇 번 가능한가요?", "DEMO-04", "주 1회"),
            ("육아 휴직 신청에 필요한 서류는 무엇인가요?", "DEMO-05", "휴직 일정표"),
        ]
        for question, article, content in cases:
            with self.subTest(question=question):
                result = p.RagAnswer.model_validate(demo.demo_answer(question))
                self.assertEqual(len(result.sources), 1)
                self.assertIn(article, result.sources[0].article)
                self.assertIn(content, result.answer)
                self.assertFalse(result.needs_review)
                self.assertFalse(result.handoff)
                self.assertIn("실제 법령이나 회사 규정이 아닙니다", result.answer)

    def test_unsupported_questions_do_not_invent_answer(self):
        for question in ["올해 연봉 인상률은 얼마인가요?", "다음 회식은 언제인가요?",
                         "육아휴직은 최대 몇 년인가요?", "제 연차가 몇 개 남았나요?",
                         "동생 결혼식 휴가는 며칠인가요?", "재택근무 신청을 취소하려면?",
                         "오늘 날씨는?", ""]:
            with self.subTest(question=question):
                result = demo.demo_answer(question)
                self.assertEqual(result["sources"], [])
                self.assertTrue(result["handoff"])
                self.assertTrue(result["needs_review"])

    def test_individual_judgment_requires_review(self):
        result = demo.demo_answer("제가 받은 징계가 정당한가요?")
        self.assertIn("검토", result["answer"])
        self.assertEqual(result["sources"], [])
        self.assertTrue(result["handoff"])

    def test_two_retrieved_rules_preserve_both_sources(self):
        result = demo.demo_answer("연차 신청 방법과 이월 기준을 알려주세요")
        self.assertEqual(len(result["sources"]), 2)
        self.assertIn("3영업일", result["answer"])
        self.assertIn("최대 2일", result["answer"])

    def test_rule_edits_change_answer(self):
        rules = json.loads(demo.RULES_PATH.read_text())
        rules[0]["content"] = "테스트에서 수정한 승인 절차입니다."
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps(rules), encoding="utf-8")
            with patch.object(demo, "RULES_PATH", path):
                result = demo.demo_answer("연차 신청 방법")
        self.assertIn("테스트에서 수정한 승인 절차", result["answer"])
        self.assertNotIn("3영업일", result["answer"])

    def test_demo_never_calls_team_rag(self):
        with patch.dict(os.environ, {"VOICE_RAG_MODE":"demo"}), patch.object(p.httpx, "Client") as network:
            result = p.ask_rag("육아휴직 신청 서류", "test-token")
        network.assert_not_called()
        self.assertIn("DEMO-05", result.sources[0].article)

    def test_bad_mode_rejected(self):
        from fastapi import HTTPException
        with patch.dict(os.environ, {"VOICE_RAG_MODE":"demoo"}):
            with self.assertRaises(HTTPException):
                p.rag_mode()

class DemoApiTests(unittest.TestCase):
    setUp = helpers.VoiceTests.setUp
    tearDown = helpers.VoiceTests.tearDown

    def test_confirmed_question_returns_demo_sources(self):
        with patch.dict(os.environ, {"VOICE_RAG_MODE":"demo"}), patch.object(
                p, "synthesize", return_value="/voice-audio/test.mp3"), patch.object(
                p.httpx, "Client") as network:
            response = self.client.post("/voice-query-text", headers=helpers.auth(),
                json={"question":"남은 연차를 이월할 수 있나요?"})
        self.assertEqual(response.status_code, 200)
        network.assert_not_called()
        result = response.json()
        self.assertEqual(result["mode"], "demo")
        self.assertIn("DEMO-02", result["sources"][0]["article"])
        self.assertTrue(result["audio_url"])

    def test_unknown_question_keeps_handoff_when_tts_fails(self):
        with patch.dict(os.environ, {"VOICE_RAG_MODE":"demo"}), patch.object(
                p, "synthesize", side_effect=RuntimeError("provider error")):
            response = self.client.post("/voice-query-text", headers=helpers.auth(),
                json={"question":"올해 연봉 인상률은 얼마인가요?"})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["handoff"])
        self.assertEqual(result["sources"], [])
        self.assertIsNone(result["audio_url"])
