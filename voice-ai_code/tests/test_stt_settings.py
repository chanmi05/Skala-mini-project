"""Verify decoder settings without downloading or loading a model."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

class SettingsTests(unittest.TestCase):
    def load(self):
        fake = types.ModuleType("faster_whisper")
        model = Mock()
        model.transcribe.return_value = (
            iter([types.SimpleNamespace(text="테스트")]), None)
        fake.WhisperModel = Mock(return_value=model)
        spec = importlib.util.spec_from_file_location(
            "isolated_stt_settings", Path(__file__).resolve().parents[1] /
            "app/services/stt_service.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"faster_whisper":fake}):
            spec.loader.exec_module(module)
        return module, model

    def test_default_hr_hint_and_korean(self):
        with patch.dict(os.environ):
            os.environ.pop("WHISPER_INITIAL_PROMPT", None)
            os.environ.pop("WHISPER_LANGUAGE", None)
            module, model = self.load()
            with tempfile.NamedTemporaryFile() as audio:
                module.transcribe_audio_file_local(audio.name)
            args = model.transcribe.call_args.kwargs
            self.assertEqual(args["language"], "ko")
            self.assertIn("육아휴직", args["initial_prompt"])
            self.assertNotIn("이효준", args["initial_prompt"])
            self.assertEqual(args["temperature"], 0)
            self.assertTrue(module.recognition_settings()["vocabulary_hint"])

    def test_hint_can_be_disabled(self):
        with patch.dict(os.environ, {"WHISPER_INITIAL_PROMPT":""}):
            module, model = self.load()
            with tempfile.NamedTemporaryFile() as audio:
                module.transcribe_audio_file_local(audio.name)
            self.assertIsNone(model.transcribe.call_args.kwargs["initial_prompt"])
            self.assertFalse(module.recognition_settings()["vocabulary_hint"])

    def test_custom_hint_and_auto_language(self):
        with patch.dict(os.environ, {
            "WHISPER_INITIAL_PROMPT":"테스트용어", "WHISPER_LANGUAGE":""}):
            module, model = self.load()
            with tempfile.NamedTemporaryFile() as audio:
                module.transcribe_audio_file_local(audio.name)
            self.assertEqual(model.transcribe.call_args.kwargs["initial_prompt"], "테스트용어")
            self.assertIsNone(model.transcribe.call_args.kwargs["language"])
