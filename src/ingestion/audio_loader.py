# src/ingestion/audio_loader.py
from src.logging_conf import get_logger

# librerías externas
from pathlib import Path
from pydub import AudioSegment

logger = get_logger(__name__)

def load_mp3(mp3_path: Path) -> AudioSegment:
    """
    Carga un archivo MP3 como objeto AudioSegment.
    """
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        raise FileNotFoundError(f"El archivo no existe: {mp3_path}")
    if mp3_path.suffix.lower() != ".mp3":
        raise ValueError(f"No es un archivo MP3: {mp3_path}")

    logger.info("Cargando MP3: %s", mp3_path)
    audio = AudioSegment.from_mp3(mp3_path)
    logger.info(
        "Archivo cargado: duración %.2f s, canales %d, frame_rate %d",
        len(audio) / 1000,
        audio.channels,
        audio.frame_rate,
    )
    return audio
