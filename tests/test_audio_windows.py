import queue
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from audio_windows import mono, WindowsDevice
from app import Session
from backends import NoAnalyzer, whisper_samples


class AudioTests(unittest.TestCase):
    def test_opposite_phase_does_not_cancel(self):
        a = np.sin(np.arange(4800) * .1).astype(np.float32)
        result = mono(np.column_stack([a, -a]))
        self.assertGreater(float(np.sqrt(np.mean(result**2))), .5)
        self.assertEqual(whisper_samples(np.column_stack([a, -a])).shape, (1600,))

    def test_native_rate_converted_for_pipeline(self):
        observed = {}
        class Stream:
            def stop_stream(self):
                observed['stopped'] = True
            def close(self):
                observed['closed'] = True
        class PA:
            def open(self, **kwargs):
                observed.update(kwargs)
                # Simulate callback audio at native 44.1 kHz stereo.
                audio = (np.ones((22050, 2)) * 1000).astype('<i2').tobytes()
                kwargs['stream_callback'](audio, 22050, None, 0)
                return Stream()
            def terminate(self):
                observed['terminated'] = True
        fake = SimpleNamespace(PyAudio=PA, paInt16=8, paContinue=0)
        device = WindowsDevice({'index': 4, 'name': 'test', 'maxInputChannels': 2,
            'defaultSampleRate': 44100, 'isLoopbackDevice': True})
        with patch.dict(sys.modules, {'pyaudiowpatch': fake}):
            with device.recorder(48000) as r:
                block = r.record(24000)
        self.assertEqual(block.shape, (24000, 2))
        self.assertEqual(observed['rate'], 44100)
        self.assertEqual(block.dtype, np.float32)
        self.assertTrue(observed['terminated'])

    def test_capture_transcribe_without_account(self):
        done = threading.Event()
        class Recorder:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def record(self, numframes):
                if not done.is_set():
                    done.set()
                    return np.ones((numframes, 2), np.float32) * .1
                session.stop.set()
                return np.zeros((numframes, 2), np.float32)
        device = SimpleNamespace(recorder=lambda **kwargs: Recorder())
        events = queue.Queue()
        session = Session(SimpleNamespace(transcribe=lambda *args: 'Prueba de audio'),
            NoAnalyzer(), device, '', '', events)
        session.start()
        for t in session.threads:
            t.join(5)
            self.assertFalse(t.is_alive())
        self.assertEqual(session.metrics['transcript_blocks'], 1)
        self.assertEqual(session.metrics['analysis_calls'], 0)
        self.assertEqual(session.transcript[0]['texto'], 'Prueba de audio')

    def test_ai_failure_does_not_stop_local_transcription(self):
        def fail(*args):
            raise ValueError('limit')
        session = Session(SimpleNamespace(transcribe=lambda *args: 'Texto'),
            SimpleNamespace(analyze=fail), None, '', '', queue.Queue())
        session.analysis.put(('Texto', [])); session.analysis.put(None)
        session.analyze()
        self.assertTrue(session.analysis_disabled)
        self.assertFalse(session.stop.is_set())

if __name__ == '__main__':
    unittest.main()
