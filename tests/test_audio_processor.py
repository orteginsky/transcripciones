# tests/test_audio_loader.py
from src.ingestion.audio_loader import load_mp3

# librerías externas
from pathlib import Path
import pytest
from pydub import AudioSegment

def test_load_valid_mp3(tmp_path: Path):
    # Crear un MP3 de prueba (pydub puede exportar WAV a MP3 si ffmpeg está)
    test_wav = tmp_path / "test.wav"
    silent = AudioSegment.silent(duration=1000)  # 1 segundo de silencio
    silent.export(test_wav, format="wav")

    test_mp3 = tmp_path / "test.mp3"
    silent.export(test_mp3, format="mp3")

    audio = load_mp3(test_mp3)
    assert isinstance(audio, AudioSegment)
    assert len(audio) >= 900  # al menos ~0.9 segundos

def test_invalid_extension_raises(tmp_path: Path):
    fake_file = tmp_path / "fake.txt"
    fake_file.write_text("not audio")
    with pytest.raises(ValueError):
        load_mp3(fake_file)

def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_mp3(Path("no_existe.mp3"))

def test_split_chunks(tmp_path):
    from pydub.generators import Sine
    from src.ingestion.audio_processor import split_wav_chunks, export_wav

    # Crear un WAV de prueba (30 seg)
    tone = Sine(440).to_audio_segment(duration=30_000).set_frame_rate(16000).set_channels(1)
    wav_path = tmp_path / "test.wav"
    export_wav(tone, wav_path)

    # Split en fragmentos de 10 seg
    chunks = split_wav_chunks(wav_path, chunk_length_ms=10_000)
    assert len(chunks) == 3
    for c in chunks:
        assert c.exists()
