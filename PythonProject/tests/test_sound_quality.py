"""Audio-content and callback regressions; no speakers or user data required."""
import unittest
from unittest.mock import patch

import numpy as np

from core.sound_engine import SoundEngine
from utils.constants import SOUND_TYPES, SOUND_LABELS, SOUND_DESCRIPTIONS


class SoundQualityTests(unittest.TestCase):
    def setUp(self):
        self.engine = SoundEngine()
        self.engine._rng = np.random.default_rng(421)

    def test_noise_spectral_slopes_are_white_pink_and_brown(self):
        self.engine._sample_rate = 12000
        for name, expected, target in [('white_noise', 0, .075),
                                       ('pink_noise', -1, .10), ('brown_noise', -2, .12)]:
            with self.subTest(sound=name):
                audio = self.engine._get_or_create_buffer(name)
                frequencies = np.fft.rfftfreq(len(audio), 1 / 12000)
                powers = abs(np.fft.rfft(audio)) ** 2
                edges = np.geomspace(80, 4000, 18)
                means = [np.mean(powers[(frequencies >= a) & (frequencies < b)])
                         for a, b in zip(edges[:-1], edges[1:])]
                slope = np.polyfit(np.log(np.sqrt(edges[:-1] * edges[1:])), np.log(means), 1)[0]
                self.assertAlmostEqual(slope, expected, delta=.12)
                self.assertAlmostEqual(float(np.sqrt(np.mean(audio ** 2))), target, delta=.005)
                self.assertLess(abs(float(np.mean(audio))), 1e-6)
                self.assertLess(float(np.max(abs(audio))), .81)
                self.assertEqual(audio.dtype, np.float32)

    def test_tones_have_correct_channels_frequencies_and_clean_long_phase(self):
        for name, frequencies in [('432hz_focus', (432,)),
                                  ('binaural_alpha', (220, 230)),
                                  ('binaural_gamma', (220, 260))]:
            audio = self.engine._get_or_create_buffer(name)
            channels = audio[:, None] if audio.ndim == 1 else audio
            for channel, hz in enumerate(frequencies):
                data = channels[:, channel]
                dominant = np.argmax(abs(np.fft.rfft(data))) * self.engine._sample_rate / len(data)
                self.assertAlmostEqual(dominant, hz, places=3)
                # Compare the last second with the first; both contain integer cycles.
                np.testing.assert_allclose(data[-44100:], data[:44100], atol=1e-6)
            self.assertAlmostEqual(float(np.sqrt(np.mean(audio ** 2))), .07, delta=.001)

    def test_crossfade_removes_duplicated_overlap_and_preserves_stereo(self):
        self.engine._sample_rate = 1000
        audio = np.column_stack((np.arange(4000), 2 * np.arange(4000))).astype(np.float32)
        result = self.engine._make_loopable(audio)
        self.assertEqual(result.shape, (3250, 2))
        np.testing.assert_allclose(result[:, 1], 2 * result[:, 0])
        np.testing.assert_allclose(result[-1], audio[749], atol=.001)
        np.testing.assert_array_equal(result[0], audio[750])

    def test_recorded_rain_is_available_offline_and_has_headroom(self):
        audio = self.engine._get_or_create_buffer('rain')
        self.assertGreater(len(audio) / 44100, 25)
        self.assertTrue(np.isfinite(audio).all())
        self.assertLess(float(np.max(abs(audio))), .81)
        self.assertAlmostEqual(float(np.sqrt(np.mean(audio ** 2))), .10, delta=.005)
        # A seam must be no larger than an ordinary local sample transition.
        seam = np.max(abs(audio[0] - audio[-1]))
        self.assertLess(seam, np.quantile(abs(np.diff(audio, axis=0)), .999))

    @patch('core.sound_engine.sd.OutputStream')
    def test_callback_wraps_and_ramps_instead_of_stepping_volume(self, output):
        with patch.object(self.engine, '_get_or_create_buffer', return_value=np.ones(11, dtype=np.float32)):
            self.engine.play('rain', .5)
        callback = output.call_args.kwargs['callback']
        data = np.empty((1024, 2), dtype=np.float32)
        callback(data, len(data), None, None)
        self.assertEqual(data[0, 0], 0)
        self.assertAlmostEqual(float(data[-1, 0]), .5)
        np.testing.assert_array_equal(data[:, 0], data[:, 1])
        self.assertEqual(self.engine._positions['rain'], 1024 % 11)
        self.engine.set_volume('rain', .1)
        callback(data, len(data), None, None)
        self.assertAlmostEqual(float(data[0, 0]), .5)
        self.assertAlmostEqual(float(data[-1, 0]), .1)
        silenced = self.engine._fade_events['rain']
        def consume_stop(timeout):
            callback(data, len(data), None, None)
            return silenced.is_set()
        with patch.object(silenced, 'wait', side_effect=consume_stop):
            self.engine.stop('rain')
        self.assertAlmostEqual(float(data[0, 0]), .1)
        self.assertEqual(data[-1, 0], 0)
        self.engine.cleanup()
        self.assertFalse(self.engine._fade_events)

    def test_catalog_has_descriptions_and_unknown_ids_do_not_play_wrong_audio(self):
        self.assertEqual(len(SOUND_TYPES), 7)
        self.assertTrue(set(SOUND_TYPES) <= SOUND_LABELS.keys())
        self.assertTrue(set(SOUND_TYPES) <= SOUND_DESCRIPTIONS.keys())
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            self.engine._get_or_create_buffer('deleted_preset')


if __name__ == '__main__':
    unittest.main()
