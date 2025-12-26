# ============================================
# src/storage/gcs_uploader.py
# ============================================

from google.cloud import storage
from google.resumable_media.common import DataCorruption
from google.api_core.exceptions import ServiceUnavailable
from pathlib import Path
from typing import Optional
import time
import os

# Módulos internos
from src.logging_conf import get_logger
from src.settings import settings

logger = get_logger(__name__)

# ---------------------------
# CONFIGURACIÓN GLOBAL
# ---------------------------
CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB por chunk por defecto
UPLOAD_TIMEOUT = 600           # 10 minutos de espera total
MAX_RETRIES = 3                # reintentos ante fallo


def _setup_auth_env():
    """
    Asegura que la variable de entorno GOOGLE_APPLICATION_CREDENTIALS
    esté configurada antes de instanciar clientes de Google.
    """
    if settings.google_application_credentials:
        # Solo la establecemos si no existe ya en el entorno, para respetar overrides del sistema
        if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
            # logger.debug("🔑 Credenciales inyectadas en entorno desde settings.")


def upload_to_gcs(
    local_path: str | Path,  # Aceptamos str o Path para flexibilidad
    bucket_name: str | None = settings.gcs_bucket,
    destination: str | None = None,
) -> str:
    """
    📤 Sube un archivo local a Google Cloud Storage con soporte de reintentos,
    chunked uploads y timeout extendido. Devuelve la URI gs://bucket/blob.

    Args:
        local_path (str | Path): Ruta local del archivo a subir.
        bucket_name (str, opcional): Nombre del bucket.
        destination (str, opcional): Nombre del blob destino.
    """
    # 1. Configurar autenticación
    _setup_auth_env()

    # Convertir a Path si viene como string
    path_obj = Path(local_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"No se encontró el archivo local: {local_path}")

    # Validar bucket
    target_bucket = bucket_name or settings.gcs_bucket
    if not target_bucket:
        raise ValueError("El nombre del bucket no puede ser nulo (revisar GCS_BUCKET en .env).")

    # 2. Inicializar Cliente
    # Al haber configurado la var de entorno arriba, esto ya no fallará.
    client = storage.Client(project=settings.gcp_project_id)
    bucket = client.bucket(target_bucket)
    
    destination_blob = destination or path_obj.name
    blob = bucket.blob(destination_blob)

    # 3. Configurar Chunk Size
    # Prioridad: ENV VAR > Constante Global
    env_chunk_mb = os.getenv("GCS_UPLOAD_CHUNK_MB")
    if env_chunk_mb:
        blob.chunk_size = int(env_chunk_mb) * 1024 * 1024
    else:
        blob.chunk_size = CHUNK_SIZE

    logger.info(
        "🚀 Subiendo a GCS: %s → gs://%s/%s (chunk=%dMB, timeout=%ds)",
        path_obj.name,
        target_bucket,
        destination_blob,
        blob.chunk_size // (1024 * 1024),
        UPLOAD_TIMEOUT,
    )

    # 4. Upload con Reintentos (Backoff Exponencial)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            blob.upload_from_filename(str(path_obj), timeout=UPLOAD_TIMEOUT)
            
            gcs_uri = f"gs://{target_bucket}/{destination_blob}"
            logger.info("✅ Subida completada: %s", gcs_uri)
            return gcs_uri

        except (TimeoutError, ConnectionError, ServiceUnavailable, DataCorruption) as e:
            logger.warning(
                "⚠️ Intento %d/%d fallido al subir '%s': %s",
                attempt,
                MAX_RETRIES,
                path_obj.name,
                e,
            )
            if attempt < MAX_RETRIES:
                sleep_time = attempt * 5
                logger.info("🔁 Reintentando en %d segundos...", sleep_time)
                time.sleep(sleep_time)
            else:
                logger.error("❌ Falló la subida tras %d intentos.", MAX_RETRIES)
                raise

        except Exception as e:
            logger.exception("❌ Error crítico e inesperado al subir '%s': %s", path_obj.name, e)
            raise
    
    # En teoría inalcanzable por el raise, pero para type safety
    raise RuntimeError("Fallo desconocido en upload loop")