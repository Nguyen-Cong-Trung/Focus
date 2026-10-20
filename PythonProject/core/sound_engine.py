"""Offline ambient audio for Focus: field-recorded rain and synthesized noise/tones."""

import threading
from functools import wraps
import numpy as np
from utils.constants import SAMPLE_RATE

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    print("Warning: sounddevice module not found. SoundEngine will be a no-op.")
    SOUNDDEVICE_AVAILABLE = False


def synchronized(function):
    @wraps(function)
    def run(self, *args, **kwargs):
        with self._audio_lock:
            return function(self, *args, **kwargs)
    return run


class SoundEngine:
    """Cache sounds on demand and play stereo without changing saved sound IDs."""

    BUFFER_SECONDS = 20
    CROSSFADE_SECONDS = 0.75

    def __init__(self):
        self._audio_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._generation = 0
        self._closed = False
        self._streams: dict = {}
        self._volumes: dict[str, float] = {}
        self._playing: dict[str, bool] = {}
        self._buffers: dict[str, np.ndarray] = {}
        self._positions: dict[str, int] = {}
        self._fade_events: dict[str, threading.Event] = {}
        self._cancellations: dict[str, threading.Event] = {}
        self._sample_rate = SAMPLE_RATE
        self._rng = np.random.default_rng()

    # ─── Utility methods ────────────────────────────────────────────

    def _apply_lowpass(self, audio: np.ndarray, cutoff_hz: float, order: float = 2.0) -> np.ndarray:
        """Apply frequency-domain low-pass filter with Butterworth-style rolloff."""
        n = len(audio)
        fft = np.fft.rfft(audio)
        freqs = np.fft.rfftfreq(n, 1.0 / self._sample_rate)
        cutoff = max(cutoff_hz, 1.0)
        response = 1.0 / (1.0 + (freqs / cutoff) ** (2 * order))
        fft *= response
        return np.fft.irfft(fft, n).astype(np.float32)

    def _apply_highpass(self, audio: np.ndarray, cutoff_hz: float, order: float = 2.0) -> np.ndarray:
        """Apply frequency-domain high-pass filter."""
        n = len(audio)
        fft = np.fft.rfft(audio)
        freqs = np.fft.rfftfreq(n, 1.0 / self._sample_rate)
        cutoff = max(cutoff_hz, 1.0)
        response = (freqs / cutoff) ** (2 * order) / (1.0 + (freqs / cutoff) ** (2 * order))
        response[0] = 0.0  # Always kill DC
        fft *= response
        return np.fft.irfft(fft, n).astype(np.float32)

    def _apply_bandpass(self, audio: np.ndarray, low_hz: float, high_hz: float, order: float = 2.0) -> np.ndarray:
        """Apply frequency-domain bandpass filter."""
        filtered = self._apply_highpass(audio, low_hz, order)
        filtered = self._apply_lowpass(filtered, high_hz, order)
        return filtered

    def _make_loopable(self, audio: np.ndarray) -> np.ndarray:
        """Overlap tail/head, then remove the duplicated head from the loop.

        Keeping both the blended head and the old tail repeats the tail and
        creates a discontinuity, especially on stereo recordings.
        """
        audio = np.asarray(audio, dtype=np.float32)
        fade_len = min(round(self._sample_rate * self.CROSSFADE_SECONDS), len(audio) // 4)
        if fade_len < 2:
            return audio.copy()
        angle = np.linspace(0, np.pi / 2, fade_len, dtype=np.float64)
        fade_out, fade_in = np.cos(angle), np.sin(angle)
        if audio.ndim == 2:
            fade_out, fade_in = fade_out[:, None], fade_in[:, None]
        result = audio[fade_len:].copy()
        result[-fade_len:] = audio[-fade_len:] * fade_out + audio[:fade_len] * fade_in
        return result

    def _normalize(self, audio: np.ndarray, peak: float = 0.4) -> np.ndarray:
        max_val = np.max(np.abs(audio))
        if max_val > 1e-6:
            audio = audio * (peak / max_val)
        return audio

    def _level(self, audio: np.ndarray, rms: float) -> np.ndarray:
        """Match average levels with peak headroom; preserve stereo balance."""
        audio = np.asarray(audio, dtype=np.float32)
        audio = audio - np.mean(audio, axis=0, keepdims=True)
        measured = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
        if measured > 1e-9:
            gain = min(rms / measured, 0.80 / max(float(np.max(np.abs(audio))), 1e-9))
            audio = audio * gain
        return np.ascontiguousarray(audio, dtype=np.float32)

    def _generate_colored_noise(self, power: float, rms: float) -> np.ndarray:
        """Power density proportional to 1/f**power, with sub-bass bounded.

        The FFT creates a periodic buffer, so no fade or silence is needed
        at its seam. Unlike low-passed white noise, brown has a 1/f² slope.
        """
        n = round(self._sample_rate * self.BUFFER_SECONDS)
        raw = self._rng.standard_normal(n).astype(np.float32)
        spectrum = np.fft.rfft(raw)
        frequencies = np.fft.rfftfreq(n, 1 / self._sample_rate)
        spectrum *= np.maximum(frequencies, 25.0) ** (-power / 2)
        spectrum *= 1 / np.sqrt(1 + (frequencies / 16000) ** 12)
        spectrum[0] = 0
        noise = np.fft.irfft(spectrum, n)
        return self._level(noise, rms)

    def _generate_white_noise_buffer(self) -> np.ndarray:
        return self._generate_colored_noise(0, 0.075)

    def _generate_pink_noise_buffer(self) -> np.ndarray:
        return self._generate_colored_noise(1, 0.10)

    def _generate_brown_noise_buffer(self) -> np.ndarray:
        return self._generate_colored_noise(2, 0.12)

    def _generate_rain_buffer(self) -> np.ndarray:
        from pathlib import Path
        recording = Path(__file__).resolve().parents[1] / 'assets' / 'audio' / 'rain.wav'
        return self._level(self._make_loopable(self._load_wav_buffer(str(recording))), 0.10)

    # ─── Playback control ───────────────────────────────────────────

    def _get_or_create_buffer(self, sound_type: str, file_path: str = None) -> np.ndarray:
        """Get cached buffer or generate a new one."""
        if sound_type not in self._buffers:
            if file_path:
                self._buffers[sound_type] = self._load_wav_buffer(file_path)
            else:
                generators = {
                    "white_noise": self._generate_white_noise_buffer,
                    "brown_noise": self._generate_brown_noise_buffer,
                    "pink_noise": self._generate_pink_noise_buffer,
                    "rain": self._generate_rain_buffer,
                    "432hz_focus": self._generate_432hz_focus_buffer,
                    "binaural_alpha": self._generate_binaural_alpha_buffer,
                    "binaural_gamma": self._generate_binaural_gamma_buffer
                }
                if sound_type not in generators:
                    raise ValueError("This sound is unavailable. Choose another sound in Sound Studio.")
                self._buffers[sound_type] = generators[sound_type]()
        return self._buffers[sound_type]

    @property
    def generation(self):
        with self._state_lock:
            return self._generation

    def request_stop_all(self, close=False):
        """Invalidate queued/in-flight play requests without waiting on synthesis.

        Call on the UI thread before scheduling a stop on the audio worker.
        Existing callbacks immediately emit silence when their token expires.
        """
        with self._state_lock:
            self._generation += 1
            self._closed = self._closed or close
            return self._generation

    def _current(self, generation):
        return not self._closed and generation == self._generation

    @synchronized
    def play(self, sound_type: str, volume: float = 0.5, file_path: str = None, generation=None) -> bool:
        """Start playing a sound type. Stops any previous instance of the same type."""
        if generation is None:
            generation = self.generation
        if not self._current(generation):
            return False
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("Audio playback is not available. Check the Windows output device.")

        self.stop(sound_type)
        if not np.isfinite(volume):
            raise ValueError('Choose a finite volume between 0 and 1.')
        self._volumes[sound_type] = max(0.0, min(1.0, volume))
        # Get or create the pre-generated audio buffer
        try:
            buffer = self._get_or_create_buffer(sound_type, file_path)
        except Exception:
            self._volumes.pop(sound_type, None)
            raise
        if not self._current(generation):
            self._volumes.pop(sound_type, None)
            return False
        buf_len = len(buffer)
        if buf_len == 0:
            self._volumes.pop(sound_type, None)
            raise ValueError("The selected sound file is empty.")
        self._positions[sound_type] = 0
        current_gain = 0.0
        silenced = threading.Event()
        cancelled = threading.Event()

        def callback(outdata, frames, time_info, status):
            nonlocal current_gain
            if cancelled.is_set() or not self._current(generation):
                outdata.fill(0)
                current_gain = 0.0
                silenced.set()
                return
            pos = self._positions.get(sound_type, 0)
            vol = self._volumes.get(sound_type, 0.0)

            # Fill output by looping through the buffer
            remaining = frames
            write_pos = 0
            is_stereo = len(buffer.shape) > 1 and buffer.shape[1] == 2
            
            while remaining > 0:
                chunk = min(remaining, buf_len - pos)
                if is_stereo:
                    outdata[write_pos:write_pos + chunk, 0] = buffer[pos:pos + chunk, 0]
                    outdata[write_pos:write_pos + chunk, 1] = buffer[pos:pos + chunk, 1]
                else:
                    outdata[write_pos:write_pos + chunk, 0] = buffer[pos:pos + chunk]
                    outdata[write_pos:write_pos + chunk, 1] = buffer[pos:pos + chunk]
                write_pos += chunk
                remaining -= chunk
                pos = (pos + chunk) % buf_len

            self._positions[sound_type] = pos
            # Ramp start, slider changes and stop rather than stepping gain.
            ramp = min(frames, max(2, round(self._sample_rate * 0.02)))
            outdata[:ramp] *= np.linspace(current_gain, vol, ramp, dtype=np.float32)[:, None]
            outdata[ramp:] *= vol
            current_gain = vol
            if vol == 0:
                silenced.set()

        stream = None
        try:
            stream = sd.OutputStream(samplerate=self._sample_rate, channels=2,
                                     callback=callback, blocksize=1024, dtype='float32')
            stream.start()
            if not self._current(generation):
                stream.abort()
                stream.close()
                self._volumes.pop(sound_type, None)
                self._positions.pop(sound_type, None)
                return False
        except Exception:
            cancelled.set()
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            self._volumes.pop(sound_type, None)
            self._positions.pop(sound_type, None)
            self._playing.pop(sound_type, None)
            raise
        self._streams[sound_type] = stream
        self._fade_events[sound_type] = silenced
        self._cancellations[sound_type] = cancelled
        self._playing[sound_type] = True
        return True

    @synchronized
    def stop(self, sound_type: str = None, expected_stream=None) -> None:
        """Stop a specific sound or all sounds if sound_type is None."""
        if sound_type:
            if expected_stream is not None and self._streams.get(sound_type) is not expected_stream:
                return
            if sound_type in self._streams:
                silenced = self._fade_events.pop(sound_type, None)
                if silenced is not None:
                    silenced.clear()
                    self._volumes[sound_type] = 0.0
                    # Audio operations already run on the app's audio worker.
                    # Bound the wait in case the output device disconnected.
                    silenced.wait(0.12)
                stream = self._streams.pop(sound_type)
                try:
                    stream.stop()
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception('Could not stop audio stream')
                finally:
                    try:
                        stream.close()
                    except Exception:
                        import logging
                        logging.getLogger(__name__).exception('Could not close audio stream')
                cancelled = self._cancellations.pop(sound_type, None)
                if cancelled is not None:
                    cancelled.set()
            self._playing.pop(sound_type, None)
            self._volumes.pop(sound_type, None)
            self._positions.pop(sound_type, None)
        else:
            self.stop_all()

    @synchronized
    def stop_all(self, invalidate=True) -> None:
        """Stop all playing sounds."""
        if invalidate:
            self.request_stop_all()
        for stype in list(self._streams.keys()):
            self.stop(stype)

    def set_volume(self, sound_type: str, volume: float) -> None:
        """Adjust volume of a playing sound in real-time (0.0 to 1.0)."""
        if sound_type in self._volumes:
            self._volumes[sound_type] = max(0.0, min(1.0, volume))

    def is_playing(self, sound_type: str) -> bool:
        """Check if a sound type is currently playing."""
        stream = self._streams.get(sound_type)
        if stream is None or self._closed:
            return False
        try:
            return self._playing.get(sound_type, False) and bool(stream.active)
        except Exception:
            return False

    def get_playing_sounds(self) -> list[str]:
        """Return list of currently playing sound types."""
        return [name for name in list(self._streams) if self.is_playing(name)]

    def playback_handle(self, sound_type):
        """Identify the exact stream owned by an automatic focus session."""
        return self._streams.get(sound_type)

    @synchronized
    def cleanup(self) -> None:
        """Stop all sounds and release resources. Call on app exit."""
        self.stop_all()
        self._buffers.clear()

    def close(self):
        """Terminal shutdown; unlike workspace cleanup, this forbids new play."""
        self.request_stop_all(close=True)
        with self._audio_lock:
            self.stop_all(invalidate=False)
            self._buffers.clear()

    def _tone(self, left_hz: float, right_hz: float = None) -> np.ndarray:
        # Float64 phase avoids the accumulating float32 phase error that made
        # the original sustained tones rough near the end of each loop.
        n = round(self._sample_rate * self.BUFFER_SECONDS)
        t = np.arange(n, dtype=np.float64) / self._sample_rate
        left = np.sin(2 * np.pi * left_hz * t)
        if right_hz is None:
            return self._level(left, 0.07)
        right = np.sin(2 * np.pi * right_hz * t)
        return self._level(np.column_stack((left, right)), 0.07)

    def _generate_432hz_focus_buffer(self) -> np.ndarray:
        return self._tone(432)

    def _generate_binaural_alpha_buffer(self) -> np.ndarray:
        return self._tone(220, 230)

    def _generate_binaural_gamma_buffer(self) -> np.ndarray:
        return self._tone(220, 260)

    def get_volume(self, sound_type):
        return self._volumes.get(sound_type, 0.5)

    @synchronized
    def forget(self, sound_type):
        self.stop(sound_type)
        self._buffers.pop(sound_type, None)

    def _load_wav_buffer(self, file_path: str) -> np.ndarray:
        import wave
        from core.audio_library import inspect_wav
        channels, width, rate, frames = inspect_wav(file_path)
        with wave.open(str(file_path), 'rb') as audio:
            data = audio.readframes(frames)
        if width == 1:
            arr = (np.frombuffer(data, dtype=np.uint8).astype(np.float32)-128)/128
        elif width == 3:
            raw = np.frombuffer(data, dtype=np.uint8).reshape(-1,3).astype(np.int32)
            signed = raw[:,0] | (raw[:,1]<<8) | (raw[:,2]<<16)
            arr = ((signed ^ 0x800000)-0x800000).astype(np.float32)/8388608
        else:
            arr = np.frombuffer(data,dtype='<i2' if width==2 else '<i4').astype(np.float32)/(32768 if width==2 else 2147483648)
        arr = arr.reshape(-1, channels)
        if channels == 1:
            arr = np.repeat(arr,2,axis=1)
        if rate != self._sample_rate:
            old = np.arange(len(arr))/rate
            new = np.arange(max(1, round(len(arr)*self._sample_rate/rate)))/self._sample_rate
            arr = np.column_stack([np.interp(new,old,arr[:,channel]) for channel in range(2)])
        return np.ascontiguousarray(arr,dtype=np.float32)
