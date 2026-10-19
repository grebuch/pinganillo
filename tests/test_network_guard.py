import threading
import unittest
from network_guard import DeadlineCall


class GuardTests(unittest.TestCase):
    def test_transcription_continues_while_ai_waits(self):
        import queue
        import numpy as np
        from types import SimpleNamespace
        from app import Session
        entered, release = threading.Event(), threading.Event()
        def waiting_ai(*args):
            entered.set()
            release.wait(3)
            return '{"conceptos":[],"preguntas":[],"resumen":""}'
        session = Session(SimpleNamespace(transcribe=lambda *a: 'Texto'),
            SimpleNamespace(analyze=waiting_ai), None, '', '', queue.Queue(), interval=0)
        session.analysis.put(('Pregunta', []))
        session.analysis.put(None)
        ai_thread = threading.Thread(target=session.analyze)
        ai_thread.start()
        try:
            self.assertTrue(entered.wait(1))
            session.audio.put(np.ones((480, 2), np.float32))
            session.audio.put(None)
            transcribe_thread = threading.Thread(target=session.transcribe)
            transcribe_thread.start()
            transcribe_thread.join(1)
            self.assertFalse(transcribe_thread.is_alive())
            self.assertEqual(session.metrics['transcript_blocks'], 1)
            self.assertTrue(ai_thread.is_alive())
        finally:
            release.set()
            ai_thread.join(3)

    def test_deadline_and_no_duplicate_requests(self):
        release = threading.Event()
        guard = DeadlineCall(timeout=.03)
        try:
            with self.assertRaises(TimeoutError):
                guard.call(lambda: release.wait(2))
            with self.assertRaises(RuntimeError):
                guard.call(lambda: 'must not start')
        finally:
            release.set()
            guard.worker.join(2)
        self.assertEqual(guard.call(lambda: 'new result'), 'new result')

    def test_exception_is_preserved(self):
        guard = DeadlineCall(timeout=1)
        def fail():
            raise ValueError('test')
        with self.assertRaisesRegex(ValueError, 'test'):
            guard.call(fail)
