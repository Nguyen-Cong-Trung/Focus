"""Validate PCM WAVs and keep imported files independent of their original names."""
from pathlib import Path
import shutil
import wave
from uuid import uuid4
from data.models import CustomSound

MAX_AUDIO_BYTES = 64 * 1024 * 1024


def inspect_wav(path):
    path = Path(path)
    if not path.is_file() or not 44 <= path.stat().st_size <= MAX_AUDIO_BYTES:
        raise ValueError('Choose a non-empty WAV file smaller than 64 MB.')
    try:
        with wave.open(str(path), 'rb') as audio:
            channels, width, rate, frames = audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()
            if channels not in (1,2) or width not in (1,2,3,4) or not 8000 <= rate <= 192000 or frames <= 0 or audio.getcomptype() != 'NONE':
                raise ValueError('Use a mono/stereo PCM WAV file (8, 16, 24 or 32 bit).')
            if frames / rate > 360:
                raise ValueError('Choose a shorter recording (up to 6 minutes) to keep memory use bounded.')
            if frames * channels * width > MAX_AUDIO_BYTES:
                raise ValueError('The WAV audio is too large.')
            # Read in bounded chunks to reject truncated files before import.
            read = 0
            while True:
                chunk = audio.readframes(16384)
                if not chunk: break
                read += len(chunk)
            if read != frames * channels * width:
                raise ValueError('The WAV file is incomplete.')
            return channels, width, rate, frames
    except (wave.Error, EOFError) as exc:
        raise ValueError('This is not a supported PCM WAV file.') from exc


class AudioLibrary:
    def __init__(self, db, directory):
        self.db, self.directory = db, Path(directory)

    def import_file(self, source):
        inspect_wav(source)
        self.directory.mkdir(parents=True, exist_ok=True)
        dest = self.directory / (uuid4().hex + '.wav')
        names = {s.name.casefold() for s in self.db.get_all_custom_sounds()}
        base = Path(source).stem.strip()[:80] or 'Imported sound'
        name, number = base, 2
        while name.casefold() in names:
            name, number = f'{base} ({number})', number+1
        try:
            shutil.copyfile(source, dest)
            ident = self.db.save_custom_sound(CustomSound(name=name, file_path=str(dest)))
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        return ident

    def remove(self, sound):
        # DB detaches all mode references in the same transaction.
        self.db.delete_custom_sound(sound.id)
        path = Path(sound.file_path).resolve()
        if path.parent == self.directory.resolve():
            path.unlink(missing_ok=True)
