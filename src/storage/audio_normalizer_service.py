# src/storage/audio_normalizer_service.py

# Librerias externas
from google.cloud import storage

# Librerias internas
import tempfile
from pathlib import Path

# Módulos
from src.ingestion.audio_processor import process_mp3_to_wav16k
from src.storage.gcs_uploader import upload_to_gcs

# Módulos Globales
from src.logging_conf import get_logger

logger = get_logger(__name__)

def normalize_and_upload_gcs(
    gcs_src_uri: str,
    case_id: str,
    bucket_name: str,
    *,
    target_sr: int | None = None,
    target_channels: int = 1,
    target_format: str = "wav",   # "wav" | "flac"
    auto_sr: bool = False,        # si True: usa 8k si la fuente es <=12k (telefónico), si no 16k
) -> str:
    """
    Descarga desde GCS, normaliza a mono y sample rate objetivo, exporta en target_format y sube a GCS.
    Devuelve la URI gs:// del archivo normalizado.
    """
    import tempfile, os
    from google.cloud import storage
    from pydub import AudioSegment

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    if not gcs_src_uri.startswith("gs://"):
        raise ValueError("gcs_src_uri inválido")

    src_bucket, src_blob = gcs_src_uri.replace("gs://", "").split("/", 1)

    with tempfile.TemporaryDirectory() as td:
        local_in = os.path.join(td, "in.bin")
        storage_client.bucket(src_bucket).blob(src_blob).download_to_filename(local_in)
        logger.info("📥 Descargado para normalizar: %s", gcs_src_uri)

        audio = AudioSegment.from_file(local_in)
        orig_sr = int(audio.frame_rate or 0)

        # Elegir SR destino
        if target_sr is None:
            if auto_sr:
                # Si la fuente es 12k o menos (típico telefónico 8k), usa 8k; si no, 16k
                target_sr = 8000 if (orig_sr and orig_sr <= 12000) else 16000
            else:
                target_sr = 16000

        audio = audio.set_frame_rate(target_sr).set_channels(target_channels)

        # Exportar
        stem = os.path.splitext(os.path.basename(src_blob))[0]
        if target_format == "flac":
            local_out = os.path.join(td, f"{stem}_{target_sr}.flac")
            content_type = "audio/flac"
            audio.export(local_out, format="flac")
        else:
            local_out = os.path.join(td, f"{stem}_{target_sr}.wav")
            content_type = "audio/wav"
            audio.export(local_out, format="wav")

        dest_name = f"processed/{os.path.basename(local_out)}"
        blob = bucket.blob(dest_name)

        # Sube con chunk grande (puedes ajustar por env)
        try:
            chunk_mb = int(os.getenv("GCS_UPLOAD_CHUNK_MB", "64"))
            blob.chunk_size = chunk_mb * 1024 * 1024
        except Exception:
            pass

        blob.upload_from_filename(local_out, content_type=content_type)
        gcs_out = f"gs://{bucket_name}/{dest_name}"
        logger.info("✅ Normalizado y subido: %s", gcs_out)
        return gcs_out
