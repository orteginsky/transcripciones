# src/storage/audio_normalizer_service.py
import os
import tempfile
from google.cloud import storage
from pydub import AudioSegment
from src.logging_conf import get_logger

logger = get_logger(__name__)

def normalize_and_upload_gcs(
    gcs_src_uri: str,
    case_id: str,
    bucket_name: str,
    *,
    target_sr: int | None = None,
    target_channels: int | None = None,
    target_format: str = "flac",
    auto_sr: bool = False,
    force_normalize: bool = True,
) -> str:
    """
    Descarga audio de GCS, lo normaliza (Mono/Stereo, 16kHz/8kHz, FLAC/WAV) y lo sube a GCS.

    Args:
        gcs_src_uri: URI de origen en GCS (gs://bucket/path)
        case_id: ID del caso (usado para organización)
        bucket_name: Bucket de destino
        target_sr: Sample rate objetivo (None = auto)
        target_channels: Canales objetivo (1=mono, 2=stereo)
        target_format: Formato de salida ('flac' o 'wav')
        auto_sr: Si True, detecta automáticamente el mejor sample rate
        force_normalize: Si False, solo normaliza si es estrictamente necesario

    Returns:
        URI del archivo normalizado en GCS
    """
    
    # Validación básica de URI
    if not gcs_src_uri.startswith("gs://"):
        raise ValueError(f"URI de origen inválida: {gcs_src_uri}")

    try:
        parts = gcs_src_uri.replace("gs://", "").split("/", 1)
        src_bucket_name = parts[0]
        src_blob_name = parts[1]
    except IndexError:
        raise ValueError(f"URI mal formada: {gcs_src_uri}")

    # Inicializar cliente
    storage_client = storage.Client()
    
    with tempfile.TemporaryDirectory() as td:
        # 1. Descarga
        local_in = os.path.join(td, "source_audio")
        
        # Detectar extensión original
        ext = os.path.splitext(src_blob_name)[1]
        if ext:
            local_in += ext

        logger.info(f"📥 Descargando audio desde: {gcs_src_uri}")
        blob_source = storage_client.bucket(src_bucket_name).blob(src_blob_name)
        blob_source.download_to_filename(local_in)

        # 2. Procesamiento con Pydub
        try:
            audio = AudioSegment.from_file(local_in)
        except Exception as e:
            logger.error(f"❌ Error al leer el audio con Pydub: {e}")
            raise

        orig_sr = int(audio.frame_rate or 0)
        orig_channels = int(audio.channels)

        # Lógica de Sample Rate (Auto)
        if target_sr is None:
            if auto_sr:
                target_sr = 8000 if (orig_sr and orig_sr <= 12000) else 16000
            else:
                target_sr = 16000

        if target_channels is None:
            target_channels = orig_channels

        # Check if normalization is actually needed
        needs_conversion = (
            orig_sr != target_sr or
            orig_channels != target_channels or
            not local_in.endswith(f".{target_format}")
        )

        if not force_normalize and not needs_conversion:
            logger.info(f"⚡ Skipping normalization - audio already in optimal format")
            return gcs_src_uri  # Return original URI without processing

        logger.info(f"🎛️ Normalizando: {orig_sr}Hz -> {target_sr}Hz | Canales: {audio.channels} -> {target_channels} | Fmt: {target_format}")

        audio = audio.set_frame_rate(target_sr).set_channels(target_channels)

        # 3. Exportación
        stem = os.path.splitext(os.path.basename(src_blob_name))[0]
        
        if target_format == "flac":
            local_out = os.path.join(td, f"{stem}_{target_sr}.flac")
            content_type = "audio/flac"
            audio.export(local_out, format="flac")
        else:
            local_out = os.path.join(td, f"{stem}_{target_sr}.wav")
            content_type = "audio/wav"
            audio.export(local_out, format="wav")

        # 4. Subida
        dest_blob_name = f"processed/{os.path.basename(local_out)}"
        bucket_dest = storage_client.bucket(bucket_name)
        blob_dest = bucket_dest.blob(dest_blob_name)

        try:
            chunk_mb = int(os.getenv("GCS_UPLOAD_CHUNK_MB", "64"))
            blob_dest.chunk_size = chunk_mb * 1024 * 1024
        except Exception:
            pass

        logger.info(f"📤 Subiendo audio procesado a: gs://{bucket_name}/{dest_blob_name}")
        blob_dest.upload_from_filename(local_out, content_type=content_type)
        
        return f"gs://{bucket_name}/{dest_blob_name}"