import io
import json
import queue
import threading
import unittest
import wave
from types import SimpleNamespace
import numpy as np
from core import wav_bytes, parse_analysis
from app import Session


class PipelineTest(unittest.TestCase):
    def test_wav_format(self):
        samples = np.ones((480, 2), dtype=np.float32) * .5
        with wave.open(io.BytesIO(wav_bytes(samples)), 'rb') as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getframerate(), 48000)
            self.assertEqual(wav.getnframes(), 480)
            self.assertEqual(wav.getsampwidth(), 2)

    def test_invalid_output(self):
        with self.assertRaises(ValueError):
            parse_analysis('{"conceptos": "wrong"}')

    def test_drain_context_and_deduplication(self):
        calls = []
        def analysis(**kwargs):
            calls.append(json.loads(kwargs['input']))
            return SimpleNamespace(output_text=json.dumps({
                'resumen': 'Se trata recuperación.',
                'conceptos': [{'termino': 'RTO', 'explicacion': 'Tiempo objetivo.'}],
                'preguntas': [{'pregunta': '¿Cómo reducir el RTO?', 'breve': 'Con réplica.'}]}))
        transcriber = SimpleNamespace(transcribe=lambda *args: '¿Cómo reducir el RTO?')
        analyzer = SimpleNamespace(analyze=lambda instructions, payload: analysis(input=payload).output_text)
        events = queue.Queue()
        session = Session(transcriber, analyzer, None, 'IT', '', events, interval=0)
        session.audio.put(np.ones((480, 2)) * .1)
        session.audio.put(np.ones((480, 2)) * .1)
        session.audio.put(None)
        threads = [threading.Thread(target=session.transcribe), threading.Thread(target=session.analyze)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
            self.assertFalse(t.is_alive())
        emitted = []
        while not events.empty():
            emitted.append(events.get()[1])
        self.assertEqual(emitted.count('transcript'), 2)
        self.assertEqual(emitted.count('concept'), 1)
        self.assertEqual(emitted.count('question'), 1)
        self.assertEqual(emitted[-1], 'done')
        self.assertEqual(len(calls[0]['contexto_reciente']), 2)
        self.assertIn('\n', calls[0]['fragmento_nuevo'])


if __name__ == '__main__':
    unittest.main()
