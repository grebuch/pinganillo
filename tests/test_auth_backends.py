import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from auth_chatgpt import validate_callback
from backends import PlanAnalyzer, LocalTranscriber


class OAuthTest(unittest.TestCase):
    def test_local_transcriber_no_cloud_calls(self):
        import numpy as np
        seen = {}
        class Model:
            def __init__(self, name, **kwargs):
                seen['name'] = name
                seen.update(kwargs)
            def transcribe(self, audio, **kwargs):
                seen['decode'] = kwargs
                if not isinstance(audio, np.ndarray) or audio.dtype != np.float32 or audio.shape != (160,):
                    raise ValueError('Whisper must receive 16 kHz mono float32 samples')
                return iter([SimpleNamespace(text=' Texto local ')]), None
        with patch.dict(sys.modules, {'faster_whisper': SimpleNamespace(WhisperModel=Model)}):
            backend = LocalTranscriber()
            self.assertEqual(backend.transcribe(np.ones((480, 2)), ''), 'Texto local')
            self.assertEqual(seen['device'], 'cpu')
            self.assertEqual(seen['name'], 'small')
            self.assertEqual(seen['decode']['language'], 'es')
            self.assertEqual(seen['decode']['beam_size'], 5)
            self.assertTrue(seen['decode']['vad_filter'])

    def test_state_and_client_binding(self):
        self.assertEqual(validate_callback({'state': ['ok'], 'code': ['code'], 'client_id': ['issued']}, 'ok'), ('issued', 'code'))
        for params, client in [({'state': ['bad']}, None),
                ({'state': ['ok'], 'code': ['code']}, None),
                ({'state': ['ok'], 'code': ['code'], 'client_id': ['other']}, 'issued'),
                ({'state': ['ok'], 'error': ['access_denied']}, None)]:
            with self.assertRaises(ValueError):
                validate_callback(params, 'ok', client)

    def test_plan_request_and_terminal_event(self):
        captured = {}
        class Stream:
            def __init__(self, completed):
                self.completed = completed
            def __enter__(self):
                return iter([SimpleNamespace(type='response.output_text.delta', delta='{}'),
                    SimpleNamespace(type='response.completed' if self.completed else 'response.incomplete')])
            def __exit__(self, *args):
                pass
        def create(**kwargs):
            captured.update(kwargs)
            return Stream(True)
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        module = SimpleNamespace(OpenAI=lambda **k: client)
        auth = SimpleNamespace(access_token=lambda: 'mock-token')
        with patch.dict(sys.modules, {'openai': module, 'httpx': SimpleNamespace(Timeout=lambda *a, **k: None)}):
            backend = PlanAnalyzer(auth, 'available-model')
            self.assertEqual(backend.analyze('instructions', '{}'), '{}')
            self.assertTrue(captured['stream'])
            self.assertFalse(captured['store'])
            self.assertIsInstance(captured['input'], list)
            self.assertNotIn('max_output_tokens', captured)
            client.responses.create = lambda **k: Stream(False)
            with self.assertRaises(ValueError):
                backend.analyze('instructions', '{}')
