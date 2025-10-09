# tests/test_audio_processor_integration.py
from pathlib import Path
from pydub import AudioSegment
import pytest

from src.ingestion.audio_processor import process_mp3_to_wav16k


@pytest.mark.integration
def test_process_mp3_to_wav16k(tmp_path: Path):
    """
    Prueba de integración:
    1) Genera un MP3 de 1 segundo de silencio.
    2) Ejecuta el pipeline de audio_processor.
    3) Verifica que el WAV de salida existe y tenga el formato correcto.
    """
    # ---------- Crear un MP3 sintético ----------
    mp3_file = tmp_path / "input_test.mp3"
    # 1 segundo de silencio
    silent = AudioSegment.silent(duration=1000)
    silent.export(mp3_file, format="mp3")

    # ---------- Procesar con nuestro módulo ----------
    wav_dir = tmp_path / "out"
    wav_path = process_mp3_to_wav16k(
        mp3_path=mp3_file,
        out_dir=wav_dir,
        target_dbfs=-20.0
    )

    # ---------- Validaciones ----------
    assert wav_path.exists(), "El archivo WAV no fue generado"
    assert wav_path.suffix.lower() == ".wav"

    # Abrimos el WAV para verificar propiedades
    wav_audio = AudioSegment.from_wav(wav_path)
    assert wav_audio.frame_rate == 16000, "La frecuencia no es 16 kHz"
    assert wav_audio.channels == 1, "El archivo no es mono"
    assert wav_audio.sample_width == 2, "El archivo no es PCM16"
    # Duración aproximada (tolerancia de 0.2 seg por conversión)
    assert abs(len(wav_audio) - 1000) <= 200, "La duración difiere demasiado"


def test_process_mp3_missing_file(tmp_path: Path):
    """
    Verifica que se lance FileNotFoundError si el MP3 no existe.
    """
    fake_file = tmp_path / "no_existe.mp3"
    with pytest.raises(FileNotFoundError):
        process_mp3_to_wav16k(fake_file, tmp_path)
