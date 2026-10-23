"""Correction and confirmation tests; all provider calls are mocked."""
import json
import os
import types
import unittest
from unittest.mock import Mock, patch

import test_voice_query as helpers
auth = helpers.auth
from app.services import transcript_review as review
from app.services import voice_pipeline as p

class ReviewTests(unittest.TestCase):
    def provider(self, corrected, uncertain=False):
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.chat.completions.create.return_value = types.SimpleNamespace(
            choices=[types.SimpleNamespace(finish_reason="stop",
                message=types.SimpleNamespace(refusal=None, content=json.dumps({
                    "corrected_question":corrected, "uncertain":uncertain})))])
        return client

    def test_context_suggestion_preserves_original(self):
        client = self.provider("육아휴직 신청 서류는 무엇인가요?")
        with patch.dict(os.environ, {"OPENAI_API_KEY":"test-only", "VOICE_CORRECTION_ENABLED":"true"}), patch("openai.OpenAI", return_value=client):
            result = review.review_transcript("유가 휴직 신청 서류는 무엇인가요?")
        self.assertEqual(result.raw_transcript, "유가 휴직 신청 서류는 무엇인가요?")
        self.assertTrue(result.changed)
        self.assertTrue(result.confirmation_required)
        args = client.chat.completions.create.call_args.kwargs
        self.assertFalse(args["store"])
        self.assertEqual(args["response_format"]["type"], "json_schema")

    def test_uncertain_preserves_original(self):
        client = self.provider("내 짝지 이름은 이효준", uncertain=True)
        with patch.dict(os.environ, {"OPENAI_API_KEY":"test-only"}), patch("openai.OpenAI", return_value=client):
            result = review.review_transcript("내 짝지 이름은 이효주")
        self.assertEqual(result.corrected_question, "내 짝지 이름은 이효주")
        self.assertFalse(result.changed)

    def test_changed_number_rejected(self):
        client = self.provider("입사 18개월입니다")
        with patch.dict(os.environ, {"OPENAI_API_KEY":"test-only"}), patch("openai.OpenAI", return_value=client):
            result = review.review_transcript("입사 8개월입니다")
        self.assertEqual(result.corrected_question, result.raw_transcript)
        self.assertTrue(result.warning)

    def test_provider_error_falls_back(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY":"test-only"}), patch("openai.OpenAI", side_effect=RuntimeError("private provider detail")):
            result = review.review_transcript("질문입니다")
        self.assertEqual(result.corrected_question, "질문입니다")
        self.assertNotIn("private provider detail", result.warning)

    def test_disabled_avoids_provider(self):
        with patch.dict(os.environ, {"VOICE_CORRECTION_ENABLED":"false"}), patch("openai.OpenAI") as provider:
            result = review.review_transcript("원문")
        provider.assert_not_called()
        self.assertEqual(result.corrected_question, "원문")

    def test_private_patterns_masked_before_provider(self):
        client = self.provider("전화번호 [전화번호]입니다")
        with patch.dict(os.environ, {"OPENAI_API_KEY":"test-only"}), patch("openai.OpenAI", return_value=client):
            result = review.review_transcript("전화번호 010-1234-5678입니다")
        sent = client.chat.completions.create.call_args.kwargs["messages"][-1]["content"]
        self.assertNotIn("010-1234-5678", sent)
        self.assertIn("[전화번호]", result.raw_transcript)

    def test_missing_key_fallback(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY":""}), patch("openai.OpenAI") as provider:
            result = review.review_transcript("질문")
        provider.assert_not_called()
        self.assertIn("OPENAI_API_KEY", result.warning)

class ConfirmationTests(unittest.TestCase):
    setUp = helpers.VoiceTests.setUp
    tearDown = helpers.VoiceTests.tearDown
    def test_review_does_not_call_rag_or_tts(self):
        proposal = review.TranscriptReview(raw_transcript="유가 휴직",
            corrected_question="육아휴직", changed=True)
        with patch.object(p, "transcribe_private", return_value="유가 휴직"), patch(
                "app.routers.voice_query_router.review_transcript", return_value=proposal), patch.object(
                p, "ask_rag") as rag, patch.object(p, "synthesize") as tts:
            response = self.client.post("/voice-transcribe",
                headers=auth(), files={"audio":("test.webm",b"test")})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["confirmation_required"])
        rag.assert_not_called()
        tts.assert_not_called()

    def test_confirmed_text_used_for_rag(self):
        answer = p.RagAnswer(answer="테스트 답변", sources=[], needs_review=False, handoff=False)
        with patch.object(p, "ask_rag", return_value=answer) as rag, patch.object(
                p, "synthesize", return_value="/voice-audio/test.mp3"):
            response = self.client.post("/voice-query-text", headers=auth(),
                json={"question":"  육아휴직 신청 서류는 무엇인가요?  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(rag.call_args.args[0], "육아휴직 신청 서류는 무엇인가요?")
        self.assertEqual(response.json()["transcript"], "육아휴직 신청 서류는 무엇인가요?")

    def test_review_auth_required(self):
        response = self.client.post("/voice-transcribe",
            files={"audio":("test.webm",b"test")})
        self.assertEqual(response.status_code, 401)

    def test_confirmation_auth_required(self):
        self.assertEqual(self.client.post("/voice-query-text",
            json={"question":"질문"}).status_code, 401)

    def test_blank_confirmation(self):
        self.assertEqual(self.client.post("/voice-query-text", headers=auth(),
            json={"question":"  "}).status_code, 422)
