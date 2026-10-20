"""Rebuild the bundled rain WAV from the credited public-domain original.

Developer tool only: requires numpy and soundfile. Usage:
    python maintenance/prepare_rain.py path/to/SV100344.ogg
The application itself needs neither soundfile nor network access.
"""
import argparse
import hashlib
from pathlib import Path
import wave

import numpy as np
import soundfile as sf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    expected = '9b450ab63ee42a5225a46f8ab2737f46d9f5c8a62bb270c93efdf9f3d4e9ce5e'
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != expected:
        raise ValueError('Use the original SV100344.ogg credited in assets/audio/rain-source.json.')
    audio, rate = sf.read(args.source, dtype='float32', always_2d=True)
    audio = audio.mean(axis=1)
    audio = audio[round(.25 * rate):-round(.25 * rate)]
    frequencies = np.fft.rfftfreq(len(audio), 1 / rate)
    high = (frequencies / 40) ** 4 / (1 + (frequencies / 40) ** 4)
    low = 1 / np.sqrt(1 + (frequencies / 9000) ** 16)
    audio = np.fft.irfft(np.fft.rfft(audio) * high * low, n=len(audio))[::2]
    audio -= np.mean(audio)
    audio *= .10 / np.sqrt(np.mean(audio * audio))
    audio = .55 * np.tanh(audio / .55)
    audio *= .10 / np.sqrt(np.mean(audio * audio))
    assert np.max(abs(audio)) < .8
    destination = Path(__file__).resolve().parents[1] / 'PythonProject/assets/audio/rain.wav'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate // 2)
        output.writeframes(np.round(audio * 32767).astype('<i2').tobytes())
    print(destination)


if __name__ == '__main__':
    main()
