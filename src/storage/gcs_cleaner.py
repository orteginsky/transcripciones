# src/storage/gcs_cleaner.py
# Librerias externas
from google.cloud import storage

# Módulos Globales
from src.logging_conf import get_logger

logger = get_logger(__name__)

def delete_gcs_files(uris: list[str]) -> list[str]:
    """
    Elimina una lista de archivos en Google Cloud Storage (si existen).

    Args:
        uris (list[str]): Lista de URIs en formato gs://bucket/path/to/file
    Returns:
        list[str]: Lista de URIs eliminadas exitosamente.
    """
    deleted = []
    client = storage.Client()

    for uri in uris:
        try:
            assert uri.startswith("gs://"), f"URI inválida: {uri}"
            bucket_name, blob_name = uri.replace("gs://", "").split("/", 1)
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)

            if blob.exists():
                blob.delete()
                deleted.append(uri)
                logger.info("🧹 Archivo eliminado de GCS: %s", uri)
            else:
                logger.warning("⚠️ Archivo no encontrado: %s", uri)

        except Exception as e:
            logger.error("❌ No se pudo eliminar %s: %s", uri, e)

    return deleted
