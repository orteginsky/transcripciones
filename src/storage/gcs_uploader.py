# ============================================
# src/storage/gcs_uploader.py
# ============================================

from google.cloud import storage
from google.resumable_media.common import DataCorruption
from google.api_core.exceptions import ServiceUnavailable
from pathlib import Path
from typing import Optional
import time

# Módulos internos
from src.logging_conf import get_logger
from src.settings import GCP_PROJECT_ID, GCS_BUCKET

logger = get_logger(__name__)

# ---------------------------
# CONFIGURACIÓN GLOBAL
# ---------------------------
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB por chunk
UPLOAD_TIMEOUT = 600           # 10 minutos de espera total
MAX_RETRIES = 3                # reintentos ante fallo


def upload_to_gcs(
    local_path: Path,
    bucket_name: str | None = GCS_BUCKET,
    destination: str | None = None,
) -> Optional[str]:
    """
    📤 Sube un archivo local a Google Cloud Storage con soporte de reintentos,
    chunked uploads y timeout extendido. Devuelve la URI gs://bucket/blob.

    Args:
        local_path (Path): Ruta local del archivo a subir.
        bucket_name (str, opcional): Nombre del bucket. Por defecto usa GCS_BUCKET.
        destination (str, opcional): Nombre del blob destino. Si no se indica, usa el nombre del archivo.
    """
    client = storage.Client(project=GCP_PROJECT_ID)
    bucket = client.bucket(bucket_name)
    destination_blob = destination or local_path.name

    blob = bucket.blob(destination_blob)

    # Habilitar "resumable upload" para archivos grandes
    blob.chunk_size = CHUNK_SIZE

    logger.info(
        "🚀 Subiendo a GCS: %s → gs://%s/%s (chunk=%dMB, timeout=%ds)",
        local_path,
        bucket_name,
        destination_blob,
        CHUNK_SIZE // (1024 * 1024),
        UPLOAD_TIMEOUT,
    )

    # Reintentos simples con backoff exponencial
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            blob.upload_from_filename(str(local_path), timeout=UPLOAD_TIMEOUT)
            gcs_uri = f"gs://{bucket_name}/{destination_blob}"
            logger.info("✅ Subida completada: %s", gcs_uri)
            gcs_uri = str(gcs_uri)
            return gcs_uri

        except (TimeoutError, ConnectionError, ServiceUnavailable, DataCorruption) as e:
            logger.warning(
                "⚠️ Intento %d/%d fallido al subir '%s': %s",
                attempt,
                MAX_RETRIES,
                local_path.name,
                e,
            )
            if attempt < MAX_RETRIES:
                sleep_time = attempt * 5
                logger.info("🔁 Reintentando en %d segundos...", sleep_time)
                time.sleep(sleep_time)
            else:
                logger.error("❌ Falló la subida tras %d intentos", MAX_RETRIES)
                raise

        except Exception as e:
            logger.exception("❌ Error inesperado al subir '%s': %s", local_path.name, e)
            raise

