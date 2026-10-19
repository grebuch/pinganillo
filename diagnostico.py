"""No account, no API. Record a short sample in memory and transcribe locally."""
import importlib.metadata
from pathlib import Path
import platform
import sys
import time
import traceback


def main():
    lines = []
    def log(message):
        text = str(message)
        print(text, flush=True)
        lines.append(text)
    log('ESCUCHATOR 0.5 · diagnóstico local sin API')
    log('No guarda audio ni transcripción. Reproduce un vídeo con voz durante esta prueba.')
    log('Sistema: ' + platform.system() + ' ' + platform.release())
    log('Python: ' + sys.version.split()[0])
    for name in ['numpy', 'pyaudiowpatch', 'SoundCard', 'faster-whisper', 'ctranslate2', 'av', 'scipy']:
        try:
            log(name + ': ' + importlib.metadata.version(name))
        except importlib.metadata.PackageNotFoundError:
            log(name + ': no instalado')
    step = 'dispositivos'
    try:
        from audio_windows import devices, mono
        import numpy as np
        available = devices()
        if not available:
            raise RuntimeError('No hay entradas WASAPI disponibles')
        for i, d in enumerate(available):
            log(f'{i}: {"PC" if d.isloopback else "MIC"} · {d.name}')
        selected = input('Número de la salida que estás escuchando: ').strip()
        device = available[int(selected)]
        log('Fuente elegida: ' + device.name)
        step = 'captura'
        blocks = []
        log('Capturando 8 segundos. Mantén el vídeo con voz reproduciéndose…')
        with device.recorder(samplerate=48000) as recorder:
            for i in range(16):
                block = recorder.record(numframes=24000)
                blocks.append(block)
                log(f'Audio {i+1}/16 · RMS {float(np.sqrt(np.mean(block**2))):.6f}')
        samples = np.concatenate(blocks)
        level = float(np.sqrt(np.mean(mono(samples)**2)))
        log(f'Captura terminada · RMS mono {level:.6f}')
        if level < .00001:
            raise RuntimeError('Captura prácticamente silenciosa. Prueba la salida exacta usada por Teams/Windows.')
        step = 'modelo local'
        from backends import LocalTranscriber
        log('Cargando Whisper; la primera vez necesita descargar el modelo de Hugging Face.')
        backend = LocalTranscriber()
        started = time.monotonic()
        backend.prepare()
        log(f'Modelo listo en {time.monotonic()-started:.1f} s')
        step = 'transcripción'
        started = time.monotonic()
        text = backend.transcribe(samples, '')
        log(f'Transcripción terminada en {time.monotonic()-started:.1f} s · caracteres: {len(text)}')
        log('RESULTADO: ' + ('Audio y transcripción funcionan. Si fallan los paneles, hay que revisar la conexión/análisis IA.' if text else 'Hay audio, pero no se reconoció voz. Prueba otra muestra con voz clara.'))
    except Exception as exc:
        log('FALLO EN: ' + step)
        log(type(exc).__name__ + ': ' + str(exc))
        # No credentials or user text are collected by this script.
    finally:
        path = Path(__file__).with_name('diagnostico-escuchator.txt')
        path.write_text('\n'.join(lines), encoding='utf-8')
        print('Informe técnico guardado en ' + path.name)
        print('Puedes compartirlo: contiene versiones, nombres de dispositivos y errores, sin audio ni consultas.')


if __name__ == '__main__':
    main()
