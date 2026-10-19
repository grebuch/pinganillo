import queue
import threading
import time


class DeadlineCall:
    """One in-flight worker maximum; late results are never reused."""
    def __init__(self, timeout=45, progress=None):
        self.timeout, self.progress = timeout, progress
        self.worker = None
        self.lock = threading.Lock()

    def call(self, target):
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise RuntimeError('Sigue pendiente una conexión anterior. No se lanzará otra en paralelo.')
            result = queue.Queue(maxsize=1)
            def run():
                try:
                    result.put((True, target()))
                except Exception as exc:
                    result.put((False, exc))
            self.worker = threading.Thread(target=run, daemon=True)
            self.worker.start()
        start = time.monotonic()
        while True:
            remaining = self.timeout - (time.monotonic() - start)
            if remaining <= 0:
                raise TimeoutError('La IA no completó una respuesta en 45 segundos. Se pausa solo el análisis; no la captura ni la transcripción.')
            try:
                ok, value = result.get(timeout=min(1, remaining))
            except queue.Empty:
                if self.progress:
                    self.progress(f'Esperando IA · {int(time.monotonic()-start)} s (límite 45 s)')
                continue
            if not ok:
                raise value
            return value
