from core import wav_bytes


def whisper_samples(samples):
    import numpy as np
    from scipy.signal import resample_poly
    from audio_windows import mono
    audio = mono(samples)
    if audio.ndim != 1:
        raise ValueError('Formato de audio no válido')
    # Capture uses 48 kHz. Whisper expects a mono float32 array at 16 kHz.
    # Passing the array bypasses PyAV's file-opening compatibility issue.
    return np.ascontiguousarray(resample_poly(audio, 1, 3), dtype=np.float32)


class LocalTranscriber:
    def __init__(self, model_name='small', language='es'):
        self.model = None
        self.model_name = model_name
        self.language = language

    def prepare(self):
        from faster_whisper import WhisperModel
        if self.model is None:
            import os
            self.model = WhisperModel(self.model_name, device='cpu', compute_type='int8',
                cpu_threads=max(1, min(4, (os.cpu_count() or 2) - 1)), num_workers=1)

    def transcribe(self, samples, prompt):
        self.prepare()
        segments, _ = self.model.transcribe(whisper_samples(samples),
            language=self.language, initial_prompt=prompt or None,
            vad_filter=True, vad_parameters={'min_silence_duration_ms': 600},
            beam_size=5, temperature=0, condition_on_previous_text=False)
        return ' '.join(s.text.strip() for s in segments).strip()


class NoAnalyzer:
    def analyze(self, instructions, payload):
        return '{"resumen":"","conceptos":[],"preguntas":[]}'


class PlanAnalyzer:
    def __init__(self, auth, model):
        self.auth, self.model = auth, model
        from network_guard import DeadlineCall
        self.guard = DeadlineCall()
        self.diagnostic = {'state': 'sin_probar'}

    def analyze(self, instructions, payload):
        self.diagnostic = {'state': 'esperando'}
        try:
            result = self.guard.call(lambda: self._request(instructions, payload))
            self.diagnostic = {'state': 'completada'}
            return result
        except Exception as exc:
            self.diagnostic = {'state': 'error', 'type': type(exc).__name__,
                'http_status': getattr(exc, 'status_code', None), 'code': getattr(exc, 'code', None)}
            raise

    def _request(self, instructions, payload):
        from openai import OpenAI
        import httpx
        client = OpenAI(api_key=self.auth.access_token(), base_url='https://api.openai.com/v1',
                        timeout=httpx.Timeout(20, connect=8, read=20, write=10, pool=8), max_retries=0)
        parts, completed = [], False
        with client.responses.create(model=self.model, instructions=instructions,
            input=[{'role': 'user', 'content': payload}], store=False, stream=True) as stream:
            for event in stream:
                if event.type == 'response.output_text.delta':
                    parts.append(event.delta)
                elif event.type == 'response.completed':
                    completed = True
                elif event.type in ('response.failed', 'response.incomplete', 'error'):
                    error = getattr(getattr(event, 'response', None), 'error', None)
                    code = getattr(error, 'code', None) or getattr(event, 'code', '')
                    raise ValueError('Análisis detenido: ' + str(code or event.type) +
                        '. Revisa los límites de tu plan o vuelve a conectar. No se usará API de pago.')
        if not completed:
            raise ValueError('Respuesta interrumpida; no se mostrará como completa.')
        return ''.join(parts)


class ApiBackend:
    """Optional future path. Only constructed after explicit API mode selection."""
    def __init__(self, key, model='gpt-4.1-mini'):
        from openai import OpenAI
        self.client = OpenAI(api_key=key, timeout=30, max_retries=1)
        self.model = model

    def transcribe(self, samples, prompt):
        result = self.client.audio.transcriptions.create(model='gpt-4o-mini-transcribe',
            file=('audio.wav', wav_bytes(samples), 'audio/wav'), prompt=prompt)
        return result.text.strip()

    def analyze(self, instructions, payload):
        return self.client.responses.create(model=self.model, instructions=instructions,
            input=payload, text={'format': {'type': 'json_object'}}, max_output_tokens=2200,
            store=False).output_text
