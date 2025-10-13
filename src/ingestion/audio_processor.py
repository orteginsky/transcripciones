# src/ingestion/audio_processor.py
from __future__ import annotations

# Librerias externas
from pydub import AudioSegment
from pydub.utils import which

# Librerias internas
from pathlib import Path
from typing import Optional

# Módulos Globales
from src.logging_conf import get_logger

logger = get_logger(__name__)


# -------------------------------
# Utilidades / Validaciones
# -------------------------------
def _ensure_ffmpeg_available() -> None:
    """
    Verifica que ffmpeg esté disponible en PATH, ya que pydub lo usa para exportar.
    Lanza RuntimeError con un mensaje claro si no está.
    """
    if which("ffmpeg") is None:
        raise RuntimeError(
            "No se encontró 'ffmpeg' en PATH. Instálalo y asegúrate de que "
            "la carpeta 'bin' esté en PATH. Prueba 'ffmpeg -version' en tu terminal."
        )


def _ensure_parent_dir(path: Path) -> None:
    """
    Crea la carpeta padre si no existe.
    """
    path.parent.mkdir(parents=True, exist_ok=True)


# -------------------------------
# Procesamiento de audio
# -------------------------------
def normalize_dbfs(audio: AudioSegment, target_dbfs: float = -20.0) -> AudioSegment:
    """
    Normaliza el nivel de audio para que el pico de loudness se acerque a target_dbfs.
    target_dbfs típico: -20 dBFS para voz (con margen de headroom).
    """
    if audio is None:
        raise ValueError("AudioSegment no puede ser None")

    # En pydub, dBFS es negativo (0 dBFS = tope digital). Ajustamos ganancia relativa.
    change_in_dBFS = target_dbfs - audio.dBFS
    normalized = audio.apply_gain(change_in_dBFS)

    logger.debug(
        "Normalización: dBFS actual=%.2f, objetivo=%.2f, delta=%.2f",
        audio.dBFS,
        target_dbfs,
        change_in_dBFS,
    )
    return normalized


def to_wav_mono16k(
    audio: AudioSegment,
    sample_width: int = 2,  # 16-bit PCM (2 bytes)
) -> AudioSegment:
    """
    Convierte a 16 kHz, mono y 16-bit (PCM16) en memoria (AudioSegment).
    No escribe a disco; usa export_wav() para persistir.
    """
    if audio is None:
        raise ValueError("AudioSegment no puede ser None")

    processed = (
        audio.set_frame_rate(16000)   # 16 kHz
        .set_channels(1)              # mono
        .set_sample_width(sample_width)  # 16-bit PCM
    )
    logger.debug(
        "Formato destino en memoria: %d Hz | %d ch | %d bytes",
        processed.frame_rate,
        processed.channels,
        processed.sample_width,
    )
    return processed


def export_wav(
    audio: AudioSegment,
    out_path: Path,
    enforce_pcm16: bool = True,
) -> Path:
    """
    Exporta AudioSegment a WAV. Si enforce_pcm16=True, fuerza 'pcm_s16le' (16-bit PCM).
    Retorna la ruta final.
    """
    _ensure_ffmpeg_available()
    _ensure_parent_dir(out_path)

    params = []
    if enforce_pcm16:
        # Fuerza códec PCM lineal 16-bit little-endian (altamente compatible)
        params = ["-acodec", "pcm_s16le"]

    logger.info("Exportando WAV: %s", out_path)
    audio.export(out_f=str(out_path), format="wav", parameters=params)
    return out_path

def split_wav_chunks(
    wav_path: Path,
    chunk_length_ms: int = 40 * 60 * 1000,  # 40 minutos por default
    prefix: Optional[str] = None
) -> list[Path]:
    """
    Divide un WAV en fragmentos de chunk_length_ms (ej: 40 min).
    Devuelve la lista de rutas a los chunks generados.
    """
    if not wav_path.exists():
        raise FileNotFoundError(f"No existe el archivo WAV: {wav_path}")

    audio = AudioSegment.from_wav(wav_path)
    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_length_ms)):
        chunk = audio[start:start + chunk_length_ms]

        # Prefijo opcional
        base_name = prefix or wav_path.stem
        chunk_path = wav_path.parent / f"{base_name}_part{i+1}.wav"

        # Exporta cada chunk como WAV PCM16
        export_wav(chunk, chunk_path, enforce_pcm16=True)
        logger.info("Chunk generado: %s", chunk_path)
        chunks.append(chunk_path)

    return chunks

def split_wav_chunks_with_overlap(
    wav_path: Path,
    chunk_length_ms: int = 40 * 60 * 1000,  # 40 minutos por default
    overlap_ms: int = 5000,  # Solapamiento de 5 segundos
    prefix: Optional[str] = None
) -> list[Path]:
    """
    Divide un WAV en fragmentos con un solapamiento específico entre ellos.
    
    Args:
        wav_path (Path): Ruta al archivo WAV.
        chunk_length_ms (int): Duración de los fragmentos en milisegundos.
        overlap_ms (int): Solapamiento en milisegundos entre fragmentos.
        prefix (str, Optional): Prefijo opcional para el nombre de los fragmentos.

    Returns:
        list[Path]: Lista de rutas a los fragmentos generados.
    """
    if not wav_path.exists():
        raise FileNotFoundError(f"No existe el archivo WAV: {wav_path}")

    audio = AudioSegment.from_wav(wav_path)
    total_length_ms = len(audio)
    chunks_info = []

    # Calcular los fragmentos con solapamiento
    for i in range(0, total_length_ms, chunk_length_ms - overlap_ms):
        start_ms = i * (chunk_length_ms - overlap_ms)
        end_ms = min(i + chunk_length_ms, total_length_ms)
        chunk = audio[start_ms:end_ms]

        # Prefijo opcional
        base_name = prefix or wav_path.stem
        chunk_path = wav_path.parent / f"{base_name}_part{i//(chunk_length_ms - overlap_ms) + 1}.wav"

        # Exporta cada chunk como WAV PCM16
        export_wav(chunk, chunk_path, enforce_pcm16=True)
        
        logger.info("Chunk generado: %s empezando en: %s", chunk_path, start_ms)
        chunks_info.append((chunk_path, start_ms))

    return chunks_info


# -------------------------------
# Flujo de alto nivel
# -------------------------------
def process_mp3_to_wav16k(
    mp3_path: Path,
    out_dir: Path,
    target_dbfs: float = -20.0,
    out_name: Optional[str] = None,
) -> Path:
    """
    Flujo completo:
      1) Carga MP3 (si ya tienes AudioSegment, usa funciones de arriba directamente).
      2) Normaliza a target_dbfs.
      3) Convierte a 16 kHz, mono, 16-bit.
      4) Exporta a .wav en out_dir.

    Devuelve la ruta del WAV generado.
    """
    from src.ingestion.audio_loader import load_mp3  # import local para evitar ciclos

    mp3_path = Path(mp3_path)
    out_dir = Path(out_dir)

    if not mp3_path.exists():
        raise FileNotFoundError(f"No existe el archivo MP3: {mp3_path}")

    audio = load_mp3(mp3_path)

    # Normalización
    normalized = normalize_dbfs(audio, target_dbfs=target_dbfs)

    # Conversión de formato en memoria
    wav_ready = to_wav_mono16k(normalized)

    # Nombre de salida
    if out_name:
        out_file = out_dir / out_name
    else:
        out_file = out_dir / (mp3_path.stem + "_16k_mono.wav")

    # Exporta WAV a disco
    return export_wav(wav_ready, out_file, enforce_pcm16=True)
