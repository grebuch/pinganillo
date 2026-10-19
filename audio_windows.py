"""Windows loopback with native sample rate and bounded callback waits."""
import math
import queue
import time


def mono(samples):
    import numpy as np
    a = np.asarray(samples, dtype=np.float32)
    if a.ndim == 1:
        return a
    if a.ndim != 2 or not a.shape[1]:
        raise ValueError('Audio sin canales válidos')
    mixed = a.mean(axis=1)
    # Some virtual/headset channels have opposite phase; avoid cancelling speech.
    levels = np.sqrt(np.mean(a * a, axis=0))
    best = int(np.argmax(levels))
    if np.sqrt(np.mean(mixed * mixed)) < levels[best] * .2:
        return a[:, best].copy()
    return mixed


class WindowsDevice:
    def __init__(self, info, default=False):
        self.info = info
        self.id = int(info['index'])
        self.name = info['name']
        self.isloopback = bool(info.get('isLoopbackDevice'))
        self.default = default

    def recorder(self, samplerate):
        return WindowsRecorder(self.info, samplerate)


def devices():
    import pyaudiowpatch as pa
    with pa.PyAudio() as p:
        try:
            default = int(p.get_default_wasapi_loopback()['index'])
        except (OSError, KeyError):
            default = -1
        result = [WindowsDevice(d, int(d['index']) == default) for d in p.get_loopback_device_info_generator()]
        wasapi = p.get_host_api_info_by_type(pa.paWASAPI)['index']
        for i in range(p.get_device_count()):
            d = p.get_device_info_by_index(i)
            if d['hostApi'] == wasapi and d['maxInputChannels'] > 0 and not d.get('isLoopbackDevice'):
                result.append(WindowsDevice(d))
        return result


class WindowsRecorder:
    def __init__(self, info, target_rate):
        self.info, self.target = info, target_rate
        self.pending = None
        self.q = queue.Queue(maxsize=100)
        self.dropped = False
        self.p = self.stream = None

    def __enter__(self):
        import numpy as np
        import pyaudiowpatch as pa
        self.rate = int(self.info['defaultSampleRate'])
        self.channels = int(self.info['maxInputChannels'])
        self.pending = np.empty((0, self.channels), np.float32)
        self.p = pa.PyAudio()
        def callback(data, count, time_info, status):
            if data:
                block = np.frombuffer(data, dtype='<i2').astype(np.float32).reshape(-1, self.channels) / 32768.
                try:
                    self.q.put_nowait(block)
                except queue.Full:
                    self.dropped = True
            return (None, pa.paContinue)
        try:
            self.stream = self.p.open(format=pa.paInt16, channels=self.channels, rate=self.rate,
                input=True, input_device_index=int(self.info['index']),
                frames_per_buffer=max(128, self.rate // 10), stream_callback=callback)
        except Exception:
            self.p.terminate()
            raise
        return self

    def record(self, numframes):
        import numpy as np
        from scipy.signal import resample_poly
        needed = round(numframes * self.rate / self.target)
        deadline = time.monotonic() + 10
        while len(self.pending) < needed:
            if self.dropped:
                raise RuntimeError('Captura desbordada. Cierra otras tareas pesadas y vuelve a probar.')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('No llegan muestras de esta salida. Reproduce voz o selecciona otra salida de audio.')
            try:
                block = self.q.get(timeout=min(.5, remaining))
            except queue.Empty:
                continue
            self.pending = np.concatenate((self.pending, block))
        block, self.pending = self.pending[:needed], self.pending[needed:]
        if self.rate != self.target:
            divisor = math.gcd(self.rate, self.target)
            block = resample_poly(block, self.target // divisor, self.rate // divisor, axis=0)
        return np.ascontiguousarray(block, dtype=np.float32)

    def __exit__(self, *args):
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
        finally:
            if self.p:
                self.p.terminate()
