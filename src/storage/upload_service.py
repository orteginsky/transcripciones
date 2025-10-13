# src/storage/upload_service.py
# Librerias internas
import tempfile
from pathlib import Path

# Módulos
from src.ingestion.drive_loader import extract_drive_id, download_from_drive
from src.ingestion.google_auth_manager import get_google_services
from src.storage.gcs_uploader import upload_to_gcs

# Módulos Globales
from src.logging_conf import get_logger

logger = get_logger(__name__)

def save_drive_audio_to_gcs(audio_link: str, case_id: str) -> str:
    """
    Descarga un audio desde Google Drive y lo sube al bucket GCS.
    Retorna la URI final gs://...
    """
    drive_service, _, _ = get_google_services()
    file_id = extract_drive_id(audio_link)

    if not file_id:
        raise ValueError(f"No se pudo extraer file_id del enlace: {audio_link}")

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = Path(tmpdir) / f"{case_id}.mp3"

        # 1️⃣ Descargar desde Drive
        download_from_drive(drive_service, file_id, local_path)

        # 2️⃣ Subir a GCS
        gcs_uri = upload_to_gcs(local_path)

        logger.info("Audio subido correctamente a: %s", gcs_uri)
        return gcs_uri