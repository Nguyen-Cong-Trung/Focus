"""Audio coexistence regressions; no real PortAudio device is opened."""
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import wave

import numpy as np

from core.audio_library import AudioLibrary
from core.sound_engine import SoundEngine
from core.work import BackgroundWork


class AudioCoexistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = SoundEngine()
        self.output = patch('core.sound_engine.sd.OutputStream').start()
        self.addCleanup(patch.stopall)
        self.output.return_value.active = True
        self.addCleanup(self.engine.close)

    def cache(self, name):
        with patch.object(self.engine, '_load_wav_buffer', return_value=np.ones(32, dtype=np.float32)):
            return self.engine._get_or_create_buffer(name, 'fixture.wav')

    def test_previewing_many_imports_evicts_idle_buffers_in_access_order(self):
        self.engine.MAX_CACHE_BYTES = 256
        for name in ('one', 'two'):
            self.cache(name)
        self.cache('one')
        self.cache('three')
        self.assertEqual(list(self.engine._buffers), ['one', 'three'])
        self.assertLessEqual(sum(buffer.nbytes for buffer in self.engine._buffers.values()), 256)

    def test_cache_eviction_never_discards_a_playing_buffer(self):
        self.engine.MAX_CACHE_BYTES = 128
        self.cache('playing')
        self.engine.play('playing')
        original = self.engine._buffers['playing']
        self.cache('preview')
        self.assertIs(self.engine._buffers['playing'], original)
        self.assertTrue(self.engine.is_playing('playing'))
        self.engine.stop('playing')
        self.assertNotIn('playing', self.engine._buffers)
        self.assertEqual(list(self.engine._buffers), ['preview'])

    def test_oversized_recording_is_released_when_stopped(self):
        self.engine.MAX_CACHE_BYTES = 64
        with patch.object(self.engine, '_load_wav_buffer', return_value=np.ones(32, dtype=np.float32)):
            self.engine.play('large', file_path='fixture.wav')
        callback = self.output.call_args.kwargs['callback']
        data = np.empty((1024, 2), dtype=np.float32)
        callback(data, len(data), None, None)
        self.assertTrue(np.any(data))
        self.engine.stop('large')
        self.assertEqual(self.engine._buffers, {})

    def test_output_busy_does_not_stop_an_unrelated_playing_sound(self):
        self.cache('first')
        first = Mock(active=True)
        self.output.return_value = first
        self.engine.play('first')
        self.cache('second')
        self.output.side_effect = RuntimeError('Device held exclusively by another audio app')
        with self.assertRaisesRegex(RuntimeError, 'exclusively'):
            self.engine.play('second')
        self.assertTrue(self.engine.is_playing('first'))
        self.assertFalse(self.engine.is_playing('second'))
        first.close.assert_not_called()
        self.assertNotIn('second', self.engine._positions)
        self.assertNotIn('second', self.engine._volumes)

    def test_cancelled_oversized_preparation_releases_buffer_without_a_stream(self):
        self.engine.MAX_CACHE_BYTES = 64
        def prepare(_):
            self.engine.request_stop_all()
            return np.ones(32, dtype=np.float32)
        with patch.object(self.engine, '_load_wav_buffer', side_effect=prepare):
            self.assertFalse(self.engine.play('large', file_path='fixture.wav'))
        self.output.assert_not_called()
        self.assertEqual(self.engine._buffers, {})
        self.engine.stop_all()
        self.assertEqual(self.engine._buffers, {})

    def test_stop_all_trims_oversized_idle_cache_even_without_streams(self):
        self.engine.MAX_CACHE_BYTES = 64
        self.cache('large')
        self.assertTrue(self.engine._buffers)
        self.engine.stop_all()
        self.assertEqual(self.engine._buffers, {})

    def test_invalidated_device_start_releases_oversized_buffer(self):
        self.engine.MAX_CACHE_BYTES = 64
        self.output.return_value.start.side_effect = self.engine.request_stop_all
        with patch.object(self.engine, '_load_wav_buffer', return_value=np.ones(32, dtype=np.float32)):
            self.assertFalse(self.engine.play('large', file_path='fixture.wav'))
        self.output.return_value.abort.assert_called_once()
        self.output.return_value.close.assert_called_once()
        self.assertEqual(self.engine._buffers, {})

    def test_busy_device_releases_failed_large_buffer_but_preserves_active_audio(self):
        self.engine.MAX_CACHE_BYTES = 128
        self.cache('playing')
        self.engine.play('playing')
        active = self.engine._buffers['playing']
        self.output.side_effect = RuntimeError('Output device is busy')
        with patch.object(self.engine, '_load_wav_buffer', return_value=np.ones(64, dtype=np.float32)):
            with self.assertRaisesRegex(RuntimeError, 'busy'):
                self.engine.play('large', file_path='fixture.wav')
        self.assertEqual(list(self.engine._buffers), ['playing'])
        self.assertIs(self.engine._buffers['playing'], active)
        self.assertTrue(self.engine.is_playing('playing'))

    def test_failed_device_start_releases_oversized_buffer(self):
        self.engine.MAX_CACHE_BYTES = 64
        self.output.return_value.start.side_effect = RuntimeError('Output device removed')
        with patch.object(self.engine, '_load_wav_buffer', return_value=np.ones(32, dtype=np.float32)):
            with self.assertRaisesRegex(RuntimeError, 'removed'):
                self.engine.play('large', file_path='fixture.wav')
        self.output.return_value.close.assert_called_once()
        self.assertEqual(self.engine._buffers, {})

    def test_unavailable_audio_backend_trims_idle_cache(self):
        self.engine.MAX_CACHE_BYTES = 64
        self.cache('large')
        with patch('core.sound_engine.SOUNDDEVICE_AVAILABLE', False):
            with self.assertRaisesRegex(RuntimeError, 'not available'):
                self.engine.play('large', file_path='fixture.wav')
        self.output.assert_not_called()
        self.assertEqual(self.engine._buffers, {})

    def test_lost_device_can_be_retried_without_stale_playing_state(self):
        self.cache('rain')
        first, replacement = Mock(active=True), Mock(active=True)
        self.output.side_effect = [first, replacement]
        self.engine.play('rain')
        first.active = False
        self.assertEqual(self.engine.get_playing_sounds(), [])
        self.assertTrue(self.engine.play('rain'))
        first.close.assert_called_once()
        self.assertIs(self.engine.playback_handle('rain'), replacement)

    def test_failed_start_releases_stream_and_allows_retry(self):
        self.cache('rain')
        failed, retry = Mock(active=False), Mock(active=True)
        failed.start.side_effect = RuntimeError('Output device was removed')
        self.output.side_effect = [failed, retry]
        with self.assertRaisesRegex(RuntimeError, 'removed'):
            self.engine.play('rain')
        failed.close.assert_called_once()
        self.assertFalse(self.engine.is_playing('rain'))
        self.assertTrue(self.engine.play('rain'))

    def test_cancellation_during_device_creation_cannot_resume_audio(self):
        self.cache('rain')
        entered, release = threading.Event(), threading.Event()
        stream = Mock(active=True)
        def create(**kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return stream
        self.output.side_effect = create
        outcome = []
        worker = threading.Thread(target=lambda: outcome.append(self.engine.play('rain')))
        worker.start()
        self.assertTrue(entered.wait(2))
        self.engine.request_stop_all()
        release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(outcome, [False])
        stream.abort.assert_called_once()
        stream.close.assert_called_once()


class RecordingImportCoexistenceTests(unittest.TestCase):
    def test_recording_rewritten_during_copy_is_rejected_without_database_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'recording.wav'
            with wave.open(str(source), 'wb') as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(8000)
                audio.writeframes(b'\x00\x00' * 800)
            db = Mock()
            db.get_all_custom_sounds.return_value = []
            library = AudioLibrary(db, root / 'sounds')
            copy = shutil.copyfile
            def racing_copy(src, dest):
                result = copy(src, dest)
                # Model an external recorder truncating the source during copy.
                Path(dest).write_bytes(Path(dest).read_bytes()[:50])
                return result
            with patch('core.audio_library.shutil.copyfile', side_effect=racing_copy):
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    library.import_file(source)
            db.save_custom_sound.assert_not_called()
            self.assertEqual(list((root / 'sounds').iterdir()), [])


class WorkerCompletionCoexistenceTests(unittest.TestCase):
    def test_failed_error_notice_cannot_block_other_completed_operations(self):
        work = BackgroundWork(report=Mock(side_effect=RuntimeError('notice widget was destroyed')))
        self.addCleanup(work.close)
        observed = []
        work.events.put(Mock(side_effect=RuntimeError('audio view no longer exists')))
        work.events.put(lambda: observed.append('next completed operation'))
        with self.assertLogs('core.work', level='ERROR'):
            work.drain()
        self.assertEqual(observed, ['next completed operation'])
        self.assertTrue(work.events.empty())


if __name__ == '__main__':
    unittest.main()
