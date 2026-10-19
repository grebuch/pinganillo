import numpy as np

from escuchator.audio.dsp import for_whisper, resample, rms, to_mono


def test_opposite_phase_channels_do_not_cancel():
    a = np.sin(np.arange(4800) * 0.1).astype(np.float32)
    mono = to_mono(np.column_stack([a, -a]))
    assert rms(mono) > 0.5


def test_normal_stereo_is_averaged():
    a = np.ones((100, 2), np.float32) * 0.5
    assert np.allclose(to_mono(a), 0.5)


def test_whisper_input_is_mono_16k_float32():
    out = for_whisper(np.ones((4800, 2), np.float32) * 0.1)
    assert out.shape == (1600,)
    assert out.dtype == np.float32
    assert out.flags["C_CONTIGUOUS"]


def test_resample_native_44k1_to_48k():
    out = resample(np.zeros((44_100, 2), np.float32), 44_100, 48_000)
    assert out.shape == (48_000, 2)


def test_rms_of_empty_block_is_zero():
    assert rms(np.empty(0)) == 0.0
