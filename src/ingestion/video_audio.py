# src/ingestion/video_audio.py
from __future__ import annotations
from pathlib import Path
import subprocess
import shutil
import os

from src.logging_conf import get_logger

logger = get_logger(__name__)

def _ffmpeg_bin() -> str:
    """Obtiene la ruta/binario de ffmpeg (usa env FFMPEG_BIN si existe)."""
    env_bin = os.getenv("FFMPEG_BIN")
    if env_bin:
        return env_bin
    return "ffmpeg"  # requiere ffmpeg en PATH

def extract_audio_to_mp3(
    video_path: Path,
    out_dir: Path,
    *,
    basename: str | None = None,
    channels: int = 1,     # 1=mono (telefónico)
    sample_rate: int = 16000,  # 16 kHz (bueno para STT/telef.)
    bitrate: str = "160k",
    overwrite: bool = True,
) -> Path:
    """
    Extrae audio MP3 desde un archivo de video usando ffmpeg.
    Devuelve la ruta del MP3 generado.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video no encontrado: {video_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = basename or video_path.stem
    out_path = out_dir / f"{stem}.mp3"

    cmd = [
        _ffmpeg_bin(),
        "-y" if overwrite else "-n",
        "-i", str(video_path),
        "-vn",                 # sin video
        "-acodec", "libmp3lame",
        "-b:a", bitrate,
        "-ac", str(channels),
        "-ar", str(sample_rate),
        str(out_path),
    ]

    try:
        logger.info("🎬 Extrayendo audio con ffmpeg → %s", out_path)
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError as e:
        raise RuntimeError("ffmpeg no está instalado o no está en PATH. "
                           "Define FFMPEG_BIN o instala ffmpeg.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg falló: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else e}") from e

    if not out_path.exists():
        raise RuntimeError("No se generó el MP3 esperado.")
    logger.info("🎧 Audio extraído: %s", out_path)
    return out_path
