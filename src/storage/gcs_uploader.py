# src/storage/gcs_uploader.py
# Librerias externas
from google.cloud import storage

# Librerias internas
from pathlib import Path

# Módulos globales
from src.logging_conf import get_logger
from src.settings import GCP_PROJECT_ID, GCS_BUCKET

logger = get_logger(__name__)

def upload_to_gcs(local_path: Path, bucket_name: str | None = GCS_BUCKET, destination: str | None = None) -> str:
    """
    Sube un archivo local a un bucket GCS y devuelve la URI gs://...
    """
    client = storage.Client(project=GCP_PROJECT_ID)
    bucket = client.bucket(bucket_name)

    # Si no especificas destino, usa el nombre del archivo
    destination_blob = destination or local_path.name

    logger.info("Subiendo a GCS: %s -> gs://%s/%s", local_path, bucket_name, destination_blob)
    blob = bucket.blob(destination_blob)
    blob.upload_from_filename(str(local_path))

    gcs_uri = f"gs://{bucket_name}/{destination_blob}"
    logger.info("Archivo disponible en: %s", gcs_uri)
    return gcs_uri
